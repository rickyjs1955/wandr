# Phase 4: Computer Vision Pipeline - Part 2 (Cross-Camera Re-Identification) - Roadmap

**Timeline**: Weeks 8-9 (14 working days)
**Status**: 🚧 **PLANNED** (Not Started)
**Owner**: Development Team
**Dependencies**:
- ✅ Phase 1 Complete (Authentication, Map Viewer, Camera Pin Management)
- ✅ Phase 2 Complete (Video Management, FFmpeg Pipeline, Background Jobs)
- ✅ Phase 3 Complete (Person Detection, Garment Classification, Within-Camera Tracking)

---

## Executive Summary

Phase 4 implements the core intelligence of the spatial tracking platform: **cross-camera re-identification** and **journey construction**. This phase takes the tracklets generated in Phase 3 (within-camera person tracks) and links them across multiple cameras to build complete visitor journeys through the mall.

### Strategic Approach

**Multi-Signal Probabilistic Fusion**:
Following the CLAUDE.md specification, we combine multiple weak signals into a robust match score:
- **Outfit similarity** (~55% base weight): type + color + visual embedding
- **Time plausibility** (~20% base weight): transit time constraints
- **Camera adjacency** (~15% base weight): spatial topology
- **Physique cues** (~10% base weight): height, aspect ratio (non-biometric)

**IMPORTANT - Dynamic Weights**: The percentages shown above (55/20/15/10) are **initial baseline values only**. In production, weights are **dynamically adjusted** and **data-driven**, governed by a confidential calibration file (`.secret`) that is:
- **Learned from real data**: Per-mall, per-camera, per-edge calibration based on observed visitor behavior
- **Continuously updated**: Monthly retraining with new labeled data and performance metrics
- **Mall-specific**: Different malls have different optimal weights based on layout, lighting, crowd patterns
- **Camera-specific**: Individual camera trust factors based on lighting quality and occlusion patterns
- **Trade secret**: The learned calibration parameters form Wandr's competitive advantage

The final composite score uses these learned weights merged at runtime from secure storage (HashiCorp Vault, AWS KMS, or encrypted database).

**Key Philosophy**: Prefer false splits over false merges. Better to track one person as two separate visitors than merge two people into one journey.

---

## Phase 4 Objectives

### Primary Goals

1. **Implement Multi-Signal Scoring System**
   - Outfit similarity scoring (type, color, embedding cosine)
   - Time plausibility scoring (transit time validation)
   - Camera adjacency scoring (graph-based constraints)
   - Physique matching (height category, aspect ratio)

2. **Build Candidate Retrieval System**
   - Temporal pre-filtering (candidate time window)
   - Spatial pre-filtering (adjacent cameras only)
   - Embedding pre-filtering (cosine similarity threshold)
   - Efficient database queries with indexes

3. **Create Association Decision Logic**
   - Link decision (high confidence match)
   - New visitor decision (no good match)
   - Ambiguous decision (multiple similar candidates)
   - Conflict resolution (multiple sources claim same target)

4. **Implement Journey Construction**
   - Start journeys at entrance pins
   - Follow association links chronologically
   - Close journeys at exit or inactivity
   - Calculate journey confidence scores

### Success Criteria

**Functional Requirements**:
- ✅ Link precision >85% on hand-labeled test set
- ✅ False merge rate <5% (prefer splits over merges)
- ✅ Ambiguous link rate <15%
- ✅ Generate valid journeys for 80%+ of visitors who enter/exit
- ✅ Journey confidence score >0.75 for 70%+ of journeys

**Performance Requirements**:
- Process associations for 10-minute video in <10 minutes
- Handle 100+ tracklets per video efficiently
- Store associations with detailed scoring components
- Support journey queries with <100ms latency

**Quality Requirements**:
- Outfit similarity precision >80% (similar outfits matched correctly)
- Time plausibility correctly filters impossible transitions
- Adjacency constraints prevent impossible jumps
- Journey paths are spatially and temporally coherent

---

## Technical Architecture

### Component Overview

```
                    Tracklets Database
                  (Phase 3 output: outfit,
                   embedding, physique)
                           ↓
        ┌──────────────────┴──────────────────┐
        ↓                                      ↓
  Candidate Retrieval              Transit Time Graph
  (Temporal + Spatial              (Precomputed μ, τ)
   + Embedding Filters)
        ↓
  Multi-Signal Scoring
  ┌─────────────────────────────────────┐
  │ • Outfit Similarity (~55% base)     │
  │   - Type score (35% of outfit)      │
  │   - Color ΔE (35% of outfit)        │
  │   - Embedding cosine (30% of outfit)│
  │ • Time Plausibility (~20% base)     │
  │ • Camera Adjacency (~15% base)      │
  │ • Physique Match (~10% base)        │
  │ [Production: Weights loaded from    │
  │  .secret calibration file]          │
  └─────────────────────────────────────┘
        ↓
  Association Decision
  (Link / New / Ambiguous)
        ↓
  Conflict Resolution
  (Highest score wins)
        ↓
  Journey Construction
  (Entry → Path → Exit)
        ↓
  Associations & Journeys
  (Stored in database)
```

### Technology Stack

**Backend Services**:
- **ScoringService**: Multi-signal fusion and scoring
- **CandidateRetriever**: Efficient tracklet candidate selection
- **AssociationService**: Decision logic and conflict resolution
- **JourneyBuilder**: Journey construction and confidence scoring
- **TransitTimeService**: Graph-based transit time computation

**Database**:
- **associations** table: Store cross-camera links with detailed scores
- **journeys** table: Store complete visitor paths
- Indexes on tracklet time ranges for fast temporal queries
- JSONB for flexible score component storage

**API Endpoints**:
- Trigger re-identification for mall
- Get associations with filters
- Get journeys with confidence thresholds
- Inspect association details (debugging)

---

## Database Schema Updates

### New Table: `associations`

```sql
CREATE TABLE associations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    from_tracklet_id UUID NOT NULL REFERENCES tracklets(id) ON DELETE CASCADE,
    to_tracklet_id UUID REFERENCES tracklets(id) ON DELETE CASCADE,
    -- NULL when decision is 'new_visitor' or 'ambiguous'

    -- Association metadata
    from_pin_id UUID NOT NULL REFERENCES camera_pins(id),
    to_pin_id UUID REFERENCES camera_pins(id),
    -- NULL when decision is 'new_visitor' or 'ambiguous'

    -- Decision
    decision VARCHAR(20) NOT NULL,
    -- Values: 'linked', 'new_visitor', 'ambiguous'

    -- Final match score (0-1)
    score NUMERIC(5,4) NOT NULL,

    -- Individual signal scores (0-1)
    scores JSONB NOT NULL,
    -- Example: {
    --   "outfit_sim": 0.83,
    --   "time_score": 0.77,
    --   "adj_score": 1.0,
    --   "physique": 0.65,
    --   "final": 0.82
    -- }

    -- Detailed components for debugging/tuning
    components JSONB NOT NULL,
    -- Example: {
    --   "type_score": 1.0,
    --   "color_deltaE": {"top": 14.2, "bottom": 9.8, "shoes": 28.1},
    --   "embed_cosine": 0.79,
    --   "delta_t_sec": 68,
    --   "expected_mu_sec": 55,
    --   "tau_sec": 30
    -- }

    -- Candidate ranking info
    candidate_count INTEGER NOT NULL,
    rank INTEGER,  -- Rank among candidates (1 = best match)

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CHECK (from_tracklet_id != to_tracklet_id),
    CHECK (score >= 0 AND score <= 1),
    -- Enforce linked decisions have both target fields populated
    CHECK (decision <> 'linked' OR (to_tracklet_id IS NOT NULL AND to_pin_id IS NOT NULL)),
    -- Enforce non-linked decisions have both target fields NULL
    CHECK (decision = 'linked' OR (to_tracklet_id IS NULL AND to_pin_id IS NULL))
);

-- Unique constraint: one association record per source tracklet
-- Note: Standard UNIQUE allows multiple (from_tracklet_id, NULL) because NULL != NULL in SQL
-- We need a partial unique index to enforce "one record per source"
CREATE UNIQUE INDEX idx_associations_one_per_source ON associations(from_tracklet_id);

-- Unique constraint: one association record per target tracklet (for linked decisions)
-- Critical: Prevents catastrophic false merges where 2+ sources claim the same target
-- This catches bugs that slip past application-level conflict resolution
CREATE UNIQUE INDEX idx_associations_one_per_target ON associations(to_tracklet_id) WHERE decision = 'linked';

-- Additional indexes for associations table
CREATE INDEX idx_associations_mall ON associations(mall_id);
CREATE INDEX idx_associations_decision ON associations(decision);
CREATE INDEX idx_associations_score ON associations(score DESC);
CREATE INDEX idx_associations_pins ON associations(from_pin_id, to_pin_id);
```

**Design Note: Storing `new_visitor` and `ambiguous` Decisions**

The associations table stores ALL association decisions, not just successful links:
- **`linked`**: `to_tracklet_id` and `to_pin_id` are populated, `score` reflects match quality
- **`new_visitor`**: `to_tracklet_id` and `to_pin_id` are NULL, `score` reflects best candidate that was rejected (or 0 if no candidates)
- **`ambiguous`**: `to_tracklet_id` and `to_pin_id` are NULL, `score` reflects best candidate that was too close to second-best

**Why store non-links?**
1. **Auditability**: Full decision history for each tracklet (why was it not linked?)
2. **Analytics**: Understand system performance (ambiguity rate, rejection reasons)
3. **Tuning**: Identify patterns in rejected matches to calibrate thresholds
4. **Debugging**: Trace why a tracklet started a new journey vs. continuing an existing one

**Storage implications**: Each tracklet generates exactly one association record, regardless of decision. This maintains consistency and simplifies queries.

**Database Integrity Guarantees**:

The schema enforces critical invariants through constraints that provide **defense in depth** against catastrophic data corruption:

1. **One Record Per Source Tracklet** (`CREATE UNIQUE INDEX idx_associations_one_per_source ON associations(from_tracklet_id)`)
   - Prevents duplicate association records for the same source tracklet
   - Important: Standard `UNIQUE (from_tracklet_id, to_tracklet_id)` would NOT work because PostgreSQL treats `NULL` values as distinct (allows multiple `(source_id, NULL)` rows)
   - This unique index ensures exactly one decision per source, even for `new_visitor`/`ambiguous` cases
   - **Protects against**: Application bugs creating multiple decisions for same source

2. **One Record Per Target Tracklet** (`CREATE UNIQUE INDEX idx_associations_one_per_target ON associations(to_tracklet_id) WHERE decision = 'linked'`)
   - **CRITICAL**: Prevents catastrophic false merges where 2+ source tracklets link to the same target
   - Uses partial index (WHERE clause) to only enforce uniqueness for `linked` decisions (new_visitor/ambiguous have NULL targets)
   - This is the **last line of defense** if conflict resolution fails in application code
   - **Example prevented failure**:
     ```sql
     -- Without this constraint, both would succeed (CATASTROPHIC!):
     INSERT INTO associations VALUES ('trk-A', 'trk-C', 'linked', 0.85);
     INSERT INTO associations VALUES ('trk-B', 'trk-C', 'linked', 0.82);
     -- Result: Two different people merged into one journey
     ```
   - **Protects against**: Conflict resolution bugs, race conditions, logic errors in association code

3. **Target Consistency for Linked Decisions** (`CHECK (decision <> 'linked' OR (to_tracklet_id IS NOT NULL AND to_pin_id IS NOT NULL))`)
   - If decision is `linked`, BOTH `to_tracklet_id` and `to_pin_id` must be populated
   - Prevents malformed links with missing target information
   - **Protects against**: Incomplete link records that would break journey construction

4. **Target Consistency for Non-Linked Decisions** (`CHECK (decision = 'linked' OR (to_tracklet_id IS NULL AND to_pin_id IS NULL))`)
   - If decision is `new_visitor` or `ambiguous`, BOTH target fields must be NULL
   - Prevents data inconsistency where decision type doesn't match target state
   - **Protects against**: Logic errors where decision is set incorrectly

**Why Database-Level Constraints Matter**:

The conflict resolution code (ConflictResolver) runs in application space and can fail due to:
- Race conditions (concurrent inserts)
- Logic bugs (incorrect winner selection)
- Exception handling errors (partial transaction commits)
- Deployment issues (old code version deployed)

Database constraints provide **guaranteed** enforcement regardless of application state, ensuring:
- **No false merges**: The absolute worst failure mode (merging two people into one journey) is **impossible**
- **Data consistency**: All records are valid and queryable without error handling
- **Fail-fast**: Bugs are caught immediately with clear error messages, not discovered weeks later in corrupted analytics

### New Table: `journeys`

```sql
CREATE TABLE journeys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    visitor_id VARCHAR(50) NOT NULL,  -- e.g., "v-2025-11-02-000123"

    -- Journey metadata
    journey_date DATE NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ,
    total_duration_minutes INTEGER,

    -- Entry/exit points
    entry_point UUID NOT NULL REFERENCES camera_pins(id),
    exit_point UUID REFERENCES camera_pins(id),

    -- Journey confidence (0-1)
    confidence NUMERIC(5,4) NOT NULL,

    -- Full path with timing and scores
    path JSONB NOT NULL,
    -- Example: [
    --   {
    --     "pin_id": "uuid",
    --     "pin_name": "Entrance A",
    --     "tracklet_id": "uuid",
    --     "t_in": "2025-11-02T10:00:00Z",
    --     "t_out": "2025-11-02T10:00:30Z",
    --     "duration_seconds": 30,
    --     "link_score": null  // First tracklet has no link
    --   },
    --   {
    --     "pin_id": "uuid",
    --     "pin_name": "Central Atrium",
    --     "tracklet_id": "uuid",
    --     "t_in": "2025-11-02T10:01:15Z",
    --     "t_out": "2025-11-02T10:03:00Z",
    --     "duration_seconds": 105,
    --     "link_score": 0.83
    --   }
    -- ]

    -- Representative outfit (from first/best tracklet)
    outfit JSONB NOT NULL,
    -- Example: {
    --   "top": {"type": "jacket", "color": "blue"},
    --   "bottom": {"type": "pants", "color": "dark_brown"},
    --   "shoes": {"type": "sneakers", "color": "white"}
    -- }

    -- Journey statistics
    num_cameras_visited INTEGER NOT NULL,
    total_tracklets INTEGER NOT NULL,
    avg_link_score NUMERIC(5,4),

    -- Status
    status VARCHAR(20) DEFAULT 'active',
    -- Values: 'active', 'completed', 'incomplete'

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for journeys table
CREATE INDEX idx_journeys_mall ON journeys(mall_id);
CREATE INDEX idx_journeys_date ON journeys(journey_date DESC);
CREATE INDEX idx_journeys_entry_time ON journeys(entry_time DESC);
CREATE INDEX idx_journeys_confidence ON journeys(confidence DESC);
CREATE INDEX idx_journeys_entry_point ON journeys(entry_point);
CREATE INDEX idx_journeys_status ON journeys(status);
CREATE INDEX idx_journeys_visitor ON journeys(visitor_id);
```

### Updated Table: `tracklets`

Add association tracking:

```sql
ALTER TABLE tracklets ADD COLUMN linked_to_tracklet_id UUID REFERENCES tracklets(id);
ALTER TABLE tracklets ADD COLUMN journey_id UUID REFERENCES journeys(id);
ALTER TABLE tracklets ADD COLUMN is_journey_start BOOLEAN DEFAULT FALSE;

CREATE INDEX idx_tracklets_journey ON tracklets(journey_id);
CREATE INDEX idx_tracklets_linked_to ON tracklets(linked_to_tracklet_id);
```

---

## API Endpoints

### Trigger Re-Identification for Mall

#### `POST /analysis/malls/{mall_id}/reidentify`

**Purpose**: Start cross-camera re-identification for all tracklets in a mall

**Request**:
```json
{
  "time_range": {
    "from": "2025-11-02T00:00:00Z",
    "to": "2025-11-02T23:59:59Z"
  },
  "options": {
    "match_threshold": 0.78,
    "outfit_sim_threshold": 0.70,
    "max_candidate_window_sec": 480,
    "ambiguity_gap": 0.04
  }
}
```

**Response** (202 Accepted):
```json
{
  "job_id": "uuid",
  "mall_id": "uuid",
  "status": "pending",
  "tracklets_to_process": 245,
  "queued_at": "2025-11-02T10:00:00Z"
}
```

---

### Get Associations for Mall

#### `GET /malls/{mall_id}/associations`

**Purpose**: Retrieve cross-camera associations with filters

**Query Parameters**:
- `decision`: Filter by decision (linked, new_visitor, ambiguous)
- `min_score`: Minimum match score (0-1)
- `from_pin`: Filter by source camera pin
- `to_pin`: Filter by target camera pin
- `from_time`: Start of time range
- `to_time`: End of time range
- `limit`: Max results (default 100, max 500)
- `offset`: Pagination offset

**Response** (200 OK):
```json
{
  "associations": [
    {
      "id": "uuid",
      "from_tracklet": {
        "id": "uuid",
        "pin_name": "Entrance A",
        "t_out": "2025-11-02T10:00:30Z"
      },
      "to_tracklet": {
        "id": "uuid",
        "pin_name": "Central Atrium",
        "t_in": "2025-11-02T10:01:15Z"
      },
      "decision": "linked",
      "score": 0.83,
      "scores": {
        "outfit_sim": 0.85,
        "time_score": 0.82,
        "adj_score": 1.0,
        "physique": 0.70
      },
      "created_at": "2025-11-02T10:05:00Z"
    }
  ],
  "total": 245,
  "limit": 100,
  "offset": 0
}
```

---

### Get Association Details

#### `GET /associations/{association_id}`

**Purpose**: Get detailed information about a specific association (debugging)

**Response** (200 OK):
```json
{
  "id": "uuid",
  "from_tracklet_id": "uuid",
  "to_tracklet_id": "uuid",
  "from_pin": {
    "id": "uuid",
    "name": "Entrance A",
    "pin_type": "entrance"
  },
  "to_pin": {
    "id": "uuid",
    "name": "Central Atrium",
    "pin_type": "normal"
  },
  "decision": "linked",
  "score": 0.83,
  "scores": {
    "outfit_sim": 0.85,
    "time_score": 0.82,
    "adj_score": 1.0,
    "physique": 0.70,
    "final": 0.83
  },
  "components": {
    "type_score": 1.0,
    "color_deltaE": {
      "top": 14.2,
      "bottom": 9.8,
      "shoes": 28.1
    },
    "embed_cosine": 0.79,
    "delta_t_sec": 45,
    "expected_mu_sec": 45,
    "tau_sec": 25,
    "height_match": 1.0,
    "aspect_ratio_diff": 0.03
  },
  "candidate_count": 8,
  "rank": 1,
  "created_at": "2025-11-02T10:05:00Z"
}
```

---

### Get Journeys for Mall

#### `GET /malls/{mall_id}/journeys`

**Purpose**: Retrieve visitor journeys with filters

**Query Parameters**:
- `from`: Start date (YYYY-MM-DD)
- `to`: End date (YYYY-MM-DD)
- `min_confidence`: Minimum journey confidence (0-1)
- `entry_pin`: Filter by entry point
- `exit_pin`: Filter by exit point
- `status`: Filter by status (active, completed, incomplete)
- `min_cameras`: Minimum cameras visited
- `limit`: Max results (default 50, max 200)
- `offset`: Pagination offset

**Response** (200 OK):
```json
{
  "journeys": [
    {
      "id": "uuid",
      "visitor_id": "v-2025-11-02-000123",
      "entry_time": "2025-11-02T10:00:00Z",
      "exit_time": "2025-11-02T10:15:30Z",
      "total_duration_minutes": 15.5,
      "entry_point": "Entrance A",
      "exit_point": "Entrance B",
      "confidence": 0.81,
      "num_cameras_visited": 5,
      "outfit": {
        "top": {"type": "jacket", "color": "blue"},
        "bottom": {"type": "pants", "color": "dark_brown"},
        "shoes": {"type": "sneakers", "color": "white"}
      },
      "path_summary": ["Entrance A", "Atrium", "Store 5", "Food Court", "Entrance B"],
      "status": "completed"
    }
  ],
  "total": 42,
  "limit": 50,
  "offset": 0
}
```

---

### Get Journey Details

#### `GET /journeys/{journey_id}`

**Purpose**: Get complete journey with full path and timing

**Response** (200 OK):
```json
{
  "id": "uuid",
  "visitor_id": "v-2025-11-02-000123",
  "mall_id": "uuid",
  "journey_date": "2025-11-02",
  "entry_time": "2025-11-02T10:00:00Z",
  "exit_time": "2025-11-02T10:15:30Z",
  "total_duration_minutes": 15.5,
  "confidence": 0.81,
  "entry_point": {
    "id": "uuid",
    "name": "Entrance A"
  },
  "exit_point": {
    "id": "uuid",
    "name": "Entrance B"
  },
  "outfit": {
    "top": {"type": "jacket", "color": "blue"},
    "bottom": {"type": "pants", "color": "dark_brown"},
    "shoes": {"type": "sneakers", "color": "white"}
  },
  "path": [
    {
      "pin_id": "uuid",
      "pin_name": "Entrance A",
      "tracklet_id": "uuid",
      "t_in": "2025-11-02T10:00:00Z",
      "t_out": "2025-11-02T10:00:30Z",
      "duration_seconds": 30,
      "link_score": null
    },
    {
      "pin_id": "uuid",
      "pin_name": "Central Atrium",
      "tracklet_id": "uuid",
      "t_in": "2025-11-02T10:01:15Z",
      "t_out": "2025-11-02T10:03:00Z",
      "duration_seconds": 105,
      "link_score": 0.83
    },
    {
      "pin_id": "uuid",
      "pin_name": "Store 5 Entrance",
      "tracklet_id": "uuid",
      "t_in": "2025-11-02T10:04:00Z",
      "t_out": "2025-11-02T10:10:00Z",
      "duration_seconds": 360,
      "link_score": 0.78
    },
    {
      "pin_id": "uuid",
      "pin_name": "Food Court",
      "tracklet_id": "uuid",
      "t_in": "2025-11-02T10:11:30Z",
      "t_out": "2025-11-02T10:14:00Z",
      "duration_seconds": 150,
      "link_score": 0.85
    },
    {
      "pin_id": "uuid",
      "pin_name": "Entrance B",
      "tracklet_id": "uuid",
      "t_in": "2025-11-02T10:15:00Z",
      "t_out": "2025-11-02T10:15:30Z",
      "duration_seconds": 30,
      "link_score": 0.80
    }
  ],
  "num_cameras_visited": 5,
  "total_tracklets": 5,
  "avg_link_score": 0.815,
  "status": "completed",
  "created_at": "2025-11-02T10:20:00Z"
}
```

---

### Delete Journey

#### `DELETE /journeys/{journey_id}`

**Purpose**: Delete journey (admin only, for data cleanup)

**Response** (204 No Content)

**Implementation**:
- Sets journey status to 'deleted'
- Unlinks tracklets (sets journey_id to NULL)
- Deletes associated associations if cascade configured

---

## Configuration Architecture

### Two-Tier Configuration System

Wandr uses a two-tier configuration system for re-identification scoring:

**1. Base Parameters** (in code):
- Initial default weights for development and testing
- Conceptual starting points: outfit ~55%, time ~20%, adjacency ~15%, physique ~10%
- Hardcoded thresholds for prototyping (match_threshold: 0.78, outfit_sim_threshold: 0.70)
- Used when `.secret` calibration file is not available

**2. Learned Calibration** (`.secret` file - not in repository):
- **Per-mall weight overrides**: Learned from labeled data specific to each mall
  - Example: Mall A uses 0.58/0.18/0.14/0.10 (optimized for multi-floor layout)
  - Example: Mall B uses 0.52/0.24/0.16/0.08 (optimized for single-floor layout)
- **Per-camera trust factors**: Reliability scores based on lighting quality and occlusion patterns
  - Example: cam-ENTR-01 = 0.95 (excellent lighting), cam-ESCALATOR-02 = 0.60 (motion blur)
- **Per-edge transit times**: Observed μ (median) and τ (std dev) from real transitions
  - Example: cam-ENTR-01 → cam-ATRIUM-01: μ=52s, τ=28s (learned from 1,245 observations)
- **Extra signal coefficients**: Crowd density penalties, uniform detection, co-movement bonuses
- **Decision threshold adjustments**: Precision/recall optimization per mall

### Production Runtime Flow

```python
def initialize_scoring_service(mall_id: str):
    """
    Production initialization: Load calibration from secure storage

    Steps:
    1. Load .secret file from HashiCorp Vault / AWS KMS / encrypted DB
    2. Parse calibration parameters (TOML/INI format)
    3. Merge base parameters with mall-specific overrides
    4. Cache in memory (refresh every 1 hour or on update signal)
    5. Initialize MultiSignalScorer with merged configuration
    """
    # Load from secure storage
    calibration = load_secret_from_vault(f"wandr/calibration/{mall_id}")

    # Parse calibration
    config = parse_calibration(calibration)

    # Initialize scorer with dynamic weights
    scorer = MultiSignalScorer(mall_id, config=config)

    return scorer
```

### Calibration Schema (from `.secret` file)

See `.secret` file for complete calibration schema including:
- `[base_weights]`: Initial default values (55/20/15/10)
- `[global_calibration]`: Outfit sub-component weights, time parameters, adjacency scores
- `[mall_overrides]`: Per-mall learned weight adjustments
- `[camera_trust]`: Per-camera reliability factors
- `[edge_transit_times]`: Per-edge learned μ and τ values
- `[extra_signals]`: Experimental features (crowd density, lighting trust, uniform penalties)
- `[decision_thresholds]`: Match thresholds and ambiguity gaps
- `[metadata]`: Version control, calibration date, performance metrics

### Security & Access Control

**Storage**:
- `.secret` file NEVER committed to version control (in `.gitignore`)
- Stored in secure vault: HashiCorp Vault, AWS Secrets Manager, or encrypted database
- Access restricted to backend services only via service account credentials
- Encrypted at rest with AES-256 or KMS
- Version controlled in secure vault (not Git)

**Audit**:
- All access to calibration logged with timestamp and service identity
- Changes tracked with who/when/why metadata
- Rollback support via versioned backups

**Continuous Learning**:
- Retrain calibration monthly using new labeled data (ground truth visitor journeys)
- A/B test new weights before production deployment
- Monitor precision/recall metrics per mall
- Detect drift in visitor behavior or camera conditions
- Auto-adjust thresholds based on false merge/split rates

**Calibration Validation Process**:

Before promoting new calibration weights to production, follow this validation pipeline:

1. **Offline Evaluation** (Phase 1: Safety Check)
   - Test new weights on held-out labeled test set (min 500 tracklet pairs)
   - Measure link precision, recall, false merge rate, ambiguity rate
   - **Go/No-Go Criteria**:
     - Precision ≥ 85%
     - False merge rate ≤ 5%
     - Ambiguity rate ≤ 20%
     - No regression > 3% on any metric vs. current production weights
   - If criteria fail, reject calibration and log failure reasons

2. **Shadow Mode Deployment** (Phase 2: Real-World Validation)
   - Deploy new weights to shadow scorer running in parallel with production
   - Process 1 week of real footage (min 10,000 associations)
   - Compare decisions and scores between production and shadow
   - Manually review 100 random disagreements (where shadow differs from production)
   - **Go/No-Go Criteria**:
     - Shadow agreement with production ≥ 90% on high-confidence cases
     - Manual review of disagreements shows shadow is correct ≥ 75% of the time
     - No catastrophic failures (e.g., merging obviously different people)
   - If criteria fail, extend shadow period or reject calibration

3. **Canary Deployment** (Phase 3: Limited Production)
   - Deploy new weights to 1 mall (canary) while others remain on current production
   - Run for 2 weeks, monitor operator feedback and journey quality metrics
   - **Go/No-Go Criteria**:
     - No increase in operator-reported false merges
     - Journey confidence scores remain stable (no drop > 5%)
     - System performance metrics stable (latency, throughput)
   - If criteria fail, rollback canary and investigate

4. **Full Deployment** (Phase 4: Production Rollout)
   - Gradually roll out to all malls over 1 week (10% → 25% → 50% → 100%)
   - Monitor telemetry dashboard for anomalies
   - Keep previous calibration version hot-swappable for instant rollback
   - After 1 month, promote to stable if no issues detected

**Success Criteria Alignment**:
This validation process ensures new calibrations meet Phase 4 success criteria:
- Link precision >85% (validated in offline eval)
- False merge rate <5% (validated in offline + shadow)
- Ambiguous link rate <15% (validated in offline)
- Journey confidence >0.75 for 70%+ journeys (validated in canary)

---

## Cross-Camera Re-Identification Implementation

### Phase 4.1: Multi-Signal Scoring System (Days 1-4)

**Objective**: Implement the scoring components for matching tracklets

#### Day 1: Outfit Similarity Scoring

**Tasks**:
- [ ] Implement type matching with confusion matrix
- [ ] Implement CIEDE2000 color difference calculation
- [ ] Implement embedding cosine similarity
- [ ] Combine into weighted outfit similarity score
- [ ] Test on sample tracklet pairs

**Outfit Similarity Service**:
```python
import numpy as np
from typing import Dict, Tuple

class OutfitSimilarityScorer:
    """
    Calculate outfit similarity using three sub-components:
    - Type matching (35% weight)
    - Color similarity via CIEDE2000 (35% weight)
    - Embedding cosine similarity (30% weight)
    """

    # Garment type confusion matrix (similar types get partial credit)
    TYPE_CONFUSION = {
        ("jacket", "jacket"): 1.0,
        ("jacket", "coat"): 0.6,
        ("coat", "coat"): 1.0,
        ("tee", "tee"): 1.0,
        ("tee", "shirt"): 0.7,
        ("shirt", "shirt"): 1.0,
        ("pants", "pants"): 1.0,
        ("shorts", "shorts"): 1.0,
        ("sneakers", "sneakers"): 1.0,
        ("loafers", "loafers"): 1.0,
        # Add more pairs as needed
    }

    def __init__(self, config: dict = None):
        # Base weights (initial defaults)
        # Production: Load from .secret calibration file via config
        self.type_weight = config.get("outfit.type_weight", 0.35) if config else 0.35
        self.color_weight = config.get("outfit.color_weight", 0.35) if config else 0.35
        self.embed_weight = config.get("outfit.embedding_weight", 0.30) if config else 0.30

    def calculate(
        self,
        outfit1: Dict,
        outfit2: Dict,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> Tuple[float, Dict]:
        """
        Calculate outfit similarity score

        Returns:
            (score, components) where components contains detailed breakdown
        """
        # Type score
        type_score = self._type_similarity(outfit1, outfit2)

        # Color score (average across garments)
        color_scores = {}
        for garment in ["top", "bottom", "shoes"]:
            if garment in outfit1 and garment in outfit2:
                delta_e = self._ciede2000(
                    np.array(outfit1[garment]["lab"]),
                    np.array(outfit2[garment]["lab"])
                )
                color_scores[garment] = np.exp(-delta_e / 12)  # Soft threshold
            else:
                color_scores[garment] = 0.0

        color_score = np.mean(list(color_scores.values()))

        # Embedding cosine similarity
        embed_cosine = self._cosine_similarity(embedding1, embedding2)

        # Weighted combination
        outfit_sim = (
            self.type_weight * type_score +
            self.color_weight * color_score +
            self.embed_weight * embed_cosine
        )

        components = {
            "type_score": type_score,
            "color_score": color_score,
            "color_deltaE": {
                garment: self._ciede2000(
                    np.array(outfit1[garment]["lab"]),
                    np.array(outfit2[garment]["lab"])
                ) if garment in outfit1 and garment in outfit2 else None
                for garment in ["top", "bottom", "shoes"]
            },
            "embed_cosine": embed_cosine
        }

        return outfit_sim, components

    def _type_similarity(self, outfit1: Dict, outfit2: Dict) -> float:
        """Calculate garment type similarity"""
        scores = []
        for garment in ["top", "bottom", "shoes"]:
            if garment in outfit1 and garment in outfit2:
                type1 = outfit1[garment]["type"]
                type2 = outfit2[garment]["type"]

                # Look up in confusion matrix
                pair = (type1, type2)
                reverse_pair = (type2, type1)

                if pair in self.TYPE_CONFUSION:
                    scores.append(self.TYPE_CONFUSION[pair])
                elif reverse_pair in self.TYPE_CONFUSION:
                    scores.append(self.TYPE_CONFUSION[reverse_pair])
                else:
                    # No match
                    scores.append(0.0)
            else:
                # Missing garment
                scores.append(0.0)

        return np.mean(scores) if scores else 0.0

    @staticmethod
    def _ciede2000(lab1: np.ndarray, lab2: np.ndarray) -> float:
        """
        Calculate CIEDE2000 color difference
        Simplified implementation (use colormath for production)
        """
        # Euclidean distance in LAB space (approximation)
        delta_L = lab1[0] - lab2[0]
        delta_a = lab1[1] - lab2[1]
        delta_b = lab1[2] - lab2[2]

        return np.sqrt(delta_L**2 + delta_a**2 + delta_b**2)

    @staticmethod
    def _cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Calculate cosine similarity between embeddings"""
        return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
```

#### Day 2: Time Plausibility Scoring

**Tasks**:
- [ ] Implement transit time graph from camera adjacency
- [ ] Calculate expected transit time μ and tolerance τ
- [ ] Implement time score with soft exponential decay
- [ ] Add hard gates (reject impossible transitions)
- [ ] Test on sample camera pairs

**Time Plausibility Service**:
```python
from datetime import datetime, timedelta
from typing import Dict, Tuple
import numpy as np

class TimePlausibilityScorer:
    """
    Calculate time plausibility score for cross-camera transitions
    Uses precomputed transit times from camera adjacency graph
    """

    def __init__(self, walk_speed_ms: float = 1.2):
        self.walk_speed_ms = walk_speed_ms
        self.transit_graph = {}  # {(from_pin, to_pin): {"mu_sec": 45, "tau_sec": 25}}

    def load_transit_graph(self, mall_id: str):
        """
        Load transit times from camera pin adjacency graph
        Precompute μ (expected transit time) and τ (tolerance)
        """
        # Query camera pins with adjacency and distances
        pins = get_camera_pins(mall_id)

        for pin in pins:
            if "transit_times" in pin and pin["transit_times"]:
                for adjacent_pin_id, times in pin["transit_times"].items():
                    key = (pin["id"], adjacent_pin_id)
                    self.transit_graph[key] = {
                        "mu_sec": times["mu_sec"],
                        "tau_sec": times["tau_sec"]
                    }

    def calculate(
        self,
        from_pin_id: str,
        to_pin_id: str,
        departure_time: datetime,
        arrival_time: datetime
    ) -> Tuple[float, Dict]:
        """
        Calculate time plausibility score

        Returns:
            (score, components) where components contains detailed breakdown
        """
        # Calculate actual transit time
        delta_t = (arrival_time - departure_time).total_seconds()

        # Look up expected transit time
        key = (from_pin_id, to_pin_id)
        if key in self.transit_graph:
            mu = self.transit_graph[key]["mu_sec"]
            tau = self.transit_graph[key]["tau_sec"]
        else:
            # No direct adjacency - use default or return 0
            mu = 60  # Default 1 minute
            tau = 30  # Default 30 seconds tolerance

        # Hard gates
        if delta_t < 1:
            # Impossible (less than 1 second)
            return 0.0, {
                "delta_t_sec": delta_t,
                "expected_mu_sec": mu,
                "tau_sec": tau,
                "reason": "transition_too_fast"
            }

        if delta_t > mu + 3 * tau:
            # Too late (beyond 3 sigma)
            return 0.0, {
                "delta_t_sec": delta_t,
                "expected_mu_sec": mu,
                "tau_sec": tau,
                "reason": "transition_too_slow"
            }

        # Soft exponential decay
        deviation = abs(delta_t - mu)
        time_score = np.exp(-deviation / tau)

        components = {
            "delta_t_sec": delta_t,
            "expected_mu_sec": mu,
            "tau_sec": tau,
            "deviation_sec": deviation
        }

        return time_score, components
```

#### Day 3: Camera Adjacency & Physique Scoring

**Tasks**:
- [ ] Implement adjacency scoring (1-hop, 2-hop, no connection)
- [ ] Implement height category matching
- [ ] Implement aspect ratio similarity
- [ ] Combine into physique score
- [ ] Test on sample tracklets

**Adjacency & Physique Scorers**:
```python
class AdjacencyScorer:
    """
    Score based on camera adjacency graph
    Prevents impossible jumps across mall
    """

    def __init__(self):
        self.adjacency_graph = {}  # {pin_id: [adjacent_pin_ids]}

    def load_adjacency_graph(self, mall_id: str):
        """Load camera adjacency from database"""
        pins = get_camera_pins(mall_id)
        for pin in pins:
            self.adjacency_graph[pin["id"]] = pin.get("adjacent_to", [])

    def calculate(self, from_pin_id: str, to_pin_id: str) -> float:
        """
        Calculate adjacency score
        1.0 for direct neighbors
        0.5 for 2-hop neighbors
        0.0 otherwise
        """
        if to_pin_id in self.adjacency_graph.get(from_pin_id, []):
            return 1.0

        # Check 2-hop
        for intermediate in self.adjacency_graph.get(from_pin_id, []):
            if to_pin_id in self.adjacency_graph.get(intermediate, []):
                return 0.5

        return 0.0


class PhysiqueScorer:
    """
    Score based on non-biometric physique cues
    Height category and aspect ratio
    """

    HEIGHT_CATEGORIES = ["short", "medium", "tall"]

    def calculate(self, physique1: Dict, physique2: Dict) -> Tuple[float, Dict]:
        """
        Calculate physique similarity score

        Returns:
            (score, components)
        """
        # Height category match
        height1 = physique1.get("height_category")
        height2 = physique2.get("height_category")

        if height1 == height2:
            height_score = 1.0
        elif self._adjacent_height(height1, height2):
            height_score = 0.5
        else:
            height_score = 0.0

        # Aspect ratio similarity
        ar1 = physique1.get("aspect_ratio", 0.4)
        ar2 = physique2.get("aspect_ratio", 0.4)
        ar_diff = abs(ar1 - ar2)

        # Threshold: 0.1 difference is acceptable
        ar_score = max(0, 1.0 - ar_diff / 0.1)

        # Weighted combination
        physique_score = 0.6 * height_score + 0.4 * ar_score

        components = {
            "height_match": height_score,
            "aspect_ratio_diff": ar_diff
        }

        return physique_score, components

    def _adjacent_height(self, h1: str, h2: str) -> bool:
        """Check if height categories are adjacent"""
        if h1 not in self.HEIGHT_CATEGORIES or h2 not in self.HEIGHT_CATEGORIES:
            return False

        idx1 = self.HEIGHT_CATEGORIES.index(h1)
        idx2 = self.HEIGHT_CATEGORIES.index(h2)

        return abs(idx1 - idx2) == 1
```

#### Day 4: Multi-Signal Fusion

**Tasks**:
- [ ] Combine all scoring components with weights
- [ ] Implement final match score calculation
- [ ] Add scoring validation and bounds checking
- [ ] Create unified ScoringService
- [ ] Test end-to-end scoring on tracklet pairs

**Multi-Signal Scoring Service**:
```python
class MultiSignalScorer:
    """
    Fuse multiple signals into final match score

    Base Weights (initial defaults):
    - Outfit similarity: ~55%
    - Time plausibility: ~20%
    - Camera adjacency: ~15%
    - Physique match: ~10%

    Production: Weights are loaded from .secret calibration file and vary
    per mall, per camera pair, with learned adjustments.
    """

    def __init__(self, mall_id: str, config: dict = None):
        # Load calibration config (from .secret file in production)
        calibration = self._load_calibration(mall_id, config)

        self.outfit_scorer = OutfitSimilarityScorer(calibration)
        self.time_scorer = TimePlausibilityScorer()
        self.adjacency_scorer = AdjacencyScorer()
        self.physique_scorer = PhysiqueScorer()

        # Load mall-specific data
        self.time_scorer.load_transit_graph(mall_id)
        self.adjacency_scorer.load_adjacency_graph(mall_id)

        # Base weights (initial defaults)
        # Production: Override from per-mall calibration
        mall_overrides = calibration.get("mall_overrides", {}).get(mall_id, {})
        self.weights = {
            "outfit": mall_overrides.get("outfit", 0.55),
            "time": mall_overrides.get("time", 0.20),
            "adjacency": mall_overrides.get("adjacency", 0.15),
            "physique": mall_overrides.get("physique", 0.10)
        }

    def _load_calibration(self, mall_id: str, config: dict = None) -> dict:
        """
        Load calibration from .secret file (production) or use defaults

        In production:
        1. Load .secret file from secure storage (Vault/KMS)
        2. Parse calibration parameters
        3. Return mall-specific overrides and global settings
        """
        if config:
            return config

        # Development mode: return base configuration
        return {
            "base_weights": {"outfit": 0.55, "time": 0.20, "adjacency": 0.15, "physique": 0.10},
            "mall_overrides": {},
            "camera_trust": {}
        }

    def score_pair(
        self,
        tracklet1: Dict,
        tracklet2: Dict
    ) -> Tuple[float, Dict, Dict]:
        """
        Calculate match score between two tracklets

        Returns:
            (final_score, scores_dict, components_dict)
        """
        # Extract data
        outfit1 = tracklet1["outfit_json"]
        outfit2 = tracklet2["outfit_json"]
        embedding1 = deserialize_embedding(tracklet1["outfit_vec"])
        embedding2 = deserialize_embedding(tracklet2["outfit_vec"])
        physique1 = tracklet1.get("physique", {})
        physique2 = tracklet2.get("physique", {})

        # Calculate individual scores
        outfit_sim, outfit_components = self.outfit_scorer.calculate(
            outfit1, outfit2, embedding1, embedding2
        )

        time_score, time_components = self.time_scorer.calculate(
            tracklet1["pin_id"],
            tracklet2["pin_id"],
            tracklet1["t_out"],
            tracklet2["t_in"]
        )

        adj_score = self.adjacency_scorer.calculate(
            tracklet1["pin_id"],
            tracklet2["pin_id"]
        )

        physique_score, physique_components = self.physique_scorer.calculate(
            physique1, physique2
        )

        # Apply camera trust factor (production: from .secret calibration)
        camera_trust = self._get_camera_trust(tracklet1["pin_id"])
        adjusted_outfit_sim = outfit_sim * camera_trust

        # Final weighted score
        # Production: w_* loaded from .secret per-mall calibration
        final_score = (
            self.weights["outfit"] * adjusted_outfit_sim +
            self.weights["time"] * time_score +
            self.weights["adjacency"] * adj_score +
            self.weights["physique"] * physique_score
        )

        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))

        scores = {
            "outfit_sim": outfit_sim,
            "time_score": time_score,
            "adj_score": adj_score,
            "physique": physique_score,
            "final": final_score
        }

        components = {
            **outfit_components,
            **time_components,
            **physique_components
        }

        return final_score, scores, components

    def _get_camera_trust(self, pin_id: str) -> float:
        """
        Get camera trust factor from calibration

        Production: Load from .secret file per-camera trust scores
        Development: Return 1.0 (no adjustment)
        """
        # TODO: Load from calibration in production
        return 1.0
```

---

### Phase 4.2: Candidate Retrieval System (Days 5-7)

**Objective**: Efficiently find candidate tracklets for matching

#### Day 5-6: Implement Pre-Filters

**Tasks**:
- [ ] Temporal filter (candidate time window)
- [ ] Spatial filter (adjacent cameras only)
- [ ] Embedding pre-filter (cosine similarity threshold)
- [ ] Database query optimization with indexes
- [ ] Test retrieval speed (target: <100ms for 100+ tracklets)

**Candidate Retrieval Service**:
```python
from typing import List, Dict
from datetime import timedelta
from sqlalchemy import and_, or_
import numpy as np

class CandidateRetriever:
    """
    Retrieve candidate tracklets for matching
    Uses pre-filters to reduce search space
    """

    def __init__(
        self,
        max_candidate_window_sec: int = 480,  # 8 minutes
        embedding_threshold: float = 0.75,
        max_candidates: int = 50
    ):
        self.max_window = max_candidate_window_sec
        self.embed_threshold = embedding_threshold
        self.max_candidates = max_candidates

    def get_candidates(
        self,
        source_tracklet: Dict,
        adjacency_graph: Dict[str, List[str]]
    ) -> List[Dict]:
        """
        Find candidate tracklets that could match source

        Pre-filters:
        1. Adjacent cameras only (1-hop or 2-hop)
        2. Arrival time within window after source departure
        3. Embedding cosine similarity > threshold
        """
        # Get adjacent pins (1-hop and 2-hop)
        adjacent_pins = self._get_adjacent_pins(
            source_tracklet["pin_id"],
            adjacency_graph,
            max_hops=2
        )

        if not adjacent_pins:
            return []

        # Temporal window
        t_out = source_tracklet["t_out"]
        t_window_end = t_out + timedelta(seconds=self.max_window)

        # Query database
        candidates = db.query(Tracklet).filter(
            and_(
                Tracklet.pin_id.in_(adjacent_pins),
                Tracklet.t_in >= t_out,
                Tracklet.t_in <= t_window_end,
                Tracklet.mall_id == source_tracklet["mall_id"]
            )
        ).order_by(Tracklet.t_in).limit(self.max_candidates * 2).all()

        # Filter by embedding similarity
        source_embedding = deserialize_embedding(source_tracklet["outfit_vec"])
        filtered_candidates = []

        for candidate in candidates:
            candidate_embedding = deserialize_embedding(candidate.outfit_vec)
            cosine_sim = np.dot(source_embedding, candidate_embedding) / (
                np.linalg.norm(source_embedding) * np.linalg.norm(candidate_embedding)
            )

            if cosine_sim >= self.embed_threshold:
                filtered_candidates.append({
                    "tracklet": candidate,
                    "embed_sim": cosine_sim
                })

        # Sort by time (earliest first) and limit
        filtered_candidates.sort(key=lambda x: x["tracklet"].t_in)
        return filtered_candidates[:self.max_candidates]

    def _get_adjacent_pins(
        self,
        pin_id: str,
        adjacency_graph: Dict[str, List[str]],
        max_hops: int = 2
    ) -> List[str]:
        """Get adjacent pins up to max_hops away"""
        adjacent = set()

        # 1-hop
        if pin_id in adjacency_graph:
            adjacent.update(adjacency_graph[pin_id])

        # 2-hop
        if max_hops >= 2:
            for hop1 in list(adjacent):
                if hop1 in adjacency_graph:
                    adjacent.update(adjacency_graph[hop1])

        # Remove source pin
        adjacent.discard(pin_id)

        return list(adjacent)
```

#### Day 7: Candidate Ranking

**Tasks**:
- [ ] Implement candidate ranking by score
- [ ] Add candidate metadata (rank, count)
- [ ] Test ranking consistency
- [ ] Optimize for top-k retrieval

---

### Phase 4.3: Association Decision Logic (Days 8-10)

**Objective**: Decide whether to link tracklets or create new visitor

#### Day 8-9: Decision Logic Implementation

**Tasks**:
- [ ] Implement link decision (high confidence)
- [ ] Implement new visitor decision (no good match)
- [ ] Implement ambiguous decision (multiple similar candidates)
- [ ] Add decision thresholds configuration
- [ ] Test decision rules on sample data

**Association Decision Service**:
```python
class AssociationDecider:
    """
    Decide whether to link tracklets across cameras

    Decision rules:
    1. Link: match_score >= 0.78 AND outfit_sim >= 0.70
    2. Ambiguous: top-2 candidates within 0.04 of each other
    3. New visitor: no candidate passes thresholds
    """

    def __init__(
        self,
        match_threshold: float = 0.78,
        outfit_sim_threshold: float = 0.70,
        ambiguity_gap: float = 0.04
    ):
        self.match_threshold = match_threshold
        self.outfit_sim_threshold = outfit_sim_threshold
        self.ambiguity_gap = ambiguity_gap

    def decide(
        self,
        source_tracklet: Dict,
        scored_candidates: List[Tuple[Dict, float, Dict, Dict]]
    ) -> Tuple[str, Dict, Dict]:
        """
        Make association decision

        Args:
            source_tracklet: Source tracklet dict
            scored_candidates: [(candidate, score, scores_dict, components_dict), ...]

        Returns:
            (decision, best_match, association_metadata)
            decision: 'linked', 'new_visitor', 'ambiguous'
        """
        if not scored_candidates:
            return "new_visitor", None, {"reason": "no_candidates"}

        # Sort by score (descending)
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # Top candidate
        best_candidate, best_score, best_scores, best_components = scored_candidates[0]

        # Check thresholds
        if best_score < self.match_threshold:
            return "new_visitor", None, {
                "reason": "below_match_threshold",
                "best_score": best_score,
                "threshold": self.match_threshold
            }

        if best_scores["outfit_sim"] < self.outfit_sim_threshold:
            return "new_visitor", None, {
                "reason": "below_outfit_threshold",
                "outfit_sim": best_scores["outfit_sim"],
                "threshold": self.outfit_sim_threshold
            }

        # Check ambiguity
        if len(scored_candidates) > 1:
            second_best_score = scored_candidates[1][1]
            score_gap = best_score - second_best_score

            if score_gap < self.ambiguity_gap:
                # Ambiguous - prefer creating new visitor over false merge
                return "ambiguous", None, {
                    "reason": "ambiguous_candidates",
                    "best_score": best_score,
                    "second_best_score": second_best_score,
                    "gap": score_gap,
                    "threshold": self.ambiguity_gap
                }

        # Link decision
        association_metadata = {
            "score": best_score,
            "scores": best_scores,
            "components": best_components,
            "candidate_count": len(scored_candidates),
            "rank": 1
        }

        return "linked", best_candidate, association_metadata
```

#### Day 10: Conflict Resolution

**Tasks**:
- [ ] Implement conflict detection (multiple sources → same target)
- [ ] Implement conflict resolution (highest score wins)
- [ ] Add cool-down period to prevent ping-pong
- [ ] Test conflict scenarios

**Conflict Resolution**:
```python
class ConflictResolver:
    """
    Resolve conflicts when multiple source tracklets claim the same target

    Strategy: Highest score wins, losers find next-best or create new visitor
    """

    def __init__(self, cooldown_sec: int = 10):
        self.cooldown_sec = cooldown_sec
        self.recent_links = {}  # {(pin_id, visitor_id): last_link_time}

    def resolve_conflicts(
        self,
        pending_links: List[Tuple[Dict, Dict, Dict]]
    ) -> List[Tuple[Dict, Dict, Dict]]:
        """
        Resolve conflicts in pending links

        Args:
            pending_links: [(source_tracklet, target_tracklet, metadata), ...]

        Returns:
            List of resolved links (conflicts removed)
        """
        # Group by target tracklet
        target_groups = {}
        for source, target, metadata in pending_links:
            target_id = target["id"]
            if target_id not in target_groups:
                target_groups[target_id] = []
            target_groups[target_id].append((source, target, metadata))

        resolved = []

        for target_id, claims in target_groups.items():
            if len(claims) == 1:
                # No conflict
                resolved.append(claims[0])
            else:
                # Conflict - choose highest score
                claims.sort(key=lambda x: x[2]["score"], reverse=True)
                winner = claims[0]
                resolved.append(winner)

                # Losers need to find alternative or create new visitor
                # (handled by caller)

        return resolved

    def check_cooldown(
        self,
        pin_id: str,
        visitor_id: str,
        current_time: datetime
    ) -> bool:
        """
        Check if visitor recently linked at this pin (prevent ping-pong)

        Returns:
            True if cool-down expired, False if still cooling
        """
        key = (pin_id, visitor_id)
        if key in self.recent_links:
            last_time = self.recent_links[key]
            elapsed = (current_time - last_time).total_seconds()
            return elapsed > self.cooldown_sec

        return True

    def record_link(self, pin_id: str, visitor_id: str, link_time: datetime):
        """Record a link for cool-down tracking"""
        self.recent_links[(pin_id, visitor_id)] = link_time
```

---

### Phase 4.4: Journey Construction (Days 11-14)

**Objective**: Build complete visitor journeys from associations

#### Day 11-12: Journey Builder Implementation

**Tasks**:
- [ ] Implement journey initialization (start at entrance)
- [ ] Follow association links chronologically
- [ ] Close journeys (exit or inactivity)
- [ ] Calculate journey confidence
- [ ] Test journey construction on sample data

**Journey Builder Service**:
```python
from collections import defaultdict
from typing import List, Dict, Optional

class JourneyBuilder:
    """
    Construct visitor journeys from cross-camera associations

    Start journeys at entrance pins
    Follow links chronologically
    Close at exit or inactivity threshold
    """

    def __init__(
        self,
        inactivity_threshold_minutes: int = 30,
        min_confidence: float = 0.65
    ):
        self.inactivity_threshold = inactivity_threshold_minutes
        self.min_confidence = min_confidence

    def build_journeys(
        self,
        mall_id: str,
        time_range: Tuple[datetime, datetime]
    ) -> List[Dict]:
        """
        Build all journeys for a mall in time range

        Algorithm:
        1. Find all tracklets at entrance pins (journey starts)
        2. For each start, follow association links
        3. Stop at exit pin or inactivity threshold
        4. Calculate confidence and store journey
        """
        # Get all tracklets in time range
        tracklets = self._get_tracklets(mall_id, time_range)

        # Get all associations
        associations = self._get_associations(mall_id, time_range)

        # Build association graph
        assoc_graph = defaultdict(list)
        for assoc in associations:
            if assoc["decision"] == "linked":
                assoc_graph[assoc["from_tracklet_id"]].append({
                    "to_tracklet_id": assoc["to_tracklet_id"],
                    "score": assoc["score"],
                    "scores": assoc["scores"]
                })

        # Get entrance pins
        entrance_pins = self._get_entrance_pins(mall_id)

        # Find starting tracklets
        start_tracklets = [
            t for t in tracklets
            if t["pin_id"] in entrance_pins and t["t_in"] >= time_range[0]
        ]

        # Build journeys
        journeys = []
        for start in start_tracklets:
            journey = self._build_single_journey(
                start, tracklets, assoc_graph, entrance_pins
            )
            if journey and journey["confidence"] >= self.min_confidence:
                journeys.append(journey)

        return journeys

    def _build_single_journey(
        self,
        start_tracklet: Dict,
        tracklets_dict: Dict[str, Dict],
        assoc_graph: Dict,
        entrance_pins: List[str]
    ) -> Optional[Dict]:
        """
        Build a single journey starting from start_tracklet

        Returns:
            Journey dict or None if invalid
        """
        path = []
        current = start_tracklet
        visited = set()
        link_scores = []

        # Add first tracklet
        path.append({
            "pin_id": current["pin_id"],
            "pin_name": self._get_pin_name(current["pin_id"]),
            "tracklet_id": current["id"],
            "t_in": current["t_in"],
            "t_out": current["t_out"],
            "duration_seconds": current["duration_seconds"],
            "link_score": None  # First tracklet has no incoming link
        })
        visited.add(current["id"])

        # Follow associations
        while True:
            # Get next tracklet(s)
            next_links = assoc_graph.get(current["id"], [])

            if not next_links:
                # End of journey
                break

            # Take highest scoring link
            next_links.sort(key=lambda x: x["score"], reverse=True)
            next_link = next_links[0]

            next_tracklet_id = next_link["to_tracklet_id"]
            if next_tracklet_id in visited:
                # Cycle detected (shouldn't happen, but guard)
                break

            next_tracklet = tracklets_dict.get(next_tracklet_id)
            if not next_tracklet:
                break

            # Check inactivity threshold
            time_gap = (next_tracklet["t_in"] - current["t_out"]).total_seconds() / 60
            if time_gap > self.inactivity_threshold:
                # Too long - end journey
                break

            # Add to path
            path.append({
                "pin_id": next_tracklet["pin_id"],
                "pin_name": self._get_pin_name(next_tracklet["pin_id"]),
                "tracklet_id": next_tracklet["id"],
                "t_in": next_tracklet["t_in"],
                "t_out": next_tracklet["t_out"],
                "duration_seconds": next_tracklet["duration_seconds"],
                "link_score": next_link["score"]
            })

            visited.add(next_tracklet_id)
            link_scores.append(next_link["score"])
            current = next_tracklet

            # Check if at exit
            if current["pin_id"] in entrance_pins:
                # Journey complete (exited)
                break

        # Require at least 2 tracklets for valid journey
        if len(path) < 2:
            return None

        # Calculate confidence
        confidence = self._calculate_journey_confidence(path, link_scores)

        # Build journey record
        journey = {
            "visitor_id": self._generate_visitor_id(start_tracklet),
            "mall_id": start_tracklet["mall_id"],
            "journey_date": start_tracklet["t_in"].date(),
            "entry_time": path[0]["t_in"],
            "exit_time": path[-1]["t_out"] if path[-1]["pin_id"] in entrance_pins else None,
            "total_duration_minutes": (path[-1]["t_out"] - path[0]["t_in"]).total_seconds() / 60,
            "entry_point": path[0]["pin_id"],
            "exit_point": path[-1]["pin_id"] if path[-1]["pin_id"] in entrance_pins else None,
            "confidence": confidence,
            "path": path,
            "outfit": start_tracklet["outfit_json"],
            "num_cameras_visited": len(set(p["pin_id"] for p in path)),
            "total_tracklets": len(path),
            "avg_link_score": np.mean(link_scores) if link_scores else None,
            "status": "completed" if path[-1]["pin_id"] in entrance_pins else "incomplete"
        }

        return journey

    def _calculate_journey_confidence(
        self,
        path: List[Dict],
        link_scores: List[float]
    ) -> float:
        """
        Calculate journey confidence score

        Factors:
        - Average link score (70% weight)
        - Path length (longer = more confident, 20% weight)
        - Timing consistency (10% weight)
        """
        # Average link score
        avg_link = np.mean(link_scores) if link_scores else 0.5

        # Path length score (longer is better, max at 5 cameras)
        length_score = min(len(path) / 5, 1.0)

        # Timing consistency (low variance in link scores = high consistency)
        if len(link_scores) > 1:
            consistency = 1.0 - min(np.std(link_scores), 0.3) / 0.3
        else:
            consistency = 0.5

        confidence = 0.7 * avg_link + 0.2 * length_score + 0.1 * consistency

        return min(max(confidence, 0.0), 1.0)

    @staticmethod
    def _generate_visitor_id(start_tracklet: Dict) -> str:
        """Generate visitor ID from start time"""
        date_str = start_tracklet["t_in"].strftime("%Y-%m-%d")
        time_str = start_tracklet["t_in"].strftime("%H%M%S")
        return f"v-{date_str}-{time_str}-{start_tracklet['id'][:8]}"
```

#### Day 13-14: End-to-End Pipeline Integration

**Tasks**:
- [ ] Create master Celery task: `reidentify_and_build_journeys`
- [ ] Chain tasks: candidate retrieval → scoring → decision → journey building
- [ ] Store associations and journeys in database
- [ ] Add comprehensive error handling
- [ ] Test full pipeline on sample mall data
- [ ] Validate journey output

**Master Re-Identification Task**:
```python
@app.task(bind=True)
def reidentify_and_build_journeys(
    self,
    mall_id: str,
    time_range: Tuple[datetime, datetime],
    options: dict
) -> dict:
    """
    Complete cross-camera re-identification and journey construction

    Stages:
    1. Load tracklets for time range
    2. For each tracklet, find candidates
    3. Score candidates with multi-signal fusion
    4. Make association decisions
    5. Resolve conflicts
    6. Build journeys from associations
    7. Store in database

    Returns:
        {
            "mall_id": "uuid",
            "associations_created": 245,
            "journeys_created": 42,
            "processing_time_seconds": 180,
            "status": "completed"
        }
    """
    start_time = time.time()

    try:
        # Initialize services
        scorer = MultiSignalScorer(mall_id)
        retriever = CandidateRetriever(
            max_candidate_window_sec=options.get("max_candidate_window_sec", 480),
            embedding_threshold=options.get("embedding_threshold", 0.75)
        )
        decider = AssociationDecider(
            match_threshold=options.get("match_threshold", 0.78),
            outfit_sim_threshold=options.get("outfit_sim_threshold", 0.70),
            ambiguity_gap=options.get("ambiguity_gap", 0.04)
        )
        resolver = ConflictResolver()
        builder = JourneyBuilder()

        # Load tracklets
        tracklets = get_tracklets_for_mall(mall_id, time_range)
        logger.info(f"Processing {len(tracklets)} tracklets")

        # Load adjacency graph
        adjacency_graph = get_adjacency_graph(mall_id)

        # Stage 1-4: Create associations
        associations_created = 0
        pending_links = []

        for i, source_tracklet in enumerate(tracklets):
            # Find candidates
            candidates = retriever.get_candidates(source_tracklet, adjacency_graph)

            # Score candidates
            scored_candidates = []
            for candidate_info in candidates:
                candidate = candidate_info["tracklet"]
                score, scores, components = scorer.score_pair(source_tracklet, candidate)

                scored_candidates.append((candidate, score, scores, components))

            # Make decision
            decision, best_match, metadata = decider.decide(source_tracklet, scored_candidates)

            # Store association
            association = {
                "mall_id": mall_id,
                "from_tracklet_id": source_tracklet["id"],
                "to_tracklet_id": best_match["id"] if best_match else None,
                "from_pin_id": source_tracklet["pin_id"],
                "to_pin_id": best_match["pin_id"] if best_match else None,
                "decision": decision,
                **metadata
            }

            store_association(association)
            associations_created += 1

            if decision == "linked":
                pending_links.append((source_tracklet, best_match, metadata))

            # Progress update
            if i % 50 == 0:
                self.update_state(
                    state='PROGRESS',
                    meta={'tracklets_processed': i, 'total_tracklets': len(tracklets)}
                )

        # Stage 5: Resolve conflicts
        resolved_links = resolver.resolve_conflicts(pending_links)

        # Stage 6: Build journeys
        journeys = builder.build_journeys(mall_id, time_range)

        # Stage 7: Store journeys
        for journey in journeys:
            store_journey(journey)

        processing_time = time.time() - start_time

        return {
            "mall_id": mall_id,
            "associations_created": associations_created,
            "journeys_created": len(journeys),
            "processing_time_seconds": processing_time,
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"Re-identification failed for {mall_id}: {str(e)}")
        raise
```

---

## Testing Strategy

### Unit Tests (Days 1-14, ongoing)

**Outfit Similarity**:
- [ ] Identical outfits score >0.95
- [ ] Similar outfits (slight color variation) score 0.75-0.85
- [ ] Different outfits score <0.5
- [ ] Type confusion matrix works correctly

**Time Plausibility**:
- [ ] Reject transitions <1 second
- [ ] Reject transitions >μ + 3τ
- [ ] Score peaks at expected transit time μ
- [ ] Exponential decay works correctly

**Adjacency**:
- [ ] Direct neighbors score 1.0
- [ ] 2-hop neighbors score 0.5
- [ ] Non-neighbors score 0.0

**Decision Logic**:
- [ ] High confidence matches link correctly
- [ ] Low confidence creates new visitor
- [ ] Ambiguous cases prefer new visitor

### Integration Tests

**End-to-End Re-Identification**:
1. Create test mall with 3 cameras (entrance → atrium → exit)
2. Create 2 tracklets per camera for same person (6 total)
3. Run re-identification
4. Verify 2 associations created (entrance→atrium, atrium→exit)
5. Verify 1 journey created with 3 tracklets
6. Verify journey confidence >0.75

**Ambiguity Handling**:
1. Create 2 tracklets with very similar outfits at atrium
2. Create 1 tracklet at entrance
3. Run re-identification
4. Verify decision is "ambiguous" or creates 2 separate journeys

### Quality Validation

**Link Precision** (on hand-labeled test set):
- [ ] Create test set of 100 tracklet pairs (50 same person, 50 different)
- [ ] Run scoring and decision
- [ ] Calculate precision (TP / (TP + FP)) - target >85%
- [ ] Calculate recall (TP / (TP + FN)) - target >75%

**Journey Quality**:
- [ ] Journeys follow spatially coherent paths
- [ ] Journeys have temporally consistent timing
- [ ] Journey confidence correlates with visual inspection

---

## Performance Optimization

### Database Optimization

**Index Strategy**:
```sql
-- Tracklets: temporal queries
CREATE INDEX idx_tracklets_time_range ON tracklets(t_in, t_out);
CREATE INDEX idx_tracklets_pin_time ON tracklets(pin_id, t_in);

-- Associations: filtering and retrieval
CREATE INDEX idx_associations_mall_decision ON associations(mall_id, decision);
CREATE INDEX idx_associations_score_desc ON associations(score DESC);

-- Journeys: common query patterns
CREATE INDEX idx_journeys_mall_date ON journeys(mall_id, journey_date);
CREATE INDEX idx_journeys_confidence_desc ON journeys(confidence DESC);
```

**Query Optimization**:
- Use EXPLAIN ANALYZE to identify slow queries
- Batch database operations (bulk insert associations)
- Use connection pooling (already configured)

### Processing Optimization

**Parallel Candidate Scoring**:
```python
from concurrent.futures import ThreadPoolExecutor

def score_candidates_parallel(source, candidates, scorer, num_workers=4):
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [
            executor.submit(scorer.score_pair, source, candidate)
            for candidate in candidates
        ]
        results = [f.result() for f in futures]
    return results
```

**Caching**:
- Cache adjacency graph (load once per mall)
- Cache transit time graph (precompute once)
- Cache embeddings in memory during processing

---

## Deployment Checklist

### Database Migration

- [ ] Run Alembic migration for associations and journeys tables
- [ ] Create indexes for performance
- [ ] Verify foreign key constraints

### Service Deployment

- [ ] Deploy updated backend with re-identification services
- [ ] Configure Celery cv_analysis queue for re-ID tasks
- [ ] Test re-identification on sample mall

### Monitoring

- [ ] Add re-ID metrics to admin dashboard
  - Associations created per run
  - Journey count and confidence distribution
  - Link precision/recall (if test set available)
- [ ] Configure alerts for re-ID failures
- [ ] Track processing time (target: <10 min for 10-min video worth of tracklets)

---

## Week-by-Week Breakdown

### Week 8: Scoring & Retrieval (Days 1-7)

**Days 1-4: Multi-Signal Scoring** (Phase 4.1)
- [x] Day 1: Outfit similarity scoring
- [x] Day 2: Time plausibility scoring
- [x] Day 3: Adjacency & physique scoring
- [x] Day 4: Multi-signal fusion

**Days 5-7: Candidate Retrieval** (Phase 4.2)
- [x] Days 5-6: Pre-filter implementation
- [x] Day 7: Candidate ranking

### Week 9: Decision & Journey (Days 8-14)

**Days 8-10: Association Decision** (Phase 4.3)
- [x] Days 8-9: Decision logic
- [x] Day 10: Conflict resolution

**Days 11-14: Journey Construction** (Phase 4.4)
- [x] Days 11-12: Journey builder
- [x] Days 13-14: End-to-end integration and testing

---

## Risk Mitigation

### Identified Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **False merges (merge different people)** | High | Medium | Prefer false splits; require high outfit_sim threshold; use ambiguity detection |
| **Scoring weights not optimal** | Medium | High | Use two-tier config: base defaults + per-mall calibration from .secret; retrain monthly |
| **Transit time estimates inaccurate** | Medium | Medium | Learn μ/τ from observed transitions; store in .secret per edge; allow manual override |
| **Ambiguity too frequent** | Medium | Medium | Expected in crowded scenarios; prefer new visitor over merge; adjust ambiguity_gap per mall |
| **Journey construction too slow** | Medium | Low | Optimize database queries; use parallel processing; batch operations |
| **Embedding similarity not discriminative** | Low | Low | Already validated in Phase 3; fine-tune threshold if needed |

### Contingency Plans

**If false merge rate is too high**:
1. Update per-mall thresholds in `.secret`: increase match_threshold from 0.78 to 0.85
2. Increase outfit_sim_threshold from 0.70 to 0.80 in `.secret`
3. Decrease ambiguity_gap from 0.04 to 0.02 (more conservative)
4. Adjust per-mall weight to increase outfit importance (e.g., 0.60 instead of 0.55)

**If too many "new visitor" decisions**:
1. Update `.secret` thresholds: decrease match_threshold from 0.78 to 0.72
2. Increase max_candidate_window from 480s to 600s
3. Reduce embedding_threshold from 0.75 to 0.70 in `.secret`
4. Adjust per-mall weights to reduce time/adjacency importance

**If processing is too slow**:
1. Add database indexes for tracklet time range queries
2. Implement parallel candidate scoring (ThreadPoolExecutor)
3. Reduce max_candidates from 50 to 20
4. Cache calibration config in Redis (avoid repeated vault lookups)

---

## Success Metrics (Detailed)

### Functional Metrics
- ✅ Link precision >85% on hand-labeled test set
- ✅ False merge rate <5%
- ✅ Ambiguous link rate <15%
- ✅ Generate valid journeys for 80%+ of entrance→exit visitors
- ✅ Journey confidence >0.75 for 70%+ of journeys

### Performance Metrics
- ✅ Process 100 tracklets in <10 minutes
- ✅ Candidate retrieval <100ms per tracklet
- ✅ Journey construction <5 minutes for 50 journeys
- ✅ Association storage <1 second per 100 associations

### Quality Metrics
- ✅ Journeys are spatially coherent (no impossible jumps)
- ✅ Journeys are temporally consistent (timing makes sense)
- ✅ Outfit descriptors consistent across journey
- ✅ Journey paths match expected visitor flow patterns

---

## Dependencies & Prerequisites

### Software Requirements

**Python Libraries** (new for Phase 4):
```txt
# All Phase 3 dependencies already installed

# Phase 4 additions
networkx>=3.2.0              # Graph algorithms for adjacency
colormath>=3.0.0             # CIEDE2000 color difference
scipy>=1.11.0                # Scientific computing
```

### Data Requirements

**From Phase 3**:
- ✅ Tracklets with outfit descriptors (type, color, LAB, histogram)
- ✅ Visual embeddings (128D vectors)
- ✅ Physique attributes (height category, aspect ratio)
- ✅ Bounding box statistics

**From Phase 1**:
- ✅ Camera adjacency graph (adjacent_to relationships)
- ✅ Camera pin metadata (entrance vs normal)

### Configuration

**Transit Time Configuration** (in camera_pins GeoJSON):
```json
{
  "transit_times": {
    "cam-ATRIUM-01": {"mu_sec": 45, "tau_sec": 25},
    "cam-LOBBY-02": {"mu_sec": 30, "tau_sec": 20}
  }
}
```

---

## Post-Phase Review Questions

After completing Phase 4, evaluate:

1. **Is link precision acceptable for production deployment?**
   - If <85%, review decision thresholds and scoring weights
   - Consider fine-tuning on more labeled data

2. **Is false merge rate low enough?**
   - Target <5%, prefer false splits
   - If too high, increase thresholds

3. **Are journeys visually sensible?**
   - Do paths follow logical visitor flow?
   - Are timing gaps reasonable?

4. **Can we process daily footage overnight?**
   - 8 hours of footage across 10 cameras = 80 hours total
   - At 3x real-time (Phase 3) + re-ID overhead, target <12 hours

5. **Do we need manual journey correction tools?**
   - Allow operators to merge/split journeys manually
   - Or adjust association decisions

---

## Next Steps: Phase 5 Preview

### Phase 5: Advanced Analytics & Reporting (Weeks 10-11)

**Objectives**:
1. Implement heatmap visualization (edge traversal counts)
2. Build entry analysis reports (entry pin statistics)
3. Create first-store analysis (top destinations after entry)
4. Add temporal pattern analysis (peak hours, days)
5. Build operator dashboard with key metrics

**Dependencies from Phase 4**:
- ✅ Complete journeys with paths and timing
- ✅ Associations with confidence scores
- ✅ Journey confidence and status tracking

**Expected Deliverables**:
- Heatmap API endpoint (edge weights for visualization)
- Entry analysis API (visitor counts per entry point)
- First-store API (where do visitors go after entry)
- Journey filtering and aggregation queries
- Dashboard UI with charts and graphs

---

## Appendix

### Sample Association Record

```json
{
  "id": "uuid",
  "mall_id": "uuid",
  "from_tracklet_id": "trk-ENTR-001",
  "to_tracklet_id": "trk-ATRIUM-042",
  "from_pin_id": "cam-ENTR-01",
  "to_pin_id": "cam-ATRIUM-01",
  "decision": "linked",
  "score": 0.83,
  "scores": {
    "outfit_sim": 0.85,
    "time_score": 0.82,
    "adj_score": 1.0,
    "physique": 0.70,
    "final": 0.83
  },
  "components": {
    "type_score": 1.0,
    "color_deltaE": {
      "top": 14.2,
      "bottom": 9.8,
      "shoes": 28.1
    },
    "embed_cosine": 0.79,
    "delta_t_sec": 45,
    "expected_mu_sec": 45,
    "tau_sec": 25,
    "height_match": 1.0,
    "aspect_ratio_diff": 0.03
  },
  "candidate_count": 8,
  "rank": 1,
  "created_at": "2025-11-02T10:05:00Z"
}
```

### Sample Journey Record

```json
{
  "id": "uuid",
  "visitor_id": "v-2025-11-02-000123",
  "mall_id": "uuid",
  "journey_date": "2025-11-02",
  "entry_time": "2025-11-02T10:00:00Z",
  "exit_time": "2025-11-02T10:15:30Z",
  "total_duration_minutes": 15.5,
  "entry_point": "cam-ENTR-01",
  "exit_point": "cam-ENTR-02",
  "confidence": 0.81,
  "path": [
    {
      "pin_id": "cam-ENTR-01",
      "pin_name": "Entrance A",
      "tracklet_id": "trk-ENTR-001",
      "t_in": "2025-11-02T10:00:00Z",
      "t_out": "2025-11-02T10:00:30Z",
      "duration_seconds": 30,
      "link_score": null
    },
    {
      "pin_id": "cam-ATRIUM-01",
      "pin_name": "Central Atrium",
      "tracklet_id": "trk-ATRIUM-042",
      "t_in": "2025-11-02T10:01:15Z",
      "t_out": "2025-11-02T10:03:00Z",
      "duration_seconds": 105,
      "link_score": 0.83
    }
  ],
  "outfit": {
    "top": {"type": "jacket", "color": "blue"},
    "bottom": {"type": "pants", "color": "dark_brown"},
    "shoes": {"type": "sneakers", "color": "white"}
  },
  "num_cameras_visited": 5,
  "total_tracklets": 5,
  "avg_link_score": 0.815,
  "status": "completed"
}
```

### Useful Resources

- [Multi-Object Tracking Survey](https://arxiv.org/abs/2104.13993)
- [Person Re-Identification Survey](https://arxiv.org/abs/1804.09708)
- [CIEDE2000 Color Difference](https://en.wikipedia.org/wiki/Color_difference#CIEDE2000)
- [Graph-Based Re-Identification](https://arxiv.org/abs/1906.04699)

---

## Changelog

### Version 1.3 (2025-11-01)
**Critical Database Integrity Fixes from Codex Follow-Up**

- **Fixed uniqueness constraint bug**: Replaced `UNIQUE (from_tracklet_id, to_tracklet_id)` with `CREATE UNIQUE INDEX idx_associations_one_per_source ON associations(from_tracklet_id)`
  - **Root Cause**: PostgreSQL treats NULL values as distinct in UNIQUE constraints, allowing multiple `(source_id, NULL)` rows for new_visitor/ambiguous decisions
  - **Impact**: Without this fix, a single tracklet could have multiple association records, breaking the "one decision per source" guarantee and corrupting journey construction
  - **Solution**: Unique index on `from_tracklet_id` alone enforces exactly one record per source tracklet
- **[CRITICAL] Added catastrophic false merge prevention**: `CREATE UNIQUE INDEX idx_associations_one_per_target ON associations(to_tracklet_id) WHERE decision = 'linked'`
  - **Root Cause**: Nothing prevented 2+ source tracklets from linking to the same target if conflict resolution had bugs or race conditions
  - **Impact**: **CATASTROPHIC** - Multiple people merged into single journey, destroying analytics accuracy and violating privacy expectations
  - **Solution**: Partial unique index on `to_tracklet_id` for linked decisions ensures at most one source can link to any target
  - **Defense in depth**: This is the last line of defense against conflict resolution failures in application code
- **Added target field consistency constraints**:
  - `CHECK (decision <> 'linked' OR (to_tracklet_id IS NOT NULL AND to_pin_id IS NOT NULL))` - linked decisions must have both target fields populated
  - `CHECK (decision = 'linked' OR (to_tracklet_id IS NULL AND to_pin_id IS NULL))` - non-linked decisions must have both target fields NULL
  - **Impact**: Prevents data corruption where decision type doesn't match target state (e.g., linked decision with NULL target, or new_visitor with populated target)
- **Enhanced design documentation**: Added comprehensive "Database Integrity Guarantees" section with:
  - Detailed explanation of all 4 constraints
  - Example SQL showing prevented failures
  - Rationale for why database-level enforcement is critical (race conditions, deployment issues, etc.)

### Version 1.2 (2025-11-01)
**Critical Fixes from Codex Review**

- **Fixed MultiSignalScorer.score_pair()**: Corrected indentation bug where return statement was nested inside _get_camera_trust(), causing method to return None instead of (score, scores, components) tuple
- **Fixed associations table schema**:
  - Changed `to_tracklet_id` and `to_pin_id` to nullable (allow NULL for 'new_visitor' and 'ambiguous' decisions)
  - Moved inline INDEX clauses to separate CREATE INDEX statements (valid PostgreSQL syntax)
  - Added design note explaining why all decisions are stored (auditability, analytics, tuning)
- **Fixed journeys table schema**: Moved inline INDEX clauses to separate CREATE INDEX statements
- **Fixed naming inconsistency**: Changed all references from "physique_pose" to "physique" for consistency with PhysiqueScorer output
- **Fixed CandidateRetriever imports**: Added missing `from datetime import timedelta` and `import numpy as np`
- **Added Calibration Validation Process**: Documented 4-phase validation pipeline (offline eval → shadow mode → canary → full deployment) with Go/No-Go criteria tied to Phase 4 success metrics

### Version 1.1 (2025-11-01)
**Dynamic Weights Architecture Update**

- **Updated Executive Summary**: Changed weight references from fixed percentages (55%, 20%, 15%, 10%) to base weights (~55%, ~20%, ~15%, ~10%)
- **Added Dynamic Weights Section**: Comprehensive explanation of two-tier configuration system (base parameters + .secret calibration)
- **Added Configuration Architecture**: Detailed documentation of calibration file structure, runtime flow, security, and continuous learning
- **Updated Component Diagram**: Added note about production weights loaded from .secret file
- **Updated Code Examples**:
  - OutfitSimilarityScorer now accepts config parameter for dynamic sub-component weights
  - MultiSignalScorer loads calibration from .secret file with per-mall overrides
  - Added _load_calibration() and _get_camera_trust() methods
  - Added camera trust factor application to outfit similarity
- **Updated Risk Mitigation**: Referenced .secret calibration in contingency plans and mitigations
- **Key Changes**: Emphasized that 55/20/15/10 are initial defaults only; production uses learned, data-driven weights from .secret file that vary per mall, per camera, and per edge

### Version 1.0 (2025-11-01)
- Initial Phase 4 roadmap with multi-signal scoring, candidate retrieval, association decisions, and journey construction

---

**Document Version**: 1.3
**Created**: 2025-11-01
**Last Updated**: 2025-11-01
**Status**: 🚧 **PLANNED** (Not Started)
**Related Documents**:
- [Phase_3_Roadmap.md](Phase_3_Roadmap.md) - Person detection and tracking
- [Phase_2_Summary.md](../summaries/Phase_2_Summary.md) - Video management infrastructure
- [CLAUDE.md](../../CLAUDE.md) - Multi-signal re-identification specification (v3.1 with dynamic weights)
- [.secret](../../.secret) - Calibration file schema (trade secret, not in repository)

---

**End of Phase 4 Roadmap**
