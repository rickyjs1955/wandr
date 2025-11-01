"""
Color Extraction Module

Extracts LAB color space information from garment regions.
Provides dominant color, LAB values, and color histograms for
outfit-based re-identification.
"""
import logging
from typing import Dict, List, Tuple, Optional
import numpy as np
import cv2
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ColorDescriptor:
    """Color information for a garment region."""
    color_name: str  # Human-readable color name
    lab: Tuple[float, float, float]  # LAB color space values (L, a, b)
    histogram: List[float]  # Color histogram (normalized)
    confidence: float  # 0-1, confidence in color extraction


class ColorExtractor:
    """
    Extract color information from garment regions.

    Uses CIELAB color space for perceptually uniform color comparison.
    Generates color histograms for detailed matching in Phase 4.

    LAB Color Space:
    - L: Lightness (0-100, 0=black, 100=white)
    - a: Green-Red axis (-128 to +127, negative=green, positive=red)
    - b: Blue-Yellow axis (-128 to +127, negative=blue, positive=yellow)
    """

    # Simplified color name mapping based on LAB ranges
    COLOR_RANGES = {
        "white": {"L": (80, 100), "a": (-10, 10), "b": (-10, 10)},
        "black": {"L": (0, 30), "a": (-10, 10), "b": (-10, 10)},
        "gray": {"L": (30, 80), "a": (-10, 10), "b": (-10, 10)},
        "red": {"L": (20, 80), "a": (20, 127), "b": (-20, 50)},
        "orange": {"L": (40, 85), "a": (10, 60), "b": (30, 80)},
        "yellow": {"L": (60, 100), "a": (-20, 20), "b": (30, 127)},
        "green": {"L": (30, 80), "a": (-60, -10), "b": (-20, 40)},
        "blue": {"L": (20, 70), "a": (-20, 20), "b": (-80, -10)},
        "purple": {"L": (20, 60), "a": (10, 60), "b": (-50, -10)},
        "pink": {"L": (50, 90), "a": (20, 60), "b": (-10, 20)},
        "brown": {"L": (20, 60), "a": (5, 40), "b": (10, 50)},
    }

    def __init__(
        self,
        histogram_bins: int = 10,
        min_pixels: int = 100
    ):
        """
        Initialize color extractor.

        Args:
            histogram_bins: Number of bins per LAB channel (default 10)
            min_pixels: Minimum pixels required for valid region
        """
        self.histogram_bins = histogram_bins
        self.min_pixels = min_pixels

    def extract(self, region: np.ndarray) -> ColorDescriptor:
        """
        Extract color descriptor from garment region.

        Gracefully handles small regions (narrow shoe crops, partial detections):
        - Regions <100px: Extract color but return low confidence
        - Very small regions (<10px): Return default gray with minimal confidence

        Args:
            region: RGB image of garment region (H x W x 3)

        Returns:
            ColorDescriptor with color name, LAB values, and histogram

        Raises:
            ValueError: Only if region is completely invalid (None, empty, wrong shape)
        """
        if region is None or region.size == 0:
            raise ValueError("Invalid region: empty or None")

        if len(region.shape) != 3 or region.shape[2] != 3:
            raise ValueError(f"Invalid region shape: {region.shape}, expected (H, W, 3)")

        h, w, _ = region.shape

        # Graceful degradation for very small regions (e.g., narrow shoe crops)
        if h * w < 10:
            logger.warning(f"Region too small for reliable color extraction: {h}x{w} = {h*w} pixels")
            # Return default gray with minimal confidence
            return ColorDescriptor(
                color_name="gray",
                lab=(50.0, 0.0, 0.0),  # Neutral gray
                histogram=[0.1] * 30,  # Flat histogram
                confidence=0.1  # Very low confidence
            )

        # Small but extractable regions: proceed with warning
        if h * w < self.min_pixels:
            logger.debug(f"Small region ({h}x{w}), color extraction may be less reliable")

        # Convert RGB to LAB
        lab_image = cv2.cvtColor(region, cv2.COLOR_RGB2LAB)

        # Extract dominant color
        dominant_lab = self._get_dominant_color(lab_image)

        # Generate histogram
        histogram = self._compute_histogram(lab_image)

        # Map to color name
        color_name = self._lab_to_color_name(dominant_lab)

        # Calculate confidence based on region uniformity
        confidence = self._calculate_confidence(lab_image, dominant_lab)

        return ColorDescriptor(
            color_name=color_name,
            lab=tuple(dominant_lab.tolist()),
            histogram=histogram.tolist(),
            confidence=float(confidence)
        )

    def _get_dominant_color(self, lab_image: np.ndarray) -> np.ndarray:
        """
        Get dominant LAB color from image using median.

        Uses median instead of mean to be more robust to outliers.

        Args:
            lab_image: LAB color space image (H x W x 3)

        Returns:
            Dominant LAB color as [L, a, b] array
        """
        # Reshape to (N_pixels, 3)
        pixels = lab_image.reshape(-1, 3)

        # Use median for robustness (less affected by extreme outliers)
        dominant = np.median(pixels, axis=0)

        return dominant

    def _compute_histogram(
        self,
        lab_image: np.ndarray
    ) -> np.ndarray:
        """
        Compute normalized LAB color histogram.

        Creates histogram with self.histogram_bins bins per channel.
        Concatenates L, a, b histograms and normalizes to sum=1.

        Args:
            lab_image: LAB color space image (H x W x 3)

        Returns:
            Normalized histogram array (bins*3,)
        """
        bins = self.histogram_bins

        # LAB ranges (OpenCV LAB format)
        # L: 0-255 (represents 0-100)
        # a: 0-255 (represents -128 to +127, shifted by +128)
        # b: 0-255 (represents -128 to +127, shifted by +128)

        hist_l = cv2.calcHist([lab_image], [0], None, [bins], [0, 256])
        hist_a = cv2.calcHist([lab_image], [1], None, [bins], [0, 256])
        hist_b = cv2.calcHist([lab_image], [2], None, [bins], [0, 256])

        # Concatenate histograms
        hist = np.concatenate([hist_l, hist_a, hist_b]).flatten()

        # Normalize to sum=1
        hist = hist / (hist.sum() + 1e-10)

        return hist

    def _lab_to_color_name(self, lab: np.ndarray) -> str:
        """
        Map LAB values to human-readable color name.

        Uses simplified color ranges for common clothing colors.

        Args:
            lab: LAB color array [L, a, b] in OpenCV format (0-255)

        Returns:
            Color name string (e.g., "blue", "red", "white")
        """
        # Convert OpenCV LAB (0-255) to standard LAB
        # L: 0-255 → 0-100
        # a, b: 0-255 → -128 to +127
        L = (lab[0] / 255.0) * 100
        a = lab[1] - 128
        b = lab[2] - 128

        # Check each color range
        for color_name, ranges in self.COLOR_RANGES.items():
            L_min, L_max = ranges["L"]
            a_min, a_max = ranges["a"]
            b_min, b_max = ranges["b"]

            if (L_min <= L <= L_max and
                a_min <= a <= a_max and
                b_min <= b <= b_max):
                return color_name

        # Default to closest achromatic color if no match
        if L > 70:
            return "white"
        elif L < 35:
            return "black"
        else:
            return "gray"

    def _calculate_confidence(
        self,
        lab_image: np.ndarray,
        dominant_lab: np.ndarray
    ) -> float:
        """
        Calculate confidence in color extraction.

        Based on color uniformity in region:
        - High uniformity (low std) = high confidence
        - Low uniformity (high std) = low confidence

        Args:
            lab_image: LAB color space image
            dominant_lab: Dominant LAB color

        Returns:
            Confidence score 0-1
        """
        pixels = lab_image.reshape(-1, 3)

        # Calculate standard deviation from dominant color
        std = np.std(pixels, axis=0)
        avg_std = np.mean(std)

        # Convert to confidence (lower std = higher confidence)
        # Standard deviation in LAB typically 0-50 for clothing
        # std < 10: very uniform → confidence 1.0
        # std > 40: very non-uniform → confidence 0.3
        confidence = np.clip(1.0 - (avg_std / 50.0), 0.3, 1.0)

        return float(confidence)

    @staticmethod
    def ciede2000(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
        """
        Calculate CIEDE2000 color difference (Delta E).

        This is a simplified implementation. For production, consider
        using colormath library for full CIEDE2000 calculation.

        Args:
            lab1: First LAB color (L, a, b) in standard format
            lab2: Second LAB color (L, a, b) in standard format

        Returns:
            Delta E value (0 = identical, >100 = very different)
            - ΔE < 1: Not perceptible
            - ΔE 1-2: Perceptible through close observation
            - ΔE 2-10: Perceptible at a glance
            - ΔE 11-49: Colors are more similar than opposite
            - ΔE > 100: Colors are exact opposites
        """
        # Simplified Euclidean distance in LAB space
        # Full CIEDE2000 includes weighting factors for perceptual uniformity
        L1, a1, b1 = lab1
        L2, a2, b2 = lab2

        delta_L = L1 - L2
        delta_a = a1 - a2
        delta_b = b1 - b2

        # Simplified formula (close to CIE76)
        delta_e = np.sqrt(delta_L**2 + delta_a**2 + delta_b**2)

        return float(delta_e)

    def compare_colors(
        self,
        desc1: ColorDescriptor,
        desc2: ColorDescriptor
    ) -> Dict[str, float]:
        """
        Compare two color descriptors.

        Returns multiple similarity metrics for Phase 4 matching.

        Args:
            desc1: First color descriptor
            desc2: Second color descriptor

        Returns:
            {
                "delta_e": 12.5,  # CIEDE2000 difference
                "histogram_similarity": 0.85,  # Chi-square similarity
                "name_match": True  # Same color name
            }
        """
        # Calculate Delta E
        delta_e = self.ciede2000(desc1.lab, desc2.lab)

        # Calculate histogram similarity (chi-square)
        hist1 = np.array(desc1.histogram)
        hist2 = np.array(desc2.histogram)
        chi_square = cv2.compareHist(
            hist1.astype(np.float32),
            hist2.astype(np.float32),
            cv2.HISTCMP_CHISQR
        )
        # Convert chi-square to similarity (0-1 range, 1=identical)
        hist_similarity = 1.0 / (1.0 + chi_square)

        # Check name match
        name_match = desc1.color_name == desc2.color_name

        return {
            "delta_e": float(delta_e),
            "histogram_similarity": float(hist_similarity),
            "name_match": bool(name_match)
        }


def create_color_extractor(histogram_bins: int = 10) -> ColorExtractor:
    """
    Factory function to create color extractor.

    Args:
        histogram_bins: Number of bins per LAB channel

    Returns:
        ColorExtractor instance
    """
    return ColorExtractor(histogram_bins=histogram_bins)
