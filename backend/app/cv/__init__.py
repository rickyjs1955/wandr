"""
Computer Vision Pipeline

This package contains all computer vision services for Phase 3:
- Person detection (YOLOv8/RT-DETR) - Phase 3.1
- Garment classification - Phase 3.2
- Visual embedding extraction (CLIP) - Phase 3.3
- Within-camera tracking (ByteTrack) - Phase 3.4
"""

from app.cv.person_detector import PersonDetector, create_detector
from app.cv.garment_segmenter import GarmentSegmenter, GarmentRegions, create_segmenter
from app.cv.color_extractor import ColorExtractor, ColorDescriptor, create_color_extractor
from app.cv.garment_type_classifier import GarmentTypeClassifier, create_type_classifier
from app.cv.garment_analyzer import GarmentAnalyzer, OutfitDescriptor, create_garment_analyzer

__all__ = [
    "PersonDetector",
    "create_detector",
    "GarmentSegmenter",
    "GarmentRegions",
    "create_segmenter",
    "ColorExtractor",
    "ColorDescriptor",
    "create_color_extractor",
    "GarmentTypeClassifier",
    "create_type_classifier",
    "GarmentAnalyzer",
    "OutfitDescriptor",
    "create_garment_analyzer",
]
