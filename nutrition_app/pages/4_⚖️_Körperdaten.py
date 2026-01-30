"""
Körperdaten-Tracking Seite
"""
import streamlit as st
from datetime import datetime, date, timedelta
import pandas as pd

st.set_page_config(page_title="Körperdaten", page_icon="⚖️", layout="wide")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
from services.database_service import DatabaseService


def init_session():
    """Session initialisieren"""
    if 'config' not in st.session_state:
        st.session_state.config = load_config()
    if 'db' not in st.session_state:
        try:
            st.session_state.db = DatabaseService(
                st.session_state.config.database.connection_string
            )
        except Exception as e:
            st.error(f"Datenbankfehler: {e}")
            return False
    if 'user' not in st.session_state:
        st.session_state.user = st.session_state.db.get_or_create_user()
    return True


def main():
    st.title("⚖️ Körperdaten")

    if not init_session():
        return

    db = st.session_state.db
    user = st.session_state.user

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📝 Neue Messung", "📈 Verlauf", "🍎 Apple Health"])

    # ==================== Neue Messung ====================
    with tab1:
        st.subheader("Neue Messung eintragen")

        # Letzte Werte als Default
        latest = db.get_latest_measurement(user.id)

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Hauptwerte")

            weight = st.number_input(
                "Gewicht (kg)",
                min_value=30.0,
                max_value=300.0,
                value=float(latest.weight_kg) if latest and latest.weight_kg else 75.0,
                step=0.1,
                format="%.1f",
            )

            body_fat = st.number_input(
                "Körperfettanteil (%)",
                min_value=3.0,
                max_value=60.0,
                value=float(latest.body_fat_percent) if latest and latest.body_fat_percent else 20.0,
                step=0.1,
                format="%.1f",
            )

            muscle_mass = st.number_input(
                "Muskelmasse (kg)",
                min_value=10.0,
                max_value=100.0,
                value=float(latest.muscle_mass_kg) if latest and latest.muscle_mass_kg else 30.0,
                step=0.1,
                format="%.1f",
            )

            water = st.number_input(
                "Wasseranteil (%)",
                min_value=30.0,
                max_value=80.0,
                value=float(latest.water_percent) if latest and latest.water_percent else 55.0,
                step=0.1,
                format="%.1f",
            )

        with col2:
            st.markdown("### Optionale Maße")

            waist = st.number_input(
                "Bauchumfang (cm)",
                min_value=40.0,
                max_value=200.0,
                value=float(latest.waist_cm) if latest and latest.waist_cm else 80.0,
                step=0.5,
            )

            hip = st.number_input(
                "Hüftumfang (cm)",
                min_value=40.0,
                max_value=200.0,
                value=float(latest.hip_cm) if latest and latest.hip_cm else 95.0,
                step=0.5,
            )

            measurement_time = st.time_input(
                "Uhrzeit",
                value=datetime.now().time(),
            )

            notes = st.text_area(
                "Notizen",
                placeholder="z.B. Morgens nüchtern, nach dem Training, etc.",
                height=100,
            )

        # BMI berechnen
        if user.height_cm:
            height_m = user.height_cm / 100
            bmi = weight / (height_m ** 2)

            st.markdown("---")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("BMI", f"{bmi:.1f}")
                if bmi < 18.5:
                    st.caption("Untergewicht")
                elif bmi < 25:
                    st.caption("Normalgewicht ✓")
                elif bmi < 30:
                    st.caption("Übergewicht")
                else:
                    st.caption("Adipositas")

            with col2:
                if body_fat:
                    ffmi = muscle_mass / (height_m ** 2)
                    st.metric("FFMI", f"{ffmi:.1f}")
                    st.caption("Fettfreie Masse Index")

            with col3:
                if waist and hip:
                    whr = waist / hip
                    st.metric("WHR", f"{whr:.2f}")
                    st.caption("Taille-Hüft-Verhältnis")
        else:
            st.warning("Bitte gib deine Körpergröße unter 'Ziele' ein für BMI-Berechnung.")

        # Speichern Button
        if st.button("💾 Messung speichern", type="primary", use_container_width=True):
            measurement_datetime = datetime.combine(date.today(), measurement_time)

            try:
                db.add_body_measurement(
                    user_id=user.id,
                    weight=weight,
                    body_fat=body_fat,
                    muscle_mass=muscle_mass,
                    water_percent=water,
                    waist_cm=waist if waist != 80.0 else None,
                    hip_cm=hip if hip != 95.0 else None,
                    measured_at=measurement_datetime,
                    notes=notes if notes else None,
                )
                st.success("✅ Messung gespeichert!")
                st.balloons()
            except Exception as e:
                st.error(f"Fehler beim Speichern: {e}")

    # ==================== Verlauf ====================
    with tab2:
        st.subheader("📈 Verlauf deiner Messungen")

        # Zeitraum auswählen
        period = st.selectbox(
            "Zeitraum",
            options=[30, 90, 180, 365],
            format_func=lambda x: f"Letzte {x} Tage",
            index=1,
        )

        measurements = db.get_body_measurements(user.id, days=period)

        if measurements:
            # In DataFrame umwandeln
            data = []
            for m in measurements:
                data.append({
                    'Datum': m.measured_at,
                    'Gewicht (kg)': m.weight_kg,
                    'Körperfett (%)': m.body_fat_percent,
                    'Muskelmasse (kg)': m.muscle_mass_kg,
                    'BMI': m.bmi,
                    'Wasseranteil (%)': m.water_percent,
                })

            df = pd.DataFrame(data)
            df = df.sort_values('Datum')

            # Charts
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Gewicht")
                if 'Gewicht (kg)' in df.columns and df['Gewicht (kg)'].notna().any():
                    st.line_chart(df.set_index('Datum')['Gewicht (kg)'])

                    # Statistiken
                    start_weight = df['Gewicht (kg)'].iloc[0]
                    end_weight = df['Gewicht (kg)'].iloc[-1]
                    change = end_weight - start_weight

                    st.metric(
                        "Veränderung",
                        f"{change:+.1f} kg",
                        delta=f"von {start_weight:.1f} auf {end_weight:.1f} kg"
                    )

            with col2:
                st.markdown("#### Körperfett")
                if 'Körperfett (%)' in df.columns and df['Körperfett (%)'].notna().any():
                    st.line_chart(df.set_index('Datum')['Körperfett (%)'])

                    start_bf = df['Körperfett (%)'].iloc[0]
                    end_bf = df['Körperfett (%)'].iloc[-1]
                    change_bf = end_bf - start_bf

                    st.metric(
                        "Veränderung",
                        f"{change_bf:+.1f}%",
                        delta=f"von {start_bf:.1f} auf {end_bf:.1f}%"
                    )

            # Muskelmasse Chart
            st.markdown("#### Muskelmasse")
            if 'Muskelmasse (kg)' in df.columns and df['Muskelmasse (kg)'].notna().any():
                st.line_chart(df.set_index('Datum')['Muskelmasse (kg)'])

            # Tabelle mit allen Daten
            st.markdown("---")
            st.markdown("#### Alle Messungen")
            st.dataframe(
                df.sort_values('Datum', ascending=False),
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info("Noch keine Messungen vorhanden. Trage deine erste Messung ein!")

    # ==================== Apple Health Sync ====================
    with tab3:
        st.subheader("🍎 Apple Health Daten")

        config = st.session_state.config

        if not config.influxdb.token:
            st.warning("""
            **Apple Health nicht konfiguriert**

            Um Körperdaten aus Apple Health zu importieren, konfiguriere die InfluxDB-Verbindung:
            - `INFLUXDB_URL`
            - `INFLUXDB_TOKEN`
            - `INFLUXDB_BUCKET`
            """)
            return

        try:
            from services.health_data_service import HealthDataService

            with HealthDataService(
                url=config.influxdb.url,
                token=config.influxdb.token,
                bucket=config.influxdb.bucket,
            ) as health:

                st.success("✓ Verbunden mit Apple Health (InfluxDB)")

                # Letzte Körperdaten aus Apple Health
                body_metrics = health.get_latest_body_metrics()

                if body_metrics:
                    st.markdown("### Letzte Werte aus Apple Health")

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        if 'body_mass' in body_metrics:
                            val = body_metrics['body_mass']
                            st.metric(
                                "Gewicht",
                                f"{val['value']:.1f} kg",
                                help=f"Gemessen: {val['time'].strftime('%d.%m.%Y %H:%M')}"
                            )

                    with col2:
                        if 'body_fat_percentage' in body_metrics:
                            val = body_metrics['body_fat_percentage']
                            st.metric(
                                "Körperfett",
                                f"{val['value']:.1f}%",
                                help=f"Gemessen: {val['time'].strftime('%d.%m.%Y %H:%M')}"
                            )

                    with col3:
                        if 'lean_body_mass' in body_metrics:
                            val = body_metrics['lean_body_mass']
                            st.metric(
                                "Muskelmasse",
                                f"{val['value']:.1f} kg",
                                help=f"Gemessen: {val['time'].strftime('%d.%m.%Y %H:%M')}"
                            )

                    with col4:
                        if 'bmi' in body_metrics:
                            val = body_metrics['bmi']
                            st.metric(
                                "BMI",
                                f"{val['value']:.1f}",
                                help=f"Gemessen: {val['time'].strftime('%d.%m.%Y %H:%M')}"
                            )

                    # Import Button
                    st.markdown("---")
                    if st.button("📥 In lokale Datenbank importieren", type="primary"):
                        imported = False
                        for metric, data in body_metrics.items():
                            if metric == 'body_mass':
                                db.add_body_measurement(
                                    user_id=user.id,
                                    weight=data['value'],
                                    measured_at=data['time'],
                                    source='apple_health',
                                )
                                imported = True

                        if imported:
                            st.success("✅ Daten importiert!")
                        else:
                            st.info("Keine neuen Daten zum Importieren.")

                else:
                    st.info("Keine Körperdaten in Apple Health gefunden.")

        except Exception as e:
            st.error(f"Fehler bei Apple Health Verbindung: {e}")


if __name__ == "__main__":
    main()
