"""
Data models for Apple Health data
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class MetricType(str, Enum):
    """Types of health metrics"""
    # Activity
    ACTIVE_ENERGY = "active_energy"
    BASAL_ENERGY = "basal_energy_burned"
    STEP_COUNT = "step_count"
    FLIGHTS_CLIMBED = "flights_climbed"
    WALKING_RUNNING_DISTANCE = "walking_running_distance"
    APPLE_EXERCISE_TIME = "apple_exercise_time"
    APPLE_STAND_TIME = "apple_stand_time"
    APPLE_STAND_HOUR = "apple_stand_hour"
    TIME_IN_DAYLIGHT = "time_in_daylight"

    # Heart
    HEART_RATE = "heart_rate"
    HEART_RATE_VARIABILITY = "heart_rate_variability"
    RESTING_HEART_RATE = "resting_heart_rate"
    WALKING_HEART_RATE_AVG = "walking_heart_rate_average"
    CARDIO_RECOVERY = "cardio_recovery"

    # Respiratory
    RESPIRATORY_RATE = "respiratory_rate"
    BLOOD_OXYGEN = "blood_oxygen_saturation"
    VO2_MAX = "vo2_max"

    # Body
    WEIGHT = "weight_body_mass"
    BODY_FAT = "body_fat_percentage"
    BMI = "body_mass_index"
    LEAN_BODY_MASS = "lean_body_mass"

    # Sleep
    SLEEP_ANALYSIS = "sleep_analysis"
    SLEEPING_WRIST_TEMP = "apple_sleeping_wrist_temperature"
    BREATHING_DISTURBANCES = "breathing_disturbances"

    # Walking metrics
    WALKING_SPEED = "walking_speed"
    WALKING_STEP_LENGTH = "walking_step_length"
    WALKING_DOUBLE_SUPPORT = "walking_double_support_percentage"
    WALKING_ASYMMETRY = "walking_asymmetry_percentage"
    STAIR_SPEED_UP = "stair_speed_up"
    STAIR_SPEED_DOWN = "stair_speed_down"
    SIX_MIN_WALK_DISTANCE = "six_minute_walking_test_distance"

    # Physical effort
    PHYSICAL_EFFORT = "physical_effort"

    # Audio
    ENVIRONMENTAL_AUDIO = "environmental_audio_exposure"
    HEADPHONE_AUDIO = "headphone_audio_exposure"

    # Cycling
    CYCLING_DISTANCE = "cycling_distance"
    CYCLING_POWER = "cycling_power"
    CYCLING_CADENCE = "cycling_cadence"
    CYCLING_FTP = "cycling_functional_threshold_power"

    # Water
    UNDERWATER_DEPTH = "underwater_depth"
    UNDERWATER_TEMP = "underwater_temperature"


@dataclass
class HealthMetricSample:
    """A single health metric data point"""
    metric_name: str
    timestamp: datetime
    value: float
    unit: str
    source: str = ""

    def to_influx_point(self) -> dict:
        """Convert to InfluxDB point format"""
        return {
            "measurement": "health_metrics",
            "tags": {
                "metric": self.metric_name,
                "source": self.source,
                "unit": self.unit,
            },
            "time": self.timestamp,
            "fields": {
                "value": float(self.value),
            },
        }


@dataclass
class AggregatedMetric:
    """Aggregated health metric (hourly/daily)"""
    metric_name: str
    timestamp: datetime  # Start of the aggregation period
    unit: str
    count: int
    sum_value: float
    avg_value: float
    min_value: float
    max_value: float

    def to_influx_point(self, measurement: str = "health_metrics_hourly") -> dict:
        """Convert to InfluxDB point format"""
        return {
            "measurement": measurement,
            "tags": {
                "metric": self.metric_name,
                "unit": self.unit,
            },
            "time": self.timestamp,
            "fields": {
                "count": self.count,
                "sum": self.sum_value,
                "avg": self.avg_value,
                "min": self.min_value,
                "max": self.max_value,
            },
        }


@dataclass
class WorkoutSample:
    """Time-series data point within a workout"""
    timestamp: datetime
    heart_rate: Optional[float] = None
    active_energy: Optional[float] = None
    distance: Optional[float] = None
    step_count: Optional[float] = None
    power: Optional[float] = None
    cadence: Optional[float] = None


@dataclass
class Workout:
    """A workout session"""
    workout_id: str
    name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    location: str = ""

    # Summary stats
    total_distance: Optional[float] = None
    distance_unit: str = "km"
    total_active_energy: Optional[float] = None
    energy_unit: str = "kJ"
    total_steps: Optional[int] = None

    # Heart rate stats
    avg_heart_rate: Optional[float] = None
    max_heart_rate: Optional[float] = None
    min_heart_rate: Optional[float] = None

    # Intensity
    intensity: Optional[float] = None
    intensity_unit: str = ""

    # Time series data (optional, for detailed analysis)
    heart_rate_data: list[WorkoutSample] = field(default_factory=list)
    heart_rate_recovery: list[dict] = field(default_factory=list)

    def to_influx_point(self) -> dict:
        """Convert to InfluxDB point format"""
        fields = {
            "duration": self.duration_seconds,
        }

        if self.total_distance is not None:
            fields["distance"] = self.total_distance
        if self.total_active_energy is not None:
            fields["active_energy"] = self.total_active_energy
        if self.total_steps is not None:
            fields["step_count"] = float(self.total_steps)
        if self.avg_heart_rate is not None:
            fields["avg_heart_rate"] = self.avg_heart_rate
        if self.max_heart_rate is not None:
            fields["max_heart_rate"] = self.max_heart_rate
        if self.min_heart_rate is not None:
            fields["min_heart_rate"] = self.min_heart_rate
        if self.intensity is not None:
            fields["intensity"] = self.intensity

        return {
            "measurement": "workouts",
            "tags": {
                "workout_id": self.workout_id,
                "name": self.name,
                "location": self.location or "unknown",
            },
            "time": self.start_time,
            "fields": fields,
        }

    def heart_rate_to_influx_points(self) -> list[dict]:
        """Convert heart rate time series to InfluxDB points"""
        points = []
        for sample in self.heart_rate_data:
            if sample.heart_rate is not None:
                points.append({
                    "measurement": "workout_heart_rate",
                    "tags": {
                        "workout_id": self.workout_id,
                        "workout_name": self.name,
                    },
                    "time": sample.timestamp,
                    "fields": {
                        "heart_rate": sample.heart_rate,
                    },
                })
        return points