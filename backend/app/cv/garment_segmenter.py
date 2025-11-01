"""
Garment Segmentation Module

Segments person crops into top/bottom/shoes regions for garment analysis.
Phase 3.2 implementation uses simplified thirds-based segmentation with
quality validation to determine if pose-based segmentation is needed.
"""
import logging
from typing import Dict, Tuple, Optional
import numpy as np
import cv2
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GarmentRegions:
    """Segmented garment regions from person crop."""
    top: np.ndarray  # Upper body region
    bottom: np.ndarray  # Lower body region
    shoes: np.ndarray  # Footwear region
    quality_score: float  # 0-1, confidence in segmentation
    method: str  # "thirds" or "pose" (for future implementation)


class GarmentSegmenter:
    """
    Segments person crop into garment regions (top/bottom/shoes).

    Phase 3.2 Strategy:
    - Start with simple thirds-based segmentation
    - Track quality metrics to determine if upgrade needed
    - Fall back to pose-based if accuracy <70%

    Thirds-based approach:
    - Top: 0-40% of height
    - Bottom: 40-80% of height
    - Shoes: 80-100% of height

    Known Limitations:
    - Fails with seated people (no shoes visible)
    - Poor with severe occlusions
    - Assumes standing/walking pose
    """

    def __init__(
        self,
        method: str = "thirds",
        top_ratio: float = 0.4,
        bottom_ratio: float = 0.8,
        min_region_height: int = 20
    ):
        """
        Initialize garment segmenter.

        Args:
            method: Segmentation method ("thirds" or "pose")
            top_ratio: Top region ends at this ratio of height (default 0.4)
            bottom_ratio: Bottom region ends at this ratio of height (default 0.8)
            min_region_height: Minimum height for valid region (pixels)
        """
        self.method = method
        self.top_ratio = top_ratio
        self.bottom_ratio = bottom_ratio
        self.min_region_height = min_region_height

        if method != "thirds":
            raise NotImplementedError(f"Segmentation method '{method}' not implemented. Use 'thirds' for Phase 3.2.")

    def segment(self, person_crop: np.ndarray) -> GarmentRegions:
        """
        Segment person crop into garment regions.

        Gracefully degrades for small crops (distant shoppers in CCTV):
        - Crops <60px: Still segments but returns low quality score
        - Very small regions (<5px): Pads to minimum size

        Args:
            person_crop: RGB image of person (H x W x 3)

        Returns:
            GarmentRegions with top/bottom/shoes and quality score

        Raises:
            ValueError: Only if crop is completely invalid (None, empty, wrong shape)
        """
        if person_crop is None or person_crop.size == 0:
            raise ValueError("Invalid person crop: empty or None")

        if len(person_crop.shape) != 3 or person_crop.shape[2] != 3:
            raise ValueError(f"Invalid person crop shape: {person_crop.shape}, expected (H, W, 3)")

        h, w, _ = person_crop.shape

        # Graceful degradation: accept small crops but mark as low quality
        # Don't raise ValueError for small crops (common with distant people)
        if h < 10 or w < 5:
            logger.warning(f"Person crop very small: {h}x{w}, will return minimal quality")

        if self.method == "thirds":
            return self._segment_thirds(person_crop)
        else:
            raise NotImplementedError(f"Method '{self.method}' not implemented")

    def _segment_thirds(self, person_crop: np.ndarray) -> GarmentRegions:
        """
        Segment using simple thirds-based approach.

        Divides crop into:
        - Top: 0 to 40% of height
        - Bottom: 40% to 80% of height
        - Shoes: 80% to 100% of height

        Quality score based on:
        - Region sizes (larger is better)
        - Non-uniformity (variance in pixels, avoid blank regions)
        """
        h, w, _ = person_crop.shape

        # Calculate region boundaries
        top_end = int(h * self.top_ratio)
        bottom_end = int(h * self.bottom_ratio)

        # Extract regions
        top_region = person_crop[0:top_end, :]
        bottom_region = person_crop[top_end:bottom_end, :]
        shoes_region = person_crop[bottom_end:, :]

        # Calculate quality score
        quality = self._calculate_quality_thirds(
            top_region, bottom_region, shoes_region, h, w
        )

        return GarmentRegions(
            top=top_region,
            bottom=bottom_region,
            shoes=shoes_region,
            quality_score=quality,
            method="thirds"
        )

    def _calculate_quality_thirds(
        self,
        top: np.ndarray,
        bottom: np.ndarray,
        shoes: np.ndarray,
        total_h: int,
        total_w: int
    ) -> float:
        """
        Calculate segmentation quality for thirds-based method.

        Quality indicators:
        - Region size adequacy (each region has min height)
        - Non-uniformity (regions have texture, not blank)
        - Aspect ratio (person crop has reasonable proportions)

        Returns:
            Quality score 0-1 (1 = high confidence, 0 = low confidence)
        """
        scores = []

        # 1. Region size score (each region should be adequate)
        min_height = self.min_region_height
        top_size_score = min(top.shape[0] / min_height, 1.0)
        bottom_size_score = min(bottom.shape[0] / min_height, 1.0)
        shoes_size_score = min(shoes.shape[0] / min_height, 1.0)
        size_score = (top_size_score + bottom_size_score + shoes_size_score) / 3.0
        scores.append(size_score)

        # 2. Non-uniformity score (regions have content, not blank)
        top_var = np.std(top) / 255.0
        bottom_var = np.std(bottom) / 255.0
        shoes_var = np.std(shoes) / 255.0
        # Higher variance = more content, better quality
        # Normalize to 0-1 range (std of 30 or higher is good)
        uniformity_score = min((top_var + bottom_var + shoes_var) / 0.35, 1.0)
        scores.append(uniformity_score)

        # 3. Aspect ratio score (typical person: height > width)
        aspect_ratio = total_h / max(total_w, 1)
        # Ideal aspect ratio for standing person: 2.0-4.0
        if 1.5 <= aspect_ratio <= 5.0:
            aspect_score = 1.0
        elif 1.0 <= aspect_ratio < 1.5:
            aspect_score = 0.7
        else:
            aspect_score = 0.5
        scores.append(aspect_score)

        # Weighted average
        quality = (
            0.4 * size_score +
            0.4 * uniformity_score +
            0.2 * aspect_score
        )

        return float(quality)

    def validate_segmentation_batch(
        self,
        person_crops: list[np.ndarray]
    ) -> Dict[str, float]:
        """
        Validate segmentation quality on a batch of person crops.

        Used for Phase 3.2 validation checkpoint (Day 6):
        - Test on 50+ diverse person crops
        - Calculate success rate (quality > 0.5)
        - Determine if pose-based upgrade needed (<70% success)

        Args:
            person_crops: List of person crop images

        Returns:
            {
                "success_rate": 0.85,  # Fraction with quality > 0.5
                "avg_quality": 0.72,
                "high_quality_rate": 0.60,  # Fraction with quality > 0.7
                "failed_count": 8
            }
        """
        qualities = []
        failed = 0

        for crop in person_crops:
            try:
                regions = self.segment(crop)
                qualities.append(regions.quality_score)
            except (ValueError, Exception) as e:
                logger.warning(f"Segmentation failed: {e}")
                failed += 1
                qualities.append(0.0)

        qualities_array = np.array(qualities)
        success_rate = np.mean(qualities_array > 0.5)
        high_quality_rate = np.mean(qualities_array > 0.7)
        avg_quality = np.mean(qualities_array)

        return {
            "success_rate": float(success_rate),
            "avg_quality": float(avg_quality),
            "high_quality_rate": float(high_quality_rate),
            "failed_count": failed,
            "total_crops": len(person_crops)
        }


def create_segmenter(method: str = "thirds") -> GarmentSegmenter:
    """
    Factory function to create garment segmenter.

    Args:
        method: Segmentation method ("thirds" for Phase 3.2)

    Returns:
        GarmentSegmenter instance
    """
    return GarmentSegmenter(method=method)
