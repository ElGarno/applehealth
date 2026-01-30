"""
Service für Apple Health Daten aus InfluxDB
"""
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
import logging

from influxdb_client import InfluxDBClient

logger = logging.getLogger(__name__)


class HealthDataService:
    """Service für Abfragen von Apple Health Daten aus InfluxDB"""

    def __init__(self, url: str, token: str, bucket: str = "apple_health", org: str = None):
        self.url = url
        self.token = token
        self.bucket = bucket
        self.org = org
        self._client: Optional[InfluxDBClient] = None
        self._query_api = None
        self._org_id = None

    def connect(self):
        """Verbindet mit InfluxDB"""
        self._client = InfluxDBClient(url=self.url, token=self.token)

        # Organisation ermitteln
        if self.org:
            self._org_id = self.org
        else:
            orgs = self._client.organizations_api().find_organizations()
            if orgs:
                self._org_id = orgs[0].id
            else:
                raise RuntimeError("Keine Organisation in InfluxDB gefunden")

        self._query_api = self._client.query_api()
        logger.info(f"Verbunden mit InfluxDB: {self.url}")

    def close(self):
        """Schließt Verbindung"""
        if self._client:
            self._client.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def is_connected(self) -> bool:
        """Prüft Verbindung"""
        try:
            return self._client and self._client.ping()
        except Exception:
            return False

    # ==================== Aktivitätsdaten ====================

    def get_daily_activity(self, target_date: date) -> Dict[str, Any]:
        """
        Holt Aktivitätsdaten für einen Tag

        Returns:
            Dict mit steps, active_calories, exercise_minutes, etc.
        """
        start = datetime.combine(target_date, datetime.min.time()).isoformat() + "Z"
        stop = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat() + "Z"

        metrics = {
            "steps": "step_count",
            "active_calories": "active_energy",
            "basal_calories": "basal_energy_burned",
            "exercise_minutes": "exercise_time",
            "stand_hours": "stand_hour",
            "distance_km": "distance_walking_running",
        }

        results = {}
        for key, metric in metrics.items():
            results[key] = self._get_daily_sum(metric, start, stop)

        return results

    def get_activity_trend(self, days: int = 7) -> List[Dict[str, Any]]:
        """Holt Aktivitätstrend der letzten X Tage"""
        trends = []
        for i in range(days - 1, -1, -1):
            target = date.today() - timedelta(days=i)
            activity = self.get_daily_activity(target)
            activity['date'] = target.isoformat()
            trends.append(activity)
        return trends

    def _get_daily_sum(self, metric: str, start: str, stop: str) -> float:
        """Holt Tagessumme für eine Metrik"""
        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r._measurement == "health_metrics_daily" or r._measurement == "health_metrics_hourly")
            |> filter(fn: (r) => r.metric == "{metric}")
            |> filter(fn: (r) => r._field == "sum" or r._field == "count")
            |> sum()
        '''

        try:
            result = self._query_api.query(query, org=self._org_id)
            for table in result:
                for record in table.records:
                    return record.get_value() or 0
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen von {metric}: {e}")

        return 0

    # ==================== Herzfrequenz ====================

    def get_resting_heart_rate(self, target_date: date) -> Optional[float]:
        """Holt Ruhepuls für einen Tag"""
        start = datetime.combine(target_date, datetime.min.time()).isoformat() + "Z"
        stop = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat() + "Z"

        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r._measurement == "health_metrics" or r._measurement == "health_metrics_daily")
            |> filter(fn: (r) => r.metric == "resting_heart_rate")
            |> filter(fn: (r) => r._field == "value" or r._field == "avg")
            |> mean()
        '''

        try:
            result = self._query_api.query(query, org=self._org_id)
            for table in result:
                for record in table.records:
                    return record.get_value()
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen des Ruhepuls: {e}")

        return None

    def get_heart_rate_variability(self, target_date: date) -> Optional[float]:
        """Holt HRV für einen Tag"""
        start = datetime.combine(target_date, datetime.min.time()).isoformat() + "Z"
        stop = datetime.combine(target_date + timedelta(days=1), datetime.min.time()).isoformat() + "Z"

        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r._measurement == "health_metrics" or r._measurement == "health_metrics_daily")
            |> filter(fn: (r) => r.metric == "heart_rate_variability")
            |> filter(fn: (r) => r._field == "value" or r._field == "avg")
            |> mean()
        '''

        try:
            result = self._query_api.query(query, org=self._org_id)
            for table in result:
                for record in table.records:
                    return record.get_value()
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen der HRV: {e}")

        return None

    # ==================== Workouts ====================

    def get_workouts(self, days: int = 7) -> List[Dict[str, Any]]:
        """Holt Workouts der letzten X Tage"""
        start = f"-{days}d"

        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start})
            |> filter(fn: (r) => r._measurement == "workouts")
            |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
        '''

        workouts = []
        try:
            result = self._query_api.query(query, org=self._org_id)
            for table in result:
                for record in table.records:
                    workout = {
                        'time': record.get_time(),
                        'name': record.values.get('name'),
                        'duration_min': (record.values.get('duration') or 0) / 60,
                        'active_calories': record.values.get('active_energy'),
                        'distance_km': record.values.get('distance'),
                        'avg_heart_rate': record.values.get('avg_heart_rate'),
                    }
                    workouts.append(workout)
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen der Workouts: {e}")

        return workouts

    def get_workout_summary(self, days: int = 7) -> Dict[str, Any]:
        """Berechnet Workout-Zusammenfassung"""
        workouts = self.get_workouts(days)

        if not workouts:
            return {
                'total_workouts': 0,
                'total_duration_min': 0,
                'total_calories': 0,
                'avg_duration_min': 0,
            }

        total_duration = sum(w.get('duration_min', 0) or 0 for w in workouts)
        total_calories = sum(w.get('active_calories', 0) or 0 for w in workouts)

        return {
            'total_workouts': len(workouts),
            'total_duration_min': round(total_duration, 1),
            'total_calories': round(total_calories),
            'avg_duration_min': round(total_duration / len(workouts), 1) if workouts else 0,
        }

    # ==================== Schlaf ====================

    def get_sleep_data(self, target_date: date) -> Dict[str, Any]:
        """Holt Schlafdaten für eine Nacht"""
        # Schlaf beginnt am Vorabend
        start = datetime.combine(target_date - timedelta(days=1), datetime.min.time().replace(hour=18)).isoformat() + "Z"
        stop = datetime.combine(target_date, datetime.min.time().replace(hour=12)).isoformat() + "Z"

        query = f'''
        from(bucket: "{self.bucket}")
            |> range(start: {start}, stop: {stop})
            |> filter(fn: (r) => r._measurement == "health_metrics")
            |> filter(fn: (r) => r.metric == "sleep_analysis")
            |> filter(fn: (r) => r._field == "value")
            |> sum()
        '''

        sleep_minutes = 0
        try:
            result = self._query_api.query(query, org=self._org_id)
            for table in result:
                for record in table.records:
                    sleep_minutes = record.get_value() or 0
        except Exception as e:
            logger.warning(f"Fehler beim Abrufen der Schlafdaten: {e}")

        return {
            'sleep_hours': round(sleep_minutes / 60, 1) if sleep_minutes else None,
            'sleep_minutes': sleep_minutes,
        }

    # ==================== Körperdaten aus Apple Health ====================

    def get_latest_body_metrics(self) -> Dict[str, Any]:
        """Holt die neuesten Körperdaten aus Apple Health"""
        metrics = ["body_mass", "body_fat_percentage", "lean_body_mass", "bmi"]
        results = {}

        for metric in metrics:
            query = f'''
            from(bucket: "{self.bucket}")
                |> range(start: -30d)
                |> filter(fn: (r) => r._measurement == "health_metrics")
                |> filter(fn: (r) => r.metric == "{metric}")
                |> filter(fn: (r) => r._field == "value")
                |> last()
            '''

            try:
                result = self._query_api.query(query, org=self._org_id)
                for table in result:
                    for record in table.records:
                        results[metric] = {
                            'value': record.get_value(),
                            'time': record.get_time(),
                        }
            except Exception as e:
                logger.warning(f"Fehler beim Abrufen von {metric}: {e}")

        return results

    # ==================== Kalorienverbrauch ====================

    def get_total_daily_energy(self, target_date: date) -> Dict[str, float]:
        """
        Berechnet den Gesamtkalorienverbrauch (TDEE)

        Returns:
            Dict mit active_calories, basal_calories, total_calories
        """
        activity = self.get_daily_activity(target_date)

        active = activity.get('active_calories', 0) or 0
        basal = activity.get('basal_calories', 0) or 0

        return {
            'active_calories': round(active),
            'basal_calories': round(basal),
            'total_calories': round(active + basal),
        }
