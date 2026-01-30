"""
Ziel-Setup Seite
"""
import streamlit as st
from datetime import date, timedelta

st.set_page_config(page_title="Ziele", page_icon="🎯", layout="wide")

# Imports nach page_config
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
from services.database_service import DatabaseService
from models.database import TrainingGoal


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


def calculate_calories(weight: float, height: float, age: int, gender: str,
                       activity_level: str, goal_type: str) -> dict:
    """
    Berechnet Kalorienbedarf und Makros basierend auf Mifflin-St Jeor

    Returns:
        Dict mit daily_calories, protein_g, carbs_g, fat_g
    """
    # Grundumsatz (BMR) nach Mifflin-St Jeor
    if gender == "männlich":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161

    # Aktivitätsfaktor
    activity_factors = {
        "sedentär": 1.2,       # Wenig/keine Bewegung
        "leicht": 1.375,        # Leichte Aktivität 1-3x/Woche
        "moderat": 1.55,        # Moderate Aktivität 3-5x/Woche
        "aktiv": 1.725,         # Starke Aktivität 6-7x/Woche
        "sehr_aktiv": 1.9,      # Sehr intensive Aktivität
    }
    factor = activity_factors.get(activity_level, 1.55)
    tdee = bmr * factor

    # Anpassung basierend auf Ziel
    if goal_type == TrainingGoal.ABNEHMEN.value:
        daily_cal = tdee - 500  # 500 kcal Defizit
        protein_ratio = 0.30   # Höherer Proteinanteil beim Abnehmen
        carb_ratio = 0.40
        fat_ratio = 0.30
    elif goal_type == TrainingGoal.MUSKELAUFBAU.value:
        daily_cal = tdee + 300  # 300 kcal Überschuss
        protein_ratio = 0.30   # Hoher Proteinanteil
        carb_ratio = 0.45
        fat_ratio = 0.25
    elif goal_type == TrainingGoal.AUSDAUER.value:
        daily_cal = tdee + 200  # Leichter Überschuss
        protein_ratio = 0.20
        carb_ratio = 0.55      # Mehr Kohlenhydrate für Ausdauer
        fat_ratio = 0.25
    else:  # Erhalt
        daily_cal = tdee
        protein_ratio = 0.25
        carb_ratio = 0.45
        fat_ratio = 0.30

    # Makros berechnen (4 kcal/g Protein & Carbs, 9 kcal/g Fett)
    protein_g = (daily_cal * protein_ratio) / 4
    carbs_g = (daily_cal * carb_ratio) / 4
    fat_g = (daily_cal * fat_ratio) / 9

    return {
        "daily_calories": round(daily_cal),
        "protein_g": round(protein_g),
        "carbs_g": round(carbs_g),
        "fat_g": round(fat_g),
        "bmr": round(bmr),
        "tdee": round(tdee),
    }


def main():
    st.title("🎯 Ziele einrichten")

    if not init_session():
        return

    db = st.session_state.db
    user = st.session_state.user

    # Aktuelles Ziel anzeigen
    current_goal = db.get_active_goal(user.id)
    if current_goal:
        st.success(f"**Aktuelles Ziel:** {current_goal.goal_type.value.title()}")
        with st.expander("Details anzeigen"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Kalorienziel", f"{current_goal.daily_calorie_target or '-'} kcal")
            with col2:
                st.metric("Protein", f"{current_goal.protein_target_g or '-'}g")
            with col3:
                st.metric("Zielgewicht", f"{current_goal.target_weight_kg or '-'} kg")
            with col4:
                st.metric("Ziel-Körperfett", f"{current_goal.target_body_fat_percent or '-'}%")

    st.divider()

    # Neues Ziel setzen
    st.subheader("Neues Ziel setzen")

    # Zwei Spalten für Profil und Ziel
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 👤 Dein Profil")

        # Profildaten laden oder defaults
        name = st.text_input("Name", value=user.name or "")

        gender = st.selectbox(
            "Geschlecht",
            options=["männlich", "weiblich", "divers"],
            index=["männlich", "weiblich", "divers"].index(user.gender) if user.gender else 0
        )

        birth_date = st.date_input(
            "Geburtsdatum",
            value=user.birth_date or date(1990, 1, 1),
            min_value=date(1920, 1, 1),
            max_value=date.today(),
        )
        age = (date.today() - birth_date).days // 365

        height = st.number_input(
            "Körpergröße (cm)",
            min_value=100,
            max_value=250,
            value=int(user.height_cm) if user.height_cm else 175,
        )

        # Aktuelles Gewicht aus letzter Messung
        latest_measurement = db.get_latest_measurement(user.id)
        current_weight = latest_measurement.weight_kg if latest_measurement else 75.0

        weight = st.number_input(
            "Aktuelles Gewicht (kg)",
            min_value=30.0,
            max_value=300.0,
            value=float(current_weight),
            step=0.1,
        )

        activity = st.selectbox(
            "Aktivitätslevel",
            options=["sedentär", "leicht", "moderat", "aktiv", "sehr_aktiv"],
            index=2,
            format_func=lambda x: {
                "sedentär": "Sedentär (kaum Bewegung)",
                "leicht": "Leicht aktiv (1-3x Sport/Woche)",
                "moderat": "Moderat aktiv (3-5x Sport/Woche)",
                "aktiv": "Aktiv (6-7x Sport/Woche)",
                "sehr_aktiv": "Sehr aktiv (täglich intensiv)",
            }[x]
        )

    with col2:
        st.markdown("### 🎯 Dein Ziel")

        goal_type = st.selectbox(
            "Was ist dein Hauptziel?",
            options=[g.value for g in TrainingGoal if g != TrainingGoal.CUSTOM],
            format_func=lambda x: {
                "abnehmen": "🏃 Abnehmen (Fett verlieren)",
                "muskelaufbau": "💪 Muskelaufbau",
                "erhalt": "⚖️ Gewicht halten",
                "ausdauer": "🚴 Ausdauer verbessern",
            }.get(x, x.title())
        )

        st.markdown("---")

        # Zielwerte
        target_weight = st.number_input(
            "Zielgewicht (kg)",
            min_value=30.0,
            max_value=200.0,
            value=weight - 5 if goal_type == "abnehmen" else weight + 3 if goal_type == "muskelaufbau" else weight,
            step=0.5,
            help="Dein Wunschgewicht"
        )

        target_body_fat = st.number_input(
            "Ziel-Körperfettanteil (%)",
            min_value=5.0,
            max_value=50.0,
            value=15.0 if gender == "männlich" else 22.0,
            step=0.5,
            help="Empfohlen: Männer 10-20%, Frauen 18-28%"
        )

        # Zeitrahmen
        weeks = st.slider(
            "Zeitrahmen (Wochen)",
            min_value=4,
            max_value=52,
            value=12,
            help="Realistischer Zeitrahmen für dein Ziel"
        )
        target_date = date.today() + timedelta(weeks=weeks)
        st.caption(f"Zieldatum: {target_date.strftime('%d.%m.%Y')}")

    st.divider()

    # Kalorien berechnen
    st.subheader("📊 Berechnete Werte")

    calculated = calculate_calories(weight, height, age, gender, activity, goal_type)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Energiebedarf**")
        st.metric("Grundumsatz (BMR)", f"{calculated['bmr']} kcal")
        st.metric("Tagesverbrauch (TDEE)", f"{calculated['tdee']} kcal")
        st.metric("Kalorienziel", f"{calculated['daily_calories']} kcal",
                  delta=f"{calculated['daily_calories'] - calculated['tdee']:+} kcal")

    with col2:
        st.markdown("**Makronährstoffe (täglich)**")
        st.metric("Protein", f"{calculated['protein_g']}g",
                  help=f"{calculated['protein_g'] / weight:.1f}g pro kg Körpergewicht")
        st.metric("Kohlenhydrate", f"{calculated['carbs_g']}g")
        st.metric("Fett", f"{calculated['fat_g']}g")

    with col3:
        st.markdown("**Prognose**")
        weight_diff = target_weight - weight
        weekly_change = weight_diff / weeks
        st.metric("Gewichtsdifferenz", f"{weight_diff:+.1f} kg")
        st.metric("Wöchentliche Änderung", f"{weekly_change:+.2f} kg",
                  help="Empfohlen: max. 0.5-1kg/Woche beim Abnehmen")

        if abs(weekly_change) > 1:
            st.warning("⚠️ Schnelle Änderung - evtl. Zeitrahmen anpassen")

    st.divider()

    # Manuelle Anpassung
    with st.expander("⚙️ Werte manuell anpassen"):
        manual_col1, manual_col2 = st.columns(2)

        with manual_col1:
            custom_calories = st.number_input(
                "Kalorien anpassen",
                min_value=1000,
                max_value=5000,
                value=calculated['daily_calories'],
            )

        with manual_col2:
            custom_protein = st.number_input(
                "Protein anpassen (g)",
                min_value=50,
                max_value=400,
                value=calculated['protein_g'],
            )

        # Wenn manuell angepasst, diese Werte verwenden
        if custom_calories != calculated['daily_calories']:
            calculated['daily_calories'] = custom_calories
        if custom_protein != calculated['protein_g']:
            calculated['protein_g'] = custom_protein

    # Speichern
    st.divider()

    if st.button("💾 Ziel speichern", type="primary", use_container_width=True):
        try:
            # Profil aktualisieren
            db.update_user_profile(
                user.id,
                name=name,
                gender=gender,
                birth_date=birth_date,
                height_cm=height,
                activity_level=activity,
            )

            # Aktuelle Messung speichern (falls geändert)
            if not latest_measurement or latest_measurement.weight_kg != weight:
                db.add_body_measurement(user.id, weight=weight)

            # Ziel speichern
            db.set_user_goal(
                user_id=user.id,
                goal_type=TrainingGoal(goal_type),
                target_weight=target_weight,
                target_body_fat=target_body_fat,
                target_date=target_date,
                daily_calories=calculated['daily_calories'],
                protein_g=calculated['protein_g'],
                carbs_g=calculated['carbs_g'],
                fat_g=calculated['fat_g'],
            )

            st.success("✅ Ziel erfolgreich gespeichert!")
            st.balloons()

            # Session aktualisieren
            st.session_state.user = db.get_or_create_user()

        except Exception as e:
            st.error(f"Fehler beim Speichern: {e}")


if __name__ == "__main__":
    main()
