"""
Service für OpenFoodFacts API Integration
"""
import httpx
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class NutritionInfo:
    """Nährwertinformationen eines Lebensmittels"""
    name: str
    brand: Optional[str] = None
    barcode: Optional[str] = None

    # Nährwerte pro 100g
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    fiber: Optional[float] = None
    sugar: Optional[float] = None
    salt: Optional[float] = None
    saturated_fat: Optional[float] = None

    # Zusatzinfos
    serving_size: Optional[str] = None
    image_url: Optional[str] = None
    categories: List[str] = None
    nutriscore: Optional[str] = None

    def __post_init__(self):
        if self.categories is None:
            self.categories = []


class FoodAPIService:
    """Service für Lebensmittel-Suche via OpenFoodFacts"""

    BASE_URL = "https://world.openfoodfacts.org"
    SEARCH_URL = f"{BASE_URL}/cgi/search.pl"
    PRODUCT_URL = f"{BASE_URL}/api/v2/product"

    def __init__(self):
        self.client = httpx.Client(timeout=10.0)

    def __del__(self):
        self.client.close()

    def search_products(self, query: str, page: int = 1, page_size: int = 20,
                        country: str = "germany") -> List[NutritionInfo]:
        """
        Sucht nach Produkten in OpenFoodFacts

        Args:
            query: Suchbegriff
            page: Seitennummer
            page_size: Ergebnisse pro Seite
            country: Länderfilter

        Returns:
            Liste von NutritionInfo Objekten
        """
        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page": page,
            "page_size": page_size,
            "tagtype_0": "countries",
            "tag_contains_0": "contains",
            "tag_0": country,
            "fields": "product_name,brands,code,nutriments,serving_size,image_url,categories,nutriscore_grade",
        }

        try:
            response = self.client.get(self.SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            products = []
            for product in data.get("products", []):
                nutrition = self._parse_product(product)
                if nutrition:
                    products.append(nutrition)

            return products

        except httpx.HTTPError as e:
            logger.error(f"OpenFoodFacts Suche fehlgeschlagen: {e}")
            return []

    def get_product_by_barcode(self, barcode: str) -> Optional[NutritionInfo]:
        """
        Holt Produktinfos anhand des Barcodes

        Args:
            barcode: EAN/UPC Barcode

        Returns:
            NutritionInfo oder None
        """
        url = f"{self.PRODUCT_URL}/{barcode}"
        params = {
            "fields": "product_name,brands,code,nutriments,serving_size,image_url,categories,nutriscore_grade"
        }

        try:
            response = self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == 1 and "product" in data:
                return self._parse_product(data["product"])
            return None

        except httpx.HTTPError as e:
            logger.error(f"OpenFoodFacts Barcode-Abfrage fehlgeschlagen: {e}")
            return None

    def _parse_product(self, product: Dict[str, Any]) -> Optional[NutritionInfo]:
        """Parsed ein OpenFoodFacts Produkt in NutritionInfo"""
        name = product.get("product_name")
        if not name:
            return None

        nutriments = product.get("nutriments", {})

        # Kategorien parsen
        categories_str = product.get("categories", "")
        categories = [c.strip() for c in categories_str.split(",") if c.strip()] if categories_str else []

        return NutritionInfo(
            name=name,
            brand=product.get("brands"),
            barcode=product.get("code"),
            calories=self._get_nutriment(nutriments, "energy-kcal_100g"),
            protein=self._get_nutriment(nutriments, "proteins_100g"),
            carbs=self._get_nutriment(nutriments, "carbohydrates_100g"),
            fat=self._get_nutriment(nutriments, "fat_100g"),
            fiber=self._get_nutriment(nutriments, "fiber_100g"),
            sugar=self._get_nutriment(nutriments, "sugars_100g"),
            salt=self._get_nutriment(nutriments, "salt_100g"),
            saturated_fat=self._get_nutriment(nutriments, "saturated-fat_100g"),
            serving_size=product.get("serving_size"),
            image_url=product.get("image_url"),
            categories=categories,
            nutriscore=product.get("nutriscore_grade"),
        )

    def _get_nutriment(self, nutriments: dict, key: str) -> Optional[float]:
        """Holt einen Nährwert sicher aus dem nutriments dict"""
        value = nutriments.get(key)
        if value is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        return None


# Vordefinierte deutsche Grundnahrungsmittel für Schnelleingabe
COMMON_FOODS_DE = [
    NutritionInfo(
        name="Haferflocken",
        calories=372,
        protein=13.5,
        carbs=58.7,
        fat=7.0,
        fiber=10.0,
        categories=["Getreide", "Frühstück"],
    ),
    NutritionInfo(
        name="Apfel",
        calories=52,
        protein=0.3,
        carbs=14,
        fat=0.2,
        fiber=2.4,
        sugar=10,
        categories=["Obst"],
    ),
    NutritionInfo(
        name="Walnüsse",
        calories=654,
        protein=15,
        carbs=14,
        fat=65,
        fiber=6.5,
        categories=["Nüsse"],
    ),
    NutritionInfo(
        name="Vollmilch (3.5%)",
        calories=64,
        protein=3.3,
        carbs=4.8,
        fat=3.5,
        categories=["Milchprodukte"],
    ),
    NutritionInfo(
        name="Hühnerbrust",
        calories=165,
        protein=31,
        carbs=0,
        fat=3.6,
        categories=["Fleisch", "Geflügel"],
    ),
    NutritionInfo(
        name="Reis (gekocht)",
        calories=130,
        protein=2.7,
        carbs=28,
        fat=0.3,
        fiber=0.4,
        categories=["Getreide", "Beilage"],
    ),
    NutritionInfo(
        name="Lachs",
        calories=208,
        protein=20,
        carbs=0,
        fat=13,
        categories=["Fisch"],
    ),
    NutritionInfo(
        name="Ei (gekocht)",
        calories=155,
        protein=13,
        carbs=1.1,
        fat=11,
        categories=["Eier"],
    ),
    NutritionInfo(
        name="Banane",
        calories=89,
        protein=1.1,
        carbs=23,
        fat=0.3,
        fiber=2.6,
        sugar=12,
        categories=["Obst"],
    ),
    NutritionInfo(
        name="Vollkornbrot",
        calories=247,
        protein=8.5,
        carbs=41,
        fat=4.2,
        fiber=7,
        categories=["Brot", "Vollkorn"],
    ),
    NutritionInfo(
        name="Griechischer Joghurt",
        calories=97,
        protein=9,
        carbs=3.6,
        fat=5,
        categories=["Milchprodukte", "Joghurt"],
    ),
    NutritionInfo(
        name="Mandeln",
        calories=579,
        protein=21,
        carbs=22,
        fat=49,
        fiber=12.5,
        categories=["Nüsse"],
    ),
    NutritionInfo(
        name="Brokkoli",
        calories=34,
        protein=2.8,
        carbs=7,
        fat=0.4,
        fiber=2.6,
        categories=["Gemüse"],
    ),
    NutritionInfo(
        name="Süßkartoffel",
        calories=86,
        protein=1.6,
        carbs=20,
        fat=0.1,
        fiber=3,
        categories=["Gemüse", "Beilage"],
    ),
    NutritionInfo(
        name="Quinoa (gekocht)",
        calories=120,
        protein=4.4,
        carbs=21,
        fat=1.9,
        fiber=2.8,
        categories=["Getreide", "Beilage"],
    ),
]
