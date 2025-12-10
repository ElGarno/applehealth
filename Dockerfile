FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency management
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock* ./
COPY *.py ./

# Install dependencies
RUN uv sync --frozen 2>/dev/null || uv sync

# Create data directory
RUN mkdir -p /data

# Default command shows help
CMD ["uv", "run", "python", "ingest.py", "--help"]