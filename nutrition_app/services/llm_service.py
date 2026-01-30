"""
LLM Service für KI-gestützte Empfehlungen (Claude + OpenAI)
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class MealPlan:
    """Generierter Mahlzeitenplan"""
    breakfast: Dict[str, Any]
    lunch: Dict[str, Any]
    dinner: Dict[str, Any]
    snacks: List[Dict[str, Any]]
    total_calories: int
    total_protein: float
    total_carbs: float
    total_fat: float
    reasoning: str


@dataclass
class NutritionAdvice:
    """KI-generierter Ernährungstipp"""
    title: str
    content: str
    category: str  # tip, warning, adjustment
    priority: int  # 1-5


class LLMService:
    """Service für LLM-basierte Ernährungsempfehlungen"""

    def __init__(self, provider: str = "claude",
                 anthropic_api_key: str = None,
                 openai_api_key: str = None):
        self.provider = provider
        self.anthropic_api_key = anthropic_api_key
        self.openai_api_key = openai_api_key
        self._anthropic_client = None
        self._openai_client = None

    def _get_anthropic_client(self):
        """Lazy loading für Anthropic Client"""
        if not self._anthropic_client and self.anthropic_api_key:
            try:
                from anthropic import Anthropic
                self._anthropic_client = Anthropic(api_key=self.anthropic_api_key)
            except ImportError:
                logger.error("anthropic Paket nicht installiert: pip install anthropic")
        return self._anthropic_client

    def _get_openai_client(self):
        """Lazy loading für OpenAI Client"""
        if not self._openai_client and self.openai_api_key:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.openai_api_key)
            except ImportError:
                logger.error("openai Paket nicht installiert: pip install openai")
        return self._openai_client

    def is_available(self) -> bool:
        """Prüft ob ein LLM-Provider verfügbar ist"""
        if self.provider == "claude":
            return bool(self.anthropic_api_key)
        elif self.provider == "openai":
            return bool(self.openai_api_key)
        return False

    def _call_llm(self, system_prompt: str, user_prompt: str,
                  temperature: float = 0.7) -> Optional[str]:
        """Ruft das konfigurierte LLM auf"""
        if self.provider == "claude":
            return self._call_claude(system_prompt, user_prompt, temperature)
        elif self.provider == "openai":
            return self._call_openai(system_prompt, user_prompt, temperature)
        return None

    def _call_claude(self, system_prompt: str, user_prompt: str,
                     temperature: float = 0.7) -> Optional[str]:
        """Ruft Claude API auf"""
        client = self._get_anthropic_client()
        if not client:
            return None

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API Fehler: {e}")
            return None

    def _call_openai(self, system_prompt: str, user_prompt: str,
                     temperature: float = 0.7) -> Optional[str]:
        """Ruft OpenAI API auf"""
        client = self._get_openai_client()
        if not client:
            return None

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=2000,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API Fehler: {e}")
            return None

    def generate_meal_plan(self, user_context: Dict[str, Any],
                           preferences: Dict[str, List[str]],
                           activity_data: Dict[str, Any]) -> Optional[str]:
        """
        Generiert einen personalisierten Mahlzeitenplan

        Args:
            user_context: Dict mit Benutzerinfos (Ziel, Gewicht, etc.)
            preferences: Dict mit Vorlieben und Abneigungen
            activity_data: Dict mit Aktivitätsdaten

        Returns:
            Formatierter Mahlzeitenplan als String
        """
        system_prompt = """Du bist ein erfahrener Ernährungsberater und Fitness-Coach.
Erstelle personalisierte Mahlzeitenpläne basierend auf:
- Den Zielen des Benutzers (Abnehmen, Muskelaufbau, etc.)
- Seinen Vorlieben und Abneigungen
- Seinem aktuellen Aktivitätslevel

Antworte immer auf Deutsch.
Gib konkrete Mahlzeiten mit Mengenangaben an.
Berücksichtige die Makronährstoff-Verteilung für das jeweilige Ziel.
Sei praktisch - schlage einfach zubereitbare Mahlzeiten vor."""

        user_prompt = f"""Erstelle einen Mahlzeitenplan für heute basierend auf diesen Informationen:

**Benutzer-Profil:**
{json.dumps(user_context, indent=2, ensure_ascii=False)}

**Essens-Vorlieben:**
- Lieblingsspeisen: {', '.join(preferences.get('favorites', ['keine angegeben']))}
- Abneigungen: {', '.join(preferences.get('dislikes', ['keine angegeben']))}
- Allergien/Unverträglichkeiten: {', '.join(preferences.get('allergies', ['keine']))}
- Ernährungsform: {preferences.get('diet_type', 'keine Einschränkung')}

**Aktivität heute:**
{json.dumps(activity_data, indent=2, ensure_ascii=False)}

Erstelle einen konkreten Plan für Frühstück, Mittagessen, Abendessen und optionale Snacks.
Gib für jede Mahlzeit an:
1. Gericht-Name
2. Zutaten mit Mengen (in Gramm)
3. Geschätzte Nährwerte (Kalorien, Protein, Kohlenhydrate, Fett)
4. Kurze Zubereitungshinweise

Am Ende: Gesamtübersicht der Tagesnährwerte und kurze Begründung warum dieser Plan zum Ziel passt."""

        return self._call_llm(system_prompt, user_prompt)

    def analyze_progress(self, body_measurements: List[Dict],
                         nutrition_data: List[Dict],
                         activity_data: List[Dict],
                         goal: Dict[str, Any]) -> Optional[str]:
        """
        Analysiert Fortschritt und gibt Empfehlungen

        Returns:
            Analyse und Anpassungsempfehlungen als String
        """
        system_prompt = """Du bist ein erfahrener Ernährungs- und Fitness-Analyst.
Analysiere die Daten des Benutzers und gib konkrete, actionable Empfehlungen.
Sei ehrlich aber motivierend.
Antworte immer auf Deutsch.
Konzentriere dich auf das, was funktioniert, und was angepasst werden sollte."""

        user_prompt = f"""Analysiere meinen Fortschritt der letzten Woche:

**Mein Ziel:**
{json.dumps(goal, indent=2, ensure_ascii=False)}

**Körpermessungen (letzte Woche):**
{json.dumps(body_measurements, indent=2, ensure_ascii=False)}

**Ernährung (Tagesdurchschnitte):**
{json.dumps(nutrition_data, indent=2, ensure_ascii=False)}

**Aktivität (letzte Woche):**
{json.dumps(activity_data, indent=2, ensure_ascii=False)}

Bitte analysiere:
1. Bin ich auf dem richtigen Weg zu meinem Ziel?
2. Was läuft gut?
3. Was sollte ich anpassen?
4. Konkrete Empfehlungen für die nächste Woche

Sei spezifisch und gib praktische Tipps."""

        return self._call_llm(system_prompt, user_prompt, temperature=0.5)

    def get_meal_suggestions(self, meal_type: str,
                             available_ingredients: List[str],
                             target_calories: int,
                             preferences: Dict[str, List[str]]) -> Optional[str]:
        """
        Schlägt Mahlzeiten basierend auf verfügbaren Zutaten vor

        Args:
            meal_type: "frühstück", "mittagessen", "abendessen", "snack"
            available_ingredients: Liste verfügbarer Zutaten
            target_calories: Ziel-Kalorien für diese Mahlzeit
            preferences: Vorlieben und Abneigungen

        Returns:
            3 Mahlzeiten-Vorschläge als String
        """
        system_prompt = """Du bist ein kreativer Koch und Ernährungsberater.
Schlage leckere, gesunde Mahlzeiten vor, die zu den Zutaten und Vorlieben passen.
Antworte immer auf Deutsch.
Sei kreativ aber praktisch."""

        meal_type_de = {
            "breakfast": "Frühstück",
            "lunch": "Mittagessen",
            "dinner": "Abendessen",
            "snack": "Snack",
            "frühstück": "Frühstück",
            "mittagessen": "Mittagessen",
            "abendessen": "Abendessen",
        }.get(meal_type.lower(), meal_type)

        user_prompt = f"""Schlage mir 3 Optionen für ein {meal_type_de} vor.

**Verfügbare Zutaten:**
{', '.join(available_ingredients) if available_ingredients else 'Keine spezifischen - schlage allgemein vor'}

**Ziel-Kalorien:** ca. {target_calories} kcal

**Meine Vorlieben:**
- Mag gerne: {', '.join(preferences.get('favorites', ['keine angegeben']))}
- Mag nicht: {', '.join(preferences.get('dislikes', ['keine angegeben']))}

Für jeden Vorschlag:
1. Name des Gerichts
2. Kurze Zutatenliste mit Mengen
3. Geschätzte Nährwerte
4. Zubereitungszeit"""

        return self._call_llm(system_prompt, user_prompt)

    def explain_nutrition_impact(self, food_name: str,
                                 nutrition_info: Dict[str, float],
                                 user_goal: str) -> Optional[str]:
        """
        Erklärt die Auswirkung eines Lebensmittels auf das Ziel

        Args:
            food_name: Name des Lebensmittels
            nutrition_info: Nährwerte
            user_goal: "abnehmen", "muskelaufbau", etc.

        Returns:
            Kurze Erklärung als String
        """
        system_prompt = """Du bist ein Ernährungsberater.
Erkläre kurz und verständlich, wie ein Lebensmittel zu einem Fitness-Ziel beiträgt.
Antworte auf Deutsch, maximal 2-3 Sätze.
Sei sachlich und hilfreich."""

        goal_de = {
            "abnehmen": "Gewicht verlieren",
            "muskelaufbau": "Muskeln aufbauen",
            "erhalt": "Gewicht halten",
            "ausdauer": "Ausdauer verbessern",
        }.get(user_goal.lower(), user_goal)

        user_prompt = f"""Wie passt "{food_name}" zu meinem Ziel: {goal_de}?

Nährwerte pro 100g:
- Kalorien: {nutrition_info.get('calories', 'unbekannt')} kcal
- Protein: {nutrition_info.get('protein', 'unbekannt')}g
- Kohlenhydrate: {nutrition_info.get('carbs', 'unbekannt')}g
- Fett: {nutrition_info.get('fat', 'unbekannt')}g

Kurze Einschätzung bitte (2-3 Sätze)."""

        return self._call_llm(system_prompt, user_prompt, temperature=0.3)

    def generate_weekly_plan(self, user_context: Dict[str, Any],
                             preferences: Dict[str, List[str]],
                             variety_level: str = "medium") -> Optional[str]:
        """
        Generiert einen Wochenplan für die Lernphase

        Args:
            user_context: Benutzerkontext
            preferences: Vorlieben
            variety_level: "low", "medium", "high" - wie viel Variation

        Returns:
            Wochenplan als String
        """
        variety_text = {
            "low": "Halte die Mahlzeiten ähnlich, damit ich Muster erkennen kann",
            "medium": "Variiere moderat, teste verschiedene Proteinquellen und Kohlenhydrate",
            "high": "Maximale Variation um herauszufinden was mir am besten bekommt",
        }.get(variety_level, "moderate Variation")

        system_prompt = """Du bist ein Ernährungsberater, der einen Testplan für die Lernphase erstellt.
Das Ziel ist herauszufinden, welche Nahrungsmittel dem Benutzer am besten bekommen.
Antworte auf Deutsch.
Strukturiere den Plan klar nach Wochentagen."""

        user_prompt = f"""Erstelle einen 7-Tage Ernährungsplan für meine Lernphase.

**Mein Profil:**
{json.dumps(user_context, indent=2, ensure_ascii=False)}

**Meine Vorlieben:**
{json.dumps(preferences, indent=2, ensure_ascii=False)}

**Variations-Level:** {variety_text}

Ziel dieser Woche: Herausfinden, welche Lebensmittel mir Energie geben und welche mich müde machen.

Für jeden Tag:
- Frühstück, Mittagessen, Abendessen
- Ungefähre Nährwerte
- Hinweis worauf ich achten soll (z.B. "Teste heute mehr Vollkorn")

Am Ende: Zusammenfassung was wir diese Woche testen."""

        return self._call_llm(system_prompt, user_prompt)
