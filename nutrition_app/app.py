"""
Ernährungs- & Fitness-Tracker - Hauptanwendung
"""
import streamlit as st
from datetime import date

# Konfiguration muss als erstes kommen
st.set_page_config(
    page_title="Ernährungs- & Fitness-Tracker",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

from config import load_config
from services.database_service import DatabaseService

# ==================== Session State Initialisierung ====================


def init_session_state():
    """Initialisiert den Session State"""
    if 'config' not in st.session_state:
        st.session_state.config = load_config()

    if 'db' not in st.session_state:
        config = st.session_state.config
        try:
            st.session_state.db = DatabaseService(config.database.connection_string)
            st.session_state.db_connected = True
        except Exception as e:
            st.session_state.db = None
            st.session_state.db_connected = False
            st.session_state.db_error = str(e)

    if 'user' not in st.session_state and st.session_state.get('db'):
        st.session_state.user = st.session_state.db.get_or_create_user()

    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = date.today()


# ==================== Sidebar ====================


def render_sidebar():
    """Rendert die Sidebar mit Navigation und Status"""
    with st.sidebar:
        st.title("🥗 Nutrition Tracker")
        st.divider()

        # Datums-Auswahl
        st.subheader("📅 Datum")
        selected = st.date_input(
            "Ausgewähltes Datum",
            value=st.session_state.selected_date,
            max_value=date.today(),
            label_visibility="collapsed",
        )
        st.session_state.selected_date = selected

        st.divider()

        # Verbindungsstatus
        st.subheader("📊 Status")

        # Datenbank
        if st.session_state.get('db_connected'):
            st.success("✓ Datenbank verbunden")
        else:
            st.error("✗ Datenbank nicht verbunden")
            if st.session_state.get('db_error'):
                st.caption(st.session_state.db_error)

        # InfluxDB (Apple Health)
        config = st.session_state.config
        if config.influxdb.token:
            st.success("✓ Apple Health konfiguriert")
        else:
            st.warning("○ Apple Health nicht konfiguriert")

        # LLM
        if config.llm.anthropic_api_key or config.llm.openai_api_key:
            provider = "Claude" if config.llm.anthropic_api_key else "OpenAI"
            st.success(f"✓ KI ({provider}) konfiguriert")
        else:
            st.warning("○ KI nicht konfiguriert")

        st.divider()

        # Quick Stats (wenn Datenbank verbunden)
        if st.session_state.get('db') and st.session_state.get('user'):
            st.subheader("📈 Heute")
            try:
                daily = st.session_state.db.get_daily_nutrition_summary(
                    st.session_state.user.id,
                    st.session_state.selected_date
                )
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Kalorien", f"{daily['calories']:.0f}")
                    st.metric("Protein", f"{daily['protein']:.0f}g")
                with col2:
                    st.metric("Carbs", f"{daily['carbs']:.0f}g")
                    st.metric("Fett", f"{daily['fat']:.0f}g")
            except Exception:
                st.caption("Keine Daten für heute")


# ==================== Hauptseite ====================


def main():
    """Hauptseite mit Übersicht"""
    init_session_state()
    render_sidebar()

    st.title("🏠 Dashboard")

    if not st.session_state.get('db_connected'):
        st.error("""
        **Datenbank nicht verbunden**

        Bitte konfiguriere die PostgreSQL-Verbindung in den Umgebungsvariablen:
        - `POSTGRES_HOST`
        - `POSTGRES_PORT`
        - `POSTGRES_DB`
        - `POSTGRES_USER`
        - `POSTGRES_PASSWORD`
        """)
        return

    # Willkommen
    user = st.session_state.get('user')
    if user:
        st.subheader(f"Willkommen, {user.name}!")

    # Hauptbereich mit Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Übersicht", "🎯 Ziele", "💡 KI-Empfehlungen"])

    with tab1:
        render_overview()

    with tab2:
        render_goals_summary()

    with tab3:
        render_ai_recommendations()


def render_overview():
    """Rendert die Tagesübersicht"""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🍽️ Heutige Ernährung")

        db = st.session_state.db
        user = st.session_state.user
        target_date = st.session_state.selected_date

        try:
            daily = db.get_daily_nutrition_summary(user.id, target_date)
            goal = db.get_active_goal(user.id)

            # Fortschrittsbalken
            if goal and goal.daily_calorie_target:
                progress = daily['calories'] / goal.daily_calorie_target
                st.progress(min(progress, 1.0), text=f"Kalorien: {daily['calories']:.0f} / {goal.daily_calorie_target}")
            else:
                st.info(f"**{daily['calories']:.0f}** kcal gegessen")

            # Makros
            cols = st.columns(3)
            with cols[0]:
                st.metric("Protein", f"{daily['protein']:.1f}g",
                          delta=f"Ziel: {goal.protein_target_g}g" if goal and goal.protein_target_g else None)
            with cols[1]:
                st.metric("Carbs", f"{daily['carbs']:.1f}g",
                          delta=f"Ziel: {goal.carbs_target_g}g" if goal and goal.carbs_target_g else None)
            with cols[2]:
                st.metric("Fett", f"{daily['fat']:.1f}g",
                          delta=f"Ziel: {goal.fat_target_g}g" if goal and goal.fat_target_g else None)

            # Mahlzeiten des Tages
            st.markdown("#### Mahlzeiten")
            meals = db.get_meals_for_date(user.id, target_date)
            if meals:
                for meal in meals:
                    with st.expander(f"{meal.meal_type.value.title()} - {meal.total_calories:.0f} kcal"):
                        st.write(f"Protein: {meal.total_protein:.1f}g | "
                                 f"Carbs: {meal.total_carbs:.1f}g | "
                                 f"Fett: {meal.total_fat:.1f}g")
            else:
                st.caption("Noch keine Mahlzeiten eingetragen")

        except Exception as e:
            st.error(f"Fehler beim Laden der Daten: {e}")

    with col2:
        st.markdown("### 🏃 Aktivität")

        config = st.session_state.config
        if config.influxdb.token:
            try:
                from services.health_data_service import HealthDataService
                with HealthDataService(
                    url=config.influxdb.url,
                    token=config.influxdb.token,
                    bucket=config.influxdb.bucket,
                ) as health:
                    activity = health.get_daily_activity(st.session_state.selected_date)
                    energy = health.get_total_daily_energy(st.session_state.selected_date)

                    cols = st.columns(2)
                    with cols[0]:
                        st.metric("Schritte", f"{activity.get('steps', 0):,.0f}")
                        st.metric("Aktive Kalorien", f"{energy.get('active_calories', 0):,.0f}")
                    with cols[1]:
                        st.metric("Training (min)", f"{activity.get('exercise_minutes', 0):.0f}")
                        st.metric("Gesamtverbrauch", f"{energy.get('total_calories', 0):,.0f}")

            except Exception as e:
                st.warning(f"Apple Health Daten nicht verfügbar: {e}")
        else:
            st.info("Verbinde Apple Health für Aktivitätsdaten")
            st.caption("Konfiguriere INFLUXDB_URL und INFLUXDB_TOKEN")


def render_goals_summary():
    """Zeigt Ziel-Zusammenfassung"""
    db = st.session_state.db
    user = st.session_state.user

    goal = db.get_active_goal(user.id)

    if goal:
        st.success(f"**Aktuelles Ziel:** {goal.goal_type.value.title()}")

        cols = st.columns(4)
        with cols[0]:
            if goal.target_weight_kg:
                st.metric("Zielgewicht", f"{goal.target_weight_kg} kg")
        with cols[1]:
            if goal.target_body_fat_percent:
                st.metric("Ziel Körperfett", f"{goal.target_body_fat_percent}%")
        with cols[2]:
            if goal.daily_calorie_target:
                st.metric("Kalorienziel", f"{goal.daily_calorie_target} kcal")
        with cols[3]:
            if goal.target_date:
                days_left = (goal.target_date - date.today()).days
                st.metric("Tage bis Ziel", days_left)

        # Fortschritt
        latest = db.get_latest_measurement(user.id)
        if latest and goal.target_weight_kg:
            st.markdown("#### Fortschritt")

            # Berechne Start und aktuellen Stand
            # Für echten Start müssten wir die erste Messung nach Zielerstellung nehmen
            current = latest.weight_kg
            target = goal.target_weight_kg

            if current and target:
                diff = current - target
                st.write(f"Aktuell: **{current:.1f} kg** → Ziel: **{target:.1f} kg** "
                         f"(Differenz: {diff:+.1f} kg)")

    else:
        st.info("Noch kein Ziel definiert")
        st.write("Gehe zu **Ziele** in der Navigation um dein erstes Ziel zu setzen.")


def render_ai_recommendations():
    """Zeigt KI-Empfehlungen"""
    config = st.session_state.config

    if not (config.llm.anthropic_api_key or config.llm.openai_api_key):
        st.info("""
        **KI-Empfehlungen aktivieren**

        Konfiguriere einen API-Key in den Umgebungsvariablen:
        - `ANTHROPIC_API_KEY` für Claude
        - `OPENAI_API_KEY` für GPT-4

        Die KI kann dann:
        - Personalisierte Mahlzeitenpläne erstellen
        - Deinen Fortschritt analysieren
        - Tipps basierend auf deinen Daten geben
        """)
        return

    db = st.session_state.db
    user = st.session_state.user

    # Letzte Empfehlungen anzeigen
    recommendations = db.get_recent_recommendations(user.id, days=7)

    if recommendations:
        st.markdown("### Letzte Empfehlungen")
        for rec in recommendations[:3]:
            with st.expander(f"{rec.recommendation_date} - {rec.recommendation_type}"):
                st.write(rec.content)
    else:
        st.caption("Noch keine Empfehlungen generiert")

    # Button für neue Empfehlung
    if st.button("🤖 Neue Empfehlung generieren", type="primary"):
        with st.spinner("Generiere Empfehlung..."):
            from services.llm_service import LLMService

            llm = LLMService(
                provider=config.llm.provider,
                anthropic_api_key=config.llm.anthropic_api_key,
                openai_api_key=config.llm.openai_api_key,
            )

            goal = db.get_active_goal(user.id)
            preferences = db.get_user_preferences(user.id)

            user_context = {
                "name": user.name,
                "goal": goal.goal_type.value if goal else "nicht definiert",
                "target_calories": goal.daily_calorie_target if goal else 2000,
            }

            pref_dict = {
                "favorites": [p.category or p.ingredient for p in preferences
                              if p.preference_type.value == "liebling"],
                "dislikes": [p.category or p.ingredient for p in preferences
                             if p.preference_type.value == "abneigung"],
                "allergies": [p.category or p.ingredient for p in preferences
                              if p.preference_type.value == "allergie"],
            }

            activity_data = {"info": "Keine Aktivitätsdaten verfügbar"}
            if config.influxdb.token:
                try:
                    from services.health_data_service import HealthDataService
                    with HealthDataService(
                        url=config.influxdb.url,
                        token=config.influxdb.token,
                        bucket=config.influxdb.bucket,
                    ) as health:
                        activity_data = health.get_daily_activity(date.today())
                except Exception:
                    pass

            result = llm.generate_meal_plan(user_context, pref_dict, activity_data)

            if result:
                st.markdown("### 📋 Dein Mahlzeitenplan")
                st.write(result)

                # Speichern
                db.save_ai_recommendation(
                    user_id=user.id,
                    recommendation_type="meal_plan",
                    content=result,
                    context_data={"user_context": user_context, "activity": activity_data}
                )
            else:
                st.error("Konnte keine Empfehlung generieren. Prüfe die API-Konfiguration.")


if __name__ == "__main__":
    main()
