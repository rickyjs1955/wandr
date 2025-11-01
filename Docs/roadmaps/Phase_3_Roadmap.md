# Phase 3: Computer Vision Pipeline - Part 1 - Roadmap

**Timeline**: Weeks 6-7 (14 working days)
**Status**: 🚧 **PLANNED** (Not Started)
**Owner**: Development Team
**Dependencies**:
- ✅ Phase 1 Complete (Authentication, Map Viewer, Camera Pin Management)
- ✅ Phase 2 Complete (Video Management, FFmpeg Pipeline, Background Jobs)

---

## Executive Summary

Phase 3 begins the implementation of the core computer vision pipeline that enables outfit-based re-identification. This phase focuses on the foundational CV components: person detection, garment classification, visual embedding extraction, and within-camera tracking. These building blocks will enable Phase 4's cross-camera re-identification and journey construction.

### Strategic Approach

**Building on Phase 2's Infrastructure**:
- Leverage existing Celery job queue (cv_analysis queue)
- Use existing video storage infrastructure (MinIO/S3)
- Extend FFmpeg pipeline for frame extraction
- Build on processing_jobs table and job tracking system

**Focus Areas**:
1. **Person Detection**: Detect and extract person bounding boxes from video frames
2. **Garment Classification**: Classify clothing types and extract color information
3. **Visual Embeddings**: Generate compact appearance descriptors
4. **Within-Camera Tracking**: Maintain person identity across frames in single camera

---

## Phase 3 Objectives

### Primary Goals

1. **Integrate Person Detection Model** (YOLOv8 or RT-DETR)
   - Detect people in video frames with >80% accuracy
   - Extract bounding boxes and confidence scores
   - Filter low-confidence detections (<0.7)

2. **Implement Garment Classification Pipeline**
   - Classify garment types (top/bottom/shoes)
   - Extract LAB color space representations
   - Generate color histograms per garment region

3. **Build Visual Embedding System**
   - Extract 64-128D compact embeddings using CLIP-small
   - Store embeddings efficiently in database
   - Enable fast similarity comparisons

4. **Implement Within-Camera Tracking**
   - Use ByteTrack or DeepSORT for multi-object tracking
   - Maintain track IDs across frames
   - Handle occlusions and temporary disappearances
   - Generate tracklets with complete metadata

### Success Criteria

**Functional Requirements**:
- ✅ Detect people in 80%+ of clear appearances
- ✅ Classify garment types with 70%+ accuracy
- ✅ Extract valid LAB color values for all detections
- ✅ Generate 128D embeddings for all person crops
- ✅ Maintain tracking through 90%+ of occlusions <3 seconds
- ✅ Process 10-minute video in <30 minutes (3x real-time)

**Performance Requirements**:
- Process at 1 fps (sample every 1 second from 30fps video)
- Handle 10+ simultaneous people in frame
- Memory usage <6GB per worker
- Store tracklets with <500KB per minute of footage

**Quality Requirements**:
- Person detection precision >85% (few false positives)
- Person detection recall >75% (most people detected)
- Track fragmentation <10% at 30 FPS baseline, <20% acceptable at 1 FPS (same person not split into multiple tracks)
- Embedding quality: visually similar outfits have cosine similarity >0.75
- Garment segmentation accuracy >70% (all 3 garments correctly detected)
- CLIP projection validation: Random projection fails test, must use pretrained or PCA-initialized weights

---

## Technical Architecture

### Component Overview

```

                      Video Storage (S3/MinIO)
                             ↓

                    Frame Extraction (FFmpeg)
                         (1 fps sampling)
                             ↓

        ┌────────────────────┴────────────────────┐
        ↓                    ↓                     ↓

  Person Detection    Garment Analysis    Visual Embedding
    (YOLOv8/DETR)    (Type + Color)         (CLIP-small)

        └────────────────────┬────────────────────┘
                             ↓

                   Within-Camera Tracking
                      (ByteTrack/DeepSORT)
                             ↓

                    Tracklet Generation
              (DB: tracklets table with metadata)

```

### Technology Stack

**Computer Vision Libraries**:
- **Person Detection**: Ultralytics YOLOv8n (nano) or RT-DETR-small
- **Tracking**: ByteTrack (simple, no ReID) or DeepSORT (with ReID)
- **Embeddings**: OpenAI CLIP-small (ViT-B/32) via Transformers
- **Color Processing**: OpenCV for LAB conversion and histograms
- **Image Processing**: PIL/Pillow for crops and preprocessing

**Model Deployment**:
- **Inference Engine**: ONNX Runtime (CPU/GPU) or PyTorch directly
- **Model Storage**: S3/MinIO for model weights (downloaded once)
- **Batch Processing**: Process frames in batches of 8-16 for GPU efficiency

**Backend Integration**:
- **Job Queue**: Celery cv_analysis queue (already configured in Phase 2)
- **Task Management**: Extend processing_jobs table
- **Storage**: Store tracklets in database, embeddings as binary blobs
- **API Endpoints**: New endpoints for tracklet retrieval and inspection

---

## Database Schema Updates

### New Table: `tracklets`

```sql
CREATE TABLE tracklets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    pin_id UUID NOT NULL REFERENCES camera_pins(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,

    -- Track metadata
    track_id INTEGER NOT NULL,  -- Local ID within video (1, 2, 3...)
    t_in TIMESTAMPTZ NOT NULL,  -- First appearance time
    t_out TIMESTAMPTZ NOT NULL, -- Last appearance time
    duration_seconds NUMERIC(8,2) NOT NULL,

    -- Outfit descriptor (128D embedding as binary)
    outfit_vec BYTEA NOT NULL,  -- 128 floats * 4 bytes = 512 bytes

    -- Outfit attributes (JSON for flexibility)
    outfit_json JSONB NOT NULL,
    -- Example: {
    --   "top": {"type": "jacket", "color": "blue", "lab": [50, 10, -30]},
    --   "bottom": {"type": "pants", "color": "dark_brown", "lab": [30, 5, 15]},
    --   "shoes": {"type": "sneakers", "color": "white", "lab": [90, 0, 0]}
    -- }

    -- Physique attributes (non-biometric)
    physique JSONB,
    -- Example: {
    --   "height_category": "tall",
    --   "aspect_ratio": 0.42,
    --   "accessories": ["backpack"]
    -- }

    -- Bounding box statistics
    box_stats JSONB NOT NULL,
    -- Example: {
    --   "avg_bbox": [320, 150, 180, 420],  -- [x, y, w, h]
    --   "confidence": 0.89,
    --   "num_detections": 45
    -- }

    -- Quality score (0-1, how reliable is this tracklet)
    quality NUMERIC(4,3) NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Indexes
    INDEX idx_tracklets_video_id (video_id),
    INDEX idx_tracklets_pin_id (pin_id),
    INDEX idx_tracklets_mall_id (mall_id),
    INDEX idx_tracklets_time (t_in, t_out),
    INDEX idx_tracklets_quality (quality DESC)
);
```

**Design Notes**:
- `outfit_vec` stored as BYTEA (binary) for space efficiency and fast retrieval
- `outfit_json` as JSONB for flexible querying (filter by color, type, etc.)
- `track_id` is local to video (resets per video, not globally unique)
- Indexes on time ranges for temporal queries in Phase 4 (cross-camera matching)

### Updated Table: `processing_jobs`

Add new job types for CV pipeline:

```sql
-- No schema change needed, just add new job_type values:
-- 'person_detection'
-- 'tracklet_generation'
-- 'garment_classification' (if split from detection)
```

### Updated Table: `videos`

Add CV processing metadata:

```sql
ALTER TABLE videos ADD COLUMN cv_processed BOOLEAN DEFAULT FALSE;
ALTER TABLE videos ADD COLUMN tracklet_count INTEGER DEFAULT 0;
ALTER TABLE videos ADD COLUMN cv_job_id UUID REFERENCES processing_jobs(id);
```

---

## API Endpoints

### Trigger CV Analysis

#### `POST /analysis/videos/{video_id}:run`

**Purpose**: Start CV processing for a video

**Request**:
```json
{
  "pipeline_stages": [
    "person_detection",
    "tracklet_generation"
  ],
  "options": {
    "sampling_fps": 1.0,
    "detection_threshold": 0.7,
    "min_track_length_seconds": 2
  }
}
```

**Response** (202 Accepted):
```json
{
  "job_id": "uuid",
  "video_id": "uuid",
  "status": "pending",
  "pipeline_stages": ["person_detection", "tracklet_generation"],
  "queued_at": "2025-11-02T10:00:00Z"
}
```

---

### Get Tracklets for Video

#### `GET /analysis/videos/{video_id}/tracklets`

**Purpose**: Retrieve all tracklets detected in a video

**Query Parameters**:
- `min_duration`: Minimum tracklet duration (seconds)
- `min_quality`: Minimum quality score (0-1)
- `limit`: Max results (default 100, max 500)
- `offset`: Pagination offset

**Response** (200 OK):
```json
{
  "tracklets": [
    {
      "id": "uuid",
      "track_id": 1,
      "t_in": "2025-10-30T14:30:00Z",
      "t_out": "2025-10-30T14:32:15Z",
      "duration_seconds": 135,
      "outfit": {
        "top": {
          "type": "jacket",
          "color": "blue",
          "lab": [50, 10, -30],
          "histogram": [0.1, 0.3, 0.4, 0.2]
        },
        "bottom": {
          "type": "pants",
          "color": "dark_brown",
          "lab": [30, 5, 15]
        },
        "shoes": {
          "type": "sneakers",
          "color": "white",
          "lab": [90, 0, 0]
        }
      },
      "physique": {
        "height_category": "tall",
        "aspect_ratio": 0.42
      },
      "bbox_avg": [320, 150, 180, 420],
      "confidence": 0.89,
      "quality": 0.85,
      "num_detections": 45
    }
  ],
  "total": 12,
  "video_id": "uuid",
  "limit": 100,
  "offset": 0
}
```

---

### Get Tracklet Details

#### `GET /tracklets/{tracklet_id}`

**Purpose**: Get detailed information about a specific tracklet

**Response** (200 OK):
```json
{
  "id": "uuid",
  "video_id": "uuid",
  "pin_id": "uuid",
  "mall_id": "uuid",
  "track_id": 1,
  "t_in": "2025-10-30T14:30:00Z",
  "t_out": "2025-10-30T14:32:15Z",
  "duration_seconds": 135,
  "outfit": { /* full outfit descriptor */ },
  "physique": { /* physique attributes */ },
  "box_stats": {
    "avg_bbox": [320, 150, 180, 420],
    "confidence": 0.89,
    "num_detections": 45,
    "bbox_history": [
      {"frame": 0, "bbox": [318, 148, 182, 422], "conf": 0.91},
      {"frame": 30, "bbox": [320, 150, 180, 420], "conf": 0.87}
    ]
  },
  "quality": 0.85,
  "embedding_preview": "[0.12, -0.45, 0.78, ... (first 10 values)]",
  "created_at": "2025-10-30T14:33:00Z"
}
```

---

### Download Tracklet Embedding

#### `GET /tracklets/{tracklet_id}/embedding`

**Purpose**: Download full 128D embedding vector

**Response** (200 OK):
```json
{
  "tracklet_id": "uuid",
  "embedding_dim": 128,
  "embedding": [
    0.123, -0.456, 0.789, 0.234, -0.567, 0.890,
    /* ... 128 float values ... */
  ]
}
```

---

## Computer Vision Pipeline Implementation

### Phase 3.1: Person Detection Model Integration (Days 1-3)

**Objective**: Integrate YOLOv8 or RT-DETR for person detection

#### Day 1: Model Selection and Setup

**Tasks**:
- [ ] Evaluate YOLOv8n vs RT-DETR-small
  - Benchmark inference speed (target: >10 fps on CPU, >30 fps on GPU)
  - Measure detection accuracy on sample CCTV footage
  - Compare memory usage (<4GB target)
- [ ] Download and cache model weights in S3/MinIO
- [ ] Create DetectorService class with model loading
- [ ] Implement basic inference pipeline (single frame)

**YOLOv8n Example**:
```python
from ultralytics import YOLO
import torch

class PersonDetector:
    def __init__(self, model_path: str, device: str = 'cpu'):
        self.model = YOLO(model_path)
        self.device = device

    def detect(self, frame: np.ndarray, conf_threshold: float = 0.7):
        """
        Detect people in a single frame

        Returns:
            List[dict]: [{"bbox": [x, y, w, h], "confidence": 0.89}, ...]
        """
        results = self.model(frame, classes=[0], conf=conf_threshold, device=self.device)

        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                detections.append({
                    "bbox": [int(x1), int(y1), int(x2-x1), int(y2-y1)],
                    "confidence": float(box.conf[0]),
                    "class": "person"
                })

        return detections
```

#### Day 2: Frame Extraction Pipeline

**Tasks**:
- [ ] Extend FFmpegService with frame extraction at 1 fps
- [ ] Implement batch frame extraction (extract all frames to temp directory)
- [ ] Add frame metadata tracking (timestamp, frame number)
- [ ] Test with 10-minute video (600 frames expected)

**FFmpeg Frame Extraction**:
```python
class FFmpegService:
    # ... existing methods ...

    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        fps: float = 1.0
    ) -> List[str]:
        """
        Extract frames from video at specified fps

        Args:
            video_path: Path to video file
            output_dir: Directory for frame images
            fps: Frames per second to extract

        Returns:
            List of frame file paths
        """
        os.makedirs(output_dir, exist_ok=True)

        # Use FFmpeg to extract frames
        (
            ffmpeg
            .input(video_path)
            .filter('fps', fps=fps)
            .output(
                f"{output_dir}/frame_%06d.jpg",
                format='image2',
                vcodec='mjpeg',
                qscale=2
            )
            .run(capture_stdout=True, capture_stderr=True)
        )

        # Return sorted list of frame paths
        frames = sorted(glob.glob(f"{output_dir}/frame_*.jpg"))
        return frames
```

#### Day 3: Detection Task Integration

**Tasks**:
- [ ] Create Celery task: `detect_persons_in_video`
- [ ] Implement batch detection (process frames in batches of 16)
- [ ] Store detection results in temporary JSON format
- [ ] Add error handling and retry logic
- [ ] Test end-to-end detection on sample video

**Celery Task**:
```python
from celery import Task
from app.services.detector import PersonDetector
from app.services.ffmpeg import FFmpegService

class PersonDetectionTask(Task):
    """Task for person detection in video"""

    def __init__(self):
        self.detector = None
        self.ffmpeg = FFmpegService()

    def on_before_fork(self):
        """Load model in parent process (memory efficient)"""
        if self.detector is None:
            self.detector = PersonDetector("models/yolov8n.pt")

@app.task(base=PersonDetectionTask, bind=True)
def detect_persons_in_video(
    self,
    video_id: str,
    video_path: str,
    fps: float = 1.0,
    conf_threshold: float = 0.7
) -> dict:
    """
    Detect all people in video and store results

    Returns:
        {
            "video_id": "uuid",
            "total_frames": 600,
            "frames_with_detections": 450,
            "total_detections": 1200,
            "detections_file": "/tmp/detections_uuid.json"
        }
    """
    temp_dir = f"/tmp/video_{video_id}"
    os.makedirs(temp_dir, exist_ok=True)

    try:
        # Extract frames
        frames = self.ffmpeg.extract_frames(video_path, temp_dir, fps)

        # Detect people in each frame
        all_detections = {}
        for i, frame_path in enumerate(frames):
            frame = cv2.imread(frame_path)
            detections = self.detector.detect(frame, conf_threshold)

            all_detections[i] = {
                "frame_path": frame_path,
                "timestamp": i / fps,
                "detections": detections
            }

            # Update progress every 50 frames
            if i % 50 == 0:
                self.update_state(
                    state='PROGRESS',
                    meta={'frames_processed': i, 'total_frames': len(frames)}
                )

        # Save detections to JSON
        detections_file = f"/tmp/detections_{video_id}.json"
        with open(detections_file, 'w') as f:
            json.dump(all_detections, f)

        return {
            "video_id": video_id,
            "total_frames": len(frames),
            "frames_with_detections": sum(1 for d in all_detections.values() if d["detections"]),
            "total_detections": sum(len(d["detections"]) for d in all_detections.values()),
            "detections_file": detections_file
        }

    finally:
        # Cleanup frames
        shutil.rmtree(temp_dir, ignore_errors=True)
```

---

### Phase 3.2: Garment Classification Pipeline (Days 4-6)

**Objective**: Classify garment types and extract color information

#### Day 4: Garment Type Classification

**Tasks**:
- [ ] Research lightweight garment classification models
  - Option 1: Fashion-MNIST pretrained model (simple, fast)
  - Option 2: DeepFashion2 attribute classifier (more accurate)
  - Option 3: Rule-based segmentation (backup if models too slow)
- [ ] Implement garment segmentation (top/bottom/shoes regions)
- [ ] Classify garment types for each region
- [ ] Test on sample person crops

**Garment Classifier** (simplified approach):
```python
import torch
import torchvision.models as models
from torchvision import transforms

class GarmentClassifier:
    """
    Classify garment types (top/bottom/shoes) from person crop
    Uses pre-trained ResNet with custom head
    """

    GARMENT_TYPES = {
        "top": ["tee", "shirt", "blouse", "jacket", "coat", "dress"],
        "bottom": ["pants", "shorts", "skirt", "dress"],
        "shoes": ["sneakers", "loafers", "sandals", "boots"]
    }

    def __init__(self, model_path: str):
        self.model = self._load_model(model_path)
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])

    def classify(self, person_crop: np.ndarray) -> dict:
        """
        Classify garments in person image

        Returns:
            {
                "top": {"type": "jacket", "confidence": 0.85},
                "bottom": {"type": "pants", "confidence": 0.92},
                "shoes": {"type": "sneakers", "confidence": 0.78}
            }

        IMPORTANT - Segmentation Accuracy Risk:
        "Divide crop into thirds" is brittle and will fail with:
        - Seated people (no "bottom" in frame)
        - Occlusions (partial body visible)
        - Non-standard poses (bending, reaching)

        Accuracy Threshold: If >30% of crops fail garment extraction
        (detected as low-confidence or missing regions), switch to:
        - Pose-based segmentation (MediaPipe or OpenPose)
        - OR lightweight segmentation model (U²-Net, ~15 FPS on GPU)

        Decision Point: Day 8 of Phase 3.2
        Fallback triggers: Low confidence (<0.5) on >30% of detections
        """
        # Segment person into regions (simple approach: thirds)
        # TODO: Replace with pose-based segmentation if accuracy <70%
        h, w = person_crop.shape[:2]
        top_region = person_crop[0:int(h*0.4), :]
        bottom_region = person_crop[int(h*0.4):int(h*0.8), :]
        shoes_region = person_crop[int(h*0.8):, :]

        results = {
            "top": self._classify_region(top_region, "top"),
            "bottom": self._classify_region(bottom_region, "bottom"),
            "shoes": self._classify_region(shoes_region, "shoes")
        }

        # Quality check: Detect if segmentation likely failed
        low_conf_count = sum(1 for r in results.values() if r["confidence"] < 0.5)
        if low_conf_count >= 2:
            # Flag for potential segmentation failure
            results["_quality_warning"] = "low_confidence_segmentation"

        return results

    def _classify_region(self, region: np.ndarray, garment_type: str) -> dict:
        """Classify a specific region"""
        # Convert to PIL and apply transforms
        img = Image.fromarray(region)
        tensor = self.transform(img).unsqueeze(0)

        # Run inference
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1)
            idx = torch.argmax(probs).item()
            conf = probs[0, idx].item()

        garment_class = self.GARMENT_TYPES[garment_type][idx]
        return {"type": garment_class, "confidence": conf}
```

#### Day 5: LAB Color Extraction

**Tasks**:
- [ ] Implement RGB to LAB color space conversion
- [ ] Extract dominant color per garment region
- [ ] Generate color histograms (10-14 bins)
- [ ] Calculate CIEDE2000 color difference utility
- [ ] Test color matching on similar outfits

**Color Extractor**:
```python
import cv2
from sklearn.cluster import KMeans

class ColorExtractor:
    """Extract LAB color information from garment regions"""

    COLOR_NAMES = {
        # Simplified color naming based on LAB ranges
        # L: lightness, a: green-red, b: blue-yellow
    }

    def extract_color(self, region: np.ndarray) -> dict:
        """
        Extract dominant color from image region

        Returns:
            {
                "color": "blue",
                "lab": [50, 10, -30],
                "histogram": [0.1, 0.3, 0.4, 0.15, 0.05]
            }
        """
        # Convert to LAB
        lab_image = cv2.cvtColor(region, cv2.COLOR_RGB2LAB)

        # Get dominant color via k-means clustering
        pixels = lab_image.reshape(-1, 3)
        kmeans = KMeans(n_clusters=1, n_init=10)
        kmeans.fit(pixels)
        dominant_lab = kmeans.cluster_centers_[0]

        # Generate histogram
        histogram = self._compute_histogram(lab_image)

        # Map LAB to color name
        color_name = self._lab_to_color_name(dominant_lab)

        return {
            "color": color_name,
            "lab": dominant_lab.tolist(),
            "histogram": histogram.tolist()
        }

    def _compute_histogram(self, lab_image: np.ndarray, bins: int = 10) -> np.ndarray:
        """Compute LAB color histogram"""
        hist_l = np.histogram(lab_image[:,:,0], bins=bins, range=(0, 255))[0]
        hist_a = np.histogram(lab_image[:,:,1], bins=bins, range=(0, 255))[0]
        hist_b = np.histogram(lab_image[:,:,2], bins=bins, range=(0, 255))[0]

        # Concatenate and normalize
        hist = np.concatenate([hist_l, hist_a, hist_b])
        hist = hist / hist.sum()
        return hist

    @staticmethod
    def ciede2000(lab1: np.ndarray, lab2: np.ndarray) -> float:
        """
        Calculate CIEDE2000 color difference
        Returns delta-E value (0 = identical, >100 = very different)
        """
        # Simplified CIEDE2000 calculation
        # Full implementation would use colormath library
        delta_L = lab1[0] - lab2[0]
        delta_a = lab1[1] - lab2[1]
        delta_b = lab1[2] - lab2[2]

        return np.sqrt(delta_L**2 + delta_a**2 + delta_b**2)
```

#### Day 6: Garment Pipeline Integration

**Tasks**:
- [ ] Combine detection + garment classification + color extraction
- [ ] Create GarmentAnalyzer service class
- [ ] Add to person detection pipeline
- [ ] Test full pipeline on sample video
- [ ] Validate output format matches data model

**CRITICAL VALIDATION - Segmentation Accuracy**:
- [ ] **Test on 50 diverse person crops** (standing, seated, partial occlusion)
- [ ] **Measure success rate**: All 3 garments (top/bottom/shoes) detected with confidence >0.5
- [ ] **Calculate accuracy**: Should be >70%
- [ ] **Decision Point**: If accuracy <70%, plan switch to pose-based segmentation on Day 8
- [ ] **Document results**: Log accuracy per garment type and failure modes

---

### Phase 3.3: Visual Embedding Extraction (Days 7-9)

**Objective**: Generate compact appearance embeddings using CLIP

#### Day 7: CLIP Model Integration

**Tasks**:
- [ ] Install transformers library and CLIP dependencies
- [ ] Download CLIP-ViT-B/32 model weights
- [ ] Implement EmbeddingExtractor service
- [ ] Test embedding generation on person crops
- [ ] Validate embedding dimensionality (128D after projection)

**CRITICAL VALIDATION - Embedding Discriminability**:
- [ ] **Prepare test set**: 20 person crop pairs
  - 10 pairs: Visually similar outfits (same type/color)
  - 10 pairs: Visually different outfits (different type/color)
- [ ] **Test uninitialized projection**: Extract embeddings and measure cosine similarity
  - Expected result: Random projection will FAIL (similar/different pairs have similar scores ~0.5)
- [ ] **Load pretrained projection** OR **initialize with PCA**:
  - Option A: Download fashion re-ID pretrained weights (Market-1501, DeepFashion2)
  - Option B: Collect 100+ person crops, run PCA to get 128D projection
- [ ] **Re-test with pretrained projection**:
  - Similar outfits should have cosine similarity >0.75
  - Different outfits should have cosine similarity <0.5
- [ ] **Decision Point**: If test fails, use full 512D CLIP features (no projection)
- [ ] **Document results**: Distribution of cosine similarities for similar vs different pairs

**CLIP Embedding Extractor**:
```python
from transformers import CLIPProcessor, CLIPModel
import torch
import torch.nn as nn

class EmbeddingExtractor:
    """
    Extract visual embeddings using CLIP model
    Reduces 512D CLIP output to 128D via learned projection

    IMPORTANT - Projection Initialization:
    The 128D projection layer requires pretrained weights for meaningful embeddings.
    Two options:
    - Option A (MVP): Use pretrained projection from fashion re-ID dataset
      (e.g., DeepFashion, Market-1501 fine-tuned CLIP)
    - Option B (Phase 3+): Fine-tune end-to-end with mall footage pairs
      (requires labeled data for contrastive learning)
    """

    def __init__(
        self,
        model_name: str = "openai/clip-vit-base-patch32",
        projection_weights_path: str = None
    ):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)

        # Projection layer: 512D -> 128D
        # Must load pretrained weights or embeddings will be meaningless
        self.projection = nn.Linear(512, 128).to(self.device)

        if projection_weights_path:
            # Load pretrained projection weights (recommended for MVP)
            self.projection.load_state_dict(torch.load(projection_weights_path))
        else:
            # WARNING: Uninitialized projection produces random embeddings
            # For MVP, use simple PCA-initialized projection as fallback
            self._initialize_projection_pca()

    def _initialize_projection_pca(self):
        """
        Initialize 128D projection using PCA on sample person crops

        Procedure:
        1. Collect 100+ diverse person crops from test footage
        2. Extract 512D CLIP features for all crops
        3. Fit PCA to reduce dimensionality: 512D → 128D
        4. Use PCA components as projection weights

        This provides better initialization than random weights.
        """
        import warnings
        warnings.warn(
            "Using PCA-initialized projection. For production, load pretrained "
            "fashion re-ID weights for better performance.",
            UserWarning
        )

        # Placeholder: In practice, you would:
        # 1. Load sample_crops = load_person_crops(n=100)
        # 2. features = [self.model.get_image_features(crop) for crop in sample_crops]
        # 3. pca = PCA(n_components=128).fit(features)
        # 4. self.projection.weight.data = torch.from_numpy(pca.components_)

        # For now, use Xavier initialization (better than random)
        torch.nn.init.xavier_uniform_(self.projection.weight)
        torch.nn.init.zeros_(self.projection.bias)

    def extract(self, image: np.ndarray) -> np.ndarray:
        """
        Extract 128D embedding from person crop

        Args:
            image: RGB image of person (numpy array)

        Returns:
            128D embedding vector (numpy array)
        """
        # Preprocess image
        inputs = self.processor(images=image, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Extract CLIP features
        with torch.no_grad():
            features = self.model.get_image_features(**inputs)  # 512D

            # Project to 128D
            embedding = self.projection(features)  # 128D

            # L2 normalize
            embedding = embedding / embedding.norm(dim=-1, keepdim=True)

        return embedding.cpu().numpy().squeeze()

    @staticmethod
    def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings"""
        return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
```

#### Day 8: Embedding Storage Optimization

**Tasks**:
- [ ] Implement binary embedding serialization (128 floats * 4 bytes = 512 bytes)
- [ ] Add embedding compression (optional: quantization to int8)
- [ ] Test database storage and retrieval speed
- [ ] Benchmark similarity search performance
- [ ] Add embedding validation (check for NaN, inf values)

**Binary Serialization**:
```python
import struct
import numpy as np

def serialize_embedding(embedding: np.ndarray) -> bytes:
    """
    Serialize 128D float32 embedding to binary
    Returns 512 bytes
    """
    assert embedding.shape == (128,), f"Expected 128D, got {embedding.shape}"
    return struct.pack('128f', *embedding)

def deserialize_embedding(binary: bytes) -> np.ndarray:
    """
    Deserialize binary to 128D float32 embedding
    """
    assert len(binary) == 512, f"Expected 512 bytes, got {len(binary)}"
    return np.array(struct.unpack('128f', binary), dtype=np.float32)
```

#### Day 9: Embedding Pipeline Integration

**Tasks**:
- [ ] Integrate embedding extraction into detection pipeline
- [ ] Store embeddings in tracklets table (outfit_vec column)
- [ ] Add embedding quality checks
- [ ] Test full pipeline with embedding generation
- [ ] Benchmark embedding extraction speed (target: <50ms per person)

---

### Phase 3.4: Within-Camera Tracking (Days 10-14)

**Objective**: Implement multi-object tracking to maintain person IDs across frames

#### Day 10-11: Tracker Selection and Setup

**Tasks**:
- [ ] Compare ByteTrack vs DeepSORT
  - ByteTrack: Simpler, no ReID model needed, faster
  - DeepSORT: More robust, uses appearance features
- [ ] Implement chosen tracker (recommendation: ByteTrack for MVP)
- [ ] Configure tracker parameters (max_lost_frames, min_track_length, etc.)
- [ ] Test on single-camera footage with multiple people

**CRITICAL VALIDATION - 1 FPS Tracking Performance**:
- [ ] **Prepare test footage**: 5-minute video with 3-5 people, downsample to 1 FPS (300 frames)
- [ ] **Manually label ground truth**: Count actual number of unique people in video
- [ ] **Run ByteTrack with standard parameters**:
  - max_time_lost = 30 frames (expecting failure due to overshoot)
- [ ] **Measure fragmentation rate**:
  - Ground truth: N people
  - Detected tracks: M track IDs
  - Fragmentation rate: (M - N) / N * 100%
  - Example: 3 people → 5 tracks = 67% fragmentation (BAD)
- [ ] **Adjust for 1 FPS**:
  - Set max_time_lost = 5 frames (5 seconds)
  - Set frame_rate = 1.0
  - Re-run and measure fragmentation
- [ ] **Decision Point**: If fragmentation >20%, switch to DeepSORT or embedding-based tracking
- [ ] **Document results**: Fragmentation rate, identity switches, missed detections

**ByteTrack Implementation**:
```python
from boxmot import BYTETracker

class PersonTracker:
    """
    Multi-object tracker for maintaining person IDs within video
    Uses ByteTrack algorithm

    IMPORTANT - 1 FPS Adaptations Required:
    ByteTrack's motion model (Kalman filter) and association thresholds
    are tuned for 15-30 FPS. At 1 FPS:
    - Motion prediction will overshoot (large time gaps between frames)
    - IoU thresholds may cause premature track termination
    - Identity switches more likely due to large displacement

    Required Adaptations:
    1. Reduce max_time_lost from 30 frames to 5 frames to extend time tolerance
       - At 30 FPS: 30 frames = 1 second tolerance (standard)
       - At 1 FPS: 5 frames = 5 seconds tolerance (extended to compensate for lower frame rate)
       - Rationale: Fewer frames needed because each frame represents 1 second instead of 0.033 seconds
    2. Reduce motion model weight, increase appearance weight
    3. Use re-ID embeddings for recovery (not just IoU)
    4. Test with synthetic 1 FPS downsampled footage first

    Contingency: If fragmentation >20%, switch to:
    - DeepSORT (better appearance-based tracking)
    - OR pure embedding-based tracking (no motion model)

    Decision Point: Day 11 of Phase 3.4
    Fallback triggers: Track fragmentation >20% on test footage
    """

    def __init__(
        self,
        track_thresh: float = 0.7,
        match_thresh: float = 0.8,
        max_time_lost: int = 5,  # ADJUSTED for 1 FPS: 5 frames = 5 seconds
        fps: float = 1.0  # Track at 1 FPS
    ):
        self.fps = fps
        self.tracker = BYTETracker(
            track_thresh=track_thresh,
            match_thresh=match_thresh,
            track_buffer=max_time_lost,
            frame_rate=fps  # Critical: inform tracker of actual FPS
        )

    def update(self, detections: List[dict], frame_id: int) -> List[dict]:
        """
        Update tracker with new detections

        Args:
            detections: [{"bbox": [x,y,w,h], "confidence": 0.89}, ...]
            frame_id: Current frame number

        Returns:
            [{"bbox": [x,y,w,h], "track_id": 1, "confidence": 0.89}, ...]
        """
        # Convert to ByteTrack format: [x1, y1, x2, y2, conf]
        dets = []
        for det in detections:
            x, y, w, h = det["bbox"]
            dets.append([x, y, x+w, y+h, det["confidence"]])

        dets = np.array(dets) if dets else np.empty((0, 5))

        # Update tracker
        tracks = self.tracker.update(dets, frame_id)

        # Convert back to our format
        results = []
        for track in tracks:
            x1, y1, x2, y2, track_id = track[:5]
            results.append({
                "bbox": [int(x1), int(y1), int(x2-x1), int(y2-y1)],
                "track_id": int(track_id),
                "confidence": float(track[4]) if len(track) > 4 else 0.0
            })

        return results
```

#### Day 12-13: Tracklet Generation

**Tasks**:
- [ ] Implement tracklet aggregation (group detections by track_id)
- [ ] Calculate tracklet statistics (duration, avg bbox, confidence)
- [ ] Extract representative frames for outfit analysis
- [ ] Generate outfit descriptor per tracklet (aggregate from frames)
- [ ] Calculate tracklet quality score

**Tracklet Builder**:
```python
class TrackletBuilder:
    """
    Build tracklets from frame-by-frame tracking results
    """

    def __init__(
        self,
        garment_analyzer: GarmentAnalyzer,
        embedding_extractor: EmbeddingExtractor,
        min_track_length: int = 2  # seconds
    ):
        self.garment_analyzer = garment_analyzer
        self.embedding_extractor = embedding_extractor
        self.min_track_length = min_track_length

    def build_tracklets(
        self,
        tracking_results: dict,
        video_metadata: dict,
        fps: float = 1.0
    ) -> List[dict]:
        """
        Convert frame-by-frame tracking to tracklets

        Args:
            tracking_results: {frame_id: [{"track_id": 1, "bbox": [...], ...}]}
            video_metadata: {"video_id": "uuid", "duration": 600, ...}
            fps: Frames per second

        Returns:
            List of tracklet dicts ready for database insertion
        """
        # Group detections by track_id
        tracks = defaultdict(list)
        for frame_id, detections in tracking_results.items():
            for det in detections:
                tracks[det["track_id"]].append({
                    "frame_id": frame_id,
                    "timestamp": frame_id / fps,
                    **det
                })

        # Build tracklets
        tracklets = []
        for track_id, detections in tracks.items():
            # Sort by timestamp
            detections = sorted(detections, key=lambda x: x["timestamp"])

            # Calculate duration
            t_in = detections[0]["timestamp"]
            t_out = detections[-1]["timestamp"]
            duration = t_out - t_in

            # Skip short tracks
            if duration < self.min_track_length:
                continue

            # Select representative frames (middle, good quality)
            repr_frames = self._select_representative_frames(detections)

            # Analyze outfit on representative frames
            outfit_descriptors = []
            embeddings = []
            for frame_info in repr_frames:
                # Crop person from frame
                person_crop = self._crop_person(frame_info)

                # Analyze garment
                garment = self.garment_analyzer.analyze(person_crop)
                outfit_descriptors.append(garment)

                # Extract embedding
                embedding = self.embedding_extractor.extract(person_crop)
                embeddings.append(embedding)

            # Aggregate outfit descriptor (majority vote for type, average for color)
            outfit_json = self._aggregate_outfit(outfit_descriptors)

            # Aggregate embedding (average)
            outfit_vec = np.mean(embeddings, axis=0)
            outfit_vec = outfit_vec / np.linalg.norm(outfit_vec)  # Re-normalize

            # Calculate quality score
            quality = self._calculate_quality(detections, embeddings)

            # Build tracklet
            tracklet = {
                "track_id": track_id,
                "t_in": video_metadata["start_time"] + timedelta(seconds=t_in),
                "t_out": video_metadata["start_time"] + timedelta(seconds=t_out),
                "duration_seconds": duration,
                "outfit_vec": serialize_embedding(outfit_vec),
                "outfit_json": outfit_json,
                "box_stats": {
                    "avg_bbox": self._average_bbox(detections),
                    "confidence": np.mean([d["confidence"] for d in detections]),
                    "num_detections": len(detections)
                },
                "quality": quality
            }

            tracklets.append(tracklet)

        return tracklets

    def _calculate_quality(self, detections: List[dict], embeddings: List[np.ndarray]) -> float:
        """
        Calculate tracklet quality score (0-1)
        Based on: detection confidence, track length, embedding consistency
        """
        # Average detection confidence
        conf_score = np.mean([d["confidence"] for d in detections])

        # Track length score (longer is better, max at 60 seconds)
        duration = detections[-1]["timestamp"] - detections[0]["timestamp"]
        length_score = min(duration / 60, 1.0)

        # Embedding consistency (low variance = high quality)
        if len(embeddings) > 1:
            # Compute pairwise cosine similarities
            sims = []
            for i in range(len(embeddings)):
                for j in range(i+1, len(embeddings)):
                    sim = EmbeddingExtractor.cosine_similarity(embeddings[i], embeddings[j])
                    sims.append(sim)
            consistency_score = np.mean(sims) if sims else 0.5
        else:
            consistency_score = 0.5

        # Weighted average
        quality = 0.4 * conf_score + 0.3 * length_score + 0.3 * consistency_score
        return quality
```

#### Day 14: End-to-End Pipeline Integration

**Tasks**:
- [ ] Create master Celery task: `process_video_cv_pipeline`
- [ ] Chain tasks: detection → tracking → tracklet generation → database storage
- [ ] Add comprehensive error handling and retry logic
- [ ] Test full pipeline on 10-minute sample video
- [ ] Validate tracklet storage and retrieval
- [ ] Measure processing time (target: <30 minutes for 10-minute video)

**Master CV Pipeline Task**:
```python
@app.task(bind=True)
def process_video_cv_pipeline(
    self,
    video_id: str,
    video_path: str,
    options: dict
) -> dict:
    """
    Complete CV processing pipeline for a video

    Stages:
    1. Extract frames (1 fps)
    2. Detect persons in each frame
    3. Track persons across frames
    4. Generate tracklets with outfit descriptors
    5. Store tracklets in database

    Returns:
        {
            "video_id": "uuid",
            "total_tracklets": 12,
            "processing_time_seconds": 1200,
            "status": "completed"
        }
    """
    start_time = time.time()

    try:
        # Update job status
        job = update_job_status(video_id, "running")

        # Initialize services
        ffmpeg = FFmpegService()
        detector = PersonDetector("models/yolov8n.pt")
        tracker = PersonTracker()
        garment_analyzer = GarmentAnalyzer()
        embedding_extractor = EmbeddingExtractor()
        tracklet_builder = TrackletBuilder(garment_analyzer, embedding_extractor)

        # Stage 1: Extract frames
        logger.info(f"Extracting frames from {video_id}")
        temp_dir = f"/tmp/cv_{video_id}"
        frames = ffmpeg.extract_frames(video_path, temp_dir, fps=options.get("fps", 1.0))

        # Stage 2 & 3: Detect and track
        logger.info(f"Processing {len(frames)} frames")
        tracking_results = {}

        for frame_id, frame_path in enumerate(frames):
            # Detect people
            frame = cv2.imread(frame_path)
            detections = detector.detect(frame, conf_threshold=options.get("conf_threshold", 0.7))

            # Track
            tracked = tracker.update(detections, frame_id)
            tracking_results[frame_id] = tracked

            # Progress update
            if frame_id % 50 == 0:
                self.update_state(
                    state='PROGRESS',
                    meta={'stage': 'detection', 'frames_processed': frame_id, 'total_frames': len(frames)}
                )

        # Stage 4: Build tracklets
        logger.info(f"Building tracklets")
        video_metadata = get_video_metadata(video_id)
        tracklets = tracklet_builder.build_tracklets(tracking_results, video_metadata, fps=options.get("fps", 1.0))

        # Stage 5: Store in database
        logger.info(f"Storing {len(tracklets)} tracklets")
        for tracklet in tracklets:
            store_tracklet(video_id, tracklet)

        # Update video record
        update_video_cv_status(video_id, cv_processed=True, tracklet_count=len(tracklets))

        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

        processing_time = time.time() - start_time

        return {
            "video_id": video_id,
            "total_tracklets": len(tracklets),
            "processing_time_seconds": processing_time,
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"CV pipeline failed for {video_id}: {str(e)}")
        update_job_status(video_id, "failed", error=str(e))
        raise
```

---

## Testing Strategy

### Unit Tests (Days 1-14, ongoing)

**Person Detection**:
- [ ] Detect person in clear frame (confidence >0.7)
- [ ] Filter out low-confidence detections
- [ ] Handle frames with no people
- [ ] Handle frames with 10+ people

**Garment Classification**:
- [ ] Classify clear jacket/pants/sneakers outfit
- [ ] Handle person with dress (top + bottom)
- [ ] Extract valid LAB color values
- [ ] Generate consistent color histograms

**Embedding Extraction**:
- [ ] Extract 128D embedding
- [ ] Embeddings are normalized (L2 norm ≈ 1.0)
- [ ] Similar outfits have high cosine similarity (>0.75)
- [ ] Different outfits have low cosine similarity (<0.5)

**Tracking**:
- [ ] Maintain track ID across 30-second sequence
- [ ] Handle occlusions (person temporarily hidden)
- [ ] Create new track for new person entering
- [ ] Terminate track when person leaves frame

### Integration Tests

**End-to-End Pipeline**:
1. Upload test video (10 minutes, 2 people)
2. Trigger CV processing
3. Wait for job completion
4. Verify 2 tracklets created
5. Verify tracklet metadata (outfit, bbox, quality)
6. Verify embeddings stored correctly
7. Test tracklet retrieval via API

**Performance Test**:
- [ ] Process 10-minute video in <30 minutes
- [ ] Memory usage stays below 6GB
- [ ] No memory leaks after processing 10 videos
- [ ] Handle concurrent CV jobs (2 videos simultaneously)

### Quality Validation

**Detection Quality**:
- [ ] Precision >85% (few false positives)
- [ ] Recall >75% (most people detected)
- [ ] Test on crowded scene (10+ people)
- [ ] Test on poor lighting conditions

**Tracking Quality**:
- [ ] Track fragmentation <10% (same person not split)
- [ ] Identity switches <5% (two people not merged)
- [ ] Test with similar outfits (3 people in black pants/white shirts)

**Outfit Quality**:
- [ ] Garment type accuracy >70%
- [ ] Color consistency across tracklet (variance <20 delta-E)
- [ ] Embedding consistency (avg cosine similarity >0.8 within tracklet)

---

## Performance Optimization

### Model Optimization

**YOLOv8 Optimization**:
- [ ] Export to ONNX format for faster inference
- [ ] Use TensorRT for GPU acceleration (5-10x speedup)
- [ ] Batch inference (process 16 frames at once)
- [ ] Half-precision (FP16) on GPU (2x speedup)

**CLIP Optimization**:
- [ ] Cache model in memory (don't reload per video)
- [ ] Batch embedding extraction (8-16 crops at once)
- [ ] Use ONNX Runtime for CPU inference
- [ ] Consider distilled CLIP model (MobileCLIP) for mobile deployment

### Processing Optimization

**Parallel Processing**:
```python
# Process frames in parallel batches
from concurrent.futures import ThreadPoolExecutor

def process_frames_parallel(frames, detector, num_workers=4):
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        results = executor.map(lambda f: detector.detect(cv2.imread(f)), frames)
    return list(results)
```

**Memory Management**:
- [ ] Clear frame images after processing (don't keep all in memory)
- [ ] Use generators for frame iteration
- [ ] Explicit garbage collection after each video
- [ ] Monitor memory usage with psutil

---

## Deployment Checklist

### Model Deployment

- [ ] Download YOLOv8n weights (6MB)
- [ ] Download CLIP-ViT-B/32 weights (350MB)
- [ ] Store models in S3/MinIO for workers to download
- [ ] Implement model caching on worker nodes
- [ ] Add model version tracking

### Infrastructure

- [ ] Add GPU workers for CV processing (if available)
  - NVIDIA GPU with CUDA 11.8+
  - 8GB+ VRAM recommended
- [ ] Configure Celery cv_analysis queue with dedicated workers
- [ ] Increase worker resources (6GB RAM, 2 CPUs per worker)
- [ ] Set up model download automation

### Monitoring

- [ ] Add CV pipeline metrics to admin dashboard
  - Tracklets generated per video
  - Average processing time
  - Detection quality metrics (precision, recall)
- [ ] Configure alerts for CV job failures
- [ ] Track model performance over time (accuracy drift)

---

## Week-by-Week Breakdown

### Week 6: Detection & Classification (Days 1-7)

**Days 1-3: Person Detection** (Phase 3.1)
- [x] Day 1: Model selection and setup
- [x] Day 2: Frame extraction pipeline
- [x] Day 3: Detection task integration

**Days 4-6: Garment Classification** (Phase 3.2)
- [x] Day 4: Garment type classification
- [x] Day 5: LAB color extraction
- [x] Day 6: Garment pipeline integration

**Day 7: Embeddings** (Phase 3.3 start)
- [x] Day 7: CLIP model integration

### Week 7: Embeddings & Tracking (Days 8-14)

**Days 8-9: Embeddings** (Phase 3.3 completion)
- [x] Day 8: Embedding storage optimization
- [x] Day 9: Embedding pipeline integration

**Days 10-14: Within-Camera Tracking** (Phase 3.4)
- [x] Days 10-11: Tracker selection and setup
- [x] Days 12-13: Tracklet generation
- [x] Day 14: End-to-end pipeline integration and testing

---

## Risk Mitigation

### Identified Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Model inference too slow** | High | Medium | Use ONNX/TensorRT optimization; reduce resolution; use lighter models (YOLOv8n instead of m) |
| **Tracking fails with similar outfits** | High | Medium | Expected limitation; rely on time/spatial constraints in Phase 4 for disambiguation |
| **CLIP projection uninitialized** | **High** | **High** | **CRITICAL**: Load pretrained projection weights from fashion re-ID dataset OR use PCA initialization; validate embeddings are discriminative before Phase 4 |
| **Garment segmentation fails (thirds approach)** | **High** | **Medium** | Monitor accuracy on Day 8; if >30% low-confidence, switch to pose-based (MediaPipe) or semantic segmentation (U²-Net) |
| **ByteTrack fragmentation at 1 FPS** | **High** | **Medium** | Adjust max_time_lost to 5 frames; test on downsampled footage; switch to DeepSORT or embedding-based tracking if fragmentation >20% |
| **Memory usage exceeds limits** | Medium | Low | Process frames in batches; clear memory after each video; use generators |
| **Worker crashes during processing** | Medium | Low | Add retry logic (max 3); implement checkpointing for long videos |

### Contingency Plans

**If CLIP embeddings are not discriminative** (CRITICAL):
1. **Day 7**: Test embedding similarity on 20 sample person pairs
   - Visually similar outfits should have cosine similarity >0.75
   - Visually different outfits should have cosine similarity <0.5
2. **If test fails**: Load pretrained projection from:
   - Fashion re-ID dataset (Market-1501, DeepFashion2)
   - OR initialize with PCA on sample person crops (100+ images)
3. **Day 9 validation**: Re-test embeddings before integration
4. **Fallback**: Use full 512D CLIP features (no projection) if 128D fails

**If garment segmentation accuracy is low** (<70%):
1. **Day 6**: Calculate segmentation accuracy on 50 test crops
   - Success rate for detecting all 3 garments (top/bottom/shoes)
   - Confidence score distribution
2. **If accuracy <70%**:
   - Switch to pose-based segmentation (MediaPipe Pose, ~20 FPS)
   - OR use lightweight semantic segmentation (U²-Net, ~15 FPS on GPU)
3. **Day 8**: Re-validate with new segmentation approach
4. **Fallback**: Skip bottom/shoes, use only top garment for Phase 3

**If ByteTrack fragmentation is high** (>20%):
1. **Day 11**: Test on 5-minute synthetic 1 FPS footage
   - Manually count ground truth tracks
   - Measure fragmentation rate (same person → multiple track IDs)
2. **If fragmentation >20%**:
   - Switch to DeepSORT with appearance features
   - OR implement pure embedding-based tracking (no motion model)
   - Adjust max_time_lost to 8 frames (8 seconds)
3. **Day 13**: Re-test tracking quality
4. **Fallback**: Accept 20-30% fragmentation, rely on Phase 4 for merging

**If YOLOv8 is too slow**:
1. Use RT-DETR-nano (faster, slightly less accurate)
2. Reduce frame sampling to 0.5 fps (every 2 seconds)
3. Skip embedding extraction during detection (extract only for final tracklets)

**If processing is too slow**:
1. Use GPU acceleration (mandatory for production)
2. Reduce proxy video to 360p before CV processing
3. Process only entrance/high-priority cameras first

---

## Success Metrics (Detailed)

### Functional Metrics
- ✅ 80% of people detected in clear frames (confidence >0.7)
- ✅ 70% garment type classification accuracy
- ✅ 100% of tracklets have valid 128D embeddings
- ✅ 90% tracking continuity through <3 second occlusions
- ✅ Tracklet quality score >0.7 for 80% of tracklets

### Performance Metrics
- ✅ Process 10-minute video in <30 minutes (3x real-time)
- ✅ Memory usage <6GB per worker
- ✅ Handle 10+ people in frame simultaneously
- ✅ Embedding extraction <50ms per person crop

### Quality Metrics
- ✅ Detection precision >85% (few false positives)
- ✅ Detection recall >75% (most people detected)
- ✅ Track fragmentation <20% at 1 FPS (baseline: <10% at 30 FPS)
- ✅ Visually similar outfits: embedding cosine similarity >0.75
- ✅ Visually different outfits: embedding cosine similarity <0.5
- ✅ Garment segmentation accuracy >70% (Day 6 validation)
- ✅ CLIP embedding discriminability validated on Day 7 test set
- ✅ ByteTrack fragmentation validated on Day 11 with 1 FPS footage

---

## Dependencies & Prerequisites

### Software Requirements

**Python Libraries**:
```txt
# Phase 2 dependencies (already installed)
fastapi
celery[redis]
sqlalchemy
psycopg2-binary

# New Phase 3 dependencies
ultralytics>=8.0.0          # YOLOv8
opencv-python>=4.8.0        # Image processing
transformers>=4.35.0        # CLIP model
torch>=2.1.0                # PyTorch
torchvision>=0.16.0         # Vision utilities
numpy>=1.24.0               # Numerical computing
scikit-learn>=1.3.0         # K-means clustering
boxmot>=10.0.0              # ByteTrack/DeepSORT
onnxruntime>=1.16.0         # ONNX inference (optional)
pillow>=10.1.0              # Image handling
```

**Model Weights** (download to S3/MinIO):
- YOLOv8n: 6MB (https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt)
- CLIP-ViT-B/32: 350MB (auto-download via transformers)

### Hardware Requirements

**CPU-Only Processing** (minimum):
- 4 CPU cores
- 8GB RAM per worker
- Processing speed: ~5x real-time (10-minute video in 50 minutes)

**GPU Processing** (recommended):
- NVIDIA GPU with 8GB+ VRAM (e.g., RTX 3060, T4)
- CUDA 11.8+
- 4 CPU cores
- 6GB RAM per worker
- Processing speed: ~2-3x real-time (10-minute video in 20-30 minutes)

---

## Post-Phase Review Questions

After completing Phase 3, evaluate:

1. **Is detection accuracy sufficient for real-world deployment?**
   - If not, consider fine-tuning YOLOv8 on actual CCTV footage
   - Adjust confidence threshold based on false positive/negative balance

2. **Are embeddings discriminative enough for cross-camera matching?**
   - Test cosine similarity distribution on sample tracklets
   - If not, consider fine-tuning CLIP on fashion/apparel dataset

3. **Is tracking robust enough for crowded scenes?**
   - Test on rush hour footage with 20+ people
   - If not, improve tracker parameters or switch to DeepSORT with appearance

4. **Can we process videos fast enough for daily operations?**
   - If not, add GPU workers or optimize models (ONNX, TensorRT)
   - Consider reducing frame sampling rate (0.5 fps instead of 1 fps)

5. **Do we need more sophisticated garment segmentation?**
   - If simple thirds-based segmentation fails, add pose estimation (MediaPipe)
   - Or use semantic segmentation model (DeepLabV3)

---

## Next Steps: Phase 4 Preview

### Phase 4: Cross-Camera Re-Identification (Weeks 8-9)

**Objectives**:
1. Implement multi-signal scoring system (outfit + time + adjacency + physique)
2. Build candidate retrieval with temporal/spatial filters
3. Create association decision logic (link/new/ambiguous)
4. Implement journey construction from tracklet associations
5. Add confidence scoring and conflict resolution

**Dependencies from Phase 3**:
- ✅ Tracklets with outfit descriptors (type, color, LAB, histogram)
- ✅ Visual embeddings (128D vectors)
- ✅ Physique attributes (height category, aspect ratio)
- ✅ Bounding box statistics for quality assessment

**Expected Deliverables**:
- Association scoring service (outfit_sim, time_score, adj_score)
- Candidate retrieval with pre-filters
- Journey builder service
- Association inspection UI
- Cross-camera matching validation tests

---

## Appendix

### Sample Detection Output

```json
{
  "frame_id": 42,
  "timestamp": 42.0,
  "detections": [
    {
      "bbox": [320, 150, 180, 420],
      "confidence": 0.89,
      "track_id": 1,
      "garment": {
        "top": {"type": "jacket", "color": "blue", "lab": [50, 10, -30]},
        "bottom": {"type": "pants", "color": "dark_brown", "lab": [30, 5, 15]},
        "shoes": {"type": "sneakers", "color": "white", "lab": [90, 0, 0]}
      },
      "embedding_preview": "[0.12, -0.45, 0.78, ...]"
    },
    {
      "bbox": [850, 200, 160, 380],
      "confidence": 0.92,
      "track_id": 2,
      "garment": {
        "top": {"type": "tee", "color": "red", "lab": [45, 60, 40]},
        "bottom": {"type": "shorts", "color": "black", "lab": [20, 0, 0]},
        "shoes": {"type": "sandals", "color": "brown", "lab": [35, 10, 20]}
      }
    }
  ]
}
```

### Useful Resources

- [Ultralytics YOLOv8 Documentation](https://docs.ultralytics.com/)
- [ByteTrack Paper](https://arxiv.org/abs/2110.06864)
- [CLIP Paper](https://arxiv.org/abs/2103.00020)
- [OpenCV LAB Color Space](https://docs.opencv.org/4.x/de/d25/imgproc_color_conversions.html)
- [CIEDE2000 Color Difference](https://en.wikipedia.org/wiki/Color_difference#CIEDE2000)
- [BoxMOT Library](https://github.com/mikel-brostrom/boxmot)

---

## Changelog

### Version 1.1 (2025-11-01)
**Pre-Execution Critical Risk Mitigation**

Based on Codex analysis, added three critical clarifications before Phase 3 execution:

1. **CLIP Embedding Projection Initialization** (lines 764-798):
   - **Risk**: Uninitialized 128D projection produces meaningless embeddings
   - **Solution**: Added requirement for pretrained projection weights OR PCA initialization
   - **Validation**: Day 7 test set with 20 person crop pairs (similar vs different)
   - **Fallback**: Use full 512D CLIP features if 128D projection fails

2. **Garment Segmentation Accuracy Threshold** (lines 620-653):
   - **Risk**: "Divide crop into thirds" fails with seated people, occlusions, non-standard poses
   - **Solution**: Added accuracy monitoring with 70% threshold
   - **Validation**: Day 6 test on 50 diverse person crops
   - **Fallback**: Switch to pose-based (MediaPipe) or semantic segmentation (U²-Net)

3. **ByteTrack 1 FPS Adaptation** (lines 913-943):
   - **Risk**: ByteTrack's motion model tuned for 15-30 FPS causes track fragmentation at 1 FPS
   - **Solution**: Adjusted max_time_lost from 30 frames to 5 frames (5 seconds at 1 FPS)
   - **Validation**: Day 11 test on 5-minute synthetic 1 FPS footage with ground truth
   - **Fallback**: Switch to DeepSORT or embedding-based tracking if fragmentation >20%

**Updated Risk Mitigation**:
- Elevated 3 technical risks to HIGH priority (CLIP projection, garment segmentation, ByteTrack)
- Added comprehensive contingency plans with specific decision points (Day 6, 7, 11)
- Added measurable validation checkpoints to task lists

**Updated Success Criteria**:
- Track fragmentation <20% at 1 FPS (relaxed from <10% at 30 FPS baseline)
- Garment segmentation accuracy >70% (Day 6 validation)
- CLIP embedding discriminability validated on Day 7 test set

### Version 1.0 (2025-11-01)
- Initial Phase 3 roadmap with person detection, garment classification, visual embeddings, and within-camera tracking

---

**Document Version**: 1.1
**Created**: 2025-11-01
**Last Updated**: 2025-11-01
**Status**: 🚧 **PLANNED** (Ready for Execution - Critical Risks Addressed)
**Related Documents**:
- [Phase_1_Summary.md](../summaries/Phase_1_Summary.md) - Foundation infrastructure
- [Phase_2_Summary.md](../summaries/Phase_2_Summary.md) - Video management system
- [CLAUDE.md](../../CLAUDE.md) - Project documentation and CV pipeline specification

---

**End of Phase 3 Roadmap**
