# Ernährungs- & Fitness-Tracker

Eine intelligente Streamlit-App für personalisiertes Ernährungs- und Fitness-Tracking mit KI-Unterstützung.

## Features

### Kernfunktionen
- **Ziel-Setup**: Definiere dein Trainingsziel (Abnehmen, Muskelaufbau, Erhalt)
- **Mahlzeiten-Tracking**: Erfasse Mahlzeiten mit Nährwert-Suche (OpenFoodFacts)
- **Körperdaten**: Tracke Gewicht, Körperfett, Muskelmasse
- **Vorlieben**: Speichere Lieblingsspeisen und Abneigungen

### Apple Health Integration
- Automatischer Import von Aktivitätsdaten (Schritte, Kalorien, Workouts)
- Körperdaten-Sync aus Apple Health
- Verbindung über bestehende InfluxDB

### KI-Empfehlungen (Claude/OpenAI)
- Personalisierte Mahlzeitenpläne
- Fortschrittsanalyse
- Wochenpläne für die Lernphase

### ML-Prognosen
- Gewichts- und Körperfett-Prognosen
- Optimale Ernährungs-/Trainingspläne
- Analyse was für dich funktioniert

## Installation

### Lokal entwickeln

```bash
cd nutrition_app
pip install -r requirements.txt
streamlit run app.py
```

### Docker (NAS Deployment)

1. Konfiguration erstellen:
```bash
cp .env.template .env
# .env Datei mit echten Werten füllen
```

2. Container starten:
```bash
docker-compose up -d
```

3. App öffnen: http://NAS-IP:8502

## Konfiguration

### Umgebungsvariablen

| Variable | Beschreibung | Default |
|----------|--------------|---------|
| `POSTGRES_HOST` | PostgreSQL Server | localhost |
| `POSTGRES_PORT` | PostgreSQL Port | 5433 |
| `POSTGRES_DB` | Datenbank-Name | nutrition_app |
| `POSTGRES_USER` | DB Benutzer | postgres |
| `POSTGRES_PASSWORD` | DB Passwort | - |
| `INFLUXDB_URL` | InfluxDB URL | http://localhost:8088 |
| `INFLUXDB_TOKEN` | InfluxDB Token | - |
| `INFLUXDB_BUCKET` | Bucket für Apple Health | apple_health |
| `LLM_PROVIDER` | claude oder openai | claude |
| `ANTHROPIC_API_KEY` | Claude API Key | - |
| `OPENAI_API_KEY` | OpenAI API Key | - |

## Projektstruktur

```
nutrition_app/
├── app.py                 # Hauptanwendung
├── config.py              # Konfiguration
├── models/
│   └── database.py        # SQLAlchemy Modelle
├── services/
│   ├── database_service.py    # DB-Operationen
│   ├── food_api_service.py    # OpenFoodFacts API
│   ├── health_data_service.py # Apple Health (InfluxDB)
│   ├── llm_service.py         # Claude/OpenAI
│   └── ml_service.py          # Prognose-Modell
├── pages/
│   ├── 1_🎯_Ziele.py
│   ├── 2_🍽️_Vorlieben.py
│   ├── 3_🥗_Mahlzeiten.py
│   ├── 4_⚖️_Körperdaten.py
│   ├── 5_🤖_KI_Empfehlungen.py
│   └── 6_📈_Prognose.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Datenbank-Schema

Die App verwendet PostgreSQL mit folgenden Haupttabellen:
- `user_profiles` - Benutzerprofil
- `user_goals` - Trainingsziele
- `body_measurements` - Körpermessungen
- `foods` - Lebensmittel-Datenbank
- `meals` / `meal_items` - Mahlzeiten
- `food_preferences` - Vorlieben/Abneigungen
- `meal_feedback` - Feedback für ML-Lernen
- `ai_recommendations` - KI-Empfehlungen

## Entwicklung

### Neue Seite hinzufügen

1. Erstelle `pages/X_<emoji>_<Name>.py`
2. Importiere Session-Initialisierung
3. Nutze Streamlit für UI

### Services erweitern

Die Services sind modular aufgebaut. Jeder Service hat eine klare Verantwortung:
- `DatabaseService`: CRUD-Operationen
- `FoodAPIService`: Lebensmittel-Suche
- `HealthDataService`: Apple Health Daten
- `LLMService`: KI-Empfehlungen
- `MLService`: Prognosen

## Lizenz

Privat / Nicht für kommerzielle Nutzung
