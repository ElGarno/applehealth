"""
Aggregation logic for health metrics

Aggregates raw per-second data into hourly and daily summaries.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Iterator

from models import HealthMetricSample, AggregatedMetric


def _truncate_to_hour(dt: datetime) -> datetime:
    """Truncate datetime to hour boundary"""
    return dt.replace(minute=0, second=0, microsecond=0)


def _truncate_to_day(dt: datetime) -> datetime:
    """Truncate datetime to day boundary"""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def aggregate_to_hourly(samples: Iterator[HealthMetricSample]) -> Iterator[AggregatedMetric]:
    """Aggregate samples to hourly buckets

    Yields AggregatedMetric for each (metric_name, hour) combination.
    """
    # Group by (metric_name, hour)
    buckets: dict[tuple[str, datetime, str], list[float]] = defaultdict(list)

    for sample in samples:
        hour = _truncate_to_hour(sample.timestamp)
        key = (sample.metric_name, hour, sample.unit)
        buckets[key].append(sample.value)

    # Calculate aggregates
    for (metric_name, hour, unit), values in buckets.items():
        yield AggregatedMetric(
            metric_name=metric_name,
            timestamp=hour,
            unit=unit,
            count=len(values),
            sum_value=sum(values),
            avg_value=sum(values) / len(values),
            min_value=min(values),
            max_value=max(values),
        )


def aggregate_to_daily(samples: Iterator[HealthMetricSample]) -> Iterator[AggregatedMetric]:
    """Aggregate samples to daily buckets

    Yields AggregatedMetric for each (metric_name, day) combination.
    """
    # Group by (metric_name, day)
    buckets: dict[tuple[str, datetime, str], list[float]] = defaultdict(list)

    for sample in samples:
        day = _truncate_to_day(sample.timestamp)
        key = (sample.metric_name, day, sample.unit)
        buckets[key].append(sample.value)

    # Calculate aggregates
    for (metric_name, day, unit), values in buckets.items():
        yield AggregatedMetric(
            metric_name=metric_name,
            timestamp=day,
            unit=unit,
            count=len(values),
            sum_value=sum(values),
            avg_value=sum(values) / len(values),
            min_value=min(values),
            max_value=max(values),
        )


def aggregate_from_hourly_to_daily(
    hourly: Iterator[AggregatedMetric]
) -> Iterator[AggregatedMetric]:
    """Aggregate hourly data to daily (more efficient than re-processing raw)"""
    # Group by (metric_name, day)
    buckets: dict[tuple[str, datetime, str], list[AggregatedMetric]] = defaultdict(list)

    for agg in hourly:
        day = _truncate_to_day(agg.timestamp)
        key = (agg.metric_name, day, agg.unit)
        buckets[key].append(agg)

    for (metric_name, day, unit), hourly_aggs in buckets.items():
        total_count = sum(a.count for a in hourly_aggs)
        total_sum = sum(a.sum_value for a in hourly_aggs)

        yield AggregatedMetric(
            metric_name=metric_name,
            timestamp=day,
            unit=unit,
            count=total_count,
            sum_value=total_sum,
            avg_value=total_sum / total_count if total_count > 0 else 0,
            min_value=min(a.min_value for a in hourly_aggs),
            max_value=max(a.max_value for a in hourly_aggs),
        )


class StreamingAggregator:
    """Memory-efficient aggregator that processes samples in a streaming fashion

    For very large datasets, this processes samples incrementally without
    loading everything into memory at once.
    """

    def __init__(self):
        self._hourly_buckets: dict[tuple[str, datetime, str], dict] = {}
        self._daily_buckets: dict[tuple[str, datetime, str], dict] = {}

    def add_sample(self, sample: HealthMetricSample):
        """Add a sample and update running aggregates"""
        # Update hourly bucket
        hour = _truncate_to_hour(sample.timestamp)
        hourly_key = (sample.metric_name, hour, sample.unit)

        if hourly_key not in self._hourly_buckets:
            self._hourly_buckets[hourly_key] = {
                "count": 0,
                "sum": 0.0,
                "min": float("inf"),
                "max": float("-inf"),
            }

        bucket = self._hourly_buckets[hourly_key]
        bucket["count"] += 1
        bucket["sum"] += sample.value
        bucket["min"] = min(bucket["min"], sample.value)
        bucket["max"] = max(bucket["max"], sample.value)

        # Update daily bucket
        day = _truncate_to_day(sample.timestamp)
        daily_key = (sample.metric_name, day, sample.unit)

        if daily_key not in self._daily_buckets:
            self._daily_buckets[daily_key] = {
                "count": 0,
                "sum": 0.0,
                "min": float("inf"),
                "max": float("-inf"),
            }

        bucket = self._daily_buckets[daily_key]
        bucket["count"] += 1
        bucket["sum"] += sample.value
        bucket["min"] = min(bucket["min"], sample.value)
        bucket["max"] = max(bucket["max"], sample.value)

    def get_hourly_aggregates(self) -> Iterator[AggregatedMetric]:
        """Get all hourly aggregates"""
        for (metric_name, hour, unit), bucket in self._hourly_buckets.items():
            yield AggregatedMetric(
                metric_name=metric_name,
                timestamp=hour,
                unit=unit,
                count=bucket["count"],
                sum_value=bucket["sum"],
                avg_value=bucket["sum"] / bucket["count"],
                min_value=bucket["min"],
                max_value=bucket["max"],
            )

    def get_daily_aggregates(self) -> Iterator[AggregatedMetric]:
        """Get all daily aggregates"""
        for (metric_name, day, unit), bucket in self._daily_buckets.items():
            yield AggregatedMetric(
                metric_name=metric_name,
                timestamp=day,
                unit=unit,
                count=bucket["count"],
                sum_value=bucket["sum"],
                avg_value=bucket["sum"] / bucket["count"],
                min_value=bucket["min"],
                max_value=bucket["max"],
            )

    def clear(self):
        """Clear all buckets"""
        self._hourly_buckets.clear()
        self._daily_buckets.clear()


if __name__ == "__main__":
    # Test aggregation
    from pathlib import Path
    from parser import HealthDataParser

    file_path = Path("data_export/HealthAutoExport-20241201-20251210.json")
    parser = HealthDataParser(file_path)

    print("Testing streaming aggregator...")
    aggregator = StreamingAggregator()

    # Process only heart rate for testing
    count = 0
    for sample in parser.get_metrics_by_name("heart_rate"):
        aggregator.add_sample(sample)
        count += 1

    print(f"Processed {count} heart rate samples")

    print("\nHourly aggregates (first 5):")
    for i, agg in enumerate(aggregator.get_hourly_aggregates()):
        if i >= 5:
            break
        print(f"  {agg.timestamp}: avg={agg.avg_value:.1f}, min={agg.min_value:.0f}, max={agg.max_value:.0f} ({agg.count} samples)")

    print("\nDaily aggregates:")
    for agg in aggregator.get_daily_aggregates():
        print(f"  {agg.timestamp.date()}: avg={agg.avg_value:.1f}, min={agg.min_value:.0f}, max={agg.max_value:.0f} ({agg.count} samples)")