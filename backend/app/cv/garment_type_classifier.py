"""
Garment Type Classification Module

Phase 3.2 implementation: Basic heuristic-based classification
Future: Replace with ML-based fashion attribute model

Provides simple type inference based on color and region characteristics.
"""
import logging
from typing import Dict
import numpy as np

logger = logging.getLogger(__name__)


class GarmentTypeClassifier:
    """
    Classify garment types using heuristics.

    Phase 3.2 Approach:
    - Uses color, brightness, and region position for basic inference
    - No ML model required (deferred to future phase)
    - Provides confidence scores for each prediction

    Garment Types:
    - Top: jacket, coat, shirt, tee, blouse, sweater, dress
    - Bottom: pants, jeans, shorts, skirt, dress
    - Shoes: sneakers, boots, sandals, loafers, heels
    """

    # Color-based type hints
    TOP_TYPE_HINTS = {
        "formal_colors": ["white", "black", "gray", "blue"],  # → shirt/blouse
        "casual_colors": ["red", "orange", "yellow", "green"],  # → tee/sweater
        "outerwear_colors": ["black", "brown", "gray", "blue"],  # → jacket/coat
    }

    BOTTOM_TYPE_HINTS = {
        "dark_colors": ["black", "blue", "brown", "gray"],  # → pants/jeans
        "light_colors": ["white", "yellow", "pink"],  # → shorts/skirt
    }

    SHOES_TYPE_HINTS = {
        "athletic_colors": ["white", "black", "gray"],  # → sneakers
        "formal_colors": ["black", "brown"],  # → loafers/heels
        "casual_colors": ["brown", "orange"],  # → sandals/boots
    }

    def classify_top(
        self,
        color_name: str,
        lab: tuple,
        region_aspect_ratio: float
    ) -> Dict[str, float]:
        """
        Classify top garment type using heuristics.

        Args:
            color_name: Color name (e.g., "blue", "red")
            lab: LAB color values (L, a, b)
            region_aspect_ratio: Region width/height ratio

        Returns:
            {"type": "shirt", "confidence": 0.65}
        """
        L, a, b = lab

        # Default to generic "top"
        garment_type = "top"
        confidence = 0.50

        # Heuristic 1: Dark colors + formal context → shirt/blouse
        if color_name in self.TOP_TYPE_HINTS["formal_colors"] and L < 60:
            garment_type = "shirt"
            confidence = 0.65

        # Heuristic 2: Bright/casual colors → tee
        elif color_name in self.TOP_TYPE_HINTS["casual_colors"] and L > 50:
            garment_type = "tee"
            confidence = 0.60

        # Heuristic 3: Very dark (L < 40) + blue/black/gray → jacket
        elif L < 40 and color_name in ["black", "blue", "gray", "brown"]:
            garment_type = "jacket"
            confidence = 0.55

        return {
            "type": garment_type,
            "confidence": confidence
        }

    def classify_bottom(
        self,
        color_name: str,
        lab: tuple,
        region_aspect_ratio: float
    ) -> Dict[str, float]:
        """
        Classify bottom garment type using heuristics.

        Args:
            color_name: Color name
            lab: LAB color values
            region_aspect_ratio: Region width/height ratio

        Returns:
            {"type": "pants", "confidence": 0.70}
        """
        L, a, b = lab

        # Default to generic "bottom"
        garment_type = "bottom"
        confidence = 0.50

        # Heuristic 1: Dark blue → jeans
        if color_name == "blue" and L < 50:
            garment_type = "jeans"
            confidence = 0.70

        # Heuristic 2: Dark colors (black/brown/gray) → pants
        elif color_name in ["black", "brown", "gray"] and L < 60:
            garment_type = "pants"
            confidence = 0.65

        # Heuristic 3: Light colors + high brightness → shorts/skirt
        elif L > 60:
            garment_type = "shorts"  # Could also be skirt, but shorts more common
            confidence = 0.55

        return {
            "type": garment_type,
            "confidence": confidence
        }

    def classify_shoes(
        self,
        color_name: str,
        lab: tuple,
        region_aspect_ratio: float
    ) -> Dict[str, float]:
        """
        Classify shoe type using heuristics.

        Args:
            color_name: Color name
            lab: LAB color values
            region_aspect_ratio: Region width/height ratio

        Returns:
            {"type": "sneakers", "confidence": 0.60}
        """
        L, a, b = lab

        # Default to generic "shoes"
        garment_type = "shoes"
        confidence = 0.50

        # Heuristic 1: White shoes → sneakers
        if color_name == "white" and L > 70:
            garment_type = "sneakers"
            confidence = 0.70

        # Heuristic 2: Black shoes + low brightness → loafers/formal
        elif color_name == "black" and L < 40:
            garment_type = "loafers"
            confidence = 0.60

        # Heuristic 3: Brown shoes → boots/casual
        elif color_name == "brown":
            garment_type = "boots"
            confidence = 0.55

        return {
            "type": garment_type,
            "confidence": confidence
        }


def create_type_classifier() -> GarmentTypeClassifier:
    """
    Factory function to create garment type classifier.

    Returns:
        GarmentTypeClassifier instance
    """
    return GarmentTypeClassifier()
