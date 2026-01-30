"""
KI-Empfehlungen Seite
"""
import streamlit as st
from datetime import date, timedelta

st.set_page_config(page_title="KI-Empfehlungen", page_icon="🤖", layout="wide")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
from services.database_service import DatabaseService
from services.llm_service import LLMService
from models.database import PreferenceType


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


def get_llm_service():
    """Erstellt LLM Service basierend auf Konfiguration"""
    config = st.session_state.config
    return LLMService(
        provider=config.llm.provider,
        anthropic_api_key=config.llm.anthropic_api_key,
        openai_api_key=config.llm.openai_api_key,
    )


def get_user_context():
    """Sammelt Benutzerkontext für LLM"""
    db = st.session_state.db
    user = st.session_state.user

    goal = db.get_active_goal(user.id)
    latest_measurement = db.get_latest_measurement(user.id)

    context = {
        "name": user.name,
        "alter": None,
        "geschlecht": user.gender,
        "größe_cm": user.height_cm,
        "aktivitätslevel": user.activity_level,
    }

    if user.birth_date:
        context["alter"] = (date.today() - user.birth_date).days // 365

    if latest_measurement:
        context["aktuelles_gewicht_kg"] = latest_measurement.weight_kg
        context["körperfett_prozent"] = latest_measurement.body_fat_percent
        context["muskelmasse_kg"] = latest_measurement.muscle_mass_kg

    if goal:
        context["ziel"] = goal.goal_type.value
        context["zielgewicht_kg"] = goal.target_weight_kg
        context["ziel_körperfett_prozent"] = goal.target_body_fat_percent
        context["kalorienziel"] = goal.daily_calorie_target
        context["protein_ziel_g"] = goal.protein_target_g
        context["zieldatum"] = goal.target_date.isoformat() if goal.target_date else None

    return context


def get_user_preferences():
    """Sammelt Vorlieben für LLM"""
    db = st.session_state.db
    user = st.session_state.user

    all_prefs = db.get_user_preferences(user.id)
    restrictions = db.get_dietary_restrictions(user.id)

    return {
        "favorites": [p.category or p.ingredient for p in all_prefs
                      if p.preference_type == PreferenceType.LIEBLING],
        "dislikes": [p.category or p.ingredient for p in all_prefs
                     if p.preference_type == PreferenceType.ABNEIGUNG],
        "allergies": [p.ingredient for p in all_prefs
                      if p.preference_type == PreferenceType.ALLERGIE],
        "diet_type": restrictions[0].restriction_type if restrictions else "keine",
    }


def get_activity_data():
    """Holt Aktivitätsdaten aus Apple Health"""
    config = st.session_state.config

    if not config.influxdb.token:
        return {"hinweis": "Apple Health nicht konfiguriert"}

    try:
        from services.health_data_service import HealthDataService

        with HealthDataService(
            url=config.influxdb.url,
            token=config.influxdb.token,
            bucket=config.influxdb.bucket,
        ) as health:
            today = date.today()
            activity = health.get_daily_activity(today)
            energy = health.get_total_daily_energy(today)
            workout = health.get_workout_summary(days=7)

            return {
                "schritte_heute": activity.get('steps', 0),
                "aktive_kalorien_heute": energy.get('active_calories', 0),
                "gesamtverbrauch_heute": energy.get('total_calories', 0),
                "trainingsminuten_heute": activity.get('exercise_minutes', 0),
                "workouts_letzte_woche": workout.get('total_workouts', 0),
                "trainingsminuten_letzte_woche": workout.get('total_duration_min', 0),
            }
    except Exception as e:
        return {"fehler": str(e)}


def main():
    st.title("🤖 KI-Empfehlungen")

    if not init_session():
        return

    config = st.session_state.config
    db = st.session_state.db
    user = st.session_state.user

    # Prüfen ob LLM konfiguriert
    if not (config.llm.anthropic_api_key or config.llm.openai_api_key):
        st.error("""
        **KI nicht konfiguriert**

        Bitte konfiguriere einen API-Key in den Umgebungsvariablen:
        - `ANTHROPIC_API_KEY` für Claude (empfohlen)
        - `OPENAI_API_KEY` für GPT-4

        Du kannst auch beide konfigurieren und unten wählen.
        """)

        st.markdown("---")
        st.markdown("### API-Keys einrichten")
        st.markdown("""
        1. **Claude (Anthropic)**:
           - Gehe zu [console.anthropic.com](https://console.anthropic.com)
           - Erstelle einen API-Key
           - Setze `ANTHROPIC_API_KEY` in deiner `.env` Datei

        2. **OpenAI**:
           - Gehe zu [platform.openai.com](https://platform.openai.com)
           - Erstelle einen API-Key
           - Setze `OPENAI_API_KEY` in deiner `.env` Datei
        """)
        return

    # Provider Auswahl
    col1, col2 = st.columns([1, 3])

    with col1:
        available_providers = []
        if config.llm.anthropic_api_key:
            available_providers.append("claude")
        if config.llm.openai_api_key:
            available_providers.append("openai")

        provider = st.selectbox(
            "KI-Anbieter",
            options=available_providers,
            format_func=lambda x: "Claude (Anthropic)" if x == "claude" else "GPT-4 (OpenAI)",
        )

    with col2:
        st.info(f"Verbunden mit: **{provider.upper()}**")

    st.divider()

    # Tabs für verschiedene Empfehlungen
    tab1, tab2, tab3, tab4 = st.tabs([
        "🍽️ Mahlzeitenplan",
        "📊 Fortschrittsanalyse",
        "💡 Mahlzeiten-Ideen",
        "📅 Wochenplan (Lernphase)"
    ])

    llm = LLMService(
        provider=provider,
        anthropic_api_key=config.llm.anthropic_api_key,
        openai_api_key=config.llm.openai_api_key,
    )

    # ==================== Mahlzeitenplan ====================
    with tab1:
        st.subheader("🍽️ Personalisierter Mahlzeitenplan für heute")

        st.markdown("""
        Die KI erstellt einen Mahlzeitenplan basierend auf:
        - Deinem Ziel und Kalorienbedarf
        - Deinen Vorlieben und Abneigungen
        - Deiner heutigen Aktivität
        """)

        if st.button("🤖 Mahlzeitenplan generieren", type="primary", key="gen_meal"):
            with st.spinner("Generiere personalisierten Plan..."):
                user_context = get_user_context()
                preferences = get_user_preferences()
                activity = get_activity_data()

                result = llm.generate_meal_plan(user_context, preferences, activity)

                if result:
                    st.markdown("---")
                    st.markdown(result)

                    # Speichern
                    db.save_ai_recommendation(
                        user_id=user.id,
                        recommendation_type="meal_plan",
                        content=result,
                        context_data={
                            "user_context": user_context,
                            "preferences": preferences,
                            "activity": activity,
                        }
                    )
                    st.success("✅ Empfehlung gespeichert")
                else:
                    st.error("Konnte keinen Plan generieren. Bitte prüfe deine API-Konfiguration.")

    # ==================== Fortschrittsanalyse ====================
    with tab2:
        st.subheader("📊 Analyse deines Fortschritts")

        st.markdown("""
        Die KI analysiert deine Daten der letzten Woche und gibt dir
        Feedback zu deinem Fortschritt sowie konkrete Empfehlungen.
        """)

        if st.button("🤖 Fortschritt analysieren", type="primary", key="analyze"):
            with st.spinner("Analysiere deine Daten..."):
                # Körpermessungen der letzten Woche
                measurements = db.get_body_measurements(user.id, days=7)
                body_data = []
                for m in measurements:
                    body_data.append({
                        "datum": m.measured_at.strftime("%d.%m.%Y"),
                        "gewicht_kg": m.weight_kg,
                        "körperfett_%": m.body_fat_percent,
                    })

                # Ernährungsdaten
                nutrition_data = []
                for i in range(7):
                    d = date.today() - timedelta(days=i)
                    daily = db.get_daily_nutrition_summary(user.id, d)
                    if daily['calories'] > 0:
                        nutrition_data.append({
                            "datum": d.strftime("%d.%m.%Y"),
                            "kalorien": daily['calories'],
                            "protein_g": daily['protein'],
                        })

                # Aktivitätsdaten
                activity = get_activity_data()

                # Ziel
                goal = db.get_active_goal(user.id)
                goal_data = {
                    "ziel": goal.goal_type.value if goal else "nicht definiert",
                    "zielgewicht_kg": goal.target_weight_kg if goal else None,
                    "kalorienziel": goal.daily_calorie_target if goal else None,
                }

                result = llm.analyze_progress(body_data, nutrition_data, activity, goal_data)

                if result:
                    st.markdown("---")
                    st.markdown(result)

                    db.save_ai_recommendation(
                        user_id=user.id,
                        recommendation_type="progress_analysis",
                        content=result,
                    )
                else:
                    st.error("Konnte Analyse nicht generieren.")

    # ==================== Mahlzeiten-Ideen ====================
    with tab3:
        st.subheader("💡 Mahlzeiten-Ideen")

        st.markdown("Lass dir Ideen für eine bestimmte Mahlzeit geben.")

        col1, col2 = st.columns(2)

        with col1:
            meal_type = st.selectbox(
                "Mahlzeit",
                options=["Frühstück", "Mittagessen", "Abendessen", "Snack"],
            )

        with col2:
            target_cal = st.number_input(
                "Ziel-Kalorien",
                min_value=100,
                max_value=1500,
                value=500,
                step=50,
            )

        available = st.text_area(
            "Verfügbare Zutaten (optional)",
            placeholder="z.B. Eier, Spinat, Tomaten, Feta...",
            height=100,
        )

        if st.button("🤖 Ideen generieren", type="primary", key="gen_ideas"):
            with st.spinner("Generiere Ideen..."):
                preferences = get_user_preferences()
                ingredients = [i.strip() for i in available.split(",") if i.strip()] if available else []

                result = llm.get_meal_suggestions(
                    meal_type=meal_type.lower(),
                    available_ingredients=ingredients,
                    target_calories=target_cal,
                    preferences=preferences,
                )

                if result:
                    st.markdown("---")
                    st.markdown(result)
                else:
                    st.error("Konnte keine Ideen generieren.")

    # ==================== Wochenplan (Lernphase) ====================
    with tab4:
        st.subheader("📅 Wochenplan für die Lernphase")

        st.markdown("""
        In der Lernphase variiert die KI deine Mahlzeiten systematisch,
        um herauszufinden, welche Lebensmittel dir am besten bekommen.

        **So funktioniert's:**
        1. Wähle den Variations-Level
        2. Generiere einen Wochenplan
        3. Folge dem Plan und gib täglich Feedback
        4. Nach einigen Wochen lernt das System deine optimale Ernährung
        """)

        variety = st.radio(
            "Variations-Level",
            options=["low", "medium", "high"],
            format_func=lambda x: {
                "low": "🔹 Niedrig - Ähnliche Mahlzeiten, kleine Variationen",
                "medium": "🔸 Mittel - Moderate Abwechslung",
                "high": "🔶 Hoch - Maximale Variation zum Testen",
            }[x],
            index=1,
            horizontal=True,
        )

        if st.button("🤖 Wochenplan generieren", type="primary", key="gen_week"):
            with st.spinner("Generiere Wochenplan..."):
                user_context = get_user_context()
                preferences = get_user_preferences()

                result = llm.generate_weekly_plan(user_context, preferences, variety)

                if result:
                    st.markdown("---")
                    st.markdown(result)

                    db.save_ai_recommendation(
                        user_id=user.id,
                        recommendation_type="weekly_plan",
                        content=result,
                        context_data={"variety_level": variety}
                    )
                else:
                    st.error("Konnte Wochenplan nicht generieren.")

        # Feedback-Bereich
        st.markdown("---")
        st.markdown("### 📝 Tägliches Feedback")
        st.caption("Gib Feedback wie du dich heute fühlst - das hilft dem System zu lernen.")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            energy = st.slider("Energie-Level", 1, 5, 3, key="fb_energy")
        with col2:
            satiety = st.slider("Sättigung", 1, 5, 3, key="fb_satiety")
        with col3:
            wellbeing = st.slider("Wohlbefinden", 1, 5, 3, key="fb_wellbeing")
        with col4:
            digestion = st.slider("Verdauung", 1, 5, 3, key="fb_digestion")

        feedback_notes = st.text_input("Notizen (optional)", placeholder="z.B. Müde nach dem Mittagessen...")

        if st.button("💾 Feedback speichern", key="save_feedback"):
            db.add_meal_feedback(
                user_id=user.id,
                energy_level=energy,
                satiety_level=satiety,
                wellbeing=wellbeing,
                digestion=digestion,
                notes=feedback_notes if feedback_notes else None,
            )
            st.success("✅ Feedback gespeichert!")

    # ==================== Letzte Empfehlungen ====================
    st.divider()
    st.subheader("📜 Letzte Empfehlungen")

    recommendations = db.get_recent_recommendations(user.id, days=7)

    if recommendations:
        for rec in recommendations[:5]:
            with st.expander(f"{rec.recommendation_date} - {rec.recommendation_type}"):
                st.markdown(rec.content)
    else:
        st.caption("Noch keine Empfehlungen generiert.")


if __name__ == "__main__":
    main()
