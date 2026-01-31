"""
Datenbank-Service für CRUD-Operationen
"""
from datetime import datetime, date, timedelta
from typing import Optional, List
from contextlib import contextmanager

from sqlalchemy import create_engine, desc, func
from sqlalchemy.orm import sessionmaker, Session

from models.database import (
    Base, UserProfile, UserGoal, BodyMeasurement, Food, Meal, MealItem,
    FoodPreference, DietaryRestriction, MealFeedback, AIRecommendation,
    TrainingGoal, MealType, PreferenceType
)


class DatabaseService:
    """Service für alle Datenbank-Operationen"""

    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def get_session(self):
        """Context manager für Sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _detach(self, session, obj):
        """Detach object from session for use outside context"""
        if obj is not None:
            session.refresh(obj)
            session.expunge(obj)
        return obj

    def _detach_all(self, session, objects):
        """Detach list of objects from session"""
        for obj in objects:
            session.refresh(obj)
            session.expunge(obj)
        return objects

    # ==================== User Profile ====================

    def get_or_create_user(self, name: str = "Benutzer") -> UserProfile:
        """Holt den Benutzer oder erstellt einen neuen"""
        with self.get_session() as session:
            user = session.query(UserProfile).first()
            if not user:
                user = UserProfile(name=name)
                session.add(user)
                session.commit()
                session.refresh(user)
            return self._detach(session, user)

    def update_user_profile(self, user_id: int, **kwargs) -> UserProfile:
        """Aktualisiert Benutzerprofil"""
        with self.get_session() as session:
            user = session.query(UserProfile).filter_by(id=user_id).first()
            if user:
                for key, value in kwargs.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                session.commit()
                session.refresh(user)
            return self._detach(session, user)

    def get_user(self, user_id: int = 1) -> Optional[UserProfile]:
        """Holt Benutzerprofil"""
        with self.get_session() as session:
            user = session.query(UserProfile).filter_by(id=user_id).first()
            return self._detach(session, user)

    # ==================== Goals ====================

    def set_user_goal(self, user_id: int, goal_type: TrainingGoal,
                      target_weight: float = None, target_body_fat: float = None,
                      target_muscle_mass: float = None, target_date: date = None,
                      daily_calories: int = None, protein_g: int = None,
                      carbs_g: int = None, fat_g: int = None) -> UserGoal:
        """Setzt ein neues Ziel (deaktiviert alte Ziele)"""
        with self.get_session() as session:
            # Deaktiviere alte Ziele
            session.query(UserGoal).filter_by(
                user_id=user_id, is_active=True
            ).update({"is_active": False})

            # Erstelle neues Ziel
            goal = UserGoal(
                user_id=user_id,
                goal_type=goal_type,
                target_weight_kg=target_weight,
                target_body_fat_percent=target_body_fat,
                target_muscle_mass_kg=target_muscle_mass,
                target_date=target_date,
                daily_calorie_target=daily_calories,
                protein_target_g=protein_g,
                carbs_target_g=carbs_g,
                fat_target_g=fat_g,
                is_active=True,
            )
            session.add(goal)
            session.commit()
            session.refresh(goal)
            return self._detach(session, goal)

    def get_active_goal(self, user_id: int) -> Optional[UserGoal]:
        """Holt das aktive Ziel des Benutzers"""
        with self.get_session() as session:
            goal = session.query(UserGoal).filter_by(
                user_id=user_id, is_active=True
            ).first()
            return self._detach(session, goal)

    # ==================== Body Measurements ====================

    def add_body_measurement(self, user_id: int, weight: float = None,
                             body_fat: float = None, muscle_mass: float = None,
                             measured_at: datetime = None, **kwargs) -> BodyMeasurement:
        """Fügt neue Körpermessung hinzu"""
        with self.get_session() as session:
            measurement = BodyMeasurement(
                user_id=user_id,
                measured_at=measured_at or datetime.now(),
                weight_kg=weight,
                body_fat_percent=body_fat,
                muscle_mass_kg=muscle_mass,
                **kwargs
            )

            # BMI berechnen wenn Gewicht und Größe vorhanden
            user = session.query(UserProfile).filter_by(id=user_id).first()
            if weight and user and user.height_cm:
                height_m = user.height_cm / 100
                measurement.bmi = round(weight / (height_m ** 2), 1)

            session.add(measurement)
            session.commit()
            session.refresh(measurement)
            return self._detach(session, measurement)

    def get_body_measurements(self, user_id: int, days: int = 30) -> List[BodyMeasurement]:
        """Holt Körpermessungen der letzten X Tage"""
        with self.get_session() as session:
            since = datetime.now() - timedelta(days=days)
            measurements = session.query(BodyMeasurement).filter(
                BodyMeasurement.user_id == user_id,
                BodyMeasurement.measured_at >= since
            ).order_by(desc(BodyMeasurement.measured_at)).all()
            return self._detach_all(session, measurements)

    def get_latest_measurement(self, user_id: int) -> Optional[BodyMeasurement]:
        """Holt die letzte Körpermessung"""
        with self.get_session() as session:
            measurement = session.query(BodyMeasurement).filter_by(
                user_id=user_id
            ).order_by(desc(BodyMeasurement.measured_at)).first()
            return self._detach(session, measurement)

    # ==================== Foods ====================

    def add_food(self, name: str, calories: float = None, protein: float = None,
                 carbs: float = None, fat: float = None, **kwargs) -> Food:
        """Fügt neues Lebensmittel hinzu"""
        with self.get_session() as session:
            food = Food(
                name=name,
                calories_per_100g=calories,
                protein_per_100g=protein,
                carbs_per_100g=carbs,
                fat_per_100g=fat,
                **kwargs
            )
            session.add(food)
            session.commit()
            session.refresh(food)
            return self._detach(session, food)

    def search_foods(self, query: str, limit: int = 20) -> List[Food]:
        """Sucht Lebensmittel nach Name"""
        with self.get_session() as session:
            foods = session.query(Food).filter(
                Food.name.ilike(f"%{query}%")
            ).limit(limit).all()
            return self._detach_all(session, foods)

    def get_food_by_barcode(self, barcode: str) -> Optional[Food]:
        """Holt Lebensmittel nach Barcode"""
        with self.get_session() as session:
            food = session.query(Food).filter_by(barcode=barcode).first()
            return self._detach(session, food)

    def get_frequently_used_foods(self, user_id: int, limit: int = 10) -> List[Food]:
        """Holt häufig verwendete Lebensmittel"""
        with self.get_session() as session:
            subquery = session.query(
                MealItem.food_id,
                func.count(MealItem.id).label('usage_count')
            ).join(Meal).filter(
                Meal.user_id == user_id
            ).group_by(MealItem.food_id).subquery()

            foods = session.query(Food).join(
                subquery, Food.id == subquery.c.food_id
            ).order_by(desc(subquery.c.usage_count)).limit(limit).all()
            return self._detach_all(session, foods)

    # ==================== Meals ====================

    def create_meal(self, user_id: int, meal_type: MealType,
                    eaten_at: datetime = None, notes: str = None,
                    is_template: bool = False, template_name: str = None) -> Meal:
        """Erstellt eine neue Mahlzeit"""
        with self.get_session() as session:
            meal = Meal(
                user_id=user_id,
                meal_type=meal_type,
                eaten_at=eaten_at or datetime.now(),
                notes=notes,
                is_template=is_template,
                template_name=template_name,
            )
            session.add(meal)
            session.commit()
            session.refresh(meal)
            return self._detach(session, meal)

    def add_item_to_meal(self, meal_id: int, food_id: int, quantity_g: float) -> MealItem:
        """Fügt ein Lebensmittel zu einer Mahlzeit hinzu"""
        with self.get_session() as session:
            food = session.query(Food).filter_by(id=food_id).first()
            if not food:
                raise ValueError(f"Lebensmittel {food_id} nicht gefunden")

            # Berechne Nährwerte
            factor = quantity_g / 100
            item = MealItem(
                meal_id=meal_id,
                food_id=food_id,
                quantity_g=quantity_g,
                calories=(food.calories_per_100g or 0) * factor,
                protein=(food.protein_per_100g or 0) * factor,
                carbs=(food.carbs_per_100g or 0) * factor,
                fat=(food.fat_per_100g or 0) * factor,
            )
            session.add(item)

            # Update Mahlzeiten-Summen
            meal = session.query(Meal).filter_by(id=meal_id).first()
            meal.total_calories += item.calories
            meal.total_protein += item.protein
            meal.total_carbs += item.carbs
            meal.total_fat += item.fat

            session.commit()
            session.refresh(item)
            return self._detach(session, item)

    def get_meals_for_date(self, user_id: int, target_date: date) -> List[Meal]:
        """Holt alle Mahlzeiten für ein Datum"""
        with self.get_session() as session:
            start = datetime.combine(target_date, datetime.min.time())
            end = datetime.combine(target_date, datetime.max.time())
            meals = session.query(Meal).filter(
                Meal.user_id == user_id,
                Meal.eaten_at >= start,
                Meal.eaten_at <= end,
                Meal.is_template == False
            ).order_by(Meal.eaten_at).all()
            return self._detach_all(session, meals)

    def get_meal_templates(self, user_id: int) -> List[Meal]:
        """Holt gespeicherte Mahlzeiten-Vorlagen"""
        with self.get_session() as session:
            meals = session.query(Meal).filter_by(
                user_id=user_id, is_template=True
            ).all()
            return self._detach_all(session, meals)

    def get_daily_nutrition_summary(self, user_id: int, target_date: date) -> dict:
        """Berechnet Tagesübersicht der Nährwerte"""
        with self.get_session() as session:
            start = datetime.combine(target_date, datetime.min.time())
            end = datetime.combine(target_date, datetime.max.time())

            result = session.query(
                func.sum(Meal.total_calories).label('calories'),
                func.sum(Meal.total_protein).label('protein'),
                func.sum(Meal.total_carbs).label('carbs'),
                func.sum(Meal.total_fat).label('fat'),
            ).filter(
                Meal.user_id == user_id,
                Meal.eaten_at >= start,
                Meal.eaten_at <= end,
                Meal.is_template == False
            ).first()

            return {
                'calories': result.calories or 0,
                'protein': result.protein or 0,
                'carbs': result.carbs or 0,
                'fat': result.fat or 0,
            }

    # ==================== Preferences ====================

    def add_food_preference(self, user_id: int, preference_type: PreferenceType,
                            food_id: int = None, category: str = None,
                            ingredient: str = None, notes: str = None) -> FoodPreference:
        """Fügt eine Essensvorliebe hinzu"""
        with self.get_session() as session:
            pref = FoodPreference(
                user_id=user_id,
                preference_type=preference_type,
                food_id=food_id,
                category=category,
                ingredient=ingredient,
                notes=notes,
            )
            session.add(pref)
            session.commit()
            session.refresh(pref)
            return self._detach(session, pref)

    def get_user_preferences(self, user_id: int) -> List[FoodPreference]:
        """Holt alle Vorlieben eines Benutzers"""
        with self.get_session() as session:
            prefs = session.query(FoodPreference).filter_by(user_id=user_id).all()
            return self._detach_all(session, prefs)

    def get_preferences_by_type(self, user_id: int,
                                pref_type: PreferenceType) -> List[FoodPreference]:
        """Holt Vorlieben nach Typ"""
        with self.get_session() as session:
            prefs = session.query(FoodPreference).filter_by(
                user_id=user_id, preference_type=pref_type
            ).all()
            return self._detach_all(session, prefs)

    def delete_preference(self, preference_id: int) -> bool:
        """Löscht eine Vorliebe"""
        with self.get_session() as session:
            pref = session.query(FoodPreference).filter_by(id=preference_id).first()
            if pref:
                session.delete(pref)
                session.commit()
                return True
            return False

    # ==================== Dietary Restrictions ====================

    def set_dietary_restriction(self, user_id: int, restriction_type: str) -> DietaryRestriction:
        """Setzt eine Ernährungseinschränkung"""
        with self.get_session() as session:
            # Prüfen ob bereits vorhanden
            existing = session.query(DietaryRestriction).filter_by(
                user_id=user_id, restriction_type=restriction_type
            ).first()
            if existing:
                existing.is_active = True
                session.commit()
                return self._detach(session, existing)

            restriction = DietaryRestriction(
                user_id=user_id,
                restriction_type=restriction_type,
            )
            session.add(restriction)
            session.commit()
            session.refresh(restriction)
            return self._detach(session, restriction)

    def get_dietary_restrictions(self, user_id: int) -> List[DietaryRestriction]:
        """Holt aktive Ernährungseinschränkungen"""
        with self.get_session() as session:
            restrictions = session.query(DietaryRestriction).filter_by(
                user_id=user_id, is_active=True
            ).all()
            return self._detach_all(session, restrictions)

    # ==================== Feedback ====================

    def add_meal_feedback(self, user_id: int, meal_id: int = None,
                          energy_level: int = None, satiety_level: int = None,
                          wellbeing: int = None, digestion: int = None,
                          notes: str = None) -> MealFeedback:
        """Fügt Feedback zu einer Mahlzeit hinzu"""
        with self.get_session() as session:
            feedback = MealFeedback(
                user_id=user_id,
                meal_id=meal_id,
                energy_level=energy_level,
                satiety_level=satiety_level,
                wellbeing=wellbeing,
                digestion=digestion,
                notes=notes,
            )
            session.add(feedback)
            session.commit()
            session.refresh(feedback)
            return self._detach(session, feedback)

    # ==================== AI Recommendations ====================

    def save_ai_recommendation(self, user_id: int, recommendation_type: str,
                               content: str, context_data: dict = None) -> AIRecommendation:
        """Speichert eine KI-Empfehlung"""
        with self.get_session() as session:
            rec = AIRecommendation(
                user_id=user_id,
                recommendation_type=recommendation_type,
                content=content,
                context_data=context_data,
            )
            session.add(rec)
            session.commit()
            session.refresh(rec)
            return self._detach(session, rec)

    def get_recent_recommendations(self, user_id: int, days: int = 7) -> List[AIRecommendation]:
        """Holt die letzten Empfehlungen"""
        with self.get_session() as session:
            since = date.today() - timedelta(days=days)
            recs = session.query(AIRecommendation).filter(
                AIRecommendation.user_id == user_id,
                AIRecommendation.recommendation_date >= since
            ).order_by(desc(AIRecommendation.created_at)).all()
            return self._detach_all(session, recs)
