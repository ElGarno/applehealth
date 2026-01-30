"""
Konfiguration für die Nutrition & Fitness App
"""
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """PostgreSQL Konfiguration"""
    host: str = "localhost"
    port: int = 5432
    database: str = "nutrition_app"
    user: str = "postgres"
    password: str = ""

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class InfluxDBConfig:
    """InfluxDB Konfiguration für Apple Health Daten"""
    url: str = "http://localhost:8088"
    token: str = ""
    bucket: str = "apple_health"
    org: str = ""


@dataclass
class LLMConfig:
    """LLM Konfiguration für KI-Empfehlungen"""
    provider: str = "claude"  # "claude" oder "openai"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    model_claude: str = "claude-sonnet-4-20250514"
    model_openai: str = "gpt-4o"


@dataclass
class AppConfig:
    """Haupt-Konfiguration"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    influxdb: InfluxDBConfig = field(default_factory=InfluxDBConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # OpenFoodFacts API (kostenlos, keine Keys nötig)
    openfoodfacts_api: str = "https://world.openfoodfacts.org/api/v2"

    # App-Einstellungen
    app_name: str = "Ernährungs- & Fitness-Tracker"
    language: str = "de"


def load_config() -> AppConfig:
    """Lädt Konfiguration aus Umgebungsvariablen"""
    db_config = DatabaseConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "nutrition_app"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )

    influx_config = InfluxDBConfig(
        url=os.getenv("INFLUXDB_URL", "http://localhost:8088"),
        token=os.getenv("INFLUXDB_TOKEN", ""),
        bucket=os.getenv("INFLUXDB_BUCKET", "apple_health"),
        org=os.getenv("INFLUXDB_ORG", ""),
    )

    llm_config = LLMConfig(
        provider=os.getenv("LLM_PROVIDER", "claude"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    )

    return AppConfig(
        database=db_config,
        influxdb=influx_config,
        llm=llm_config,
    )
