# Code Review Fixes for Phase 2.3 - Upload Service

## Overview
This document summarizes the fixes applied to address the HIGH and MEDIUM priority issues identified in the Phase 2.3 code review for the upload service layer.

---

## HIGH Priority Issues Fixed

### 1. NOT NULL Constraint Violation on Video Creation

**Issue Location:** [upload_service.py:130](../backend/app/services/upload_service.py#L130)

**Problem:**
The service explicitly set `uploaded_at=None` when creating the video record, but the `videos.uploaded_at` column is declared as `nullable=False` with a database default of `datetime.utcnow`. By passing `None` explicitly, SQLAlchemy overrides the database default, causing the INSERT statement to violate the NOT NULL constraint.

**Impact:**
- Every call to `initiate_upload()` fails with database error
- No upload sessions can be created
- Complete upload flow is blocked

**Example Error:**
```python
sqlalchemy.exc.IntegrityError: (psycopg2.errors.NotNullViolation)
null value in column "uploaded_at" of relation "videos" violates not-null constraint
DETAIL:  Failing row contains (..., uploaded_at=null, ...)
```

**Root Cause:**
Misunderstanding of SQLAlchemy defaults. When a column has `nullable=False` and `default=datetime.utcnow`, you must either:
1. Omit the field entirely (let DB default populate), or
2. Provide a valid non-None value

Passing `None` explicitly tells SQLAlchemy "I want to set this to NULL", which overrides the default.

**Fix Applied:**
Remove the explicit `uploaded_at=None` assignment and let the database default populate the field:

```python
# Before (INCORRECT):
video = Video(
    # ... other fields ...
    uploaded_at=None,  # L Overrides default, causes NOT NULL violation
    processing_status="pending",
)

# After (CORRECT):
video = Video(
    # ... other fields ...
    # uploaded_at: let DB default populate (datetime.utcnow)
    processing_status="pending",
)
```

**Behavior Change:**
- **Before:** `uploaded_at` set to NULL � database rejects INSERT
- **After:** `uploaded_at` populated by DB default (current timestamp) � INSERT succeeds
- **Semantic:** The "uploaded at" timestamp now represents when the upload *session* was created, not when it completed. The `upload_status` field distinguishes "uploading" from "uploaded".

**Alternative Considered:**
We could have set `uploaded_at=datetime.utcnow()`, but allowing the DB default is cleaner and consistent with other timestamp columns that use defaults.

**Files Modified:**
- [backend/app/services/upload_service.py](../backend/app/services/upload_service.py)
  - Line 130: Removed `uploaded_at=None`

---

### 2. Missing upload_id Parameter in generate_presigned_upload_url Call

**Issue Location:** [upload_service.py:200-205](../backend/app/services/upload_service.py#L200-L205)

**Problem:**
The `generate_part_url()` method called `storage.generate_presigned_upload_url()` using the old signature without the `upload_id` parameter. In Phase 2.2, we updated the storage service to require `upload_id` for session namespace isolation, but this caller wasn't updated.

**Impact:**
- Runtime crash with `TypeError: generate_presigned_upload_url() missing 1 required positional argument: 'upload_id'`
- All part URL generation requests fail
- Frontend cannot upload video parts
- Complete upload flow is blocked

**Root Cause:**
API signature change in Phase 2.2 wasn't propagated to this new service layer added in Phase 2.3. The upload service was written before the storage service signature change was finalized.

**Fix Applied:**
Pass `str(upload_id)` to the storage service method:

```python
# Before (INCORRECT):
presigned_url = self.storage.generate_presigned_upload_url(
    video.original_path,
    part_number=part_number,  # L Missing upload_id parameter
    expires=expires,
)

# After (CORRECT):
presigned_url = self.storage.generate_presigned_upload_url(
    video.original_path,
    upload_id=str(upload_id),  #  Added required parameter
    part_number=part_number,
    expires=expires,
)
```

**Why `str(upload_id)`:**
- The `upload_id` parameter in `generate_part_url()` is a `UUID` object
- The storage service expects `upload_id: str` (matches S3 upload session ID format)
- We convert UUID � string for consistency

**Files Modified:**
- [backend/app/services/upload_service.py](../backend/app/services/upload_service.py)
  - Line 203: Added `upload_id=str(upload_id)` parameter

---

## MEDIUM Priority Issues Fixed

### 3. Video Metadata Column Name Mismatches

**Issue Location:** [upload_service.py:126-129](../backend/app/services/upload_service.py#L126-L129)

**Problem:**
The service assigned video metadata to parameters with prefixed names (`video_width`, `video_height`, `video_fps`, `video_duration_seconds`), but the actual ORM column names are unprefixed (`width`, `height`, `fps`, `duration_seconds`). SQLAlchemy silently ignores unknown keyword arguments, so this metadata was never persisted to the database.

**Impact:**
- Video resolution (width/height) not stored � proxy generation uses defaults
- Frame rate not stored � CV pipeline can't optimize sampling
- Duration not stored � reports show incorrect video lengths
- Silent data loss: no error, but metadata vanishes

**Example:**
```python
# Client sends video metadata in upload request:
{
  "filename": "mall-recording.mp4",
  "video_width": 1920,
  "video_height": 1080,
  "video_fps": 30.0,
  "video_duration_seconds": 3600
}

# Before fix: Database record after INSERT:
SELECT width, height, fps, duration_seconds FROM videos WHERE id = ...;
 width | height | fps | duration_seconds
-------+--------+-----+------------------
  NULL |   NULL | NULL |             NULL  -- L All metadata lost!

# After fix:
 width | height |  fps | duration_seconds
-------+--------+------+------------------
  1920 |   1080 | 30.00|             3600  --  Metadata persisted!
```

**Root Cause:**
Parameter naming inconsistency between service method signature and ORM model. The method parameters used `video_*` prefix for clarity, but forgot to map to actual column names when constructing the model instance.

**Fix Applied:**
Use correct column names when creating the Video instance:

```python
# Before (INCORRECT):
video = Video(
    # ... other fields ...
    video_width=video_width,          # L No such column
    video_height=video_height,        # L No such column
    video_fps=video_fps,              # L No such column
    video_duration_seconds=video_duration_seconds,  # L No such column
)

# After (CORRECT):
video = Video(
    # ... other fields ...
    width=video_width,                #  Maps to videos.width
    height=video_height,              #  Maps to videos.height
    fps=video_fps,                    #  Maps to videos.fps
    duration_seconds=video_duration_seconds,  #  Maps to videos.duration_seconds
)
```

**Why This Matters:**
- **Proxy Generation:** FFmpeg needs target resolution to scale videos properly
- **CV Pipeline:** Frame sampling rate depends on knowing original FPS
- **Reports:** Duration used for analytics (hours of footage uploaded, etc.)
- **Debugging:** Operators need video specs when troubleshooting issues

**Files Modified:**
- [backend/app/services/upload_service.py](../backend/app/services/upload_service.py)
  - Lines 126-129: Corrected column names (removed `video_` prefix)

---

### 4. Assignment to Non-Existent s3_etag and s3_version_id Columns

**Issue Location:** [upload_service.py:279-280](../backend/app/services/upload_service.py#L279-L280)

**Problem:**
The `complete_upload()` method attempted to assign S3 result metadata to `video.s3_etag` and `video.s3_version_id`, but these columns don't exist in the `Video` model. SQLAlchemy silently accepts the assignment (creates instance attributes), but on `commit()`, these values are discarded since they don't map to database columns.

**Impact:**
- Minor: S3 metadata not persisted (low priority for MVP)
- No functional breakage: the attributes vanish on commit, but operation succeeds
- Confusing for developers: looks like data is saved, but it isn't
- Future issue: if code later reads `video.s3_etag`, it will be `None`

**Why These Columns Don't Exist:**
Looking at the Video model schema:
```python
# Existing columns for file metadata:
checksum_sha256 = Column(String(64), nullable=True, index=True)
original_path = Column(String(512), nullable=True)
# ... but no s3_etag or s3_version_id columns
```

The schema intentionally omits S3-specific metadata because:
1. ETags are already exposed via the checksum field (often the same value)
2. Version IDs only matter if S3 versioning is enabled (it's not in MVP)
3. This metadata is transient/recoverable via S3 API if needed

**Fix Applied:**
Remove the non-existent column assignments and add explanatory comment:

```python
# Before (INCORRECT):
video.upload_status = "uploaded"
video.uploaded_at = datetime.utcnow()
video.s3_etag = result.get("etag")              # L Column doesn't exist
video.s3_version_id = result.get("version_id")  # L Column doesn't exist

# After (CORRECT):
video.upload_status = "uploaded"
video.uploaded_at = datetime.utcnow()
# Note: s3_etag and s3_version_id columns don't exist in Video model
# etag is returned in completion result for API response
```

**Alternative Solutions Considered:**

**Option A:** Add the columns to the Video model
```python
# In models/camera.py
s3_etag = Column(String(64), nullable=True)
s3_version_id = Column(String(100), nullable=True)
```
**Rejected:** Not needed for MVP. Adds migration overhead for minimal benefit.

**Option B:** Store in JSONB metadata column
```python
video.s3_metadata = {"etag": result["etag"], "version_id": result["version_id"]}
```
**Rejected:** Over-engineering. If we need this later, easy to add.

**Option C:** Remove assignments (chosen)
- Simplest solution
- ETags still available in API response for client validation
- Can add columns in Phase 3 if use case emerges

**Files Modified:**
- [backend/app/services/upload_service.py](../backend/app/services/upload_service.py)
  - Lines 279-281: Removed non-existent column assignments, added comment

---

## Summary of All Fixes

| Issue | Priority | Status | Files Modified | Impact |
|-------|----------|--------|----------------|---------|
| NOT NULL violation on uploaded_at | HIGH |  Fixed | upload_service.py:130 | Upload sessions now create successfully |
| Missing upload_id parameter | HIGH |  Fixed | upload_service.py:203 | Part URL generation now works |
| Column name mismatches | MEDIUM |  Fixed | upload_service.py:126-129 | Video metadata now persists |
| Non-existent column assignments | MEDIUM |  Fixed | upload_service.py:279-281 | Code clarity improved |

**Issues Resolved:** 4/4 (2 HIGH, 2 MEDIUM)

---

## Verification Steps

### 1. Test Upload Session Creation

```python
# Test that initiate_upload no longer fails with NOT NULL constraint
from app.services.upload_service import UploadService
from app.core.database import SessionLocal

db = SessionLocal()
upload_service = UploadService(db)

try:
    upload_id, video_id, expires_at = upload_service.initiate_upload(
        mall_id=UUID("..."),
        pin_id=UUID("..."),
        filename="test-video.mp4",
        file_size_bytes=1024000,
        video_width=1920,
        video_height=1080,
        video_fps=30.0,
        video_duration_seconds=3600,
    )
    print(f" Upload session created: video_id={video_id}, upload_id={upload_id}")

    # Verify metadata persisted
    video = db.query(Video).filter(Video.id == video_id).first()
    assert video.width == 1920, "Width should be 1920"
    assert video.height == 1080, "Height should be 1080"
    assert video.fps == 30.0, "FPS should be 30.0"
    assert video.duration_seconds == 3600, "Duration should be 3600"
    assert video.uploaded_at is not None, "uploaded_at should have DB default"
    print(" All metadata persisted correctly")

except Exception as e:
    print(f"L Failed: {e}")
finally:
    db.close()
```

### 2. Test Part URL Generation

```python
# Test that generate_part_url includes upload_id parameter
try:
    presigned_url, url_expires_at = upload_service.generate_part_url(
        upload_id=upload_id,
        video_id=video_id,
        part_number=1,
    )
    print(f" Part URL generated: {presigned_url}")

    # Verify URL contains namespaced part object
    # Format: videos/.../video.mp4.{upload_id}.part1
    assert str(upload_id) in presigned_url, "URL should contain upload_id"
    print(" Part URL correctly namespaced")

except TypeError as e:
    print(f"L Missing parameter: {e}")
except Exception as e:
    print(f"L Failed: {e}")
```

### 3. Test Upload Completion

```python
# Test that complete_upload doesn't try to set non-existent columns
try:
    result = upload_service.complete_upload(
        upload_id=upload_id,
        video_id=video_id,
        parts=[
            {"part_number": 1, "etag": "abc123"},
        ],
        final_checksum_sha256="def456",
    )
    print(f" Upload completed: {result}")

    # Verify video status updated
    video = db.query(Video).filter(Video.id == video_id).first()
    assert video.upload_status == "uploaded", "Status should be 'uploaded'"
    assert video.checksum_sha256 == "def456", "Checksum should be updated"

    # Verify no AttributeError when accessing non-existent columns
    # (They shouldn't exist on the model at all)
    assert not hasattr(video, 's3_etag'), "s3_etag should not exist"
    assert not hasattr(video, 's3_version_id'), "s3_version_id should not exist"
    print(" No phantom attributes created")

except Exception as e:
    print(f"L Failed: {e}")
```

### 4. Integration Test

```bash
# Run upload service integration tests
cd backend
pytest app/tests/test_upload_service.py -v

# Expected results:
# test_initiate_upload .......................... PASSED
# test_generate_part_url ........................ PASSED
# test_complete_upload .......................... PASSED
# test_abort_upload ............................. PASSED
# test_duplicate_detection ...................... PASSED
```

---

## API Impact Analysis

### Endpoints Affected
These fixes unblock the following API endpoints (implemented in Phase 2.3):

**1. POST /api/malls/{mall_id}/pins/{pin_id}/uploads/initiate**
- **Before:** Failed with database constraint error
- **After:** Successfully creates upload session
- **Response includes:** `upload_id`, `video_id`, `expires_at`

**2. GET /api/uploads/{upload_id}/parts/{part_number}/url**
- **Before:** Crashed with `TypeError`
- **After:** Returns presigned URL with proper namespace
- **Response includes:** `presigned_url`, `expires_at`

**3. POST /api/uploads/{upload_id}/complete**
- **Before:** Metadata not persisted, phantom columns assigned
- **After:** All metadata saved correctly, clean completion
- **Response includes:** `video_id`, `etag`, `checksum_sha256`

### Breaking Changes
None - these are bug fixes to make the service work as originally intended.

---

## Database Schema Notes

### Video Table Structure (After Phase 2.1 Migration)
```sql
-- Actual columns (Phase 2.1 schema):
CREATE TABLE videos (
    id UUID PRIMARY KEY,
    mall_id UUID NOT NULL,
    pin_id UUID NOT NULL,

    -- File metadata
    filename VARCHAR(255) NOT NULL,
    original_path VARCHAR(512),
    file_size_bytes BIGINT NOT NULL,
    checksum_sha256 VARCHAR(64),

    -- Video properties (THESE are the correct names!)
    width INTEGER,              -- NOT video_width
    height INTEGER,             -- NOT video_height
    fps NUMERIC(5,2),          -- NOT video_fps
    duration_seconds INTEGER,   -- NOT video_duration_seconds
    codec VARCHAR(50),

    -- Upload tracking
    upload_status VARCHAR(20) NOT NULL DEFAULT 'uploading',
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- Has DB default!
    uploaded_by_user_id UUID,

    -- Processing tracking
    processing_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    processing_job_id VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Legacy fields (backward compatibility)
    camera_pin_id UUID NOT NULL,
    file_path VARCHAR(500),
    original_filename VARCHAR(255),
    processed BOOLEAN DEFAULT FALSE,
    upload_timestamp TIMESTAMPTZ
);
```

### Columns That DON'T Exist
```sql
-- These columns were attempted but don't exist:
-- s3_etag VARCHAR(64)           L Not in schema
-- s3_version_id VARCHAR(100)    L Not in schema
```

If these are needed in the future, add them via a new migration:
```python
# Future migration (Phase 3.x if needed)
op.add_column('videos', sa.Column('s3_etag', sa.String(64), nullable=True))
op.add_column('videos', sa.Column('s3_version_id', sa.String(100), nullable=True))
```

---

## Lessons Learned

### 1. Avoid Explicit None for Columns with Defaults
**Bad Pattern:**
```python
column_with_default=None  # Overrides default!
```

**Good Pattern:**
```python
# Option A: Omit entirely
Video(other_fields=...)

# Option B: Use valid value
Video(column_with_default=datetime.utcnow())
```

### 2. Match Parameter Names to Column Names
When wrapping ORM models in service layers:
```python
def service_method(video_width: int):  # � Service layer naming
    video = Video(
        width=video_width  # � Map to actual column name
    )
```

### 3. Keep Caller Updates in Sync with API Changes
When changing a method signature:
1. Update the method implementation 
2. Update all callers 
3. Update tests 
4. Update documentation 

### 4. SQLAlchemy Silent Failures
SQLAlchemy doesn't error on unknown kwargs:
```python
Video(fake_column="value")  # No error, just ignored!
```

Always verify column names in the model definition.

---

**Reviewer:** Codex
**Fixed By:** Claude (Assistant)
**Date:** 2025-10-31
**Status:**  All Issues Resolved - Ready for Testing

---END---
