#!/usr/bin/env python3
"""
Main ingestion script for Apple Health data

Usage:
    uv run ingest.py <json_file> [--dry-run] [--no-raw] [--no-hourly] [--no-daily]
    uv run ingest.py <json_file> --incremental  # Only import new data

Example:
    uv run ingest.py data_export/HealthAutoExport-20241201-20251210.json
    uv run ingest.py data_export/HealthAutoExport-20251210-20251217.json --incremental
"""
import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

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
    since: datetime = None,
) -> dict:
    """Ingest a Health Auto Export JSON file into InfluxDB

    Args:
        file_path: Path to the JSON file
        client: Connected InfluxDB client
        write_raw: Write raw per-second data
        write_hourly: Write hourly aggregates
        write_daily: Write daily aggregates
        dry_run: If True, parse but don't write to DB
        since: Only import data after this timestamp (for incremental imports)

    Returns:
        Dictionary with statistics about the ingestion
    """
    stats = {
        "file": str(file_path),
        "raw_metrics": 0,
        "hourly_aggregates": 0,
        "daily_aggregates": 0,
        "workouts": 0,
        "skipped_metrics": 0,
        "skipped_workouts": 0,
        "errors": [],
    }

    logger.info(f"Loading {file_path}...")
    parser = HealthDataParser(file_path, since=since)
    summary = parser.get_summary()
    logger.info(f"Found {summary['total_metric_samples']:,} metric samples, {summary['total_workouts']} workouts in file")

    if since:
        logger.info(f"Incremental mode: only importing data after {since}")

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
        stats["skipped_metrics"] = summary['total_metric_samples'] - count
        logger.info(f"Processed {count:,} raw metrics" + (f" (skipped {stats['skipped_metrics']:,} already imported)" if since else ""))

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
    stats["skipped_workouts"] = summary['total_workouts'] - workout_count
    logger.info(f"Processed {workout_count} workouts" + (f" (skipped {stats['skipped_workouts']} already imported)" if since else ""))

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
        "--clean",
        action="store_true",
        help="Delete and recreate the bucket before importing (fixes type conflicts)",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only import data newer than the last imported timestamp (skips duplicates)",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Only import data after this timestamp (format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
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

    # Parse --since timestamp if provided
    since_timestamp = None
    if args.since:
        try:
            # Try full datetime format first
            since_timestamp = datetime.fromisoformat(args.since)
        except ValueError:
            try:
                # Try date-only format
                since_timestamp = datetime.strptime(args.since, "%Y-%m-%d")
            except ValueError:
                logger.error(f"Invalid --since format: {args.since}. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS")
                sys.exit(1)

    # Connect and ingest
    logger.info(f"Connecting to InfluxDB at {config.influxdb.url}...")

    with HealthInfluxClient(config.influxdb) as client:
        if not client.health_check():
            logger.error("Cannot connect to InfluxDB")
            sys.exit(1)

        logger.info("Connected to InfluxDB")
        client.ensure_bucket_exists(clean=args.clean)

        # Handle incremental mode
        if args.incremental:
            if since_timestamp:
                logger.warning("Both --incremental and --since specified. Using --since value.")
            else:
                # Query the last import time from the database
                last_times = client.get_last_import_times()
                since_timestamp = last_times.get("raw")

                if since_timestamp:
                    logger.info(f"Incremental mode: last import was at {since_timestamp}")
                    # Delete overlapping aggregates to prevent double-counting
                    # We delete from the start of the hour containing the cutoff
                    cutoff_hour = since_timestamp.replace(minute=0, second=0, microsecond=0)
                    logger.info(f"Deleting hourly aggregates after {cutoff_hour} to prevent double-counting...")
                    client.delete_data_after(cutoff_hour, "health_metrics_hourly")

                    cutoff_day = since_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                    logger.info(f"Deleting daily aggregates after {cutoff_day} to prevent double-counting...")
                    client.delete_data_after(cutoff_day, "health_metrics_daily")
                else:
                    logger.info("No existing data found. Performing full import.")

        start_time = datetime.now()
        stats = ingest_file(
            file_path=args.file,
            client=client,
            write_raw=not args.no_raw,
            write_hourly=not args.no_hourly,
            write_daily=not args.no_daily,
            dry_run=args.dry_run,
            since=since_timestamp,
        )
        elapsed = datetime.now() - start_time

    # Print summary
    logger.info("=" * 50)
    logger.info("Ingestion complete!")
    logger.info(f"  File: {stats['file']}")
    logger.info(f"  Raw metrics: {stats['raw_metrics']:,}")
    if stats.get('skipped_metrics'):
        logger.info(f"  Skipped metrics (already imported): {stats['skipped_metrics']:,}")
    logger.info(f"  Hourly aggregates: {stats['hourly_aggregates']:,}")
    logger.info(f"  Daily aggregates: {stats['daily_aggregates']:,}")
    logger.info(f"  Workouts: {stats['workouts']}")
    if stats.get('skipped_workouts'):
        logger.info(f"  Skipped workouts (already imported): {stats['skipped_workouts']}")
    logger.info(f"  Time elapsed: {elapsed}")


if __name__ == "__main__":
    main()