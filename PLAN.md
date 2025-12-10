# Apple Health Data Pipeline - Project Plan

## Overview
Build a data pipeline to process Apple Health data exported via "Health Auto Export" app, store it in InfluxDB, and visualize it in Grafana.

## Architecture

```
┌─────────────────────┐
│   iPhone            │
│   Health Auto Export│
└─────────┬───────────┘
          │ JSON Export (REST API / File)
          ▼
┌─────────────────────┐
│   Synology NAS      │
│   ┌───────────────┐ │
│   │ Python Script │ │
│   │ (Ingestion)   │ │
│   └───────┬───────┘ │
│           ▼         │
│   ┌───────────────┐ │
│   │   InfluxDB    │ │
│   └───────┬───────┘ │
│           ▼         │
│   ┌───────────────┐ │
│   │    Grafana    │ │
│   └───────────────┘ │
└─────────────────────┘
```

## Phase 1: Data Ingestion Pipeline

### 1.1 JSON Parser (`parser.py`)
- Parse Health Auto Export JSON format (v2)
- Handle both metrics and workouts
- Support incremental imports (track last imported timestamp)
- Data validation and error handling

**Metrics to parse:**
- active_energy, basal_energy_burned
- heart_rate, heart_rate_variability, resting_heart_rate
- step_count, flights_climbed
- walking_running_distance, walking_speed, walking_step_length
- sleep_analysis, respiratory_rate
- blood_oxygen_saturation
- apple_exercise_time, apple_stand_time, apple_stand_hour
- physical_effort
- environmental_audio_exposure
- time_in_daylight
- underwater_depth, underwater_temperature (if applicable)
- + all other available metrics

**Workout data:**
- Basic info: name, start, end, duration, location
- Aggregated stats: total distance, active energy, step count
- Time series: heart rate during workout, per-second energy/steps
- Heart rate recovery data

### 1.2 Data Models (`models.py`)
- Pydantic models for type safety and validation
- HealthMetric: generic metric data point
- Workout: workout summary and metadata
- WorkoutTimeSeries: detailed workout time series data

### 1.3 InfluxDB Client (`influx_client.py`)
- Connection management
- Batch writing for performance
- Query helpers for common operations
- Error handling and retry logic

## Phase 2: InfluxDB Schema Design

### Measurements (Tables)

#### `health_metrics`
Primary measurement for all health data points.

| Field | Type | Description |
|-------|------|-------------|
| time | timestamp | Measurement time |
| metric_name | tag | e.g., "heart_rate", "step_count" |
| source | tag | e.g., "Apple Watch von Fabian" |
| value | field (float) | The metric value |
| unit | tag | e.g., "count/min", "km" |

#### `health_metrics_hourly`
Pre-aggregated hourly data for dashboards.

| Field | Type | Description |
|-------|------|-------------|
| time | timestamp | Hour bucket |
| metric_name | tag | Metric identifier |
| avg | field | Hourly average |
| min | field | Hourly minimum |
| max | field | Hourly maximum |
| sum | field | Hourly sum (for cumulative metrics) |
| count | field | Number of samples |

#### `health_metrics_daily`
Pre-aggregated daily data for long-term trends.

| Field | Type | Description |
|-------|------|-------------|
| time | timestamp | Day bucket |
| metric_name | tag | Metric identifier |
| avg | field | Daily average |
| min | field | Daily minimum |
| max | field | Daily maximum |
| sum | field | Daily sum |
| count | field | Number of samples |

#### `workouts`
Workout summary data.

| Field | Type | Description |
|-------|------|-------------|
| time | timestamp | Workout start time |
| workout_id | tag | Unique workout ID |
| name | tag | Workout type |
| location | tag | Indoor/Outdoor |
| duration | field | Duration in seconds |
| distance | field | Total distance |
| active_energy | field | Calories burned |
| avg_heart_rate | field | Average HR |
| max_heart_rate | field | Maximum HR |
| step_count | field | Total steps |

#### `workout_timeseries`
Detailed per-second/minute workout data.

| Field | Type | Description |
|-------|------|-------------|
| time | timestamp | Sample time |
| workout_id | tag | Links to workout |
| heart_rate | field | HR at this moment |
| active_energy | field | Energy at this moment |
| distance | field | Distance at this moment |
| step_count | field | Steps at this moment |

### Retention Policies

| Policy | Duration | Aggregation | Use Case |
|--------|----------|-------------|----------|
| raw | 30 days | None | Detailed analysis |
| hourly | 1 year | 1 hour | Medium-term trends |
| daily | Forever | 1 day | Long-term trends |

## Phase 3: Aggregation Strategy

### Problem
- Raw data: ~44 MB/day (~16 GB/year)
- Per-second data is excessive for most visualizations

### Solution: Multi-resolution storage

1. **Raw data**: Keep for 30 days, useful for:
   - Workout analysis
   - Debugging
   - Detailed daily patterns

2. **Hourly aggregates**: Keep for 1 year
   - avg, min, max, sum, count
   - Good for weekly/monthly dashboards

3. **Daily aggregates**: Keep forever
   - Perfect for long-term trends
   - Minimal storage (~1 KB/day)

### Aggregation Implementation
- Use InfluxDB Continuous Queries or Tasks
- Or: Python-based aggregation during import

## Phase 4: Grafana Dashboards

### Dashboard 1: Daily Overview
- Today's steps, distance, calories
- Activity rings (exercise, stand, move)
- Heart rate range
- Sleep duration last night

### Dashboard 2: Heart Health
- Resting heart rate trend
- Heart rate variability trend
- Heart rate zones distribution
- Walking heart rate average

### Dashboard 3: Activity & Fitness
- Steps per day (bar chart)
- Distance over time
- Flights climbed
- Active energy burned
- Exercise minutes

### Dashboard 4: Sleep Analysis
- Sleep duration trend
- Time in bed vs actual sleep
- Sleep schedule consistency
- Respiratory rate during sleep

### Dashboard 5: Workout Analysis
- Workout calendar/heatmap
- Workout duration by type
- Heart rate during workouts
- Performance trends over time

### Dashboard 6: Long-term Trends
- Weight trend (if tracked)
- Resting heart rate over months
- Activity level changes
- Seasonal patterns

## Phase 5: Advanced Python Analysis

Jupyter notebooks for deeper analysis:

### `analysis/correlations.ipynb`
- Sleep vs next-day HRV
- Exercise vs resting heart rate
- Activity vs sleep quality

### `analysis/predictions.ipynb`
- Predict recovery needs
- Identify overtraining patterns
- Forecast fitness trends

### `analysis/anomaly_detection.ipynb`
- Detect unusual heart rate patterns
- Identify sleep disruptions
- Flag potential health concerns

## File Structure

```
applehealth/
├── PLAN.md                 # This file
├── config.py               # Configuration (InfluxDB connection, etc.)
├── models.py               # Pydantic data models
├── parser.py               # JSON parsing logic
├── influx_client.py        # InfluxDB operations
├── aggregator.py           # Aggregation logic
├── ingest.py               # Main ingestion script
├── api_server.py           # REST API endpoint (for Health Auto Export)
├── grafana/
│   └── dashboards/         # Dashboard JSON exports
├── analysis/
│   └── *.ipynb             # Jupyter notebooks
├── tests/
│   └── test_*.py           # Unit tests
└── data/                   # Raw JSON exports (gitignored)
```

## Configuration Needed

```python
# config.py
INFLUXDB_URL = "http://nas-ip:8086"
INFLUXDB_TOKEN = "your-token"
INFLUXDB_ORG = "your-org"
INFLUXDB_BUCKET = "apple_health"

# Aggregation settings
KEEP_RAW_DAYS = 30
AGGREGATE_HOURLY = True
AGGREGATE_DAILY = True
```

## Next Steps

1. [ ] Set up Python project structure
2. [ ] Implement JSON parser
3. [ ] Create InfluxDB schema (bucket, measurements)
4. [ ] Build ingestion pipeline
5. [ ] Test with sample data
6. [ ] Create Grafana dashboards
7. [ ] Set up automation (REST API or scheduled sync)
8. [ ] Document deployment on Synology NAS

## Questions to Clarify

1. What InfluxDB version is running on your NAS? (1.x or 2.x)
2. Do you want to set up the REST API endpoint for automatic exports, or start with manual file imports?
3. Any specific metrics you're most interested in analyzing first?
4. Do you have historical data exports we should backfill?