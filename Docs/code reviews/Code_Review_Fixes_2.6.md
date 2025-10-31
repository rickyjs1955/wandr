# Phase 2.6 Code Review Fixes

## Issues Addressed

### HIGH Priority Issue 1: Incorrect Method Name `generate_presigned_url`
**Location**: `backend/app/services/video_service.py:155`, `:196`

**Problem**: Code called `self.storage.generate_presigned_url()`, but `StorageService` only implements `generate_presigned_get_url()` and `generate_presigned_upload_url()`. This caused `AttributeError` when attempting to generate streaming URLs.

**Fix**: Updated both calls to use the correct method name `generate_presigned_get_url()`:

```python
# Before (line 155, 196):
presigned_url = self.storage.generate_presigned_url(
    file_path,
    expires=expires_delta,
)

# After:
presigned_url = self.storage.generate_presigned_get_url(
    file_path,
    expires=expires_delta,
)
```

**Files Modified**:
- `backend/app/services/video_service.py` (lines 155, 196)

---

### HIGH Priority Issue 2: Non-existent `thumbnail_path` Column Access
**Location**: `backend/app/services/video_service.py:191`, `backend/app/api/v1/videos.py:455`, `:526`

**Problem**: Code accessed `video.thumbnail_path`, but the `Video` ORM model has no such column. This caused `AttributeError` on video list and detail API endpoints even when videos exist. The thumbnail path is stored in the `ProcessingJob.result_data` JSONB column, not as a dedicated video column.

**Fix**:

1. **Updated `video_service.py:generate_thumbnail_url()`** to query the processing job's `result_data`:

```python
# Before (line 191):
if not video.thumbnail_path:
    raise ValueError("Thumbnail not available (still processing or failed)")

# After (lines 191-206):
# Thumbnail path is deterministic: thumbnails/{mall_id}/{video_id}.jpg
# Check processing job result_data for confirmation
thumbnail_job = (
    self.db.query(ProcessingJob)
    .filter(ProcessingJob.video_id == video_id)
    .filter(ProcessingJob.job_type == "proxy_generation")
    .filter(ProcessingJob.status == "completed")
    .first()
)

if not thumbnail_job or not thumbnail_job.result_data:
    raise ValueError("Thumbnail not available (still processing or failed)")

thumbnail_path = thumbnail_job.result_data.get("thumbnail_path")
if not thumbnail_path:
    raise ValueError("Thumbnail not available (still processing or failed)")
```

2. **Added helper function** in `videos.py` to retrieve thumbnail path from job:

```python
def get_thumbnail_path_from_job(db: Session, video_id: UUID) -> Optional[str]:
    """
    Get thumbnail path from processing job result_data.

    Args:
        db: Database session
        video_id: Video UUID

    Returns:
        Thumbnail path or None if not available
    """
    job = (
        db.query(ProcessingJob)
        .filter(ProcessingJob.video_id == video_id)
        .filter(ProcessingJob.job_type == "proxy_generation")
        .filter(ProcessingJob.status == "completed")
        .first()
    )

    if job and job.result_data:
        return job.result_data.get("thumbnail_path")
    return None
```

3. **Updated video list endpoint** (line 455) to use helper function:

```python
# Before:
has_thumbnail=video.thumbnail_path is not None,

# After:
thumbnail_path = get_thumbnail_path_from_job(db, video.id)
# ... then in VideoListItem constructor:
has_thumbnail=thumbnail_path is not None,
```

4. **Updated video detail endpoint** (line 526) to use helper function:

```python
# Before:
thumbnail_path=video.thumbnail_path,

# After:
thumbnail_path = get_thumbnail_path_from_job(db, video.id)
# ... then in VideoDetailResponse constructor:
thumbnail_path=thumbnail_path,
```

**Files Modified**:
- `backend/app/services/video_service.py` (lines 191-206, 218)
- `backend/app/api/v1/videos.py` (added helper function lines 58-79, updated lines 474-487, 547-561)

---

### HIGH Priority Issue 3: Non-existent `get_file_size()` Method
**Location**: `backend/app/api/v1/videos.py:543`, `:641`

**Problem**: Code called `storage.get_file_size()`, but `StorageService` only provides `get_file_metadata()` which returns a dict with a `size` key. This caused `AttributeError` when retrieving proxy file sizes for video detail and streaming endpoints.

**Fix**: Updated both calls to use `get_file_metadata()` and extract the `size` field:

```python
# Before (line 543):
proxy_size_bytes = storage.get_file_size(video.proxy_path)

# After:
metadata = storage.get_file_metadata(video.proxy_path)
proxy_size_bytes = metadata.get("size")

# Before (line 641):
file_size_bytes = storage.get_file_size(video.proxy_path)

# After:
metadata = storage.get_file_metadata(video.proxy_path)
file_size_bytes = metadata.get("size")
```

**Files Modified**:
- `backend/app/api/v1/videos.py` (lines 543-544, 641-642)

---

## Summary

All three HIGH priority issues in Phase 2.6 have been resolved:

1.  Fixed incorrect method name `generate_presigned_url` � `generate_presigned_get_url` in video streaming service
2.  Fixed non-existent `thumbnail_path` column access by querying `ProcessingJob.result_data` JSONB field instead
3.  Fixed non-existent `get_file_size()` method calls by using `get_file_metadata()["size"]` instead

**Key Architectural Pattern**: Thumbnail paths (and other processing outputs) are stored in `ProcessingJob.result_data` JSONB column rather than as dedicated video columns. This provides flexibility for storing variable processing outputs without schema changes.

**Files Modified**: 3
- `backend/app/services/video_service.py`
- `backend/app/api/v1/videos.py` (added helper function, fixed 4 locations)

**Testing Recommendation**: Test video list, detail, streaming, and thumbnail endpoints to verify:
- No `AttributeError` on method calls
- Thumbnail availability correctly reflects processing job status
- Proxy file sizes are retrieved successfully

---SEPARATOR---

## Re-Review Issues Addressed

### HIGH Priority Re-Review Issue 1: Missing `ProcessingJob` Import
**Location**: `backend/app/services/video_service.py`

**Problem**: The `generate_thumbnail_url()` method references `ProcessingJob` without importing it. When the method runs, it raises `NameError: name 'ProcessingJob' is not defined`, causing the thumbnail endpoint and any callers to crash.

**Fix**: Added `ProcessingJob` to the imports from `app.models`:

```python
# Before (line 18):
from app.models import Video, CameraPin, Mall

# After:
from app.models import Video, CameraPin, Mall, ProcessingJob
```

**Files Modified**:
- `backend/app/services/video_service.py` (line 18)

---

### HIGH Priority Re-Review Issue 2: `video.thumbnail_path` Usage in `delete_video` Method
**Location**: `backend/app/services/video_service.py:255-256`

**Problem**: The `delete_video()` method still accessed `video.thumbnail_path` (line 255), even though that column doesn't exist. Deleting a video (or any code path that touches that branch) raises `AttributeError`, breaking video cleanup functionality.

**Fix**: Updated the deletion logic to derive thumbnail path from `ProcessingJob.result_data` instead of accessing the non-existent column:

```python
# Before (lines 255-256):
if video.thumbnail_path:
    files_to_delete.append(video.thumbnail_path)

# After (lines 255-266):
# Get thumbnail path from processing job result_data
thumbnail_job = (
    self.db.query(ProcessingJob)
    .filter(ProcessingJob.video_id == video_id)
    .filter(ProcessingJob.job_type == "proxy_generation")
    .filter(ProcessingJob.status == "completed")
    .first()
)
if thumbnail_job and thumbnail_job.result_data:
    thumbnail_path = thumbnail_job.result_data.get("thumbnail_path")
    if thumbnail_path:
        files_to_delete.append(thumbnail_path)
```

**Files Modified**:
- `backend/app/services/video_service.py` (lines 255-266)

---

## Re-Review Summary

Both HIGH priority re-review issues have been resolved:

1. ✅ Added missing `ProcessingJob` import to prevent `NameError` in thumbnail generation
2. ✅ Fixed `video.thumbnail_path` access in `delete_video()` method to query `ProcessingJob.result_data` instead

**Key Pattern Applied**: Consistently derive thumbnail paths from `ProcessingJob.result_data` across all methods in the service layer, maintaining architectural consistency established in the first round of fixes.

**Files Modified**: 1
- `backend/app/services/video_service.py` (import line 18, delete method lines 255-266)

**Testing Recommendation**:
- Test thumbnail URL generation to verify no `NameError` occurs
- Test video deletion to ensure thumbnails are properly cleaned up without `AttributeError`
- Verify all three file types (original, proxy, thumbnail) are deleted from storage when a video is removed

---END---
