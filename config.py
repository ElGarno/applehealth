"""
Configuration for Apple Health Data Pipeline
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InfluxDBConfig:
    """InfluxDB 2.x connection configuration"""
    url: str = "http://localhost:8088"
    token: str = ""  # Set via environment variable INFLUXDB_TOKEN
    bucket: str = "apple_health"


@dataclass
class PipelineConfig:
    """Data pipeline configuration"""
    # Data retention settings
    keep_raw_days: int = 30  # Keep raw per-second data for 30 days

    # Aggregation settings
    aggregate_to_minute: bool = True  # Aggregate to minute-level
    aggregate_to_hour: bool = True    # Aggregate to hour-level
    aggregate_to_day: bool = True     # Aggregate to day-level

    # Batch size for InfluxDB writes
    batch_size: int = 5000

    # Data directory
    data_dir: Path = Path("data_export")


@dataclass
class Config:
    """Main configuration"""
    influxdb: InfluxDBConfig
    pipeline: PipelineConfig


def get_config() -> Config:
    """Get configuration, loading sensitive values from environment"""
    import os

    influx_config = InfluxDBConfig(
        url=os.getenv("INFLUXDB_URL", "http://localhost:8088"),
        token=os.getenv("INFLUXDB_TOKEN", ""),
        bucket=os.getenv("INFLUXDB_BUCKET", "apple_health"),
    )

    pipeline_config = PipelineConfig(
        data_dir=Path(os.getenv("DATA_DIR", "data_export"))
    )

    return Config(influxdb=influx_config, pipeline=pipeline_config)