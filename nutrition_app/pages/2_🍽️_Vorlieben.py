"""
Essensvorlieben Seite
"""
import streamlit as st

st.set_page_config(page_title="Vorlieben", page_icon="🍽️", layout="wide")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
from services.database_service import DatabaseService
from models.database import PreferenceType


# Vordefinierte Kategorien
FOOD_CATEGORIES = [
    "Fleisch", "Geflügel", "Fisch", "Meeresfrüchte",
    "Milchprodukte", "Eier", "Hülsenfrüchte", "Tofu/Tempeh",
    "Gemüse", "Obst", "Getreide", "Reis", "Pasta", "Brot",
    "Nüsse", "Samen", "Öle", "Süßigkeiten",
]

COMMON_INGREDIENTS = [
    "Zwiebeln", "Knoblauch", "Tomaten", "Paprika", "Pilze",
    "Brokkoli", "Spinat", "Karotten", "Zucchini", "Aubergine",
    "Äpfel", "Bananen", "Beeren", "Zitrusfrüchte",
    "Haferflocken", "Quinoa", "Linsen", "Kichererbsen",
    "Lachs", "Thunfisch", "Hähnchen", "Rind", "Schwein",
    "Joghurt", "Käse", "Milch", "Quark",
]

ALLERGENS = [
    "Gluten", "Laktose", "Nüsse", "Erdnüsse", "Soja",
    "Eier", "Fisch", "Schalentiere", "Sellerie", "Senf",
    "Sesam", "Sulfite", "Lupinen", "Weichtiere",
]

DIET_TYPES = [
    ("keine", "Keine Einschränkung"),
    ("vegetarisch", "Vegetarisch"),
    ("vegan", "Vegan"),
    ("pescetarisch", "Pescetarisch (Fisch ok)"),
    ("flexitarisch", "Flexitarisch (wenig Fleisch)"),
    ("keto", "Ketogen (Low Carb)"),
    ("paleo", "Paleo"),
]


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
    st.title("🍽️ Essensvorlieben")
    st.caption("Teile uns mit, was du gerne isst und was nicht. Das hilft bei personalisierten Empfehlungen.")

    if not init_session():
        return

    db = st.session_state.db
    user = st.session_state.user

    # Tabs für verschiedene Bereiche
    tab1, tab2, tab3, tab4 = st.tabs([
        "❤️ Lieblingsspeisen",
        "👎 Abneigungen",
        "⚠️ Allergien",
        "🥗 Ernährungsform"
    ])

    # ==================== Lieblingsspeisen ====================
    with tab1:
        st.subheader("Was isst du besonders gerne?")

        # Vorhandene Lieblinge laden
        favorites = db.get_preferences_by_type(user.id, PreferenceType.LIEBLING)
        favorite_items = [f.category or f.ingredient for f in favorites]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Kategorien**")
            selected_categories = st.multiselect(
                "Wähle Kategorien",
                options=FOOD_CATEGORIES,
                default=[c for c in favorite_items if c in FOOD_CATEGORIES],
                key="fav_categories",
                label_visibility="collapsed",
            )

        with col2:
            st.markdown("**Zutaten**")
            selected_ingredients = st.multiselect(
                "Wähle Zutaten",
                options=COMMON_INGREDIENTS,
                default=[i for i in favorite_items if i in COMMON_INGREDIENTS],
                key="fav_ingredients",
                label_visibility="collapsed",
            )

        # Eigene Eingabe
        custom_favorite = st.text_input(
            "Weitere Lieblinge (kommagetrennt)",
            placeholder="z.B. Overnight Oats, Griechischer Salat, Curry",
            key="custom_fav",
        )

        if st.button("💾 Lieblingsspeisen speichern", key="save_fav"):
            # Alte löschen
            for pref in favorites:
                db.delete_preference(pref.id)

            # Neue speichern
            all_favorites = selected_categories + selected_ingredients
            if custom_favorite:
                all_favorites.extend([f.strip() for f in custom_favorite.split(",") if f.strip()])

            for item in all_favorites:
                if item in FOOD_CATEGORIES:
                    db.add_food_preference(user.id, PreferenceType.LIEBLING, category=item)
                else:
                    db.add_food_preference(user.id, PreferenceType.LIEBLING, ingredient=item)

            st.success(f"✅ {len(all_favorites)} Lieblinge gespeichert!")

    # ==================== Abneigungen ====================
    with tab2:
        st.subheader("Was magst du nicht?")

        # Vorhandene Abneigungen laden
        dislikes = db.get_preferences_by_type(user.id, PreferenceType.ABNEIGUNG)
        dislike_items = [d.category or d.ingredient for d in dislikes]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Kategorien**")
            disliked_categories = st.multiselect(
                "Wähle Kategorien",
                options=FOOD_CATEGORIES,
                default=[c for c in dislike_items if c in FOOD_CATEGORIES],
                key="dislike_categories",
                label_visibility="collapsed",
            )

        with col2:
            st.markdown("**Zutaten**")
            disliked_ingredients = st.multiselect(
                "Wähle Zutaten",
                options=COMMON_INGREDIENTS,
                default=[i for i in dislike_items if i in COMMON_INGREDIENTS],
                key="dislike_ingredients",
                label_visibility="collapsed",
            )

        custom_dislike = st.text_input(
            "Weitere Abneigungen (kommagetrennt)",
            placeholder="z.B. Rosenkohl, Innereien, Oliven",
            key="custom_dislike",
        )

        if st.button("💾 Abneigungen speichern", key="save_dislike"):
            for pref in dislikes:
                db.delete_preference(pref.id)

            all_dislikes = disliked_categories + disliked_ingredients
            if custom_dislike:
                all_dislikes.extend([d.strip() for d in custom_dislike.split(",") if d.strip()])

            for item in all_dislikes:
                if item in FOOD_CATEGORIES:
                    db.add_food_preference(user.id, PreferenceType.ABNEIGUNG, category=item)
                else:
                    db.add_food_preference(user.id, PreferenceType.ABNEIGUNG, ingredient=item)

            st.success(f"✅ {len(all_dislikes)} Abneigungen gespeichert!")

    # ==================== Allergien ====================
    with tab3:
        st.subheader("Hast du Allergien oder Unverträglichkeiten?")
        st.caption("Diese werden strikt bei Empfehlungen berücksichtigt.")

        # Vorhandene Allergien laden
        allergies = db.get_preferences_by_type(user.id, PreferenceType.ALLERGIE)
        allergy_items = [a.ingredient for a in allergies if a.ingredient]

        selected_allergens = st.multiselect(
            "Wähle Allergene",
            options=ALLERGENS,
            default=[a for a in allergy_items if a in ALLERGENS],
            key="allergens",
        )

        custom_allergy = st.text_input(
            "Weitere Unverträglichkeiten",
            placeholder="z.B. Histamin, Fructose",
            key="custom_allergy",
        )

        allergy_notes = st.text_area(
            "Zusätzliche Hinweise",
            placeholder="z.B. Kreuzallergien, Schweregrad, etc.",
            key="allergy_notes",
        )

        if st.button("💾 Allergien speichern", key="save_allergy"):
            for pref in allergies:
                db.delete_preference(pref.id)

            all_allergies = selected_allergens.copy()
            if custom_allergy:
                all_allergies.extend([a.strip() for a in custom_allergy.split(",") if a.strip()])

            for allergen in all_allergies:
                db.add_food_preference(
                    user.id,
                    PreferenceType.ALLERGIE,
                    ingredient=allergen,
                    notes=allergy_notes if allergy_notes else None
                )

            st.success(f"✅ {len(all_allergies)} Allergien/Unverträglichkeiten gespeichert!")
            if all_allergies:
                st.warning("⚠️ Diese werden bei allen Empfehlungen berücksichtigt!")

    # ==================== Ernährungsform ====================
    with tab4:
        st.subheader("Welche Ernährungsform verfolgst du?")

        # Aktuelle Einschränkungen laden
        restrictions = db.get_dietary_restrictions(user.id)
        current_diet = restrictions[0].restriction_type if restrictions else "keine"

        selected_diet = st.radio(
            "Ernährungsform",
            options=[d[0] for d in DIET_TYPES],
            format_func=lambda x: dict(DIET_TYPES).get(x, x),
            index=[d[0] for d in DIET_TYPES].index(current_diet) if current_diet in [d[0] for d in DIET_TYPES] else 0,
            key="diet_type",
        )

        if st.button("💾 Ernährungsform speichern", key="save_diet"):
            # Alte deaktivieren (könnten wir auch löschen)
            db.set_dietary_restriction(user.id, selected_diet)
            st.success(f"✅ Ernährungsform '{dict(DIET_TYPES).get(selected_diet)}' gespeichert!")

    # ==================== Übersicht ====================
    st.divider()
    st.subheader("📋 Deine Vorlieben-Übersicht")

    # Alles nochmal laden für Übersicht
    all_prefs = db.get_user_preferences(user.id)
    restrictions = db.get_dietary_restrictions(user.id)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**❤️ Lieblinge**")
        favs = [p.category or p.ingredient for p in all_prefs if p.preference_type == PreferenceType.LIEBLING]
        if favs:
            for f in favs:
                st.write(f"• {f}")
        else:
            st.caption("Keine angegeben")

    with col2:
        st.markdown("**👎 Abneigungen**")
        dislikes = [p.category or p.ingredient for p in all_prefs if p.preference_type == PreferenceType.ABNEIGUNG]
        if dislikes:
            for d in dislikes:
                st.write(f"• {d}")
        else:
            st.caption("Keine angegeben")

    with col3:
        st.markdown("**⚠️ Allergien**")
        allergies = [p.ingredient for p in all_prefs if p.preference_type == PreferenceType.ALLERGIE]
        if allergies:
            for a in allergies:
                st.write(f"• {a}")
        else:
            st.caption("Keine angegeben")

    if restrictions:
        st.info(f"**Ernährungsform:** {dict(DIET_TYPES).get(restrictions[0].restriction_type, restrictions[0].restriction_type)}")


if __name__ == "__main__":
    main()
