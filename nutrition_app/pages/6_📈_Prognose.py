"""
ML Prognose Seite
"""
import streamlit as st
from datetime import date, timedelta

st.set_page_config(page_title="Prognose", page_icon="📈", layout="wide")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
from services.database_service import DatabaseService
from services.ml_service import MLService


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
    if 'ml' not in st.session_state:
        st.session_state.ml = MLService()
    return True


def main():
    st.title("📈 Prognose & Optimierung")

    if not init_session():
        return

    db = st.session_state.db
    user = st.session_state.user
    ml = st.session_state.ml

    # Tabs
    tab1, tab2, tab3 = st.tabs([
        "🔮 Fortschrittsprognose",
        "🎯 Optimaler Plan",
        "📊 Was funktioniert?"
    ])

    # ==================== Prognose ====================
    with tab1:
        st.subheader("🔮 Deine Fortschrittsprognose")

        st.markdown("""
        Basierend auf deinen bisherigen Daten prognostiziert das System,
        wie sich dein Gewicht und Körperfett entwickeln werden.
        """)

        # Daten sammeln
        goal = db.get_active_goal(user.id)
        measurements = db.get_body_measurements(user.id, days=30)

        if not goal:
            st.warning("Bitte definiere zuerst ein Ziel unter **Ziele**.")
            return

        if len(measurements) < 2:
            st.info("""
            **Mehr Daten benötigt**

            Für eine gute Prognose brauchen wir mindestens 2 Körpermessungen.
            Trage regelmäßig dein Gewicht unter **Körperdaten** ein.
            """)
            return

        # User Data aufbereiten
        user_data = {
            'height_cm': user.height_cm,
            'age': (date.today() - user.birth_date).days // 365 if user.birth_date else 30,
            'gender': user.gender,
            'activity_level': user.activity_level,
            'goal': goal.goal_type.value,
            'weight': measurements[-1].weight_kg,
        }

        # Body History aufbereiten
        body_history = [
            {'weight': m.weight_kg, 'body_fat': m.body_fat_percent, 'date': m.measured_at}
            for m in measurements if m.weight_kg
        ]

        # Nutrition History (letzte 14 Tage)
        nutrition_history = []
        for i in range(14):
            d = date.today() - timedelta(days=i)
            daily = db.get_daily_nutrition_summary(user.id, d)
            if daily['calories'] > 0:
                nutrition_history.append({
                    'date': d,
                    'calories': daily['calories'],
                    'protein': daily['protein'],
                    'carbs': daily['carbs'],
                    'fat': daily['fat'],
                })

        # Activity History (von Apple Health wenn verfügbar)
        activity_history = []
        config = st.session_state.config
        if config.influxdb.token:
            try:
                from services.health_data_service import HealthDataService
                with HealthDataService(
                    url=config.influxdb.url,
                    token=config.influxdb.token,
                    bucket=config.influxdb.bucket,
                ) as health:
                    activity_history = health.get_activity_trend(days=14)
            except Exception:
                pass

        # Prognose-Zeitraum
        forecast_days = st.slider(
            "Prognose-Zeitraum",
            min_value=7,
            max_value=90,
            value=30,
            step=7,
            format="%d Tage"
        )

        if st.button("🔮 Prognose berechnen", type="primary"):
            with st.spinner("Berechne Prognose..."):
                prediction = ml.predict_progress(
                    user_data=user_data,
                    nutrition_history=nutrition_history,
                    activity_history=activity_history,
                    body_history=body_history,
                    target_days=forecast_days,
                )

                st.markdown("---")

                # Ergebnis anzeigen
                col1, col2, col3 = st.columns(3)

                current_weight = measurements[-1].weight_kg
                current_bf = measurements[-1].body_fat_percent

                with col1:
                    st.metric(
                        "Prognostiziertes Gewicht",
                        f"{prediction.predicted_weight:.1f} kg",
                        delta=f"{prediction.predicted_weight - current_weight:+.1f} kg",
                        help=f"Prognose für {prediction.target_date.strftime('%d.%m.%Y')}"
                    )

                with col2:
                    if prediction.predicted_body_fat and current_bf:
                        st.metric(
                            "Prognostiziertes Körperfett",
                            f"{prediction.predicted_body_fat:.1f}%",
                            delta=f"{prediction.predicted_body_fat - current_bf:+.1f}%",
                        )

                with col3:
                    st.metric(
                        "Konfidenz",
                        f"{prediction.confidence * 100:.0f}%",
                        help="Wie sicher ist die Prognose (mehr Daten = höhere Konfidenz)"
                    )

                # Zielvergleich
                if goal.target_weight_kg:
                    st.markdown("### 🎯 Zielvergleich")

                    target = goal.target_weight_kg
                    progress_to_goal = (current_weight - prediction.predicted_weight) / (current_weight - target) * 100 if current_weight != target else 100

                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Zielgewicht:** {target:.1f} kg")
                        st.write(f"**Aktuell:** {current_weight:.1f} kg")
                        st.write(f"**Prognose ({forecast_days} Tage):** {prediction.predicted_weight:.1f} kg")

                    with col2:
                        if progress_to_goal > 0:
                            st.progress(min(progress_to_goal / 100, 1.0),
                                        text=f"{progress_to_goal:.0f}% zum Ziel in {forecast_days} Tagen")
                        else:
                            st.warning("Du bewegst dich vom Ziel weg.")

                # Empfehlungen
                if prediction.recommendations:
                    st.markdown("### 💡 Empfehlungen")
                    for rec in prediction.recommendations:
                        st.info(rec)

    # ==================== Optimaler Plan ====================
    with tab2:
        st.subheader("🎯 Dein optimaler Plan")

        st.markdown("""
        Das System berechnet den optimalen Ernährungs- und Trainingsplan
        um dein Ziel zu erreichen.
        """)

        if not goal:
            st.warning("Bitte definiere zuerst ein Ziel unter **Ziele**.")
            return

        latest = db.get_latest_measurement(user.id)
        if not latest:
            st.warning("Bitte trage zuerst eine Körpermessung ein.")
            return

        # User Data
        user_data = {
            'height_cm': user.height_cm,
            'age': (date.today() - user.birth_date).days // 365 if user.birth_date else 30,
            'gender': user.gender,
            'activity_level': user.activity_level,
        }

        goal_data = {
            'target_weight': goal.target_weight_kg,
            'target_body_fat': goal.target_body_fat_percent,
            'target_date': goal.target_date,
        }

        current_body = {
            'weight': latest.weight_kg,
            'body_fat': latest.body_fat_percent,
        }

        optimal = ml.calculate_optimal_plan(user_data, goal_data, current_body)

        # Ergebnis anzeigen
        st.markdown("### 📋 Empfohlener Plan")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Ernährung (täglich)")

            st.metric("Kalorien", f"{optimal.daily_calories} kcal")

            cols = st.columns(3)
            cols[0].metric("Protein", f"{optimal.protein_g}g")
            cols[1].metric("Carbs", f"{optimal.carbs_g}g")
            cols[2].metric("Fett", f"{optimal.fat_g}g")

            # Makro-Verteilung visualisieren
            total_cal = optimal.protein_g * 4 + optimal.carbs_g * 4 + optimal.fat_g * 9

            st.markdown("**Makro-Verteilung:**")
            st.write(f"- Protein: {(optimal.protein_g * 4 / total_cal * 100):.0f}%")
            st.write(f"- Kohlenhydrate: {(optimal.carbs_g * 4 / total_cal * 100):.0f}%")
            st.write(f"- Fett: {(optimal.fat_g * 9 / total_cal * 100):.0f}%")

        with col2:
            st.markdown("#### Training")

            st.metric("Trainingsminuten/Woche", f"{optimal.exercise_minutes_per_week} min")

            # Beispiel-Aufteilung
            st.markdown("**Beispiel-Aufteilung:**")
            if goal.goal_type.value == "muskelaufbau":
                st.write("- 4x Krafttraining (45 min)")
                st.write("- 1x Cardio (30 min)")
            elif goal.goal_type.value == "abnehmen":
                st.write("- 3x Krafttraining (40 min)")
                st.write("- 2x Cardio (40 min)")
            else:
                st.write("- 3x Krafttraining (40 min)")
                st.write("- 1-2x Cardio (30 min)")

        st.markdown("---")

        # Prognose mit diesem Plan
        st.markdown("### 📈 Erwarteter Fortschritt")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Erwartete wöchentliche Änderung",
                f"{optimal.expected_weight_loss_per_week:+.2f} kg"
            )

        with col2:
            st.metric(
                "Geschätzte Zeit bis Ziel",
                f"{optimal.expected_weeks_to_goal} Wochen"
            )

        with col3:
            st.metric(
                "Plan-Konfidenz",
                f"{optimal.confidence * 100:.0f}%"
            )

        # Vergleich mit aktuellem Plan
        st.markdown("---")
        st.markdown("### 🔄 Vergleich mit aktuellem Ziel")

        if goal.daily_calorie_target:
            diff = optimal.daily_calories - goal.daily_calorie_target
            if abs(diff) > 100:
                if diff > 0:
                    st.info(f"💡 Der optimierte Plan empfiehlt **{diff}** kcal mehr pro Tag.")
                else:
                    st.info(f"💡 Der optimierte Plan empfiehlt **{abs(diff)}** kcal weniger pro Tag.")
            else:
                st.success("✅ Dein aktueller Plan ist bereits gut optimiert!")

        # Button zum Übernehmen
        if st.button("✅ Diesen Plan als neues Ziel übernehmen"):
            db.set_user_goal(
                user_id=user.id,
                goal_type=goal.goal_type,
                target_weight=goal.target_weight_kg,
                target_body_fat=goal.target_body_fat_percent,
                target_date=goal.target_date,
                daily_calories=optimal.daily_calories,
                protein_g=optimal.protein_g,
                carbs_g=optimal.carbs_g,
                fat_g=optimal.fat_g,
            )
            st.success("✅ Neuer Plan gespeichert!")
            st.rerun()

    # ==================== Was funktioniert? ====================
    with tab3:
        st.subheader("📊 Was funktioniert für dich?")

        st.markdown("""
        Das System analysiert deine Daten um herauszufinden,
        welche Ernährung und welches Training die besten Ergebnisse für dich bringt.
        """)

        # Daten laden
        body_history = [
            {'weight': m.weight_kg, 'body_fat': m.body_fat_percent, 'date': m.measured_at.isoformat()}
            for m in db.get_body_measurements(user.id, days=30) if m.weight_kg
        ]

        nutrition_history = []
        for i in range(30):
            d = date.today() - timedelta(days=i)
            daily = db.get_daily_nutrition_summary(user.id, d)
            if daily['calories'] > 0:
                nutrition_history.append({
                    'date': d.isoformat(),
                    'calories': daily['calories'],
                    'protein': daily['protein'],
                })

        # TODO: Feedback History aus DB laden
        feedback_history = []  # Placeholder

        if len(body_history) < 7:
            st.info("""
            **Mehr Daten benötigt**

            Für eine aussagekräftige Analyse benötigen wir mindestens 7 Tage Daten.

            Tracke weiterhin:
            - Dein Gewicht (täglich oder mehrmals pro Woche)
            - Deine Mahlzeiten
            - Dein tägliches Wohlbefinden (unter KI-Empfehlungen)
            """)
            return

        # Analyse durchführen
        insights = ml.analyze_what_works(body_history, nutrition_history, feedback_history)

        if insights.get('status') == 'need_more_data':
            st.warning(insights.get('message'))
            return

        # Gewichtstrend anzeigen
        if 'weight_trend' in insights:
            trend = insights['weight_trend']
            st.markdown("### ⚖️ Gewichtstrend")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Gesamtänderung", f"{trend['total_change']:+.2f} kg")
            with col2:
                st.metric("Richtung", trend['direction'].title())
            with col3:
                st.metric("Ø täglich", f"{trend['avg_daily_change']:+.3f} kg")

        # Patterns
        if insights.get('patterns'):
            st.markdown("### 🔍 Erkannte Muster")
            for pattern in insights['patterns']:
                st.info(f"**{pattern['type']}:** {pattern['description']}")

        # Hinweis für mehr Daten
        st.markdown("---")
        st.info("""
        💡 **Tipp:** Je mehr Daten du trackst, desto bessere Erkenntnisse kann das System gewinnen.

        Besonders wertvoll:
        - Tägliches Feedback zu Energie und Wohlbefinden
        - Konsistentes Mahlzeiten-Tracking
        - Regelmäßige Körpermessungen
        """)


if __name__ == "__main__":
    main()
