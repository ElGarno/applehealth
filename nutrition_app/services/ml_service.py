"""
ML Service für Prognosen und Optimierung
"""
from datetime import date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import logging
import pickle
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    """Vorhersage des ML-Modells"""
    target_date: date
    predicted_weight: Optional[float]
    predicted_body_fat: Optional[float]
    confidence: float
    recommendations: List[str]
    model_version: str


@dataclass
class OptimalPlan:
    """Optimaler Ernährungs- und Trainingsplan"""
    daily_calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    exercise_minutes_per_week: int
    expected_weight_loss_per_week: float
    expected_weeks_to_goal: int
    confidence: float


class MLService:
    """
    ML Service für Fortschrittsprognosen und Optimierung

    Verwendet ein einfaches, interpretierbare Modell basierend auf:
    - Energiebilanz (CICO - Calories In, Calories Out)
    - Historische Daten des Benutzers
    - Wissenschaftliche Grundlagen der Körperkomposition
    """

    MODEL_VERSION = "1.0.0"

    # Wissenschaftliche Konstanten
    KCAL_PER_KG_FAT = 7700  # kcal pro kg Körperfett
    KCAL_PER_KG_MUSCLE = 5500  # kcal pro kg Muskelgewebe (grob)
    MAX_SAFE_DEFICIT_PERCENT = 0.25  # Max 25% unter TDEE
    MAX_FAT_LOSS_PER_WEEK = 1.0  # kg
    MAX_MUSCLE_GAIN_PER_WEEK = 0.25  # kg (für Anfänger)

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path
        self._model = None

    def predict_progress(self, user_data: Dict[str, Any],
                        nutrition_history: List[Dict],
                        activity_history: List[Dict],
                        body_history: List[Dict],
                        target_days: int = 30) -> Prediction:
        """
        Prognostiziert Gewichts- und Körperfett-Entwicklung

        Args:
            user_data: Benutzerprofil (Alter, Geschlecht, Größe, Aktivität)
            nutrition_history: Ernährungsdaten der letzten Wochen
            activity_history: Aktivitätsdaten
            body_history: Körpermessungen
            target_days: Tage in die Zukunft

        Returns:
            Prediction mit erwarteten Werten
        """
        # Aktuelle Werte
        current_weight = body_history[-1].get('weight') if body_history else user_data.get('weight', 75)
        current_bf = body_history[-1].get('body_fat') if body_history else 20

        # Durchschnittliche Kalorienbilanz berechnen
        avg_intake = self._calculate_avg_intake(nutrition_history)
        avg_expenditure = self._calculate_avg_expenditure(user_data, activity_history, current_weight)

        daily_balance = avg_intake - avg_expenditure

        # Gewichtsprognose basierend auf Energiebilanz
        total_balance = daily_balance * target_days
        expected_fat_change = total_balance / self.KCAL_PER_KG_FAT

        # Begrenzung auf realistische Werte
        if expected_fat_change < 0:  # Fettabbau
            expected_fat_change = max(expected_fat_change, -self.MAX_FAT_LOSS_PER_WEEK * (target_days / 7))
        else:  # Fettzunahme
            expected_fat_change = min(expected_fat_change, self.MAX_FAT_LOSS_PER_WEEK * (target_days / 7))

        predicted_weight = current_weight + expected_fat_change

        # Körperfett-Schätzung
        if current_weight > 0:
            current_fat_mass = current_weight * (current_bf / 100)
            predicted_fat_mass = current_fat_mass + expected_fat_change
            predicted_body_fat = (predicted_fat_mass / predicted_weight) * 100
        else:
            predicted_body_fat = current_bf

        # Konfidenz basierend auf Datenmenge
        data_points = len(nutrition_history) + len(body_history)
        confidence = min(0.95, 0.5 + (data_points * 0.02))

        # Empfehlungen generieren
        recommendations = self._generate_recommendations(
            daily_balance, avg_intake, avg_expenditure, user_data
        )

        return Prediction(
            target_date=date.today() + timedelta(days=target_days),
            predicted_weight=round(predicted_weight, 1),
            predicted_body_fat=round(predicted_body_fat, 1) if predicted_body_fat else None,
            confidence=round(confidence, 2),
            recommendations=recommendations,
            model_version=self.MODEL_VERSION,
        )

    def calculate_optimal_plan(self, user_data: Dict[str, Any],
                               goal: Dict[str, Any],
                               current_body: Dict[str, Any]) -> OptimalPlan:
        """
        Berechnet den optimalen Plan zum Erreichen des Ziels

        Args:
            user_data: Benutzerprofil
            goal: Zieldaten (Gewicht, Körperfett, Zeitrahmen)
            current_body: Aktuelle Körperdaten

        Returns:
            OptimalPlan mit empfohlenen Werten
        """
        current_weight = current_body.get('weight', 75)
        target_weight = goal.get('target_weight', current_weight)
        target_bf = goal.get('target_body_fat')
        target_date = goal.get('target_date')

        # Zeitrahmen berechnen
        if target_date:
            days_to_goal = (target_date - date.today()).days
        else:
            days_to_goal = 90  # Default 3 Monate

        weeks_to_goal = max(1, days_to_goal // 7)

        # Gewichtsdifferenz
        weight_diff = target_weight - current_weight

        # TDEE berechnen
        tdee = self._calculate_tdee(user_data, current_weight)

        # Optimale Kalorienzufuhr
        if weight_diff < 0:  # Abnehmen
            # Kaloriendefizit berechnen
            required_deficit = (abs(weight_diff) * self.KCAL_PER_KG_FAT) / days_to_goal
            max_deficit = tdee * self.MAX_SAFE_DEFICIT_PERCENT

            daily_deficit = min(required_deficit, max_deficit)
            daily_calories = int(tdee - daily_deficit)

            # Protein hoch für Muskelerhalt
            protein_per_kg = 2.0
            expected_loss = daily_deficit * 7 / self.KCAL_PER_KG_FAT

        elif weight_diff > 0:  # Zunehmen/Muskelaufbau
            # Kalorienüberschuss
            daily_surplus = min(300, (weight_diff * self.KCAL_PER_KG_MUSCLE) / days_to_goal)
            daily_calories = int(tdee + daily_surplus)

            protein_per_kg = 2.2  # Höher für Muskelaufbau
            expected_loss = -daily_surplus * 7 / self.KCAL_PER_KG_MUSCLE  # Negativ = Zunahme

        else:  # Erhalt
            daily_calories = int(tdee)
            protein_per_kg = 1.8
            expected_loss = 0

        # Makros berechnen
        protein_g = int(current_weight * protein_per_kg)
        protein_cal = protein_g * 4

        # Fett: 25-30% der Kalorien
        fat_cal = daily_calories * 0.27
        fat_g = int(fat_cal / 9)

        # Rest sind Kohlenhydrate
        carbs_cal = daily_calories - protein_cal - fat_cal
        carbs_g = int(carbs_cal / 4)

        # Trainingsempfehlung
        if weight_diff < 0:
            exercise_minutes = 200  # Mehr Bewegung zum Abnehmen
        elif weight_diff > 0:
            exercise_minutes = 180  # Krafttraining
        else:
            exercise_minutes = 150

        return OptimalPlan(
            daily_calories=daily_calories,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            exercise_minutes_per_week=exercise_minutes,
            expected_weight_loss_per_week=round(expected_loss, 2),
            expected_weeks_to_goal=weeks_to_goal,
            confidence=0.75,  # Moderate Konfidenz für theoretische Berechnung
        )

    def analyze_what_works(self, body_history: List[Dict],
                           nutrition_history: List[Dict],
                           feedback_history: List[Dict]) -> Dict[str, Any]:
        """
        Analysiert welche Ernährung/Aktivität die besten Ergebnisse bringt

        Returns:
            Dict mit Erkenntnissen
        """
        insights = {
            "best_days": [],
            "patterns": [],
            "recommendations": [],
        }

        if len(body_history) < 7 or len(feedback_history) < 7:
            insights["status"] = "need_more_data"
            insights["message"] = "Mindestens 7 Tage Daten benötigt für Analyse"
            return insights

        # Korrelation zwischen Ernährung und Wohlbefinden
        high_energy_days = [f for f in feedback_history if f.get('energy_level', 0) >= 4]
        low_energy_days = [f for f in feedback_history if f.get('energy_level', 0) <= 2]

        if high_energy_days:
            insights["patterns"].append({
                "type": "high_energy",
                "count": len(high_energy_days),
                "description": f"Du hattest {len(high_energy_days)} Tage mit hohem Energielevel"
            })

        # Gewichtstrend analysieren
        if len(body_history) >= 2:
            weights = [b.get('weight', 0) for b in body_history if b.get('weight')]
            if len(weights) >= 2:
                trend = weights[-1] - weights[0]
                avg_change = trend / len(weights)

                insights["weight_trend"] = {
                    "total_change": round(trend, 2),
                    "avg_daily_change": round(avg_change, 3),
                    "direction": "abnehmend" if trend < 0 else "zunehmend" if trend > 0 else "stabil"
                }

        insights["status"] = "analyzed"
        return insights

    def _calculate_avg_intake(self, nutrition_history: List[Dict]) -> float:
        """Berechnet durchschnittliche Kalorienaufnahme"""
        if not nutrition_history:
            return 2000  # Default

        total = sum(n.get('calories', 0) for n in nutrition_history)
        return total / len(nutrition_history)

    def _calculate_avg_expenditure(self, user_data: Dict, activity_history: List[Dict],
                                   weight: float) -> float:
        """Berechnet durchschnittlichen Kalorienverbrauch"""
        tdee = self._calculate_tdee(user_data, weight)

        # Zusätzliche Aktivität aus History
        if activity_history:
            avg_active = sum(a.get('active_calories', 0) for a in activity_history) / len(activity_history)
            # TDEE enthält bereits Basisaktivität, nur Extra hinzufügen
            extra = max(0, avg_active - 300)
            tdee += extra

        return tdee

    def _calculate_tdee(self, user_data: Dict, weight: float) -> float:
        """Berechnet TDEE nach Mifflin-St Jeor"""
        height = user_data.get('height_cm', 175)
        age = user_data.get('age', 30)
        gender = user_data.get('gender', 'männlich')
        activity = user_data.get('activity_level', 'moderat')

        # BMR
        if gender == 'männlich':
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161

        # Aktivitätsfaktor
        factors = {
            'sedentär': 1.2,
            'leicht': 1.375,
            'moderat': 1.55,
            'aktiv': 1.725,
            'sehr_aktiv': 1.9,
        }

        return bmr * factors.get(activity, 1.55)

    def _generate_recommendations(self, daily_balance: float, intake: float,
                                  expenditure: float, user_data: Dict) -> List[str]:
        """Generiert Empfehlungen basierend auf Analyse"""
        recommendations = []

        goal = user_data.get('goal', 'erhalt')

        if goal in ['abnehmen', 'Abnehmen']:
            if daily_balance > 0:
                recommendations.append(f"Du bist aktuell im Kalorienüberschuss (+{daily_balance:.0f} kcal/Tag). Reduziere die Kalorienzufuhr oder steigere die Aktivität.")
            elif daily_balance > -300:
                recommendations.append("Dein Defizit ist klein. Für schnellere Ergebnisse könntest du das Defizit erhöhen.")
            else:
                recommendations.append("Gutes Defizit! Achte darauf, ausreichend Protein zu essen um Muskeln zu erhalten.")

        elif goal in ['muskelaufbau', 'Muskelaufbau']:
            if daily_balance < 200:
                recommendations.append(f"Für Muskelaufbau brauchst du einen Überschuss. Aktuell: {daily_balance:.0f} kcal/Tag")
            else:
                recommendations.append("Guter Überschuss für Muskelaufbau! Stelle sicher, dass du genug trainierst.")

        # Allgemeine Empfehlungen
        if intake < 1500:
            recommendations.append("⚠️ Deine Kalorienzufuhr ist sehr niedrig. Das kann zu Nährstoffmangel führen.")

        return recommendations
