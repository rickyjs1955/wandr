"""
Benchmark Person Detector

Tests YOLOv8n performance on sample frames.
Usage: python -m scripts.benchmark_person_detector
"""

import sys
import os
import numpy as np
import cv2

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.cv.person_detector import PersonDetector
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_frame(width: int = 1920, height: int = 1080) -> np.ndarray:
    """
    Create a synthetic test frame (random noise)

    In production, replace this with actual CCTV footage.
    """
    frame = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    return frame


def main():
    logger.info("=== YOLOv8n Person Detector Benchmark ===")

    # Create sample frame
    frame = create_sample_frame()
    logger.info(f"Created sample frame: {frame.shape}")

    # Test CPU
    logger.info("\n--- Testing on CPU ---")
    detector_cpu = PersonDetector(
        model_name="yolov8n.pt",
        device="cpu",
        conf_threshold=0.7
    )

    # Run detection once to verify it works
    detections = detector_cpu.detect(frame)
    logger.info(f"Detected {len(detections)} people (on synthetic frame, likely 0)")

    # Benchmark
    results_cpu = detector_cpu.benchmark(frame, num_iterations=50)
    logger.info(f"CPU Performance:")
    logger.info(f"  Average time: {results_cpu['avg_time_ms']} ms")
    logger.info(f"  Throughput: {results_cpu['fps']} FPS")

    # Test GPU/MPS if available
    import torch
    if torch.cuda.is_available() or torch.backends.mps.is_available():
        device = "cuda" if torch.cuda.is_available() else "mps"
        logger.info(f"\n--- Testing on {device.upper()} ---")

        detector_gpu = PersonDetector(
            model_name="yolov8n.pt",
            device=device,
            conf_threshold=0.7
        )

        results_gpu = detector_gpu.benchmark(frame, num_iterations=50)
        logger.info(f"{device.upper()} Performance:")
        logger.info(f"  Average time: {results_gpu['avg_time_ms']} ms")
        logger.info(f"  Throughput: {results_gpu['fps']} FPS")
        logger.info(f"  Speedup: {results_cpu['fps'] / results_gpu['fps']:.2f}x faster than CPU")
    else:
        logger.info("\nNo GPU/MPS available, skipping accelerated test")

    # Success criteria check
    logger.info("\n=== Success Criteria Check ===")
    target_fps_cpu = 10
    target_fps_gpu = 30

    if results_cpu['fps'] >= target_fps_cpu:
        logger.info(f"✅ CPU meets target ({results_cpu['fps']} >= {target_fps_cpu} FPS)")
    else:
        logger.warning(f"❌ CPU below target ({results_cpu['fps']} < {target_fps_cpu} FPS)")

    logger.info("\n=== Benchmark Complete ===")


if __name__ == "__main__":
    main()
