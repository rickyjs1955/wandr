"""
Garment Analysis Service

Combines garment segmentation and color extraction to generate
complete outfit descriptors for person re-identification.

Phase 3.2 implementation with basic garment type classification.
"""
import logging
from typing import Dict, List, Optional
import numpy as np
from dataclasses import dataclass, asdict

from app.cv.garment_segmenter import GarmentSegmenter, GarmentRegions, create_segmenter
from app.cv.color_extractor import ColorExtractor, ColorDescriptor, create_color_extractor
from app.cv.garment_type_classifier import GarmentTypeClassifier, create_type_classifier

logger = logging.getLogger(__name__)


@dataclass
class GarmentDescriptor:
    """Single garment description (top, bottom, or shoes)."""
    type: str  # "top", "bottom", or "shoes"
    color: str  # Color name (e.g., "blue", "red")
    lab: tuple  # LAB color values (L, a, b)
    histogram: list  # Color histogram
    confidence: float  # 0-1, confidence in this garment's analysis
    region_quality: float  # 0-1, quality of segmentation


@dataclass
class OutfitDescriptor:
    """Complete outfit description for a person."""
    top: GarmentDescriptor
    bottom: GarmentDescriptor
    shoes: GarmentDescriptor
    overall_quality: float  # 0-1, overall outfit analysis quality
    segmentation_method: str  # "thirds" or "pose"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "top": {
                "type": self.top.type,
                "color": self.top.color,
                "lab": list(self.top.lab),
                "histogram": self.top.histogram,
                "confidence": self.top.confidence
            },
            "bottom": {
                "type": self.bottom.type,
                "color": self.bottom.color,
                "lab": list(self.bottom.lab),
                "histogram": self.bottom.histogram,
                "confidence": self.bottom.confidence
            },
            "shoes": {
                "type": self.shoes.type,
                "color": self.shoes.color,
                "lab": list(self.shoes.lab),
                "histogram": self.shoes.histogram,
                "confidence": self.shoes.confidence
            },
            "overall_quality": self.overall_quality,
            "segmentation_method": self.segmentation_method
        }


class GarmentAnalyzer:
    """
    Analyze person crops to extract complete outfit descriptors.

    Workflow:
    1. Segment person crop into top/bottom/shoes regions
    2. Extract color from each region
    3. Classify garment type (simplified for Phase 3.2)
    4. Generate complete outfit descriptor

    Phase 3.2 Implementation:
    - Basic garment type classification using heuristics
    - Color-based type inference (shirt/tee, pants/jeans, sneakers/boots)
    - Confidence scores for type predictions
    - Robust color extraction with graceful degradation
    """

    def __init__(
        self,
        segmenter: Optional[GarmentSegmenter] = None,
        color_extractor: Optional[ColorExtractor] = None,
        type_classifier: Optional[GarmentTypeClassifier] = None
    ):
        """
        Initialize garment analyzer.

        Args:
            segmenter: GarmentSegmenter instance (creates default if None)
            color_extractor: ColorExtractor instance (creates default if None)
            type_classifier: GarmentTypeClassifier instance (creates default if None)
        """
        self.segmenter = segmenter or create_segmenter()
        self.color_extractor = color_extractor or create_color_extractor()
        self.type_classifier = type_classifier or create_type_classifier()

    def analyze(self, person_crop: np.ndarray) -> OutfitDescriptor:
        """
        Analyze person crop to extract outfit descriptor.

        Args:
            person_crop: RGB image of person (H x W x 3)

        Returns:
            OutfitDescriptor with top/bottom/shoes information

        Raises:
            ValueError: If person crop is invalid or analysis fails
        """
        # Step 1: Segment into garment regions
        try:
            regions = self.segmenter.segment(person_crop)
        except Exception as e:
            logger.error(f"Segmentation failed: {e}")
            raise ValueError(f"Failed to segment person crop: {e}")

        # Step 2: Extract color from each region
        try:
            top_color = self.color_extractor.extract(regions.top)
            bottom_color = self.color_extractor.extract(regions.bottom)
            shoes_color = self.color_extractor.extract(regions.shoes)
        except Exception as e:
            logger.error(f"Color extraction failed: {e}")
            raise ValueError(f"Failed to extract colors: {e}")

        # Step 3: Classify garment types and create descriptors
        # Use heuristic-based type classifier (Phase 3.2)
        top_h, top_w = regions.top.shape[:2]
        top_aspect = top_w / max(top_h, 1)
        top_type_result = self.type_classifier.classify_top(
            top_color.color_name,
            top_color.lab,
            top_aspect
        )

        bottom_h, bottom_w = regions.bottom.shape[:2]
        bottom_aspect = bottom_w / max(bottom_h, 1)
        bottom_type_result = self.type_classifier.classify_bottom(
            bottom_color.color_name,
            bottom_color.lab,
            bottom_aspect
        )

        shoes_h, shoes_w = regions.shoes.shape[:2]
        shoes_aspect = shoes_w / max(shoes_h, 1)
        shoes_type_result = self.type_classifier.classify_shoes(
            shoes_color.color_name,
            shoes_color.lab,
            shoes_aspect
        )

        # Combine color confidence and type confidence
        top_desc = GarmentDescriptor(
            type=top_type_result["type"],
            color=top_color.color_name,
            lab=top_color.lab,
            histogram=top_color.histogram,
            confidence=min(top_color.confidence * top_type_result["confidence"], 1.0),
            region_quality=regions.quality_score
        )

        bottom_desc = GarmentDescriptor(
            type=bottom_type_result["type"],
            color=bottom_color.color_name,
            lab=bottom_color.lab,
            histogram=bottom_color.histogram,
            confidence=min(bottom_color.confidence * bottom_type_result["confidence"], 1.0),
            region_quality=regions.quality_score
        )

        shoes_desc = GarmentDescriptor(
            type=shoes_type_result["type"],
            color=shoes_color.color_name,
            lab=shoes_color.lab,
            histogram=shoes_color.histogram,
            confidence=min(shoes_color.confidence * shoes_type_result["confidence"], 1.0),
            region_quality=regions.quality_score
        )

        # Step 4: Calculate overall quality
        overall_quality = self._calculate_overall_quality(
            regions, top_color, bottom_color, shoes_color
        )

        return OutfitDescriptor(
            top=top_desc,
            bottom=bottom_desc,
            shoes=shoes_desc,
            overall_quality=overall_quality,
            segmentation_method=regions.method
        )

    def _calculate_overall_quality(
        self,
        regions: GarmentRegions,
        top_color: ColorDescriptor,
        bottom_color: ColorDescriptor,
        shoes_color: ColorDescriptor
    ) -> float:
        """
        Calculate overall outfit analysis quality.

        Combines:
        - Segmentation quality
        - Color extraction confidence for each garment

        Args:
            regions: Segmented garment regions
            top_color: Top garment color descriptor
            bottom_color: Bottom garment color descriptor
            shoes_color: Shoes color descriptor

        Returns:
            Overall quality score 0-1
        """
        # Weighted average of all quality indicators
        segmentation_quality = regions.quality_score
        avg_color_confidence = (
            top_color.confidence +
            bottom_color.confidence +
            shoes_color.confidence
        ) / 3.0

        # Segmentation quality is more important (60% weight)
        # because poor segmentation ruins color extraction
        overall = 0.6 * segmentation_quality + 0.4 * avg_color_confidence

        return float(overall)

    def analyze_batch(
        self,
        person_crops: List[np.ndarray]
    ) -> List[Optional[OutfitDescriptor]]:
        """
        Analyze multiple person crops in batch.

        Args:
            person_crops: List of RGB person crop images

        Returns:
            List of OutfitDescriptor (None for failed analyses)
        """
        results = []

        for i, crop in enumerate(person_crops):
            try:
                descriptor = self.analyze(crop)
                results.append(descriptor)
            except Exception as e:
                logger.warning(f"Failed to analyze crop {i}: {e}")
                results.append(None)

        return results

    def validate_accuracy(
        self,
        person_crops: List[np.ndarray],
        min_quality: float = 0.5
    ) -> Dict[str, float]:
        """
        Validate garment analysis accuracy on test set.

        Used for Phase 3.2 checkpoint (Day 6):
        - Test on 50+ diverse person crops
        - Calculate success rate (overall_quality > min_quality)
        - Determine if segmentation upgrade needed

        Args:
            person_crops: List of person crop images for testing
            min_quality: Minimum quality threshold for success

        Returns:
            {
                "success_rate": 0.82,
                "avg_quality": 0.75,
                "high_quality_rate": 0.68,  # quality > 0.7
                "failed_count": 9,
                "total_crops": 50
            }
        """
        qualities = []
        failed = 0

        for crop in person_crops:
            try:
                descriptor = self.analyze(crop)
                qualities.append(descriptor.overall_quality)
            except Exception as e:
                logger.warning(f"Analysis failed: {e}")
                failed += 1
                qualities.append(0.0)

        qualities_array = np.array(qualities)
        success_rate = np.mean(qualities_array > min_quality)
        high_quality_rate = np.mean(qualities_array > 0.7)
        avg_quality = np.mean(qualities_array)

        result = {
            "success_rate": float(success_rate),
            "avg_quality": float(avg_quality),
            "high_quality_rate": float(high_quality_rate),
            "failed_count": int(failed),
            "total_crops": len(person_crops)
        }

        # Log validation summary
        logger.info(
            f"Garment analysis validation: "
            f"success_rate={result['success_rate']:.2%}, "
            f"avg_quality={result['avg_quality']:.3f}, "
            f"failed={result['failed_count']}/{result['total_crops']}"
        )

        return result


def create_garment_analyzer() -> GarmentAnalyzer:
    """
    Factory function to create garment analyzer with default components.

    Returns:
        GarmentAnalyzer instance
    """
    segmenter = create_segmenter()
    color_extractor = create_color_extractor()
    type_classifier = create_type_classifier()
    return GarmentAnalyzer(segmenter, color_extractor, type_classifier)
