"""
ByteTrack Multi-Object Tracker

Lightweight ByteTrack implementation optimized for 1 FPS CCTV footage.
Tracks persons across frames using IoU-based association with adaptive thresholds.

Phase 3.4 implementation for within-camera tracking.

Key Features:
- IoU-based detection-to-track association
- Two-stage matching (high/low confidence detections)
- Track state management (Active, Lost, Removed)
- Adaptive track aging for 1 FPS footage
- Kalman filter-free (suitable for low FPS)

References:
- ByteTrack: https://arxiv.org/abs/2110.06864
- Adapted for 1 FPS CCTV with relaxed temporal assumptions
"""
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)


class TrackState(Enum):
    """Track lifecycle states"""
    NEW = 1          # Just created, not yet confirmed
    TRACKED = 2      # Active tracking
    LOST = 3         # Temporarily lost (occlusion, missed detection)
    REMOVED = 4      # Permanently removed from tracking


@dataclass
class Detection:
    """
    Person detection from YOLO.

    Attributes:
        bbox: Bounding box [x1, y1, x2, y2] in image coordinates
        confidence: Detection confidence score (0-1)
        frame_id: Frame number where detected
    """
    bbox: np.ndarray  # [x1, y1, x2, y2]
    confidence: float
    frame_id: int

    def __post_init__(self):
        self.bbox = np.asarray(self.bbox, dtype=np.float32)

    @property
    def tlwh(self) -> np.ndarray:
        """Return bounding box in top-left-width-height format"""
        x1, y1, x2, y2 = self.bbox
        return np.array([x1, y1, x2 - x1, y2 - y1])

    @property
    def tlbr(self) -> np.ndarray:
        """Return bounding box in top-left-bottom-right format"""
        return self.bbox

    @property
    def area(self) -> float:
        """Return bounding box area"""
        x1, y1, x2, y2 = self.bbox
        return max(0, (x2 - x1) * (y2 - y1))


@dataclass
class Track:
    """
    Person track within single camera.

    Maintains state for a single person across frames.
    Optimized for 1 FPS footage with relaxed temporal constraints.
    """
    track_id: int
    bbox: np.ndarray  # Current bounding box [x1, y1, x2, y2]
    confidence: float  # Detection confidence
    frame_id: int  # Last updated frame

    # Track metadata
    state: TrackState = TrackState.NEW
    age: int = 0  # Frames since creation
    hits: int = 0  # Total successful matches
    time_since_update: int = 0  # Frames since last match

    # Track history for quality assessment
    bbox_history: List[np.ndarray] = field(default_factory=list)
    confidence_history: List[float] = field(default_factory=list)
    frame_history: List[int] = field(default_factory=list)

    def __post_init__(self):
        self.bbox = np.asarray(self.bbox, dtype=np.float32)
        # Initialize history
        self.bbox_history.append(self.bbox.copy())
        self.confidence_history.append(self.confidence)
        self.frame_history.append(self.frame_id)

    def update(self, detection: Detection):
        """
        Update track with new detection.

        Args:
            detection: Matched detection
        """
        self.bbox = detection.bbox.copy()
        self.confidence = detection.confidence
        self.frame_id = detection.frame_id

        self.hits += 1
        self.time_since_update = 0

        # Append to history (limit to last 30 frames ~30 seconds at 1 FPS)
        self.bbox_history.append(self.bbox.copy())
        self.confidence_history.append(self.confidence)
        self.frame_history.append(self.frame_id)

        if len(self.bbox_history) > 30:
            self.bbox_history.pop(0)
            self.confidence_history.pop(0)
            self.frame_history.pop(0)

        # Update state
        if self.state == TrackState.NEW and self.hits >= 3:
            self.state = TrackState.TRACKED
        elif self.state == TrackState.LOST:
            self.state = TrackState.TRACKED

    def mark_missed(self):
        """Mark track as missed in current frame"""
        self.time_since_update += 1
        self.age += 1

        # State transition: TRACKED -> LOST -> REMOVED
        # At 1 FPS: Allow 10 seconds (10 frames) lost before removal
        if self.time_since_update > 10:
            self.state = TrackState.REMOVED
        elif self.time_since_update > 3:
            self.state = TrackState.LOST

    @property
    def tlwh(self) -> np.ndarray:
        """Return current bbox in top-left-width-height format"""
        x1, y1, x2, y2 = self.bbox
        return np.array([x1, y1, x2 - x1, y2 - y1])

    @property
    def tlbr(self) -> np.ndarray:
        """Return current bbox in top-left-bottom-right format"""
        return self.bbox

    @property
    def is_active(self) -> bool:
        """Check if track is actively being tracked"""
        return self.state in [TrackState.NEW, TrackState.TRACKED]

    @property
    def average_confidence(self) -> float:
        """Return average detection confidence across history"""
        if not self.confidence_history:
            return 0.0
        return float(np.mean(self.confidence_history))

    @property
    def average_bbox(self) -> np.ndarray:
        """Return average bounding box across recent history (smoothing)"""
        if not self.bbox_history:
            return self.bbox
        return np.mean(self.bbox_history, axis=0)


class ByteTracker:
    """
    ByteTrack multi-object tracker optimized for 1 FPS CCTV footage.

    Two-stage matching strategy:
    1. High confidence detections matched with active tracks (IoU)
    2. Low confidence detections matched with lost tracks (IoU recovery)

    Attributes:
        track_thresh: Minimum confidence for high-confidence detections (default: 0.6)
        match_thresh: IoU threshold for first-stage matching (default: 0.5)
        track_buffer: Frames to keep lost tracks before removal (default: 10 at 1 FPS)
        min_box_area: Minimum bounding box area to filter noise (default: 100)
    """

    def __init__(
        self,
        track_thresh: float = 0.6,
        match_thresh: float = 0.5,
        track_buffer: int = 10,
        min_box_area: float = 100
    ):
        """
        Initialize ByteTracker.

        Args:
            track_thresh: High-confidence threshold (default: 0.6)
            match_thresh: IoU threshold for matching (default: 0.5)
            track_buffer: Frames to buffer lost tracks (default: 10 for 1 FPS)
            min_box_area: Minimum bbox area (default: 100 pixels)
        """
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.track_buffer = track_buffer
        self.min_box_area = min_box_area

        # Track management
        self.tracked_tracks: List[Track] = []
        self.lost_tracks: List[Track] = []
        self.removed_tracks: List[Track] = []

        # Track ID counter
        self.next_id = 1
        self.frame_id = 0

    def update(self, detections: List[Detection]) -> List[Track]:
        """
        Update tracker with new detections.

        Args:
            detections: List of person detections from current frame

        Returns:
            List of active tracks after update
        """
        self.frame_id += 1

        # Filter out low-area detections (noise)
        detections = [d for d in detections if d.area >= self.min_box_area]

        # Split detections by confidence
        high_dets = [d for d in detections if d.confidence >= self.track_thresh]
        low_dets = [d for d in detections if d.confidence < self.track_thresh]

        # Separate active and lost tracks
        unconfirmed_tracks = [t for t in self.tracked_tracks if t.state == TrackState.NEW]
        confirmed_tracks = [t for t in self.tracked_tracks if t.state == TrackState.TRACKED]

        ### Stage 1: Match high-confidence detections with confirmed tracks
        matches_stage1, unmatched_dets_stage1, unmatched_tracks_stage1 = self._match(
            confirmed_tracks, high_dets, self.match_thresh
        )

        # Update matched tracks
        for track_idx, det_idx in matches_stage1:
            confirmed_tracks[track_idx].update(high_dets[det_idx])

        # Collect unmatched confirmed tracks
        unmatched_confirmed = [confirmed_tracks[i] for i in unmatched_tracks_stage1]

        ### Stage 2: Match low-confidence detections with unmatched confirmed tracks
        matches_stage2, unmatched_dets_stage2, unmatched_tracks_stage2 = self._match(
            unmatched_confirmed, low_dets, self.match_thresh * 0.8  # Relaxed threshold
        )

        # Update matched tracks from stage 2
        for track_idx, det_idx in matches_stage2:
            unmatched_confirmed[track_idx].update(low_dets[det_idx])

        # Collect final unmatched tracks
        unmatched_confirmed_final = [unmatched_confirmed[i] for i in unmatched_tracks_stage2]

        ### Stage 3: Match remaining high-confidence detections with lost tracks (recovery)
        matches_stage3, unmatched_dets_stage3, unmatched_lost = self._match(
            self.lost_tracks,
            [high_dets[i] for i in unmatched_dets_stage1],
            self.match_thresh * 0.7  # More relaxed for recovery
        )

        # Recover lost tracks
        for track_idx, det_idx in matches_stage3:
            self.lost_tracks[track_idx].update(high_dets[unmatched_dets_stage1[det_idx]])
            self.tracked_tracks.append(self.lost_tracks[track_idx])

        # Remove recovered tracks from lost list
        self.lost_tracks = [self.lost_tracks[i] for i in unmatched_lost]

        ### Create new tracks for remaining unmatched high-confidence detections
        remaining_high_det_indices = [unmatched_dets_stage1[i] for i in unmatched_dets_stage3]
        for det_idx in remaining_high_det_indices:
            det = high_dets[det_idx]
            new_track = Track(
                track_id=self.next_id,
                bbox=det.bbox,
                confidence=det.confidence,
                frame_id=det.frame_id,
                state=TrackState.NEW
            )
            new_track.hits = 1
            self.tracked_tracks.append(new_track)
            self.next_id += 1

        ### Mark unmatched tracks as missed
        for track in unmatched_confirmed_final:
            track.mark_missed()
            if track.state == TrackState.REMOVED:
                self.removed_tracks.append(track)
            else:
                self.lost_tracks.append(track)

        # Remove unmatched tracks from tracked list
        self.tracked_tracks = [t for t in self.tracked_tracks if t.is_active]

        ### Clean up lost tracks that exceeded buffer
        self.lost_tracks = [t for t in self.lost_tracks if t.state != TrackState.REMOVED]
        for track in self.lost_tracks:
            if track.time_since_update > self.track_buffer:
                track.state = TrackState.REMOVED
                self.removed_tracks.append(track)
        self.lost_tracks = [t for t in self.lost_tracks if t.state != TrackState.REMOVED]

        # Return only actively tracked tracks (exclude NEW tracks with <3 hits)
        return [t for t in self.tracked_tracks if t.state == TrackState.TRACKED]

    def _match(
        self,
        tracks: List[Track],
        detections: List[Detection],
        iou_threshold: float
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Match tracks to detections using IoU-based Hungarian algorithm.

        Args:
            tracks: List of tracks to match
            detections: List of detections to match
            iou_threshold: Minimum IoU for valid match

        Returns:
            Tuple of (matches, unmatched_detections, unmatched_tracks)
            - matches: List of (track_idx, detection_idx) pairs
            - unmatched_detections: List of detection indices
            - unmatched_tracks: List of track indices
        """
        if len(tracks) == 0 or len(detections) == 0:
            return [], list(range(len(detections))), list(range(len(tracks)))

        # Compute IoU cost matrix
        iou_matrix = np.zeros((len(tracks), len(detections)), dtype=np.float32)
        for t_idx, track in enumerate(tracks):
            for d_idx, det in enumerate(detections):
                iou_matrix[t_idx, d_idx] = self._iou(track.tlbr, det.tlbr)

        # Convert IoU to cost (1 - IoU)
        cost_matrix = 1 - iou_matrix

        # Hungarian algorithm for optimal assignment
        row_indices, col_indices = linear_sum_assignment(cost_matrix)

        # Filter matches by IoU threshold
        matches = []
        unmatched_tracks = list(range(len(tracks)))
        unmatched_dets = list(range(len(detections)))

        for row, col in zip(row_indices, col_indices):
            if iou_matrix[row, col] >= iou_threshold:
                matches.append((row, col))
                unmatched_tracks.remove(row)
                unmatched_dets.remove(col)

        return matches, unmatched_dets, unmatched_tracks

    @staticmethod
    def _iou(bbox1: np.ndarray, bbox2: np.ndarray) -> float:
        """
        Calculate Intersection over Union (IoU) between two bounding boxes.

        Args:
            bbox1: First bbox [x1, y1, x2, y2]
            bbox2: Second bbox [x1, y1, x2, y2]

        Returns:
            IoU score (0-1)
        """
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2

        # Calculate intersection area
        x_left = max(x1_1, x1_2)
        y_top = max(y1_1, y1_2)
        x_right = min(x2_1, x2_2)
        y_bottom = min(y2_1, y2_2)

        if x_right < x_left or y_bottom < y_top:
            return 0.0

        intersection = (x_right - x_left) * (y_bottom - y_top)

        # Calculate union area
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection

        if union == 0:
            return 0.0

        return intersection / union

    def reset(self):
        """Reset tracker state"""
        self.tracked_tracks.clear()
        self.lost_tracks.clear()
        self.removed_tracks.clear()
        self.next_id = 1
        self.frame_id = 0
        logger.info("Tracker reset")

    def get_all_tracks(self) -> List[Track]:
        """Get all tracks (active + lost)"""
        return self.tracked_tracks + self.lost_tracks

    def get_active_tracks(self) -> List[Track]:
        """Get only actively tracked tracks (confirmed)"""
        return [t for t in self.tracked_tracks if t.state == TrackState.TRACKED]


def create_byte_tracker(
    track_thresh: float = 0.6,
    match_thresh: float = 0.5,
    track_buffer: int = 10
) -> ByteTracker:
    """
    Factory function to create ByteTracker instance.

    Args:
        track_thresh: High-confidence detection threshold
        match_thresh: IoU matching threshold
        track_buffer: Frames to buffer lost tracks (1 FPS: 10 frames = 10 seconds)

    Returns:
        ByteTracker instance
    """
    return ByteTracker(
        track_thresh=track_thresh,
        match_thresh=match_thresh,
        track_buffer=track_buffer
    )
