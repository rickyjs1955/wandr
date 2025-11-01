"""
Person Detection Service

Detects people in video frames using YOLOv8 or RT-DETR.
Optimized for CCTV footage with configurable confidence thresholds.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
import torch
from ultralytics import YOLO
import logging

logger = logging.getLogger(__name__)


class PersonDetector:
    """
    Detect people in video frames using YOLOv8

    Supports:
    - YOLOv8n (nano) - fastest, lowest accuracy
    - YOLOv8s (small) - balanced
    - YOLOv8m (medium) - slower, higher accuracy

    For MVP, YOLOv8n is recommended (>30 FPS on CPU, >100 FPS on GPU)
    """

    # COCO class ID for 'person'
    PERSON_CLASS_ID = 0

    def __init__(
        self,
        model_name: str = "yolov8n.pt",
        device: str = "cpu",
        conf_threshold: float = 0.7,
        iou_threshold: float = 0.45
    ):
        """
        Initialize person detector

        Args:
            model_name: YOLOv8 model name (yolov8n.pt, yolov8s.pt, yolov8m.pt)
            device: 'cpu', 'cuda', 'mps' (Mac Metal)
            conf_threshold: Confidence threshold (0.0-1.0)
            iou_threshold: IoU threshold for NMS (Non-Maximum Suppression)
        """
        self.model_name = model_name
        self.device = self._get_device(device)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold

        logger.info(f"Initializing PersonDetector with {model_name} on {self.device}")

        # Load YOLO model (will download on first run)
        self.model = YOLO(model_name)
        self.model.to(self.device)

        logger.info(f"PersonDetector initialized successfully")

    def _get_device(self, requested_device: str) -> str:
        """
        Get available device with fallback

        Priority: CUDA > MPS (Mac Metal) > CPU
        """
        if requested_device == "cuda" and torch.cuda.is_available():
            return "cuda"
        elif requested_device == "mps" and torch.backends.mps.is_available():
            return "mps"
        else:
            if requested_device != "cpu":
                logger.warning(f"{requested_device} not available, falling back to CPU")
            return "cpu"

    def detect(
        self,
        frame: np.ndarray,
        conf_threshold: Optional[float] = None
    ) -> List[Dict]:
        """
        Detect people in a single frame

        Args:
            frame: RGB image as numpy array (H, W, 3)
            conf_threshold: Optional override for confidence threshold

        Returns:
            List of detections, each containing:
            {
                "bbox": [x, y, w, h],  # Bounding box in XYWH format
                "confidence": 0.89,     # Detection confidence
                "class": "person"       # Always "person"
            }
        """
        conf = conf_threshold if conf_threshold is not None else self.conf_threshold

        # Run inference
        results = self.model(
            frame,
            classes=[self.PERSON_CLASS_ID],  # Only detect persons
            conf=conf,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False  # Suppress YOLO logging
        )

        detections = []

        # Extract detections
        for result in results:
            if result.boxes is None or len(result.boxes) == 0:
                continue

            for box in result.boxes:
                # Get bounding box in xyxy format
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                # Convert to xywh format
                x, y, w, h = int(x1), int(y1), int(x2 - x1), int(y2 - y1)

                # Get confidence
                confidence = float(box.conf[0].cpu().numpy())

                detections.append({
                    "bbox": [x, y, w, h],
                    "confidence": confidence,
                    "class": "person"
                })

        return detections

    def detect_batch(
        self,
        frames: List[np.ndarray],
        conf_threshold: Optional[float] = None
    ) -> List[List[Dict]]:
        """
        Detect people in multiple frames (batch inference)

        More efficient than calling detect() multiple times.

        Args:
            frames: List of RGB images as numpy arrays
            conf_threshold: Optional override for confidence threshold

        Returns:
            List of detection lists (one per frame)
        """
        conf = conf_threshold if conf_threshold is not None else self.conf_threshold

        # Run batch inference
        results = self.model(
            frames,
            classes=[self.PERSON_CLASS_ID],
            conf=conf,
            iou=self.iou_threshold,
            device=self.device,
            verbose=False
        )

        all_detections = []

        for result in results:
            detections = []

            if result.boxes is not None and len(result.boxes) > 0:
                for box in result.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    x, y, w, h = int(x1), int(y1), int(x2 - x1), int(y2 - y1)
                    confidence = float(box.conf[0].cpu().numpy())

                    detections.append({
                        "bbox": [x, y, w, h],
                        "confidence": confidence,
                        "class": "person"
                    })

            all_detections.append(detections)

        return all_detections

    def extract_person_crops(
        self,
        frame: np.ndarray,
        detections: List[Dict],
        padding: float = 0.1
    ) -> List[Tuple[np.ndarray, Dict]]:
        """
        Extract person crops from frame given detections

        Args:
            frame: RGB image as numpy array
            detections: List of detections from detect()
            padding: Padding around bbox as fraction of width/height (0.1 = 10%)

        Returns:
            List of (crop, detection) tuples
        """
        crops = []
        h, w = frame.shape[:2]

        for detection in detections:
            x, y, box_w, box_h = detection["bbox"]

            # Add padding
            pad_x = int(box_w * padding)
            pad_y = int(box_h * padding)

            # Calculate padded bbox with bounds checking
            x1 = max(0, x - pad_x)
            y1 = max(0, y - pad_y)
            x2 = min(w, x + box_w + pad_x)
            y2 = min(h, y + box_h + pad_y)

            # Extract crop
            crop = frame[y1:y2, x1:x2]

            # Store crop with adjusted bbox (for reference)
            crop_detection = detection.copy()
            crop_detection["original_bbox"] = detection["bbox"]
            crop_detection["crop_bbox"] = [x1, y1, x2 - x1, y2 - y1]

            crops.append((crop, crop_detection))

        return crops

    def benchmark(
        self,
        frame: np.ndarray,
        num_iterations: int = 100
    ) -> Dict[str, float]:
        """
        Benchmark inference speed

        Args:
            frame: Sample frame for testing
            num_iterations: Number of iterations for averaging

        Returns:
            {
                "avg_time_ms": 15.2,
                "fps": 65.8,
                "device": "cuda"
            }
        """
        import time

        # Warmup
        for _ in range(10):
            self.detect(frame)

        # Benchmark
        times = []
        for _ in range(num_iterations):
            start = time.time()
            self.detect(frame)
            end = time.time()
            times.append((end - start) * 1000)  # Convert to ms

        avg_time = np.mean(times)
        fps = 1000.0 / avg_time if avg_time > 0 else 0

        return {
            "avg_time_ms": round(avg_time, 2),
            "fps": round(fps, 2),
            "device": str(self.device),
            "model": self.model_name
        }


def create_detector(
    model_name: str = "yolov8n.pt",
    device: str = "cpu",
    conf_threshold: float = 0.7
) -> PersonDetector:
    """
    Factory function to create PersonDetector instance

    This is the recommended way to instantiate the detector,
    as it handles device selection and logging.
    """
    return PersonDetector(
        model_name=model_name,
        device=device,
        conf_threshold=conf_threshold
    )
