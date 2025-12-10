"""
Parser for Health Auto Export JSON files
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from dataclasses import dataclass

from models import HealthMetricSample, Workout, WorkoutSample


@dataclass
class ParseResult:
    """Result of parsing a Health Auto Export file"""
    metrics_count: int = 0
    workouts_count: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def parse_timestamp(date_str: str) -> Optional[datetime]:
    """Parse timestamp from Health Auto Export format

    Format: '2025-12-08 00:12:43 +0100'
    """
    if not date_str:
        return None

    try:
        # Format: '2025-12-08 00:12:43 +0100'
        # Python's %z expects +0100 not +01:00, so this should work
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        try:
            # Try without timezone
            return datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def parse_metrics(data: dict) -> Iterator[HealthMetricSample]:
    """Parse health metrics from JSON data

    Yields HealthMetricSample objects for each data point.
    """
    metrics = data.get("data", {}).get("metrics", [])

    for metric in metrics:
        metric_name = metric.get("name", "")
        unit = metric.get("units", "")

        for sample in metric.get("data", []):
            # Try 'date' first, then 'start' (different export formats)
            date_str = sample.get("date") or sample.get("start", "")
            timestamp = parse_timestamp(date_str)
            if timestamp is None:
                continue

            # Get the value - can be 'qty' or 'value' depending on metric
            value = sample.get("qty")
            if value is None:
                value = sample.get("value")
            if value is None:
                continue

            # Source can be 'source' or 'sources'
            source = sample.get("source") or sample.get("sources", "")

            yield HealthMetricSample(
                metric_name=metric_name,
                timestamp=timestamp,
                value=float(value),
                unit=unit,
                source=source,
            )


def parse_workouts(data: dict) -> Iterator[Workout]:
    """Parse workouts from JSON data

    Yields Workout objects.
    """
    workouts = data.get("data", {}).get("workouts", [])

    for w in workouts:
        start_time = parse_timestamp(w.get("start", ""))
        end_time = parse_timestamp(w.get("end", ""))

        if start_time is None:
            continue

        # Extract summary stats
        distance_data = w.get("distance", {})
        total_distance = distance_data.get("qty") if isinstance(distance_data, dict) else None

        energy_data = w.get("activeEnergyBurned", {})
        total_energy = energy_data.get("qty") if isinstance(energy_data, dict) else None

        intensity_data = w.get("intensity", {})
        intensity = intensity_data.get("qty") if isinstance(intensity_data, dict) else None
        intensity_unit = intensity_data.get("units", "") if isinstance(intensity_data, dict) else ""

        # Calculate total steps from stepCount array if available
        step_count_data = w.get("stepCount", [])
        total_steps = None
        if step_count_data:
            total_steps = sum(s.get("qty", 0) for s in step_count_data)

        # Parse heart rate data for stats
        hr_data = w.get("heartRateData", [])
        avg_hr = None
        max_hr = None
        min_hr = None
        heart_rate_samples = []

        if hr_data:
            hr_values = []
            for hr in hr_data:
                timestamp = parse_timestamp(hr.get("date", ""))
                avg_val = hr.get("Avg")
                max_val = hr.get("Max")
                min_val = hr.get("Min")

                if avg_val is not None:
                    hr_values.append(avg_val)

                if timestamp and avg_val is not None:
                    heart_rate_samples.append(WorkoutSample(
                        timestamp=timestamp,
                        heart_rate=avg_val,
                    ))

            if hr_values:
                avg_hr = sum(hr_values) / len(hr_values)
                max_hr = max(hr_values)
                min_hr = min(hr_values)

        # Parse heart rate recovery
        hr_recovery = w.get("heartRateRecovery", [])

        workout = Workout(
            workout_id=w.get("id", ""),
            name=w.get("name", "Unknown"),
            start_time=start_time,
            end_time=end_time or start_time,
            duration_seconds=w.get("duration", 0),
            location=w.get("location", ""),
            total_distance=total_distance,
            distance_unit=distance_data.get("units", "km") if isinstance(distance_data, dict) else "km",
            total_active_energy=total_energy,
            energy_unit=energy_data.get("units", "kJ") if isinstance(energy_data, dict) else "kJ",
            total_steps=int(total_steps) if total_steps else None,
            avg_heart_rate=avg_hr,
            max_heart_rate=max_hr,
            min_heart_rate=min_hr,
            intensity=intensity,
            intensity_unit=intensity_unit,
            heart_rate_data=heart_rate_samples,
            heart_rate_recovery=hr_recovery,
        )

        yield workout


def parse_file(file_path: Path) -> tuple[Iterator[HealthMetricSample], Iterator[Workout], ParseResult]:
    """Parse a Health Auto Export JSON file

    Returns iterators for metrics and workouts, plus a result summary.
    Note: The iterators share the same underlying data, so the file is loaded once.
    """
    result = ParseResult()

    with open(file_path, "r") as f:
        data = json.load(f)

    # Count totals for result
    metrics_list = data.get("data", {}).get("metrics", [])
    for m in metrics_list:
        result.metrics_count += len(m.get("data", []))

    result.workouts_count = len(data.get("data", {}).get("workouts", []))

    return parse_metrics(data), parse_workouts(data), result


def load_and_parse(file_path: Path) -> tuple[list[HealthMetricSample], list[Workout]]:
    """Load and parse file, returning lists (for when you need all data in memory)"""
    with open(file_path, "r") as f:
        data = json.load(f)

    metrics = list(parse_metrics(data))
    workouts = list(parse_workouts(data))

    return metrics, workouts


class HealthDataParser:
    """Streaming parser for large Health Auto Export files"""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._data = None

    def _load(self):
        """Lazy load the JSON data"""
        if self._data is None:
            with open(self.file_path, "r") as f:
                self._data = json.load(f)

    def get_metrics(self) -> Iterator[HealthMetricSample]:
        """Iterate over all health metrics"""
        self._load()
        yield from parse_metrics(self._data)

    def get_workouts(self) -> Iterator[Workout]:
        """Iterate over all workouts"""
        self._load()
        yield from parse_workouts(self._data)

    def get_metric_names(self) -> list[str]:
        """Get list of available metric names"""
        self._load()
        metrics = self._data.get("data", {}).get("metrics", [])
        return [m.get("name", "") for m in metrics]

    def get_metrics_by_name(self, name: str) -> Iterator[HealthMetricSample]:
        """Get metrics filtered by name"""
        for metric in self.get_metrics():
            if metric.metric_name == name:
                yield metric

    def get_summary(self) -> dict:
        """Get summary statistics"""
        self._load()

        metrics = self._data.get("data", {}).get("metrics", [])
        workouts = self._data.get("data", {}).get("workouts", [])

        metric_summary = {}
        total_samples = 0
        for m in metrics:
            name = m.get("name", "unknown")
            count = len(m.get("data", []))
            metric_summary[name] = {
                "count": count,
                "unit": m.get("units", ""),
            }
            total_samples += count

        return {
            "total_metric_samples": total_samples,
            "metric_types": len(metrics),
            "metrics": metric_summary,
            "total_workouts": len(workouts),
        }


if __name__ == "__main__":
    # Test the parser
    import sys

    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        file_path = Path("data_export/HealthAutoExport-20241201-20251210.json")

    if not file_path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    print(f"Parsing {file_path}...")
    parser = HealthDataParser(file_path)

    summary = parser.get_summary()
    print(f"\nTotal metric samples: {summary['total_metric_samples']:,}")
    print(f"Metric types: {summary['metric_types']}")
    print(f"Total workouts: {summary['total_workouts']}")

    print("\n--- First 5 heart rate samples ---")
    for i, sample in enumerate(parser.get_metrics_by_name("heart_rate")):
        if i >= 5:
            break
        print(f"  {sample.timestamp}: {sample.value} {sample.unit}")

    print("\n--- First 3 workouts ---")
    for i, workout in enumerate(parser.get_workouts()):
        if i >= 3:
            break
        print(f"  {workout.name} on {workout.start_time.date()}: {workout.duration_seconds/60:.1f} min")
        if workout.avg_heart_rate:
            print(f"    HR: avg={workout.avg_heart_rate:.0f}, max={workout.max_heart_rate:.0f}")