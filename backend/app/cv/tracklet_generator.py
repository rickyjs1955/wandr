"""
Tracklet Generation Pipeline

Combines person detection, garment analysis, visual embeddings, and tracking
to generate rich tracklet descriptors for cross-camera re-identification.

Phase 3.4 implementation - integrates all Phase 3 components:
- Phase 3.1: Person Detection (YOLOv8)
- Phase 3.2: Garment Classification (type + color)
- Phase 3.3: Visual Embeddings (CLIP 512D)
- Phase 3.4: Within-Camera Tracking (ByteTrack)

Key Features:
- Frame-by-frame processing at 1 FPS
- Outfit descriptor extraction per tracklet
- Visual embedding aggregation
- Tracklet quality scoring
- Temporal consistency validation
"""
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import cv2

from app.cv.byte_tracker import ByteTracker, Detection, Track, TrackState, create_byte_tracker
from app.cv.person_detector import PersonDetector, create_detector
from app.cv.garment_analyzer import GarmentAnalyzer, OutfitDescriptor, create_garment_analyzer
from app.cv.embedding_extractor import EmbeddingExtractor

logger = logging.getLogger(__name__)


@dataclass
class Tracklet:
    """
    Complete tracklet descriptor for a single person within one camera.

    Combines temporal tracking info with appearance descriptors.
    Ready for cross-camera re-identification in Phase 4.
    """
    track_id: int  # Camera-local track ID
    camera_id: str  # Camera identifier
    mall_id: str  # Mall identifier

    # Temporal information
    t_in: datetime  # Entry timestamp
    t_out: datetime  # Exit timestamp
    duration_seconds: float

    # Spatial information
    bbox_sequence: List[np.ndarray]  # Bounding box sequence
    frame_sequence: List[int]  # Frame IDs
    avg_bbox: np.ndarray  # Average bounding box for visualization

    # Appearance descriptors
    outfit: OutfitDescriptor  # Outfit (type + color) from garment analysis
    visual_embedding: np.ndarray  # 512D CLIP embedding (aggregated)

    # Physique attributes (non-biometric)
    height_category: str  # "short", "medium", "tall"
    aspect_ratio: float  # Bounding box w/h ratio

    # Quality metrics
    confidence: float  # Average detection confidence
    quality: float  # Overall tracklet quality (0-1)
    num_observations: int  # Number of frames where person detected

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        """
        Serialize tracklet to dictionary.

        Returns:
            Dictionary representation suitable for JSON export or database storage
        """
        return {
            "track_id": self.track_id,
            "camera_id": self.camera_id,
            "mall_id": self.mall_id,
            "t_in": self.t_in.isoformat(),
            "t_out": self.t_out.isoformat(),
            "duration_seconds": self.duration_seconds,
            "avg_bbox": self.avg_bbox.tolist(),
            "outfit": {
                "top": {"type": self.outfit.top.type, "color": self.outfit.top.color},
                "bottom": {"type": self.outfit.bottom.type, "color": self.outfit.bottom.color},
                "shoes": {"type": self.outfit.shoes.type, "color": self.outfit.shoes.color},
            },
            "visual_embedding": self.visual_embedding.tolist(),  # 512D list
            "height_category": self.height_category,
            "aspect_ratio": self.aspect_ratio,
            "confidence": self.confidence,
            "quality": self.quality,
            "num_observations": self.num_observations,
            "created_at": self.created_at.isoformat()
        }


class TrackletGenerator:
    """
    Tracklet generation pipeline for single camera.

    Processes video frames at 1 FPS to generate tracklets with:
    - Person detection (YOLOv8)
    - Multi-object tracking (ByteTrack)
    - Garment analysis (type + color)
    - Visual embedding (CLIP 512D)
    - Quality scoring

    Workflow:
    1. Detect persons in frame
    2. Update tracker with detections
    3. For each active track, extract person crop
    4. Analyze outfit and extract embedding
    5. Aggregate appearance descriptors across track lifetime
    6. Generate tracklet when track ends
    """

    def __init__(
        self,
        camera_id: str,
        mall_id: str,
        person_detector: PersonDetector,
        garment_analyzer: GarmentAnalyzer,
        tracker: ByteTracker,
        extract_embeddings: bool = True,
        frame_sample_rate: float = 1.0  # FPS for analysis
    ):
        """
        Initialize tracklet generator.

        Args:
            camera_id: Unique camera identifier
            mall_id: Mall identifier
            person_detector: Person detection model
            garment_analyzer: Garment analysis pipeline
            tracker: ByteTrack tracker instance
            extract_embeddings: Whether to extract visual embeddings
            frame_sample_rate: FPS for processing (default: 1.0 for 1 FPS)
        """
        self.camera_id = camera_id
        self.mall_id = mall_id
        self.person_detector = person_detector
        self.garment_analyzer = garment_analyzer
        self.tracker = tracker
        self.extract_embeddings = extract_embeddings
        self.frame_sample_rate = frame_sample_rate

        # Track appearance cache: {track_id: {"outfits": [], "embeddings": [], "crops": []}}
        self.track_appearances: Dict[int, Dict] = {}

        # Completed tracklets
        self.completed_tracklets: List[Tracklet] = []

        # Frame counter
        self.frame_count = 0

        logger.info(
            f"TrackletGenerator initialized for camera={camera_id}, "
            f"mall={mall_id}, embeddings={extract_embeddings}"
        )

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp: datetime,
        frame_id: int
    ) -> List[Track]:
        """
        Process a single video frame.

        Args:
            frame: RGB video frame (H, W, 3)
            timestamp: Frame timestamp
            frame_id: Frame number

        Returns:
            List of active tracks after processing
        """
        self.frame_count += 1

        # Step 1: Detect persons
        detections = self.person_detector.detect(frame)

        # Convert to ByteTracker Detection format
        byte_detections = [
            Detection(
                bbox=np.array(det['bbox']),
                confidence=det['confidence'],
                frame_id=frame_id
            )
            for det in detections
        ]

        # Step 2: Update tracker
        active_tracks = self.tracker.update(byte_detections)

        # Step 3: Extract appearance for each active track
        for track in active_tracks:
            # Extract person crop from bounding box
            x1, y1, x2, y2 = track.bbox.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)

            if x2 <= x1 or y2 <= y1:
                continue  # Invalid crop

            person_crop = frame[y1:y2, x1:x2]

            # Analyze outfit every N frames to save compute (e.g., every 3 frames = 3 sec at 1 FPS)
            if track.track_id not in self.track_appearances:
                self.track_appearances[track.track_id] = {
                    "outfits": [],
                    "embeddings": [],
                    "crops": [],
                    "frame_ids": [],  # Frame IDs for keyframe sampling
                    "timestamps": [],  # Datetime timestamps for t_in/t_out
                    "bboxes": []
                }

            # Sample keyframes for appearance extraction (e.g., every 3 frames)
            if len(self.track_appearances[track.track_id]["crops"]) == 0 or \
               (frame_id - self.track_appearances[track.track_id]["frame_ids"][-1]) >= 3:

                # Analyze garment and extract embedding
                try:
                    outfit = self.garment_analyzer.analyze(person_crop)

                    # Store appearance data
                    self.track_appearances[track.track_id]["outfits"].append(outfit)
                    if outfit.visual_embedding is not None:
                        self.track_appearances[track.track_id]["embeddings"].append(
                            outfit.visual_embedding
                        )
                    self.track_appearances[track.track_id]["crops"].append(person_crop)
                    self.track_appearances[track.track_id]["frame_ids"].append(frame_id)
                    self.track_appearances[track.track_id]["timestamps"].append(timestamp)
                    self.track_appearances[track.track_id]["bboxes"].append(track.bbox.copy())

                except Exception as e:
                    logger.warning(
                        f"Failed to analyze outfit for track {track.track_id}: {e}"
                    )

        # Step 4: Finalize removed tracks (generate tracklets)
        for track in self.tracker.removed_tracks:
            if track.track_id in self.track_appearances:
                tracklet = self._create_tracklet(track, timestamp)
                if tracklet is not None:
                    self.completed_tracklets.append(tracklet)
                # Clean up appearance cache
                del self.track_appearances[track.track_id]

        # Clear removed tracks
        self.tracker.removed_tracks.clear()

        return active_tracks

    def _create_tracklet(self, track: Track, current_timestamp: datetime) -> Optional[Tracklet]:
        """
        Create tracklet from completed track.

        Args:
            track: Completed Track object
            current_timestamp: Current timestamp for t_out

        Returns:
            Tracklet object or None if insufficient data
        """
        if track.track_id not in self.track_appearances:
            logger.debug(f"Track {track.track_id} has no appearance data, skipping tracklet")
            return None

        appearance_data = self.track_appearances[track.track_id]

        # Require minimum observations
        if len(appearance_data["outfits"]) < 2:
            logger.debug(f"Track {track.track_id} has insufficient observations ({len(appearance_data['outfits'])}), skipping")
            return None

        # Aggregate outfit descriptors (use most frequent type/color)
        outfit = self._aggregate_outfits(appearance_data["outfits"])

        # Aggregate visual embeddings (mean pooling)
        visual_embedding = None
        if self.extract_embeddings and appearance_data["embeddings"]:
            visual_embedding = np.mean(appearance_data["embeddings"], axis=0)
            # Re-normalize after averaging
            visual_embedding = visual_embedding / np.linalg.norm(visual_embedding)

        # Calculate physique attributes
        height_category, aspect_ratio = self._estimate_physique(appearance_data["bboxes"])

        # Calculate quality score
        quality = self._calculate_quality(track, appearance_data)

        # Calculate timestamps from cached appearance data
        if appearance_data["timestamps"]:
            t_in = appearance_data["timestamps"][0]  # First observation timestamp
            t_out = appearance_data["timestamps"][-1]  # Last observation timestamp
            duration_sec = (t_out - t_in).total_seconds()
        else:
            # Fallback if no timestamps (shouldn't happen with >=2 observations)
            t_in = current_timestamp
            t_out = current_timestamp
            duration_sec = 0.0

        tracklet = Tracklet(
            track_id=track.track_id,
            camera_id=self.camera_id,
            mall_id=self.mall_id,
            t_in=t_in,
            t_out=t_out,
            duration_seconds=duration_sec,
            bbox_sequence=[bbox.tolist() for bbox in track.bbox_history],
            frame_sequence=track.frame_history.copy(),
            avg_bbox=track.average_bbox,
            outfit=outfit,
            visual_embedding=visual_embedding,
            height_category=height_category,
            aspect_ratio=aspect_ratio,
            confidence=track.average_confidence,
            quality=quality,
            num_observations=len(appearance_data["outfits"])
        )

        logger.info(
            f"Created tracklet: track_id={track.track_id}, "
            f"observations={tracklet.num_observations}, quality={quality:.2f}"
        )

        return tracklet

    def _aggregate_outfits(self, outfits: List[OutfitDescriptor]) -> OutfitDescriptor:
        """
        Aggregate multiple outfit observations into single descriptor.

        Uses mode (most frequent) for type/color selection.

        Args:
            outfits: List of outfit descriptors from track

        Returns:
            Aggregated outfit descriptor
        """
        from collections import Counter

        # Aggregate top
        top_types = [o.top.type for o in outfits if o.top]
        top_colors = [o.top.color for o in outfits if o.top]
        top_type = Counter(top_types).most_common(1)[0][0] if top_types else "unknown"
        top_color = Counter(top_colors).most_common(1)[0][0] if top_colors else "unknown"

        # Aggregate bottom
        bottom_types = [o.bottom.type for o in outfits if o.bottom]
        bottom_colors = [o.bottom.color for o in outfits if o.bottom]
        bottom_type = Counter(bottom_types).most_common(1)[0][0] if bottom_types else "unknown"
        bottom_color = Counter(bottom_colors).most_common(1)[0][0] if bottom_colors else "unknown"

        # Aggregate shoes
        shoe_types = [o.shoes.type for o in outfits if o.shoes]
        shoe_colors = [o.shoes.color for o in outfits if o.shoes]
        shoe_type = Counter(shoe_types).most_common(1)[0][0] if shoe_types else "unknown"
        shoe_color = Counter(shoe_colors).most_common(1)[0][0] if shoe_colors else "unknown"

        # Return aggregated outfit (using first outfit as template)
        outfit = outfits[0]
        outfit.top.type = top_type
        outfit.top.color = top_color
        outfit.bottom.type = bottom_type
        outfit.bottom.color = bottom_color
        outfit.shoes.type = shoe_type
        outfit.shoes.color = shoe_color

        return outfit

    def _estimate_physique(self, bboxes: List[np.ndarray]) -> Tuple[str, float]:
        """
        Estimate non-biometric physique attributes from bounding boxes.

        Args:
            bboxes: List of bounding boxes [[x1, y1, x2, y2], ...]

        Returns:
            Tuple of (height_category, aspect_ratio)
        """
        if not bboxes:
            return "medium", 0.5

        # Calculate average aspect ratio (width/height)
        aspect_ratios = []
        for bbox in bboxes:
            x1, y1, x2, y2 = bbox
            w, h = x2 - x1, y2 - y1
            if h > 0:
                aspect_ratios.append(w / h)

        avg_aspect_ratio = np.mean(aspect_ratios) if aspect_ratios else 0.5

        # Estimate height category from average bbox height
        # TODO: Calibrate per camera using reference objects
        heights = [bbox[3] - bbox[1] for bbox in bboxes]
        avg_height = np.mean(heights)

        if avg_height < 100:
            height_category = "short"
        elif avg_height > 200:
            height_category = "tall"
        else:
            height_category = "medium"

        return height_category, float(avg_aspect_ratio)

    def _calculate_quality(self, track: Track, appearance_data: Dict) -> float:
        """
        Calculate tracklet quality score (0-1).

        Factors:
        - Number of observations (more = better)
        - Detection confidence (higher = better)
        - Track stability (longer = better)

        Args:
            track: Track object
            appearance_data: Appearance data dictionary

        Returns:
            Quality score (0-1)
        """
        # Factor 1: Observation count (normalize to 0-1, saturate at 10 observations)
        obs_score = min(1.0, len(appearance_data["outfits"]) / 10.0)

        # Factor 2: Detection confidence
        conf_score = track.average_confidence

        # Factor 3: Track stability (hits/age ratio)
        stability_score = track.hits / max(1, track.age)

        # Weighted combination
        quality = 0.4 * obs_score + 0.4 * conf_score + 0.2 * stability_score

        return float(np.clip(quality, 0.0, 1.0))

    def finalize_all_tracks(self, timestamp: datetime) -> List[Tracklet]:
        """
        Finalize all remaining tracks (called at end of video).

        Args:
            timestamp: Final timestamp

        Returns:
            List of completed tracklets
        """
        # Mark all tracks as removed
        all_tracks = self.tracker.get_all_tracks()
        for track in all_tracks:
            track.state = TrackState.REMOVED  # Force removal
            tracklet = self._create_tracklet(track, timestamp)
            if tracklet is not None:
                self.completed_tracklets.append(tracklet)

        # Clear cache
        self.track_appearances.clear()
        self.tracker.reset()

        return self.completed_tracklets

    def get_tracklets(self) -> List[Tracklet]:
        """Get all completed tracklets"""
        return self.completed_tracklets

    def reset(self):
        """Reset generator state"""
        self.tracker.reset()
        self.track_appearances.clear()
        self.completed_tracklets.clear()
        self.frame_count = 0
        logger.info("TrackletGenerator reset")


def create_tracklet_generator(
    camera_id: str,
    mall_id: str,
    extract_embeddings: bool = True
) -> TrackletGenerator:
    """
    Factory function to create TrackletGenerator with default components.

    Args:
        camera_id: Camera identifier
        mall_id: Mall identifier
        extract_embeddings: Whether to extract visual embeddings

    Returns:
        TrackletGenerator instance
    """
    # Create components
    person_detector = create_detector()
    garment_analyzer = create_garment_analyzer(extract_embeddings=extract_embeddings)
    tracker = create_byte_tracker()

    return TrackletGenerator(
        camera_id=camera_id,
        mall_id=mall_id,
        person_detector=person_detector,
        garment_analyzer=garment_analyzer,
        tracker=tracker,
        extract_embeddings=extract_embeddings
    )
