"""
InfluxDB 2.x client for Apple Health data
"""
from datetime import datetime
from typing import Iterator, Optional
import logging

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS, WriteOptions

from config import InfluxDBConfig
from models import HealthMetricSample, Workout, AggregatedMetric

logger = logging.getLogger(__name__)


class HealthInfluxClient:
    """Client for writing Apple Health data to InfluxDB 2.x"""

    def __init__(self, config: InfluxDBConfig):
        self.config = config
        self._client: Optional[InfluxDBClient] = None
        self._write_api = None
        self._query_api = None
        self._org_id: Optional[str] = None

    def connect(self):
        """Establish connection to InfluxDB"""
        self._client = InfluxDBClient(
            url=self.config.url,
            token=self.config.token,
        )

        # Get org_id (required for writes)
        orgs = self._client.organizations_api().find_organizations()
        if orgs:
            self._org_id = orgs[0].id
            logger.info(f"Using organization: {orgs[0].name} ({self._org_id})")
        else:
            raise RuntimeError("No organization found in InfluxDB")

        # Use batching for better performance
        self._write_api = self._client.write_api(write_options=WriteOptions(
            batch_size=5000,
            flush_interval=1000,
            jitter_interval=0,
            retry_interval=5000,
            max_retries=3,
        ))
        self._query_api = self._client.query_api()
        logger.info(f"Connected to InfluxDB at {self.config.url}")

    def close(self):
        """Close connection"""
        if self._write_api:
            self._write_api.close()
        if self._client:
            self._client.close()
        logger.info("Disconnected from InfluxDB")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def health_check(self) -> bool:
        """Check if InfluxDB is reachable"""
        try:
            return self._client.ping()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        buckets_api = self._client.buckets_api()

        bucket = buckets_api.find_bucket_by_name(self.config.bucket)
        if bucket is None:
            logger.info(f"Creating bucket: {self.config.bucket}")
            buckets_api.create_bucket(bucket_name=self.config.bucket, org_id=self._org_id)
        else:
            logger.info(f"Bucket exists: {self.config.bucket}")

    def write_metric(self, sample: HealthMetricSample):
        """Write a single health metric sample"""
        point = (
            Point("health_metrics")
            .tag("metric", sample.metric_name)
            .tag("source", sample.source)
            .tag("unit", sample.unit)
            .field("value", float(sample.value))
            .time(sample.timestamp)
        )
        self._write_api.write(bucket=self.config.bucket, org=self._org_id, record=point)

    def write_metrics_batch(self, samples: Iterator[HealthMetricSample],
                           progress_callback=None) -> int:
        """Write multiple health metric samples efficiently

        Args:
            samples: Iterator of HealthMetricSample objects
            progress_callback: Optional callback(count) called periodically

        Returns:
            Total number of samples written
        """
        count = 0
        points = []

        for sample in samples:
            point = (
                Point("health_metrics")
                .tag("metric", sample.metric_name)
                .tag("source", sample.source)
                .tag("unit", sample.unit)
                .field("value", float(sample.value))
                .time(sample.timestamp)
            )
            points.append(point)
            count += 1

            # Write in batches
            if len(points) >= 5000:
                self._write_api.write(bucket=self.config.bucket, org=self._org_id, record=points)
                points = []
                if progress_callback:
                    progress_callback(count)

        # Write remaining points
        if points:
            self._write_api.write(bucket=self.config.bucket, org=self._org_id, record=points)
            if progress_callback:
                progress_callback(count)

        return count

    def write_workout(self, workout: Workout):
        """Write a workout summary"""
        # Main workout point
        point = (
            Point("workouts")
            .tag("workout_id", workout.workout_id)
            .tag("name", workout.name)
            .tag("location", workout.location or "unknown")
            .field("duration", workout.duration_seconds)
            .time(workout.start_time)
        )

        if workout.total_distance is not None:
            point.field("distance", workout.total_distance)
        if workout.total_active_energy is not None:
            point.field("active_energy", workout.total_active_energy)
        if workout.total_steps is not None:
            point.field("step_count", float(workout.total_steps))
        if workout.avg_heart_rate is not None:
            point.field("avg_heart_rate", workout.avg_heart_rate)
        if workout.max_heart_rate is not None:
            point.field("max_heart_rate", workout.max_heart_rate)
        if workout.min_heart_rate is not None:
            point.field("min_heart_rate", workout.min_heart_rate)

        self._write_api.write(bucket=self.config.bucket, org=self._org_id, record=point)

        # Write heart rate time series for workout
        hr_points = []
        for sample in workout.heart_rate_data:
            if sample.heart_rate is not None:
                hr_point = (
                    Point("workout_heart_rate")
                    .tag("workout_id", workout.workout_id)
                    .tag("workout_name", workout.name)
                    .field("heart_rate", sample.heart_rate)
                    .time(sample.timestamp)
                )
                hr_points.append(hr_point)

        if hr_points:
            self._write_api.write(bucket=self.config.bucket, org=self._org_id, record=hr_points)

    def write_workouts_batch(self, workouts: Iterator[Workout],
                            progress_callback=None) -> int:
        """Write multiple workouts"""
        count = 0
        for workout in workouts:
            self.write_workout(workout)
            count += 1
            if progress_callback:
                progress_callback(count)
        return count

    def write_aggregated_metric(self, agg: AggregatedMetric,
                                measurement: str = "health_metrics_hourly"):
        """Write an aggregated metric"""
        point = (
            Point(measurement)
            .tag("metric", agg.metric_name)
            .tag("unit", agg.unit)
            .field("count", agg.count)
            .field("sum", agg.sum_value)
            .field("avg", agg.avg_value)
            .field("min", agg.min_value)
            .field("max", agg.max_value)
            .time(agg.timestamp)
        )
        self._write_api.write(bucket=self.config.bucket, org=self._org_id, record=point)

    def write_aggregated_batch(self, aggregates: Iterator[AggregatedMetric],
                               measurement: str = "health_metrics_hourly",
                               progress_callback=None) -> int:
        """Write multiple aggregated metrics"""
        count = 0
        points = []

        for agg in aggregates:
            point = (
                Point(measurement)
                .tag("metric", agg.metric_name)
                .tag("unit", agg.unit)
                .field("count", agg.count)
                .field("sum", agg.sum_value)
                .field("avg", agg.avg_value)
                .field("min", agg.min_value)
                .field("max", agg.max_value)
                .time(agg.timestamp)
            )
            points.append(point)
            count += 1

            if len(points) >= 5000:
                self._write_api.write(bucket=self.config.bucket, org=self._org_id, record=points)
                points = []
                if progress_callback:
                    progress_callback(count)

        if points:
            self._write_api.write(bucket=self.config.bucket, org=self._org_id, record=points)
            if progress_callback:
                progress_callback(count)

        return count

    def query_metrics(self, metric_name: str, start: str = "-7d",
                     stop: str = "now()") -> list[dict]:
        """Query metrics by name

        Args:
            metric_name: Name of the metric to query
            start: Start time (e.g., "-7d", "-1h", "2024-01-01T00:00:00Z")
            stop: Stop time

        Returns:
            List of records
        """
        query = f'''
        from(bucket: "{self.config.bucket}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r._measurement == "health_metrics")
            |> filter(fn: (r) => r.metric == "{metric_name}")
            |> filter(fn: (r) => r._field == "value")
        '''

        result = self._query_api.query(query, org=self._org_id)
        records = []
        for table in result:
            for record in table.records:
                records.append({
                    "time": record.get_time(),
                    "value": record.get_value(),
                    "metric": record.values.get("metric"),
                    "source": record.values.get("source"),
                })
        return records

    def query_daily_aggregates(self, metric_name: str, start: str = "-30d") -> list[dict]:
        """Query daily aggregated data"""
        query = f'''
        from(bucket: "{self.config.bucket}")
            |> range(start: {start})
            |> filter(fn: (r) => r._measurement == "health_metrics_daily")
            |> filter(fn: (r) => r.metric == "{metric_name}")
        '''

        result = self._query_api.query(query, org=self._org_id)
        records = []
        for table in result:
            for record in table.records:
                records.append({
                    "time": record.get_time(),
                    "field": record.get_field(),
                    "value": record.get_value(),
                })
        return records

    def get_last_import_time(self, metric_name: str = None) -> Optional[datetime]:
        """Get the timestamp of the most recent data point

        Useful for incremental imports.
        """
        metric_filter = ""
        if metric_name:
            metric_filter = f'|> filter(fn: (r) => r.metric == "{metric_name}")'

        query = f'''
        from(bucket: "{self.config.bucket}")
            |> range(start: -365d)
            |> filter(fn: (r) => r._measurement == "health_metrics")
            {metric_filter}
            |> filter(fn: (r) => r._field == "value")
            |> last()
        '''

        result = self._query_api.query(query, org=self._org_id)
        for table in result:
            for record in table.records:
                return record.get_time()
        return None

    def delete_data(self, start: str, stop: str, measurement: str = None):
        """Delete data in a time range

        Use with caution!
        """
        delete_api = self._client.delete_api()

        predicate = ""
        if measurement:
            predicate = f'_measurement="{measurement}"'

        delete_api.delete(
            start=start,
            stop=stop,
            predicate=predicate,
            bucket=self.config.bucket,
            org=self._org_id,
        )
        logger.info(f"Deleted data from {start} to {stop}")
