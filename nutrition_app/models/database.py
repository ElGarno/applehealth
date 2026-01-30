"""
SQLAlchemy Datenbank-Modelle für die Nutrition App
"""
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Date,
    Boolean, Text, ForeignKey, Enum as SQLEnum, JSON, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class TrainingGoal(str, Enum):
    """Trainingsziele"""
    ABNEHMEN = "abnehmen"
    MUSKELAUFBAU = "muskelaufbau"
    ERHALT = "erhalt"
    AUSDAUER = "ausdauer"
    CUSTOM = "custom"  # Für spezifisches Wunschgewicht/Körperfett


class MealType(str, Enum):
    """Mahlzeitentypen"""
    FRUEHSTUECK = "frühstück"
    MITTAGESSEN = "mittagessen"
    ABENDESSEN = "abendessen"
    SNACK = "snack"


class PreferenceType(str, Enum):
    """Typ der Vorliebe"""
    LIEBLING = "liebling"
    NEUTRAL = "neutral"
    ABNEIGUNG = "abneigung"
    ALLERGIE = "allergie"


# ==================== Benutzer & Ziele ====================

class UserProfile(Base):
    """Benutzerprofil mit Grunddaten"""
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    birth_date = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)  # männlich, weiblich, divers
    height_cm = Column(Float, nullable=True)  # Körpergröße in cm
    activity_level = Column(String(50), default="moderat")  # sedentär, leicht, moderat, aktiv, sehr_aktiv

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    goals = relationship("UserGoal", back_populates="user", cascade="all, delete-orphan")
    body_measurements = relationship("BodyMeasurement", back_populates="user", cascade="all, delete-orphan")
    food_preferences = relationship("FoodPreference", back_populates="user", cascade="all, delete-orphan")
    meals = relationship("Meal", back_populates="user", cascade="all, delete-orphan")


class UserGoal(Base):
    """Trainingsziele des Benutzers"""
    __tablename__ = "user_goals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)

    goal_type = Column(SQLEnum(TrainingGoal), nullable=False)

    # Zielwerte (optional, je nach Ziel)
    target_weight_kg = Column(Float, nullable=True)
    target_body_fat_percent = Column(Float, nullable=True)
    target_muscle_mass_kg = Column(Float, nullable=True)

    # Zeitrahmen
    target_date = Column(Date, nullable=True)

    # Kalorienziel (wird berechnet oder manuell gesetzt)
    daily_calorie_target = Column(Integer, nullable=True)
    protein_target_g = Column(Integer, nullable=True)
    carbs_target_g = Column(Integer, nullable=True)
    fat_target_g = Column(Integer, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("UserProfile", back_populates="goals")


# ==================== Körperdaten ====================

class BodyMeasurement(Base):
    """Körpermessungen über Zeit"""
    __tablename__ = "body_measurements"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    measured_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    weight_kg = Column(Float, nullable=True)
    body_fat_percent = Column(Float, nullable=True)
    muscle_mass_kg = Column(Float, nullable=True)
    water_percent = Column(Float, nullable=True)
    bmi = Column(Float, nullable=True)  # Wird berechnet

    # Zusätzliche Messungen
    waist_cm = Column(Float, nullable=True)
    hip_cm = Column(Float, nullable=True)
    chest_cm = Column(Float, nullable=True)

    notes = Column(Text, nullable=True)
    source = Column(String(50), default="manual")  # manual, apple_health, scale_sync

    # Relationship
    user = relationship("UserProfile", back_populates="body_measurements")

    __table_args__ = (
        UniqueConstraint('user_id', 'measured_at', name='unique_measurement_time'),
    )


# ==================== Lebensmittel & Mahlzeiten ====================

class Food(Base):
    """Lebensmittel-Datenbank"""
    __tablename__ = "foods"

    id = Column(Integer, primary_key=True)

    # Identifikation
    name = Column(String(200), nullable=False)
    brand = Column(String(100), nullable=True)
    barcode = Column(String(50), nullable=True, unique=True)
    openfoodfacts_id = Column(String(100), nullable=True)

    # Nährwerte pro 100g
    calories_per_100g = Column(Float, nullable=True)
    protein_per_100g = Column(Float, nullable=True)
    carbs_per_100g = Column(Float, nullable=True)
    fat_per_100g = Column(Float, nullable=True)
    fiber_per_100g = Column(Float, nullable=True)
    sugar_per_100g = Column(Float, nullable=True)
    salt_per_100g = Column(Float, nullable=True)
    saturated_fat_per_100g = Column(Float, nullable=True)

    # Standard-Portionsgröße
    default_portion_g = Column(Float, default=100.0)
    portion_description = Column(String(100), nullable=True)  # z.B. "1 Scheibe", "1 Tasse"

    # Kategorisierung
    category = Column(String(100), nullable=True)
    tags = Column(JSON, default=list)  # ["vegan", "glutenfrei", etc.]

    # Quelle & Zeitstempel
    source = Column(String(50), default="manual")  # manual, openfoodfacts, user_created
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    meal_items = relationship("MealItem", back_populates="food")
    preferences = relationship("FoodPreference", back_populates="food")


class Meal(Base):
    """Eine Mahlzeit (Frühstück, Mittag, etc.)"""
    __tablename__ = "meals"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)

    meal_type = Column(SQLEnum(MealType), nullable=False)
    eaten_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Berechnete Gesamtwerte
    total_calories = Column(Float, default=0)
    total_protein = Column(Float, default=0)
    total_carbs = Column(Float, default=0)
    total_fat = Column(Float, default=0)

    notes = Column(Text, nullable=True)

    # Für Favoriten/Templates
    is_template = Column(Boolean, default=False)
    template_name = Column(String(100), nullable=True)  # z.B. "Meine Overnight Oats"

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("UserProfile", back_populates="meals")
    items = relationship("MealItem", back_populates="meal", cascade="all, delete-orphan")


class MealItem(Base):
    """Einzelnes Lebensmittel in einer Mahlzeit"""
    __tablename__ = "meal_items"

    id = Column(Integer, primary_key=True)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False)
    food_id = Column(Integer, ForeignKey("foods.id"), nullable=False)

    quantity_g = Column(Float, nullable=False)  # Menge in Gramm

    # Berechnete Werte für diese Portion
    calories = Column(Float, default=0)
    protein = Column(Float, default=0)
    carbs = Column(Float, default=0)
    fat = Column(Float, default=0)

    # Relationships
    meal = relationship("Meal", back_populates="items")
    food = relationship("Food", back_populates="meal_items")


# ==================== Vorlieben ====================

class FoodPreference(Base):
    """Essensvorlieben des Benutzers"""
    __tablename__ = "food_preferences"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)

    # Kann auf spezifisches Lebensmittel oder Kategorie verweisen
    food_id = Column(Integer, ForeignKey("foods.id"), nullable=True)
    category = Column(String(100), nullable=True)  # z.B. "Fisch", "Hülsenfrüchte"
    ingredient = Column(String(100), nullable=True)  # z.B. "Laktose", "Nüsse"

    preference_type = Column(SQLEnum(PreferenceType), nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("UserProfile", back_populates="food_preferences")
    food = relationship("Food", back_populates="preferences")


class DietaryRestriction(Base):
    """Ernährungsform und Einschränkungen"""
    __tablename__ = "dietary_restrictions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)

    restriction_type = Column(String(50), nullable=False)  # vegetarisch, vegan, pescetarisch, etc.
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== KI-Lernphase ====================

class MealFeedback(Base):
    """Feedback zu Mahlzeiten für ML-Lernen"""
    __tablename__ = "meal_feedback"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=True)

    feedback_date = Column(Date, nullable=False, default=date.today)

    # Subjektives Feedback
    energy_level = Column(Integer, nullable=True)  # 1-5 Skala
    satiety_level = Column(Integer, nullable=True)  # 1-5 Sättigungsgefühl
    wellbeing = Column(Integer, nullable=True)  # 1-5 Allgemeines Wohlbefinden
    digestion = Column(Integer, nullable=True)  # 1-5 Verdauung

    # Optionale Notizen
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class AIRecommendation(Base):
    """KI-generierte Empfehlungen zur Nachverfolgung"""
    __tablename__ = "ai_recommendations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)

    recommendation_date = Column(Date, nullable=False, default=date.today)
    recommendation_type = Column(String(50), nullable=False)  # meal_plan, tip, adjustment

    content = Column(Text, nullable=False)  # JSON oder Text der Empfehlung

    # Tracking ob befolgt
    was_followed = Column(Boolean, nullable=True)
    user_rating = Column(Integer, nullable=True)  # 1-5

    # Kontext für Lernen
    context_data = Column(JSON, nullable=True)  # Aktivitätsdaten, Körperdaten zum Zeitpunkt

    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== ML Prognose Tracking ====================

class ProgressPrediction(Base):
    """ML-Modell Vorhersagen und tatsächliche Ergebnisse"""
    __tablename__ = "progress_predictions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)

    prediction_date = Column(Date, nullable=False)
    target_date = Column(Date, nullable=False)

    # Vorhersagen
    predicted_weight = Column(Float, nullable=True)
    predicted_body_fat = Column(Float, nullable=True)

    # Tatsächliche Werte (später eingetragen)
    actual_weight = Column(Float, nullable=True)
    actual_body_fat = Column(Float, nullable=True)

    # Model Metadaten
    model_version = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)

    # Features die für Vorhersage genutzt wurden
    feature_data = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== Datenbank Setup ====================

def init_database(connection_string: str):
    """Initialisiert die Datenbank und erstellt alle Tabellen"""
    engine = create_engine(connection_string)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    """Erstellt eine neue Datenbank-Session"""
    Session = sessionmaker(bind=engine)
    return Session()
