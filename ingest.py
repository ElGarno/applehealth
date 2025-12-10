#!/usr/bin/env python3
"""
Main ingestion script for Apple Health data

Usage:
    uv run ingest.py <json_file> [--dry-run] [--no-raw] [--no-hourly] [--no-daily]

Example:
    uv run ingest.py data_export/HealthAutoExport-20241201-20251210.json
"""
import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime

from config import get_config
from parser import HealthDataParser
from influx_client import HealthInfluxClient
from aggregator import StreamingAggregator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def progress_callback(count: int, label: str = "samples"):
    """Print progress updates"""
    print(f"\r  Processed {count:,} {label}...", end="", flush=True)


def ingest_file(
    file_path: Path,
    client: HealthInfluxClient,
    write_raw: bool = True,
    write_hourly: bool = True,
    write_daily: bool = True,
    dry_run: bool = False,
) -> dict:
    """Ingest a Health Auto Export JSON file into InfluxDB

    Args:
        file_path: Path to the JSON file
        client: Connected InfluxDB client
        write_raw: Write raw per-second data
        write_hourly: Write hourly aggregates
        write_daily: Write daily aggregates
        dry_run: If True, parse but don't write to DB

    Returns:
        Dictionary with statistics about the ingestion
    """
    stats = {
        "file": str(file_path),
        "raw_metrics": 0,
        "hourly_aggregates": 0,
        "daily_aggregates": 0,
        "workouts": 0,
        "errors": [],
    }

    logger.info(f"Loading {file_path}...")
    parser = HealthDataParser(file_path)
    summary = parser.get_summary()
    logger.info(f"Found {summary['total_metric_samples']:,} metric samples, {summary['total_workouts']} workouts")

    # Initialize streaming aggregator
    aggregator = StreamingAggregator()

    # Process metrics
    if write_raw or write_hourly or write_daily:
        logger.info("Processing metrics...")
        count = 0

        for sample in parser.get_metrics():
            # Add to aggregator
            if write_hourly or write_daily:
                aggregator.add_sample(sample)

            # Write raw data
            if write_raw and not dry_run:
                client.write_metric(sample)

            count += 1
            if count % 100000 == 0:
                progress_callback(count, "metrics")

        print()  # New line after progress
        stats["raw_metrics"] = count
        logger.info(f"Processed {count:,} raw metrics")

    # Write hourly aggregates
    if write_hourly and not dry_run:
        logger.info("Writing hourly aggregates...")
        hourly_list = list(aggregator.get_hourly_aggregates())
        count = client.write_aggregated_batch(
            iter(hourly_list),
            measurement="health_metrics_hourly",
            progress_callback=lambda c: progress_callback(c, "hourly aggregates"),
        )
        print()
        stats["hourly_aggregates"] = count
        logger.info(f"Wrote {count:,} hourly aggregates")

    # Write daily aggregates
    if write_daily and not dry_run:
        logger.info("Writing daily aggregates...")
        daily_list = list(aggregator.get_daily_aggregates())
        count = client.write_aggregated_batch(
            iter(daily_list),
            measurement="health_metrics_daily",
            progress_callback=lambda c: progress_callback(c, "daily aggregates"),
        )
        print()
        stats["daily_aggregates"] = count
        logger.info(f"Wrote {count:,} daily aggregates")

    # Process workouts
    logger.info("Processing workouts...")
    workout_count = 0
    for workout in parser.get_workouts():
        if not dry_run:
            client.write_workout(workout)
        workout_count += 1

    stats["workouts"] = workout_count
    logger.info(f"Processed {workout_count} workouts")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Apple Health data into InfluxDB"
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to Health Auto Export JSON file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse data but don't write to InfluxDB",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Skip writing raw per-second data",
    )
    parser.add_argument(
        "--no-hourly",
        action="store_true",
        help="Skip writing hourly aggregates",
    )
    parser.add_argument(
        "--no-daily",
        action="store_true",
        help="Skip writing daily aggregates",
    )
    parser.add_argument(
        "--url",
        type=str,
        help="InfluxDB URL (default: from INFLUXDB_URL env var)",
    )
    parser.add_argument(
        "--token",
        type=str,
        help="InfluxDB token (default: from INFLUXDB_TOKEN env var)",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        help="InfluxDB bucket (default: from INFLUXDB_BUCKET env var)",
    )

    args = parser.parse_args()

    # Validate file exists
    if not args.file.exists():
        logger.error(f"File not found: {args.file}")
        sys.exit(1)

    # Get config
    config = get_config()

    # Override with command line args
    if args.url:
        config.influxdb.url = args.url
    if args.token:
        config.influxdb.token = args.token
    if args.bucket:
        config.influxdb.bucket = args.bucket

    # Validate config
    if not config.influxdb.token and not args.dry_run:
        logger.error("InfluxDB token not set. Use --token or set INFLUXDB_TOKEN environment variable.")
        logger.info("For dry-run mode without database, use --dry-run flag")
        sys.exit(1)

    if args.dry_run:
        logger.info("DRY RUN MODE - No data will be written to InfluxDB")
        # Create a mock client for dry run
        stats = {
            "file": str(args.file),
            "raw_metrics": 0,
            "hourly_aggregates": 0,
            "daily_aggregates": 0,
            "workouts": 0,
        }

        parser_obj = HealthDataParser(args.file)
        summary = parser_obj.get_summary()

        logger.info(f"File: {args.file}")
        logger.info(f"Total metric samples: {summary['total_metric_samples']:,}")
        logger.info(f"Metric types: {summary['metric_types']}")
        logger.info(f"Total workouts: {summary['total_workouts']}")

        logger.info("\nMetrics breakdown:")
        for name, info in sorted(summary['metrics'].items(), key=lambda x: -x[1]['count']):
            logger.info(f"  {name}: {info['count']:,} samples ({info['unit']})")

        return

    # Connect and ingest
    logger.info(f"Connecting to InfluxDB at {config.influxdb.url}...")

    with HealthInfluxClient(config.influxdb) as client:
        if not client.health_check():
            logger.error("Cannot connect to InfluxDB")
            sys.exit(1)

        logger.info("Connected to InfluxDB")
        client.ensure_bucket_exists()

        start_time = datetime.now()
        stats = ingest_file(
            file_path=args.file,
            client=client,
            write_raw=not args.no_raw,
            write_hourly=not args.no_hourly,
            write_daily=not args.no_daily,
            dry_run=args.dry_run,
        )
        elapsed = datetime.now() - start_time

    # Print summary
    logger.info("=" * 50)
    logger.info("Ingestion complete!")
    logger.info(f"  File: {stats['file']}")
    logger.info(f"  Raw metrics: {stats['raw_metrics']:,}")
    logger.info(f"  Hourly aggregates: {stats['hourly_aggregates']:,}")
    logger.info(f"  Daily aggregates: {stats['daily_aggregates']:,}")
    logger.info(f"  Workouts: {stats['workouts']}")
    logger.info(f"  Time elapsed: {elapsed}")


if __name__ == "__main__":
    main()