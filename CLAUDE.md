# Spatial Intelligence Platform - Project Documentation

<!-- #region Executive Summary -->
## Executive Summary

A spatial intelligence platform that enables mall operators to track visitor journeys through outfit-based re-identification across multiple CCTV cameras. The platform provides actionable insights about visitor behavior patterns and foot traffic analytics.
<!-- #endregion -->

<!-- #region Project Vision -->
## Project Vision

Transform how property owners understand and optimize visitor flow by combining computer vision, spatial mapping, and behavioral analytics. Starting with shopping malls, the platform will track anonymous visitor journeys using outfit characteristics as identifiers, providing unprecedented insights into customer behavior patterns.
<!-- #endregion -->

<!-- #region Core Value Proposition -->
## Core Value Proposition

- **For Mall Operators**: Understand visitor flow patterns, optimize layout, measure marketing effectiveness
- **For Tenants** (Future): Data-driven insights about foot traffic and visitor behavior specific to their stores
- **Differentiator**: Non-intrusive, privacy-preserving tracking using outfit-based re-identification instead of facial recognition
<!-- #endregion -->

<!-- #region MVP/Prototype Scope -->
## MVP/Prototype Scope

### Must-Have Features

1. **Authentication System**
   - Basic login for mall operators (no signup flow)
   - Session management
   - Password security with hashing

2. **Directory Map Management**
   - Upload/display GeoJSON-based mall directory maps
   - Interactive map viewer in web UI
   - Coordinate system for pin placement

3. **Camera Pin Management**
   - Add camera pins to specific locations on the map
   - Remove camera pins
   - Mark pins as "Entrance" or "Normal"
   - Upload MP4 footage to each pin
   - Store metadata (timestamp, pin ID, footage reference)

4. **Outfit-Based Re-Identification**
   - Detect walking persons in CCTV footage
   - Extract multi-signal descriptors (all non-biometric):
     - **Outfit descriptors**: {type, color} for top/bottom/shoes + visual embedding
     - **Time windows**: Transit plausibility based on walking speed & camera adjacency
     - **Spatial topology**: Camera adjacency graph with path distances
     - **Physique cues**: Height category, aspect ratio (no biometric identification)
   - Fuse signals into probabilistic match score (0-1 range)
   - Handle ambiguity: Prefer false splits over false merges
   - Build visitor profiles with confidence scores

5. **Journey Tracking**
   - Track visitor from entrance pin through the mall
   - Record sequence of camera pins where visitor appears
   - Continue tracking until exit at entrance pins
   - Handle multiple simultaneous visitors with different outfits

6. **Journey Output**
   - Generate JSON output for each visitor journey
   - Include: visitor ID (outfit hash), timestamps, pin sequence, duration at each location

### Out of Scope for Prototype

- Tenant login and RBAC
- Tenant-specific insights and reports
- Payment processing
- Real-time streaming (batch processing is acceptable)
- Mobile app
- Advanced analytics dashboard
- Multi-property management
<!-- #endregion -->

<!-- #region API Design -->
## API Design

### Authentication
```
POST   /auth/login              → Create session, return cookie
POST   /auth/logout             → Destroy session
GET    /auth/me                 → Current user info
```

### Malls & Maps
```
GET    /malls/{mall_id}         → Mall details
GET    /malls/{mall_id}/map     → GeoJSON map
PUT    /malls/{mall_id}/map     → Replace/update GeoJSON map
```

### Camera Pins
```
GET    /malls/{mall_id}/pins                    → List all pins
POST   /malls/{mall_id}/pins                    → Create pin
GET    /malls/{mall_id}/pins/{pin_id}           → Pin details
PATCH  /malls/{mall_id}/pins/{pin_id}           → Update pin (label, type, adjacency)
DELETE /malls/{mall_id}/pins/{pin_id}           → Delete pin
```

### Videos
```
POST   /malls/{mall_id}/pins/{pin_id}/uploads   → Upload MP4 (multipart/form-data)
GET    /malls/{mall_id}/pins/{pin_id}/videos    → List videos for pin
GET    /videos/{video_id}                        → Video details
DELETE /videos/{video_id}                        → Delete video
GET    /videos/{video_id}/proxy                  → Stream low-res proxy
```

### Analysis & Processing
```
POST   /analysis/videos/{video_id}:run          → Trigger processing, return job_id
GET    /analysis/jobs/{job_id}                  → Job status & progress
GET    /analysis/videos/{video_id}/tracklets    → Tracklets detected in video
```

### Cross-Camera Associations
```
GET    /malls/{mall_id}/associations            → List associations (with filters)
GET    /associations/{association_id}           → Association details with scores
```

### Journeys
```
GET    /malls/{mall_id}/journeys                → List journeys
       ?from=2025-10-30&to=2025-10-31           Query params: date range
       &min_confidence=0.75                      min confidence
       &entry_pin=uuid                           specific entry point
GET    /journeys/{journey_id}                   → Journey details with full path
DELETE /journeys/{journey_id}                   → Delete journey (admin)
```

### Reports (Operator Only - MVP)
```
GET    /malls/{mall_id}/reports/summary         → Journey counts, unique visitors
       ?from=2025-10-30&to=2025-10-31
GET    /malls/{mall_id}/reports/entry-analysis  → Entry pin statistics
GET    /malls/{mall_id}/reports/first-store     → Top first destinations after entry
GET    /malls/{mall_id}/reports/heatmap         → Edge traversal counts for graph viz
```

### Future: Tenant Endpoints (Feature-Flagged)
```
GET    /tenants/{tenant_id}/insights            → Store-specific analytics
GET    /tenants/{tenant_id}/foot-traffic        → Visitors near/entering store
```
<!-- #endregion -->

<!-- #region Technical Architecture -->
## Technical Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Web UI Layer                         │
│  (Login, Map Viewer, Pin Management, Upload Interface)       │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                    Application Backend                       │
│  (Authentication, File Storage, Job Queue, API)              │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│                  Computer Vision Pipeline                    │
│  (Person Detection, Outfit Analysis, Re-ID, Journey Builder) │
└──────────────────────────────────────────────────────────────┘
```

### Technology Stack Recommendations

**Frontend**
- React or Vue.js for web UI
- Mapbox GL JS or Leaflet for GeoJSON map rendering
- TailwindCSS for styling

**Backend**
- Python (Flask/FastAPI) or Node.js (Express)
- PostgreSQL or MongoDB for data storage
- Redis for session management
- S3 or local storage for video files

**Computer Vision**
- Python for CV pipeline
- OpenCV for video processing
- **Person detection**: YOLOv8n/s or RT-DETR small
- **Within-camera tracking**: ByteTrack or DeepSORT
- **Garment classification**: Lightweight fashion attribute model + LAB color histograms
- **Visual embeddings**: CLIP-small or apparel-focused encoder (64-128D)
- **Video processing**: FFmpeg for format conversion and proxy generation
- **Inference**: ONNX Runtime or TensorRT for GPU optimization

**Infrastructure**
- Docker for containerization
- Celery or RQ for background job processing
- Nginx for reverse proxy
<!-- #endregion -->

<!-- #region Data Models -->
## Data Models

### User (Mall Operator)
```json
{
  "id": "uuid",
  "email": "string",
  "username": "string",
  "password_hash": "string",
  "role": "MALL_OPERATOR | TENANT_MANAGER | TENANT_VIEWER",
  "mall_id": "uuid",
  "tenant_id": "uuid | null",
  "created_at": "timestamp",
  "last_login": "timestamp"
}
```
**Note**: MVP only implements `MALL_OPERATOR` role. Other roles are scaffolded for future use.

### Mall
```json
{
  "id": "uuid",
  "name": "string",
  "geojson_map": "geojson",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Camera Pin
```json
{
  "id": "uuid",
  "mall_id": "uuid",
  "name": "string",
  "label": "string",
  "location": {
    "lat": "float",
    "lng": "float"
  },
  "pin_type": "entrance | normal",
  "adjacent_to": ["uuid", "uuid"],
  "store_id": "uuid | null",
  "camera_fps": "integer",
  "camera_note": "string",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Footage
```json
{
  "id": "uuid",
  "camera_pin_id": "uuid",
  "file_path": "string",
  "upload_timestamp": "timestamp",
  "duration_seconds": "integer",
  "processed": "boolean",
  "processing_status": "pending | processing | completed | failed"
}
```

### Visitor Profile (Outfit-Based)
```json
{
  "id": "uuid",
  "outfit_hash": "string",
  "detection_date": "date",
  "outfit": {
    "top": {
      "type": "string",
      "color": "string"
    },
    "bottom": {
      "type": "string",
      "color": "string"
    },
    "shoes": {
      "type": "string",
      "color": "string"
    }
  },
  "first_seen": "timestamp",
  "last_seen": "timestamp"
}
```

### Visitor Journey
```json
{
  "id": "uuid",
  "visitor_id": "uuid",
  "mall_id": "uuid",
  "journey_date": "date",
  "entry_time": "timestamp",
  "exit_time": "timestamp",
  "total_duration_minutes": "integer",
  "confidence": "float",
  "path": [
    {
      "camera_pin_id": "uuid",
      "camera_pin_name": "string",
      "arrival_time": "timestamp",
      "departure_time": "timestamp",
      "duration_seconds": "integer",
      "link_score": "float"
    }
  ],
  "entry_point": "uuid",
  "exit_point": "uuid"
}
```

### Tracklet (Within-Camera Detection)
```json
{
  "id": "uuid",
  "mall_id": "uuid",
  "pin_id": "uuid",
  "video_id": "uuid",
  "track_id": "integer",
  "t_in": "timestamp",
  "t_out": "timestamp",
  "outfit_vec": "float[]",
  "outfit_json": {
    "top": {"type": "string", "color": "string"},
    "bottom": {"type": "string", "color": "string"},
    "shoes": {"type": "string", "color": "string"}
  },
  "physique": {
    "height_category": "short | medium | tall",
    "aspect_ratio": "float"
  },
  "box_stats": {
    "avg_bbox": [x, y, w, h],
    "confidence": "float"
  },
  "quality": "float"
}
```

### Association (Cross-Camera Link)
```json
{
  "id": "uuid",
  "mall_id": "uuid",
  "from_tracklet_id": "uuid",
  "to_tracklet_id": "uuid",
  "score": "float",
  "decision": "linked | new_visitor | ambiguous",
  "scores": {
    "outfit_sim": "float",
    "time_score": "float",
    "adj_score": "float",
    "physique_pose": "float",
    "final": "float"
  },
  "components": {
    "type_score": "float",
    "color_deltaE": {
      "top": "float",
      "bottom": "float",
      "shoes": "float"
    },
    "embed_cosine": "float",
    "delta_t_sec": "integer",
    "expected_mu_sec": "integer",
    "tau_sec": "integer"
  },
  "candidate_count": "integer",
  "created_at": "timestamp"
}
```

### Store (Future Use)
```json
{
  "id": "uuid",
  "mall_id": "uuid",
  "name": "string",
  "category": "string",
  "polygon": "geojson",
  "tenant_id": "uuid | null",
  "created_at": "timestamp"
}
```

### Tenant (Future Use)
```json
{
  "id": "uuid",
  "mall_id": "uuid",
  "name": "string",
  "contact_email": "string",
  "status": "active | inactive",
  "created_at": "timestamp"
}
```

### GeoJSON Camera Pin Specification

Camera pins are stored in the mall's GeoJSON map as a FeatureCollection. Each pin is a Feature with Point geometry:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [103.8198, 1.3521]
      },
      "properties": {
        "id": "cam-ENTR-01",
        "label": "Entrance A - Main",
        "type": "camera",
        "pin_kind": "entrance",
        "adjacent_to": ["cam-ATRIUM-01", "cam-LOBBY-02"],
        "store_id": null,
        "camera_fps": 15,
        "camera_note": "Overhead angle, good lighting",
        "transit_times": {
          "cam-ATRIUM-01": {"mu_sec": 45, "tau_sec": 25},
          "cam-LOBBY-02": {"mu_sec": 30, "tau_sec": 20}
        }
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [103.8205, 1.3525]
      },
      "properties": {
        "id": "cam-ATRIUM-01",
        "label": "Central Atrium",
        "type": "camera",
        "pin_kind": "normal",
        "adjacent_to": ["cam-ENTR-01", "cam-STORE-05", "cam-STORE-12"],
        "store_id": null,
        "camera_fps": 15,
        "camera_note": "Wide angle, covers main circulation",
        "transit_times": {
          "cam-ENTR-01": {"mu_sec": 45, "tau_sec": 25},
          "cam-STORE-05": {"mu_sec": 60, "tau_sec": 30},
          "cam-STORE-12": {"mu_sec": 55, "tau_sec": 30}
        }
      }
    }
  ]
}
```

**Key Properties:**
- `id`: Unique camera pin identifier
- `label`: Human-readable name
- `pin_kind`: "entrance" for entry/exit points, "normal" for interior
- `adjacent_to`: Array of camera IDs that are directly reachable (defines the graph)
- `transit_times`: Expected walking time (μ) and tolerance (τ) to each adjacent camera
- `store_id`: Links to store if camera monitors a specific retail location (future use)
- `camera_fps`: Actual camera frame rate for processing optimization
- `camera_note`: Operator notes about camera positioning, lighting, etc.
<!-- #endregion -->

<!-- #region Computer Vision Pipeline -->
## Computer Vision Pipeline

### Overview: Multi-Signal Probabilistic Fusion for Re-Identification

**Core Philosophy**: Don't rely on any single weak signal (like color alone). Instead, fuse multiple privacy-safe, non-biometric signals into a robust probabilistic match score (0-1 range) for cross-camera re-identification.

**Key Risk Mitigation**: The naive assumption that "no duplicate outfit combinations exist in a single day" will fail immediately on busy days and with employee uniforms. We mitigate this by combining:
- **Outfit descriptors** (type + color + visual embedding): 55% weight
- **Time-window constraints** (transit plausibility): 20% weight  
- **Camera adjacency** (spatial topology): 15% weight
- **Basic physique cues** (height category, aspect ratio): 10% weight

This multi-signal fusion allows the system to gracefully handle ambiguity, prefer false splits over false merges, and adapt to different mall conditions.

### Step 1: Person Detection
- Sample video frames at 1 fps for analysis (15 fps for preview proxies)
- Use object detection model (YOLOv8 or RT-DETR) to find bounding boxes of people
- Filter confidence threshold (e.g., >0.7)
- Store bounding box coordinates and person crops

### Step 2: Outfit Feature Extraction (Enhanced)

Extract three complementary representations per person:

**2.1 Garment Attributes**
- **Types**: Classify top, bottom, shoes into categories
  - Top: {tee, shirt, blouse, jacket, coat, dress, ...}
  - Bottom: {pants, shorts, skirt, ...}
  - Shoes: {sneakers, loafers, sandals, boots, ...}
- **Colors**: Convert to CIELAB color space, quantize to 10-14 bins
  - Compute mean color per garment
  - Generate small color histogram per garment region
  - Use CIEDE2000 (ΔE) for color similarity scoring

**2.2 Visual Embedding**
- Extract 64-128D compact embedding from person crop
- Use lightweight model (CLIP-small or garment-focused encoder)
- Provides appearance similarity beyond discrete attributes
- Keeps dimensionality low for speed and privacy

**2.3 Physique Attributes (Non-biometric)**
- Approximate height category: {short, medium, tall}
  - Normalized by camera's typical person scale
- Body aspect ratio from bounding box (w/h)
- Coarse accessories detection (backpack, large bags)
- Optional: Average step direction vector from tracker

### Step 3: Within-Camera Tracking (Tracklets)
- Use ByteTrack or DeepSORT to maintain person ID within single camera
- Generate tracklets with:
  - Track ID (camera-local)
  - Time in/out timestamps
  - Person crops at key frames
  - Outfit descriptor (combined attributes + embedding)
  - Bounding box statistics
- Handle occlusions and temporary disappearances
- Output: Tracklet records with complete outfit vectors

### Step 4: Cross-Camera Re-Identification (Multi-Signal Fusion)

For each new tracklet at target camera B, compare against recent tracklets from adjacent cameras using a **fused scoring system**:

#### Signal 1: Outfit Similarity (55% weight)

Combines three sub-components:

**Type Score** (35% of outfit similarity)
```
type_score = exact_match ? 1.0 : confusion_matrix_score
```
- Exact matches (jacket=jacket): 1.0
- Similar types (coat≈jacket): 0.6
- Mismatches: 0.0

**Color Score** (35% of outfit similarity)
```
color_score = exp(-ΔE/12)
```
- Calculate ΔE (CIEDE2000) per garment
- Soft threshold: ΔE ≤ 20-25 indicates "same color"
- Per-garment scoring, weighted by visibility

**Embedding Cosine** (30% of outfit similarity)
```
embed_score = cosine_similarity(vec_A, vec_B)
```
- Compare 64-128D visual embeddings
- Pre-filter threshold: ≥ 0.75 for candidates

**Combined Outfit Similarity:**
```
outfit_sim = 0.35 * type_score + 0.35 * color_score + 0.30 * embed_cosine
```

#### Signal 2: Time Plausibility (20% weight)

Validates that transit time between cameras is physically plausible:

**Precompute Transit Times**
- Use graph distance from GeoJSON `adjacent_to` relationships
- Typical walking speed: 1.0-1.6 m/s (use 1.2 m/s default)
- Account for escalators, elevators with adjusted speeds
- Store expected transit time μ and tolerance τ per edge

**Time Score Calculation:**
```
Δt = arrival_time_B - departure_time_A
time_score = exp(-max(0, |Δt - μ|) / τ)
```

**Hard Gates:**
- Reject if Δt < 1 second (impossible)
- Reject if Δt > μ + 3τ (too late, unless high-dwell area)
- Starting values: τ = 30 seconds

#### Signal 3: Camera Adjacency (15% weight)

Leverages spatial topology to constrain matching:

```
adj_score = 1.0  if direct neighbor (in adjacent_to list)
          = 0.5  if 2-hop neighbor
          = 0.0  otherwise
```

**Benefits:**
- Prevents impossible jumps across mall
- Respects directional flow (entrance → interior)
- Allows 2-hop at reduced weight for blind spots

#### Signal 4: Physique & Pose (10% weight)

Non-biometric physical cues as tiebreakers:

**Height Category Match:**
```
height_score = 1.0  if same category
             = 0.5  if adjacent category
             = 0.0  otherwise
```

**Aspect Ratio & Direction:**
- Penalty if walking direction contradicts expected path
- Bonus for consistent gait patterns (optional)

#### Final Match Score

```
match_score = 0.55 * outfit_sim
            + 0.20 * time_score
            + 0.15 * adj_score
            + 0.10 * physique_pose_score
```

**Decision Rules:**
1. **Link**: If `match_score ≥ 0.78` AND `outfit_sim ≥ 0.70`
2. **Ambiguous**: If top-2 candidates within 0.04 of each other → start new visitor
3. **New Visitor**: If no candidate passes thresholds

**Conflict Handling:**
- Two source tracklets claim same target: Keep highest score
- Loser links to next-best or spawns new visitor
- Apply cool-down (10-20s) per visitor per camera to prevent ping-pong

### Step 5: Journey Construction

**Per-Visitor Journey Building:**
1. Start journey when visitor detected at entrance pin
2. Follow association links across cameras chronologically
3. Build path: `[(pin_id, t_in, t_out), ...]`
4. Close journey when:
   - Visitor reaches exit/entrance pin
   - Inactivity exceeds threshold (e.g., 30+ minutes)
   - End of footage reached

**Journey Confidence Score:**
```
confidence = f(avg_link_score, path_length, timing_consistency)
```

**Output JSON per Journey:**
```json
{
  "visitor_id": "v-2025-10-30-000123",
  "mall_id": "mall-001",
  "start_pin": "cam-ENTR-01",
  "end_pin": "cam-ENTR-02",
  "confidence": 0.81,
  "steps": [
    {
      "pin_id": "cam-ENTR-01",
      "pin_name": "Entrance A",
      "t_in": "2025-10-30T10:01:12Z",
      "t_out": "2025-10-30T10:01:20Z",
      "duration_seconds": 8
    },
    {
      "pin_id": "cam-ATRIUM-01",
      "pin_name": "Central Atrium",
      "t_in": "2025-10-30T10:02:05Z",
      "t_out": "2025-10-30T10:03:30Z",
      "duration_seconds": 85,
      "link_score": 0.83
    }
  ],
  "outfit": {
    "top": {"type": "jacket", "color": "blue"},
    "bottom": {"type": "pants", "color": "dark_brown"},
    "shoes": {"type": "sneakers", "color": "white"}
  },
  "entry_time": "2025-10-30T10:01:12Z",
  "exit_time": "2025-10-30T10:15:40Z",
  "total_duration_minutes": 14.5,
  "created_at": "2025-10-30T10:16:00Z"
}
```

### Handling Edge Cases

**Uniforms & Frequent Outfits:**
- Maintain mall-level "frequent outfit" table
- Track outfit frequency per hour window
- If combo exceeds threshold, down-weight its contribution by 0.8
- Example: Food court workers in black pants + white shirt

**Rush Hours:**
- Dynamically raise outfit_sim requirement by +0.05 when candidate pool > 12
- Prefer splitting over merging when ambiguous

**Groups & Co-movement:**
- Detect when 2+ tracklets enter camera within ±2s
- Add co-movement hint to prefer linking them together
- Useful for families, shopping groups

**Lighting Variations:**
- Per-camera color calibration factors
- Rely more on embedding and type in problematic cameras
- Log per-camera performance for tuning

### Tuning & Observability

**Parameters to Start With:**
```python
# Frame sampling
ANALYSIS_FPS = 1.0
PREVIEW_FPS = 10.0

# Transit timing
WALK_SPEED_MS = 1.2
TIME_TOLERANCE_SEC = 30

# Color matching
COLOR_DELTA_E_THRESHOLD = 25
COLOR_SOFT_THRESHOLD = 12

# Embeddings
EMBEDDING_DIM = 128
EMBEDDING_COSINE_THRESHOLD = 0.75

# Matching thresholds
MATCH_SCORE_THRESHOLD = 0.78
OUTFIT_SIM_MIN_THRESHOLD = 0.70
AMBIGUITY_GAP = 0.04

# Candidate window
MAX_CANDIDATE_WINDOW_SEC = 480  # 8 minutes
```

**Logging per Link:**
```json
{
  "from_tracklet": "trk-A-00123",
  "to_tracklet": "trk-B-00456",
  "scores": {
    "outfit_sim": 0.83,
    "time_score": 0.77,
    "adj_score": 1.0,
    "physique_pose": 0.65,
    "final": 0.82
  },
  "components": {
    "type_score": 1.0,
    "color_deltaE": {"top": 14.2, "bottom": 9.8, "shoes": 28.1},
    "embed_cosine": 0.79,
    "delta_t_sec": 68,
    "expected_mu_sec": 55,
    "tau_sec": 30
  },
  "decision": "linked",
  "candidate_count": 8,
  "timestamp": "2025-10-30T12:04:09Z"
}
```

**Metrics to Monitor:**
- Link precision on hand-labeled sample (target: >85%)
- Ambiguous link rate (target: <15%)
- False split rate (prefer splits over merges)
- Processing throughput (frames/sec)
- Per-camera performance variations
<!-- #endregion -->

<!-- #region Future Enhancements -->
## Future Enhancements (Post-MVP)

### Phase 2: Tenant Platform
- Multi-tenant RBAC system
- Tenant dashboards with store-specific insights
- Foot traffic analytics per tenant
- Visitor flow reports: "X% of visitors who entered at entrance A visited your store within Y minutes"

### Phase 3: Advanced Analytics
- Heatmaps of visitor density
- Dwell time analysis
- Popular path visualization
- Conversion funnel: entrance → store visits → exit
- Temporal patterns (peak hours, days)

### Phase 4: Enhanced Re-ID
- Additional differentiators: watches, bags, accessories
- Handle outfit changes (e.g., removing jacket)
- Group detection (families, friends traveling together)
- Age and gender estimation (privacy-permitting)

### Phase 5: Real-Time Processing
- Live camera feeds
- Real-time alerts and notifications
- Current occupancy tracking
- Dynamic layout optimization

### Phase 6: Multi-Property
- Support for multiple malls per operator
- Cross-property insights
- Comparative analytics
<!-- #endregion -->

<!-- #region Privacy & Ethics -->
## Privacy & Ethics Considerations

### Privacy-First Approach
- **No facial recognition**: Using outfit-based tracking only
- **No PII storage**: Visitors are anonymous profiles
- **Temporary data**: Consider data retention policies
- **GDPR/CCPA compliance**: Ensure local regulations are met

### Data Security
- Encrypt footage at rest and in transit
- Secure authentication and session management
- Access logging and audit trails
- Regular security assessments

### Transparency
- Clear signage about CCTV monitoring (mall responsibility)
- Data usage policies documented
- Opt-out mechanisms where legally required
<!-- #endregion -->

<!-- #region Development Roadmap -->
## Development Roadmap

### Phase 1: Foundation (Weeks 1-3)
- [ ] Set up development environment (Docker, Python, Node.js)
- [ ] Create basic authentication system with role scaffolding
- [ ] Implement map viewer with GeoJSON support (Leaflet/Mapbox)
- [ ] Build camera pin CRUD operations with adjacency relationships
- [ ] Design and implement database schema (all tables including future-use)
- [ ] Set up object storage (S3/MinIO) for videos
- [ ] Implement session management (HttpOnly cookies, CSRF protection)

### Phase 2: Video Management (Weeks 4-5)
- [ ] Implement video upload functionality with validation
- [ ] Create FFmpeg pipeline for proxy generation (480p, 10fps)
- [ ] Build video metadata management system
- [ ] Set up background job queue (Celery/RQ with Redis)
- [ ] Implement signed URL generation for secure video access
- [ ] Create video listing and playback UI

### Phase 3: Computer Vision - Part 1 (Weeks 6-7)
- [ ] Integrate person detection model (YOLOv8/RT-DETR)
- [ ] Implement garment classification pipeline
  - [ ] Garment type classifier (top/bottom/shoes)
  - [ ] LAB color space conversion and quantization
  - [ ] Color histogram generation per garment
- [ ] Build visual embedding extractor (CLIP-small)
- [ ] Implement physique attribute extraction (height, aspect ratio)
- [ ] Create tracklet data model and storage

### Phase 4: Computer Vision - Part 2 (Weeks 8-9)
- [ ] Integrate within-camera tracking (ByteTrack/DeepSORT)
- [ ] Build tracklet generation pipeline
- [ ] Implement outfit vector computation (128D embedding)
- [ ] Create tracklet quality scoring
- [ ] Test with single-camera footage

### Phase 5: Cross-Camera Re-ID (Weeks 10-11)
- [ ] Implement multi-signal scoring system:
  - [ ] Outfit similarity (type + color + embedding)
  - [ ] Time plausibility with transit time precomputation
  - [ ] Camera adjacency scoring from graph
  - [ ] Physique/pose similarity
- [ ] Build candidate retrieval system with pre-filters
- [ ] Implement association decision logic (link/new/ambiguous)
- [ ] Create conflict resolution (collision handling, cool-downs)
- [ ] Build journey construction algorithm
- [ ] Implement confidence scoring

### Phase 6: Integration & Optimization (Weeks 12-13)
- [ ] Connect CV pipeline with backend APIs
- [ ] Build journey JSON export with full metadata
- [ ] Implement logging system for all link decisions
- [ ] Create monitoring dashboard for pipeline metrics
- [ ] End-to-end testing with multi-camera footage
- [ ] Performance optimization (GPU utilization, batch processing)
- [ ] Implement uniform/frequent-outfit filtering

### Phase 7: Reporting & UI (Weeks 14-15)
- [ ] Build journey viewer UI with map visualization
- [ ] Create operator reports (entry analysis, first-store)
- [ ] Implement heatmap visualization (edge traversal counts)
- [ ] Add filtering and search for journeys
- [ ] Create association inspection UI for debugging
- [ ] Build video preview with bounding box overlay

### Phase 8: Testing & Hardening (Week 16)
- [ ] Comprehensive testing with edge cases:
  - [ ] Rush hour scenarios (20+ people per camera)
  - [ ] Similar outfits (uniforms, common colors)
  - [ ] Long transit times and camera gaps
  - [ ] Lighting variations
- [ ] Security hardening (RBAC checks, input validation)
- [ ] Performance benchmarking
- [ ] Bug fixes and refinements
- [ ] Parameter tuning on real data

### Phase 9: Documentation & Demo (Week 17)
- [ ] User documentation (operator guide)
- [ ] API documentation (OpenAPI/Swagger)
- [ ] System architecture documentation
- [ ] Prepare demo with sample mall data (synthetic + real)
- [ ] Create presentation materials
- [ ] Record demo video
<!-- #endregion -->

<!-- #region Success Metrics -->
## Success Metrics for Prototype

**Authentication & Infrastructure:**
- Successfully authenticate mall operators
- Upload and display GeoJSON mall map with adjacency graph
- Add/remove camera pins with entrance/normal designation and adjacency relationships
- Upload MP4 files to camera pins

**Computer Vision Performance:**
- Detect and extract outfit features from 80%+ of clear person appearances
- Within-camera tracking maintains ID through 90%+ of occlusions <3 seconds
- Cross-camera matching achieves 85%+ precision on hand-labeled test set
- False merge rate <5% (prefer false splits over false merges)
- Ambiguous link rate <15%

**Journey Construction:**
- Correctly track visitors across 3+ cameras with average confidence >0.75
- Generate valid journey JSON for 80%+ of visitors who traverse entrance → interior → exit
- Process a full day's footage (8 hours across 10 cameras) within 12 hours compute time

**System Performance:**
- Average processing speed: 4x real-time (process 4 hours of footage in 1 hour)
- Handle rush hour scenarios with 20+ simultaneous visitors per camera
- Support 50 camera pins with <2GB memory per pin for tracklet storage

**Why This Multi-Signal Approach Works:**
1. **Robustness**: No single signal failure breaks the system
2. **Graceful Degradation**: Works in suboptimal conditions (poor lighting, crowded scenes)
3. **Tunable**: Weights and thresholds can be adjusted per mall
4. **Explainable**: Each link has audit trail showing why it was made
5. **Privacy-Preserving**: All signals are non-biometric and aggregate-safe
6. **Scalable**: Efficient candidate pre-filtering keeps computation manageable
<!-- #endregion -->

<!-- #region Known Limitations & Assumptions -->
## Known Limitations & Assumptions

### Assumptions
1. ~~No duplicate outfit combinations in a single day~~ **UPDATED**: Multi-signal fusion (outfit + time + adjacency + physique) mitigates duplicate outfits. System handles busy periods and uniforms through dynamic thresholds and frequent-outfit filtering
2. Visitors don't change outfits mid-visit (removing/adding jackets may cause tracking loss)
3. Camera coverage is sufficient to track major pathways (2-hop adjacency allows some gaps)
4. Lighting conditions are adequate for feature extraction (per-camera calibration helps)
5. CCTV footage quality is minimum 720p at 15 fps

### Limitations
1. ~~Cannot track visitors who wear identical outfits~~ **UPDATED**: Can handle similar outfits through time windowing and spatial constraints, though perfect duplicates in same area may cause ambiguity (system prefers creating separate visitors over false merges)
2. Accuracy depends on camera angles and positioning (overhead angles reduce accuracy)
3. Batch processing only (not real-time in MVP)
4. Employee uniforms require manual flagging as "frequent outfits" for proper handling
5. May lose track in extreme crowding (>50 people in frame) or severe occlusions
6. Cross-camera matching accuracy decreases with longer transit times (>8 minutes)
7. Outfit changes (removing jacket, adding shopping bags) can break tracking continuity

### Trade-offs
- **Prefer false splits over false merges**: Better to track one person as two visitors than merge two people into one
- **Privacy vs. accuracy**: No facial recognition means some ambiguous cases cannot be resolved
- **Speed vs. quality**: 1 fps analysis is fast but may miss quick transitions; adjustable per deployment
<!-- #endregion -->

<!-- #region Getting Started -->
## Getting Started

### Prerequisites
- Python 3.9+ with pip
- Node.js 16+ with npm (for frontend)
- PostgreSQL 13+ or MongoDB 5+
- Redis 6+
- Docker & Docker Compose (optional but recommended)
- GPU recommended for CV processing (CUDA-capable)

### Installation
```bash
# Clone repository
git clone <repository-url>
cd spatial-intelligence-platform

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Start development servers
# Backend
cd backend
python app.py

# Frontend
cd frontend
npm run dev
```

### Configuration
Create `.env` file with:
```
DATABASE_URL=postgresql://user:password@localhost/spatial_intel
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
VIDEO_STORAGE_PATH=/path/to/video/storage
```
<!-- #endregion -->

<!-- #region Contributing & License -->
## Contributing

This is a prototype project. Key areas for contribution:
- Computer vision model optimization
- UI/UX improvements
- Performance enhancements
- Documentation
- Testing coverage

## License

[To be determined]

## Contact & Support

[Project owner contact information]
<!-- #endregion -->

<!-- #region Changelog -->
---

## Changelog

### Version 2.0 (2025-10-30)
**Major Update: Multi-Signal Re-Identification Strategy**

- **Enhanced CV Pipeline**: Replaced simple outfit matching with sophisticated multi-signal fusion system
  - Outfit similarity: type + color (CIEDE2000) + visual embedding (CLIP)
  - Time plausibility: transit time constraints with soft scoring
  - Camera adjacency: graph-based spatial constraints
  - Physique cues: height, aspect ratio, pose (non-biometric)
- **New Data Models**: Added Tracklet, Association, Store, and Tenant tables
- **Expanded Camera Pins**: Added `adjacent_to`, `store_id`, and camera metadata fields
- **Comprehensive API Design**: Full REST API specification with all endpoints
- **Updated Assumptions**: Multi-signal approach handles duplicate outfits and uniforms
- **Enhanced Roadmap**: 17-week detailed development plan with specific CV milestones
- **Observability**: Detailed logging structure for tuning and debugging
- **Parameter Documentation**: Starting values for all thresholds and scoring weights

### Version 1.0 (2025-10-30)
- Initial project documentation
- Basic MVP scope definition
- Simple outfit-based re-ID concept
- 12-week development roadmap

---

**Document Version**: 2.0
**Last Updated**: 2025-10-30
**Status**: Pre-Development / Planning Phase
<!-- #endregion -->