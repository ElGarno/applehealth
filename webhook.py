#!/usr/bin/env python3
"""
Webhook receiver for Health Auto Export app

Receives JSON data from the Health Auto Export iOS app and triggers the import pipeline.

Usage:
    python webhook.py

Environment variables:
    WEBHOOK_PORT: Port to listen on (default: 8080)
    WEBHOOK_SECRET: Optional secret token for authentication
    INFLUXDB_URL: InfluxDB URL
    INFLUXDB_TOKEN: InfluxDB token
    INFLUXDB_BUCKET: InfluxDB bucket name
    DATA_DIR: Directory to save received JSON files (default: /data)
"""
import json
import logging
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import threading

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_config
from parser import HealthDataParser
from influx_client import HealthInfluxClient
from aggregator import StreamingAggregator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration
WEBHOOK_PORT = int(os.environ.get("WEBHOOK_PORT", 8080))
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))


def run_import(file_path: Path, incremental: bool = True):
    """Run the import pipeline on a JSON file"""
    config = get_config()

    logger.info(f"Starting import of {file_path}...")

    try:
        with HealthInfluxClient(config.influxdb) as client:
            if not client.health_check():
                logger.error("Cannot connect to InfluxDB")
                return False

            # Get last import time for incremental mode
            since_timestamp = None
            if incremental:
                last_times = client.get_last_import_times()
                since_timestamp = last_times.get("raw")

                if since_timestamp:
                    logger.info(f"Incremental mode: last import was at {since_timestamp}")
                    # Delete overlapping aggregates
                    cutoff_hour = since_timestamp.replace(minute=0, second=0, microsecond=0)
                    client.delete_data_after(cutoff_hour, "health_metrics_hourly")

                    cutoff_day = since_timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                    client.delete_data_after(cutoff_day, "health_metrics_daily")

            # Parse and import
            parser = HealthDataParser(file_path, since=since_timestamp)
            summary = parser.get_summary()
            logger.info(f"Found {summary['total_metric_samples']:,} samples, {summary['total_workouts']} workouts")

            # Initialize aggregator
            aggregator = StreamingAggregator()

            # Process metrics
            count = 0
            for sample in parser.get_metrics():
                aggregator.add_sample(sample)
                client.write_metric(sample)
                count += 1

            logger.info(f"Wrote {count:,} raw metrics")

            # Write aggregates
            hourly_list = list(aggregator.get_hourly_aggregates())
            hourly_count = client.write_aggregated_batch(
                iter(hourly_list),
                measurement="health_metrics_hourly",
            )
            logger.info(f"Wrote {hourly_count:,} hourly aggregates")

            daily_list = list(aggregator.get_daily_aggregates())
            daily_count = client.write_aggregated_batch(
                iter(daily_list),
                measurement="health_metrics_daily",
            )
            logger.info(f"Wrote {daily_count:,} daily aggregates")

            # Process workouts
            workout_count = 0
            for workout in parser.get_workouts():
                client.write_workout(workout)
                workout_count += 1

            logger.info(f"Wrote {workout_count} workouts")
            logger.info("Import complete!")
            return True

    except Exception as e:
        logger.error(f"Import failed: {e}")
        return False


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for receiving Health Auto Export webhooks"""

    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"{self.address_string()} - {format % args}")

    def send_json_response(self, status_code: int, data: dict):
        """Send a JSON response"""
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        """Handle GET requests - health check"""
        if self.path == "/health":
            self.send_json_response(200, {"status": "ok", "service": "health-auto-export-webhook"})
        else:
            self.send_json_response(200, {
                "status": "ok",
                "message": "Health Auto Export Webhook Receiver",
                "endpoints": {
                    "POST /webhook": "Receive health data export",
                    "GET /health": "Health check",
                }
            })

    def do_POST(self):
        """Handle POST requests - receive health data"""
        if self.path != "/webhook":
            self.send_json_response(404, {"error": "Not found"})
            return

        # Check authentication if secret is configured
        if WEBHOOK_SECRET:
            auth_header = self.headers.get("Authorization", "")
            expected = f"Bearer {WEBHOOK_SECRET}"
            if auth_header != expected:
                logger.warning(f"Unauthorized request from {self.address_string()}")
                self.send_json_response(401, {"error": "Unauthorized"})
                return

        # Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self.send_json_response(400, {"error": "Empty request body"})
            return

        try:
            body = self.rfile.read(content_length)
            data = json.loads(body)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            self.send_json_response(400, {"error": f"Invalid JSON: {e}"})
            return

        # Validate it looks like Health Auto Export data
        if "data" not in data:
            self.send_json_response(400, {"error": "Invalid format: missing 'data' field"})
            return

        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"HealthAutoExport-webhook-{timestamp}.json"
        file_path = DATA_DIR / filename

        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                json.dump(data, f)
            logger.info(f"Saved export to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            self.send_json_response(500, {"error": f"Failed to save file: {e}"})
            return

        # Send immediate response
        self.send_json_response(202, {
            "status": "accepted",
            "message": "Data received, import started",
            "file": filename,
        })

        # Run import in background thread
        thread = threading.Thread(target=run_import, args=(file_path, True))
        thread.daemon = True
        thread.start()


def main():
    """Start the webhook server"""
    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    server_address = ("", WEBHOOK_PORT)
    httpd = HTTPServer(server_address, WebhookHandler)

    logger.info(f"Starting webhook server on port {WEBHOOK_PORT}")
    logger.info(f"Data directory: {DATA_DIR}")
    if WEBHOOK_SECRET:
        logger.info("Authentication enabled (WEBHOOK_SECRET is set)")
    else:
        logger.warning("No authentication configured (WEBHOOK_SECRET not set)")

    logger.info(f"Webhook endpoint: http://<your-ip>:{WEBHOOK_PORT}/webhook")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    main()