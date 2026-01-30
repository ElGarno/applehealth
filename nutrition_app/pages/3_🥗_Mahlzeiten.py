"""
Mahlzeiten-Tracking Seite
"""
import streamlit as st
from datetime import datetime, date

st.set_page_config(page_title="Mahlzeiten", page_icon="🥗", layout="wide")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
from services.database_service import DatabaseService
from services.food_api_service import FoodAPIService, COMMON_FOODS_DE
from models.database import MealType


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
    if 'food_api' not in st.session_state:
        st.session_state.food_api = FoodAPIService()
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = date.today()
    if 'current_meal_items' not in st.session_state:
        st.session_state.current_meal_items = []
    return True


def search_food(query: str):
    """Sucht Lebensmittel in DB und API"""
    db = st.session_state.db
    api = st.session_state.food_api

    results = []

    # Erst in lokaler DB suchen
    local_results = db.search_foods(query, limit=5)
    for food in local_results:
        results.append({
            'source': 'lokal',
            'id': food.id,
            'name': food.name,
            'brand': food.brand,
            'calories': food.calories_per_100g,
            'protein': food.protein_per_100g,
            'carbs': food.carbs_per_100g,
            'fat': food.fat_per_100g,
        })

    # Dann in OpenFoodFacts suchen
    if len(results) < 10:
        api_results = api.search_products(query, page_size=10 - len(results))
        for product in api_results:
            results.append({
                'source': 'openfoodfacts',
                'id': None,
                'name': product.name,
                'brand': product.brand,
                'barcode': product.barcode,
                'calories': product.calories,
                'protein': product.protein,
                'carbs': product.carbs,
                'fat': product.fat,
            })

    return results


def add_food_to_db(food_data: dict):
    """Fügt ein Lebensmittel zur lokalen DB hinzu"""
    db = st.session_state.db
    return db.add_food(
        name=food_data['name'],
        calories=food_data.get('calories'),
        protein=food_data.get('protein'),
        carbs=food_data.get('carbs'),
        fat=food_data.get('fat'),
        brand=food_data.get('brand'),
        barcode=food_data.get('barcode'),
        source='openfoodfacts' if food_data.get('barcode') else 'manual',
    )


def main():
    st.title("🥗 Mahlzeiten tracken")

    if not init_session():
        return

    db = st.session_state.db
    user = st.session_state.user

    # Datum auswählen
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_date = st.date_input(
            "Datum",
            value=st.session_state.selected_date,
            max_value=date.today(),
        )
        st.session_state.selected_date = selected_date

    with col2:
        # Tagesübersicht
        daily = db.get_daily_nutrition_summary(user.id, selected_date)
        goal = db.get_active_goal(user.id)
        target_cal = goal.daily_calorie_target if goal else 2000

        progress = daily['calories'] / target_cal if target_cal else 0
        st.metric(
            "Kalorien heute",
            f"{daily['calories']:.0f} / {target_cal}",
            delta=f"{daily['calories'] - target_cal:.0f}" if daily['calories'] > 0 else None,
        )

    st.divider()

    # Tabs für Mahlzeiten
    tabs = st.tabs(["🌅 Frühstück", "☀️ Mittagessen", "🌙 Abendessen", "🍎 Snacks", "📋 Vorlagen"])

    meal_types = [MealType.FRUEHSTUECK, MealType.MITTAGESSEN, MealType.ABENDESSEN, MealType.SNACK]

    for i, (tab, meal_type) in enumerate(zip(tabs[:4], meal_types)):
        with tab:
            render_meal_section(meal_type, selected_date)

    # Vorlagen Tab
    with tabs[4]:
        render_templates_section()


def render_meal_section(meal_type: MealType, target_date: date):
    """Rendert einen Mahlzeiten-Abschnitt"""
    db = st.session_state.db
    user = st.session_state.user

    meal_name = meal_type.value.title()

    # Existierende Mahlzeiten für diesen Typ laden
    all_meals = db.get_meals_for_date(user.id, target_date)
    meals_of_type = [m for m in all_meals if m.meal_type == meal_type]

    # Vorhandene Mahlzeiten anzeigen
    if meals_of_type:
        for meal in meals_of_type:
            with st.expander(f"📝 {meal_name} - {meal.total_calories:.0f} kcal", expanded=True):
                st.caption(f"Gegessen um {meal.eaten_at.strftime('%H:%M')}")

                # Nährwerte
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Kalorien", f"{meal.total_calories:.0f}")
                col2.metric("Protein", f"{meal.total_protein:.1f}g")
                col3.metric("Carbs", f"{meal.total_carbs:.1f}g")
                col4.metric("Fett", f"{meal.total_fat:.1f}g")

                # Items anzeigen (TODO: laden aus DB)
                if meal.notes:
                    st.caption(meal.notes)

    # Neue Mahlzeit hinzufügen
    st.markdown(f"### ➕ {meal_name} hinzufügen")

    # Suchfeld
    search_query = st.text_input(
        "Lebensmittel suchen",
        placeholder="z.B. Haferflocken, Apfel, Joghurt...",
        key=f"search_{meal_type.value}",
    )

    if search_query and len(search_query) >= 2:
        with st.spinner("Suche..."):
            results = search_food(search_query)

        if results:
            st.markdown("**Suchergebnisse:**")

            for idx, food in enumerate(results):
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    display_name = food['name']
                    if food.get('brand'):
                        display_name += f" ({food['brand']})"
                    st.write(display_name)
                    st.caption(
                        f"{food.get('calories', '?')} kcal | "
                        f"P: {food.get('protein', '?')}g | "
                        f"C: {food.get('carbs', '?')}g | "
                        f"F: {food.get('fat', '?')}g"
                    )

                with col2:
                    quantity = st.number_input(
                        "Gramm",
                        min_value=1,
                        max_value=2000,
                        value=100,
                        key=f"qty_{meal_type.value}_{idx}",
                        label_visibility="collapsed",
                    )

                with col3:
                    if st.button("➕", key=f"add_{meal_type.value}_{idx}"):
                        add_food_to_meal(meal_type, food, quantity, target_date)
                        st.rerun()
        else:
            st.info("Keine Ergebnisse gefunden. Versuche einen anderen Suchbegriff.")

    # Schnelleingabe mit häufigen Lebensmitteln
    st.markdown("---")
    st.markdown("**Schnelleingabe:**")

    # Häufig verwendete Lebensmittel
    frequent = db.get_frequently_used_foods(user.id, limit=5)

    cols = st.columns(5)
    display_foods = frequent if frequent else COMMON_FOODS_DE[:5]

    for idx, (col, food) in enumerate(zip(cols, display_foods)):
        with col:
            if hasattr(food, 'name'):  # DB Food
                name = food.name[:12] + "..." if len(food.name) > 12 else food.name
                if st.button(f"🍽️ {name}", key=f"quick_{meal_type.value}_{idx}"):
                    add_food_to_meal(
                        meal_type,
                        {
                            'id': food.id,
                            'name': food.name,
                            'calories': food.calories_per_100g,
                            'protein': food.protein_per_100g,
                            'carbs': food.carbs_per_100g,
                            'fat': food.fat_per_100g,
                            'source': 'lokal',
                        },
                        100,
                        target_date,
                    )
                    st.rerun()
            else:  # NutritionInfo
                name = food.name[:12] + "..." if len(food.name) > 12 else food.name
                if st.button(f"🍽️ {name}", key=f"quick_{meal_type.value}_{idx}"):
                    add_food_to_meal(
                        meal_type,
                        {
                            'name': food.name,
                            'calories': food.calories,
                            'protein': food.protein,
                            'carbs': food.carbs,
                            'fat': food.fat,
                            'source': 'common',
                        },
                        100,
                        target_date,
                    )
                    st.rerun()


def add_food_to_meal(meal_type: MealType, food: dict, quantity: float, target_date: date):
    """Fügt ein Lebensmittel zu einer Mahlzeit hinzu"""
    db = st.session_state.db
    user = st.session_state.user

    # Food in DB speichern falls noch nicht vorhanden
    food_id = food.get('id')
    if not food_id:
        saved_food = add_food_to_db(food)
        food_id = saved_food.id

    # Prüfen ob heute schon eine Mahlzeit dieses Typs existiert
    meals = db.get_meals_for_date(user.id, target_date)
    existing_meal = next((m for m in meals if m.meal_type == meal_type), None)

    if existing_meal:
        meal_id = existing_meal.id
    else:
        # Neue Mahlzeit erstellen
        new_meal = db.create_meal(
            user_id=user.id,
            meal_type=meal_type,
            eaten_at=datetime.combine(target_date, datetime.now().time()),
        )
        meal_id = new_meal.id

    # Item hinzufügen
    db.add_item_to_meal(meal_id, food_id, quantity)
    st.success(f"✅ {food['name']} ({quantity}g) hinzugefügt!")


def render_templates_section():
    """Rendert den Vorlagen-Bereich"""
    db = st.session_state.db
    user = st.session_state.user

    st.subheader("📋 Gespeicherte Mahlzeiten-Vorlagen")
    st.caption("Speichere häufig gegessene Mahlzeiten als Vorlage für schnelles Tracking.")

    templates = db.get_meal_templates(user.id)

    if templates:
        for template in templates:
            with st.expander(f"📝 {template.template_name or template.meal_type.value}"):
                st.write(f"**Typ:** {template.meal_type.value.title()}")
                st.write(f"**Kalorien:** {template.total_calories:.0f} kcal")
                st.write(
                    f"P: {template.total_protein:.1f}g | "
                    f"C: {template.total_carbs:.1f}g | "
                    f"F: {template.total_fat:.1f}g"
                )

                if st.button(f"Diese Vorlage verwenden", key=f"use_template_{template.id}"):
                    # TODO: Vorlage für heute anwenden
                    st.info("Vorlage anwenden - Coming Soon!")
    else:
        st.info("""
        Du hast noch keine Vorlagen gespeichert.

        **Tipp:** Du erwähntest, dass du jeden Morgen Overnight Oats isst.
        Speichere solche wiederkehrenden Mahlzeiten als Vorlage!
        """)

    # Neue Vorlage erstellen
    st.markdown("---")
    st.markdown("### ➕ Neue Vorlage erstellen")

    template_name = st.text_input(
        "Name der Vorlage",
        placeholder="z.B. Meine Overnight Oats",
    )

    template_type = st.selectbox(
        "Mahlzeiten-Typ",
        options=[mt.value for mt in MealType],
        format_func=lambda x: x.title(),
    )

    st.caption("Füge Lebensmittel hinzu:")

    # Einfache Vorlagen-Erstellung
    col1, col2 = st.columns(2)

    with col1:
        food_name = st.text_input("Lebensmittel", placeholder="z.B. Haferflocken")
    with col2:
        food_qty = st.number_input("Menge (g)", min_value=1, value=50)

    if st.button("Vorlage speichern", disabled=not template_name):
        st.info("Vorlagen-Erstellung - Coming Soon!")
        # TODO: Implementieren


if __name__ == "__main__":
    main()
