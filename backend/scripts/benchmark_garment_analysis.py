"""
Benchmark Garment Analysis Pipeline

Tests garment segmentation and color extraction on sample person crops.
Used for Phase 3.2 validation (Day 6 checkpoint).

Usage:
    python backend/scripts/benchmark_garment_analysis.py

Validation Criteria:
- Success rate >70% (overall_quality > 0.5)
- If fails, upgrade to pose-based segmentation needed
"""
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import cv2
import logging

from app.cv.garment_analyzer import create_garment_analyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_synthetic_person_crops(num_crops: int = 20) -> list:
    """
    Generate synthetic person crops for testing.

    In production, replace with actual CCTV footage person crops.

    Generates diverse synthetic images:
    - Different heights (tall, short)
    - Different colors (uniforms, varied outfits)
    - Different aspect ratios
    """
    crops = []

    for i in range(num_crops):
        # Random dimensions (typical person crop: 180-480 height, 80-200 width)
        height = np.random.randint(200, 500)
        width = np.random.randint(90, 220)

        # Create synthetic person crop with 3 regions of different colors
        crop = np.zeros((height, width, 3), dtype=np.uint8)

        # Top region (40% of height) - random color
        top_end = int(height * 0.4)
        top_color = np.random.randint(50, 250, size=3)
        crop[0:top_end, :] = top_color

        # Bottom region (40-80% of height) - different color
        bottom_end = int(height * 0.8)
        bottom_color = np.random.randint(30, 220, size=3)
        crop[top_end:bottom_end, :] = bottom_color

        # Shoes region (80-100% of height) - typically darker
        shoes_color = np.random.randint(10, 100, size=3)
        crop[bottom_end:, :] = shoes_color

        # Add some noise for realism
        noise = np.random.normal(0, 15, crop.shape).astype(np.int16)
        crop = np.clip(crop.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        crops.append(crop)

    logger.info(f"Generated {len(crops)} synthetic person crops")
    return crops


def benchmark_garment_analysis():
    """
    Benchmark garment analysis pipeline.

    Tests on synthetic person crops and reports:
    - Success rate
    - Average quality
    - Processing time
    """
    logger.info("=" * 60)
    logger.info("Garment Analysis Benchmark - Phase 3.2")
    logger.info("=" * 60)

    # Initialize analyzer
    logger.info("\n1. Initializing GarmentAnalyzer...")
    analyzer = create_garment_analyzer()
    logger.info("   ✓ GarmentAnalyzer initialized")

    # Generate test crops
    logger.info("\n2. Generating test person crops...")
    test_crops = generate_synthetic_person_crops(num_crops=50)
    logger.info(f"   ✓ Generated {len(test_crops)} synthetic crops")

    # Test single analysis
    logger.info("\n3. Testing single crop analysis...")
    try:
        test_crop = test_crops[0]
        descriptor = analyzer.analyze(test_crop)
        logger.info(f"   ✓ Single analysis successful")
        logger.info(f"     - Top: {descriptor.top.color} (confidence: {descriptor.top.confidence:.3f})")
        logger.info(f"     - Bottom: {descriptor.bottom.color} (confidence: {descriptor.bottom.confidence:.3f})")
        logger.info(f"     - Shoes: {descriptor.shoes.color} (confidence: {descriptor.shoes.confidence:.3f})")
        logger.info(f"     - Overall quality: {descriptor.overall_quality:.3f}")
    except Exception as e:
        logger.error(f"   ✗ Single analysis failed: {e}")
        return

    # Validate accuracy on full test set
    logger.info("\n4. Validating accuracy on test set...")
    validation_results = analyzer.validate_accuracy(test_crops, min_quality=0.5)

    logger.info(f"\n{'='*60}")
    logger.info("VALIDATION RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Total crops tested:     {validation_results['total_crops']}")
    logger.info(f"Failed analyses:        {validation_results['failed_count']}")
    logger.info(f"Success rate (>0.5):    {validation_results['success_rate']:.1%}")
    logger.info(f"High quality rate (>0.7): {validation_results['high_quality_rate']:.1%}")
    logger.info(f"Average quality:        {validation_results['avg_quality']:.3f}")

    # Determine if upgrade needed
    logger.info(f"\n{'='*60}")
    logger.info("DECISION CHECKPOINT")
    logger.info(f"{'='*60}")

    success_rate = validation_results['success_rate']
    target_rate = 0.70

    if success_rate >= target_rate:
        logger.info(f"✓ SUCCESS: {success_rate:.1%} >= {target_rate:.1%}")
        logger.info("  Thirds-based segmentation is ADEQUATE for Phase 3.2")
        logger.info("  No upgrade to pose-based segmentation needed")
    else:
        logger.warning(f"✗ BELOW TARGET: {success_rate:.1%} < {target_rate:.1%}")
        logger.warning("  Thirds-based segmentation INADEQUATE")
        logger.warning("  ACTION REQUIRED: Upgrade to pose-based segmentation")
        logger.warning("  Options:")
        logger.warning("    1. Implement MediaPipe Pose (~20 FPS)")
        logger.warning("    2. Use U²-Net semantic segmentation (~15 FPS on GPU)")

    # Benchmark performance
    logger.info(f"\n{'='*60}")
    logger.info("PERFORMANCE BENCHMARK")
    logger.info(f"{'='*60}")

    import time
    num_iterations = 20
    times = []

    logger.info(f"Running {num_iterations} iterations...")
    for i in range(num_iterations):
        crop = test_crops[i % len(test_crops)]
        start = time.time()
        analyzer.analyze(crop)
        end = time.time()
        times.append((end - start) * 1000)  # ms

    avg_time = np.mean(times)
    fps = 1000.0 / avg_time if avg_time > 0 else 0

    logger.info(f"Average analysis time: {avg_time:.2f} ms")
    logger.info(f"Throughput:            {fps:.2f} crops/sec")

    # Target performance
    target_fps = 10  # Should process 10 crops per second minimum
    if fps >= target_fps:
        logger.info(f"✓ Performance ADEQUATE: {fps:.2f} >= {target_fps} crops/sec")
    else:
        logger.warning(f"✗ Performance SLOW: {fps:.2f} < {target_fps} crops/sec")

    logger.info(f"\n{'='*60}")
    logger.info("Benchmark Complete!")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    try:
        benchmark_garment_analysis()
    except KeyboardInterrupt:
        logger.info("\nBenchmark interrupted by user")
    except Exception as e:
        logger.error(f"\nBenchmark failed with error: {e}", exc_info=True)
        sys.exit(1)
