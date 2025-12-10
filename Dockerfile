FROM python:3.12-slim

WORKDIR /app

# Install dependencies directly with pip (simpler for Docker)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY config.py models.py parser.py aggregator.py influx_client.py ingest.py ./

# Create data directory
RUN mkdir -p /data

# Default command shows help
CMD ["python", "ingest.py", "--help"]