# Phase 2.5: FFmpeg Proxy Generation Pipeline - Completion Summary

**Date**: 2025-10-31
**Status**: ✅ COMPLETED (Code Implementation)
**Action Required**: Install FFmpeg system dependency

---

## Overview

Phase 2.5 implements the complete FFmpeg-based video processing pipeline for proxy generation, metadata extraction, and thumbnail creation. This phase replaces all placeholder implementations from Phase 2.4 with fully functional video processing tasks.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Upload Completion (Phase 2.3)              │
│  - Video uploaded to S3                                       │
│  - Queue proxy generation job                                 │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Celery Task Queued
                 ▼
┌──────────────────────────────────────────────────────────────┐
│              generate_proxy_video Task (Celery Worker)        │
│                                                               │
│  1. Download original video from S3 to temp directory        │
│  2. Validate video file with FFprobe                          │
│  3. Extract metadata (width, height, fps, duration, codec)    │
│  4. Generate proxy video (480p @ 10fps, H.264, CRF 28)       │
│  5. Generate thumbnail (320px wide, at 5s or midpoint)        │
│  6. Upload proxy video to S3 (proxy/ folder)                  │
│  7. Upload thumbnail to S3 (thumbnails/{mall_id}/)            │
│  8. Update Video record with metadata and paths               │
│  9. Update ProcessingJob with completion status               │
│ 10. Clean up temp files                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## Implemented Components

### 1. FFmpeg Service (`app/services/ffmpeg_service.py`)

**Purpose**: Wrapper service for FFmpeg operations with comprehensive error handling.

**Lines of Code**: 323 lines

#### Methods

**`extract_metadata(input_path: str) -> Dict[str, Any]`**
- Uses FFprobe to extract video metadata
- Returns:
  - `width`, `height` (int)
  - `fps` (float) - Handles variable frame rate (r_frame_rate)
  - `duration_seconds` (float)
  - `codec` (str) - Video codec name
  - `bitrate` (int) - Bitrate in bps
  - `file_size_bytes` (int)
- Validates video has at least one video stream
- Raises: `FFmpegError`, `FileNotFoundError`, `ValueError`

**`generate_proxy(input_path, output_path, ...) -> Dict[str, Any]`**
- Generates low-res proxy video for streaming
- **Parameters**:
  - `target_height`: Default 480 (maintains aspect ratio)
  - `target_fps`: Default 10
  - `preset`: FFmpeg preset (ultrafast, fast, medium, slow) - default: medium
  - `crf`: Quality 18-28 (lower=better) - default: 28
- **FFmpeg pipeline**:
  ```
  Input → Scale (maintain aspect, height=480)
        → FPS (10fps)
        → H.264 encode (libx264, CRF 28, faststart)
        → AAC audio (64k)
        → Output MP4
  ```
- **Output settings**:
  - Codec: H.264 (libx264)
  - Audio: AAC @ 64kbps
  - Pixel format: yuv420p (compatibility)
  - `movflags=faststart`: Enable streaming (moov atom at start)
- Returns metadata of generated proxy
- Cleans up partial output on error

**`generate_thumbnail(input_path, output_path, ...) -> Dict[str, Any]`**
- Extracts single frame as thumbnail image
- **Parameters**:
  - `timestamp_seconds`: Default 5.0
  - `width`: Default 320 (height auto-scaled)
- **FFmpeg pipeline**:
  ```
  Input (seek to timestamp) → Scale (width=320) → Extract 1 frame → JPEG (quality 2)
  ```
- Returns: `width`, `height`, `file_size_bytes`, `timestamp_seconds`
- Output format: JPEG with qscale=2 (high quality)

**`validate_video(input_path: str) -> Tuple[bool, Optional[str]]`**
- Validates file is a valid video
- Checks:
  - File exists
  - Contains at least one video stream
  - Has valid duration > 0
- Returns: `(is_valid: bool, error_message: Optional[str])`

**Singleton Pattern**:
```python
_ffmpeg_service: Optional[FFmpegService] = None

def get_ffmpeg_service() -> FFmpegService:
    global _ffmpeg_service
    if _ffmpeg_service is None:
        _ffmpeg_service = FFmpegService()
    return _ffmpeg_service
```

**Error Handling**:
- Verifies FFmpeg is installed on initialization
- Raises `RuntimeError` with installation instructions if FFmpeg missing
- Captures and logs stderr output from FFmpeg on errors
- Cleans up partial files on failure

---

### 2. Updated Video Tasks (`app/tasks/video_tasks.py`)

**Changes**: Replaced all placeholder implementations with actual FFmpeg processing.

#### `generate_proxy_video(video_id, job_id)`

**Complete workflow** (80 lines of implementation):

1. **Fetch records**: Get Video and ProcessingJob from database
2. **Update job status**: Set to 'running', store celery_task_id, timestamp
3. **Download original**: S3 → temp directory
4. **Validate**: Ensure video file is valid
5. **Extract metadata**: FFprobe → update Video record (width, height, fps, duration, codec)
6. **Generate proxy**: FFmpeg → 480p @ 10fps, H.264
7. **Generate thumbnail**: FFmpeg → 320px JPEG at 5s (or midpoint if shorter)
8. **Upload proxy**: temp → S3 (proxy/ folder)
9. **Upload thumbnail**: temp → S3 (thumbnails/{mall_id}/{video_id}.jpg)
10. **Update Video**: Set proxy_path, thumbnail_path, processing_status='completed'
11. **Update Job**: Set status='completed', store result_data with all metadata
12. **Cleanup**: Temp files automatically deleted (using `tempfile.TemporaryDirectory`)

**Result Data Structure**:
```json
{
  "status": "success",
  "proxy_path": "videos/{mall_id}/proxy/{video_id}.mp4",
  "thumbnail_path": "thumbnails/{mall_id}/{video_id}.jpg",
  "metadata": {
    "original": {
      "width": 1920,
      "height": 1080,
      "fps": 30.0,
      "duration_seconds": 120.5,
      "codec": "h264",
      "bitrate": 5000000,
      "file_size_bytes": 75625000
    },
    "proxy": {
      "width": 854,
      "height": 480,
      "fps": 10.0,
      "duration_seconds": 120.5,
      "codec": "h264",
      "file_size_bytes": 8500000
    },
    "thumbnail": {
      "width": 320,
      "height": 180,
      "file_size_bytes": 24567,
      "timestamp_seconds": 5.0
    }
  }
}
```

**Error Handling**:
- Updates video.processing_status = 'failed' on error
- Stores error in video.processing_error
- Updates job.status = 'failed', job.error_message
- Retries transient errors (max 3 attempts, 5-minute delay)
- Temp files automatically cleaned up even on error

#### `extract_video_metadata(video_id)`

**Standalone metadata extraction task** (45 lines):
- Download video from S3
- Extract metadata with FFprobe
- Update Video record
- Return metadata dict
- Max retries: 2

**Use case**: Can be called independently to refresh metadata without regenerating proxy.

#### `generate_thumbnail(video_id, timestamp_seconds=5.0)`

**Standalone thumbnail generation task** (50 lines):
- Download video from S3
- Generate thumbnail at specified timestamp
- Upload to S3
- Update Video.thumbnail_path
- Return thumbnail metadata
- Max retries: 2

**Use case**: Generate thumbnail at different timestamp, or regenerate if needed.

---

## Dependencies

### Python Package
```
ffmpeg-python==0.2.0
```

Added to `requirements.txt` under "# Video Processing" section.

**Installation**:
```bash
cd backend
./venv/bin/pip install ffmpeg-python==0.2.0
```

### System Dependency: FFmpeg

**CRITICAL**: FFmpeg must be installed on the system before running video processing tasks.

#### macOS Installation
```bash
brew install ffmpeg
```

#### Linux (Ubuntu/Debian) Installation
```bash
sudo apt-get update
sudo apt-get install -y ffmpeg
```

#### Linux (RHEL/CentOS) Installation
```bash
sudo yum install -y epel-release
sudo yum install -y ffmpeg
```

#### Docker Installation
Add to `Dockerfile` (if using Docker for workers):
```dockerfile
# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
```

#### Verification
```bash
ffmpeg -version
# Should output: ffmpeg version 4.x or later
```

**What FFmpeg provides**:
- `ffmpeg`: Video transcoding and processing
- `ffprobe`: Metadata extraction
- Codecs: H.264 (libx264), AAC, and many others

---

## Integration with Existing Phases

### Phase 2.3 Integration (Multipart Upload)

**Upload completion endpoint** (`POST /upload/{upload_id}/complete`):
```python
# After completing upload
processing_job = job_service.queue_proxy_generation(
    video_id=video_id,
    priority=5,
)

return MultipartUploadCompleteResponse(
    video_id=video.id,
    processing_job_id=processing_job.id,  # Client can poll this
    ...
)
```

### Phase 2.4 Integration (Celery Job Queue)

**Job queueing** (`job_service.queue_proxy_generation`):
```python
# Create job record
job = ProcessingJob(
    video_id=video_id,
    job_type="proxy_generation",
    status="pending",
)

# Queue Celery task
task = generate_proxy_video.apply_async(
    args=(str(video_id), str(job.id)),
    queue="video_processing",
    priority=priority,
)

job.celery_task_id = task.id
```

**Job monitoring** (`GET /jobs/{job_id}/status`):
- Returns real-time status: pending → running → completed/failed
- Includes result_data with proxy/thumbnail paths and metadata
- Calculates duration between started_at and completed_at

---

## File Structure

### New Files
- ✅ `backend/app/services/ffmpeg_service.py` (323 lines)
- ✅ `backend/docs/phase_2.5_ffmpeg_proxy_generation_summary.md` (this file)

### Modified Files
- ✅ `backend/requirements.txt` (+2 lines: ffmpeg-python)
- ✅ `backend/app/services/__init__.py` (exported FFmpegService)
- ✅ `backend/app/tasks/video_tasks.py` (replaced placeholders with full implementation)
  - `generate_proxy_video`: 120 lines (was 30 lines placeholder)
  - `extract_video_metadata`: 45 lines (was 15 lines placeholder)
  - `generate_thumbnail`: 50 lines (was 15 lines placeholder)

---

## Testing the Pipeline

### Manual Test

1. **Start required services**:
```bash
# Terminal 1: Start Redis (if not already running)
docker-compose up -d redis

# Terminal 2: Start Celery worker
cd backend
./scripts/start_celery_worker.sh video_processing 1

# Terminal 3: Start Flower (optional monitoring)
cd backend
./scripts/start_flower.sh
# Open http://localhost:5555
```

2. **Upload a video** (using multipart upload API):
```bash
# Step 1: Initiate upload
curl -X POST http://localhost:8000/api/v1/videos/upload/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "mall_id": "your-mall-id",
    "pin_id": "your-pin-id",
    "filename": "test_video.mp4",
    "file_size_bytes": 10485760,
    "checksum_sha256": "abc123..."
  }'

# Returns: {"upload_id": "...", "video_id": "...", "expires_at": "..."}

# Step 2: Upload parts (using presigned URLs)
# ... (see Phase 2.3 docs)

# Step 3: Complete upload
curl -X POST http://localhost:8000/api/v1/videos/upload/{upload_id}/complete \
  -H "Content-Type: application/json" \
  -d '{
    "parts": [
      {"part_number": 1, "etag": "..."},
      {"part_number": 2, "etag": "..."}
    ],
    "final_checksum_sha256": "abc123..."
  }'

# Returns: {"processing_job_id": "..."}
```

3. **Monitor job progress**:
```bash
# Check job status
curl http://localhost:8000/api/v1/jobs/{job_id}/status

# Response (running):
{
  "job_id": "...",
  "status": "running",
  "started_at": "2025-10-31T10:00:00Z",
  "duration_seconds": 15
}

# Response (completed):
{
  "job_id": "...",
  "status": "completed",
  "completed_at": "2025-10-31T10:02:30Z",
  "duration_seconds": 150,
  "result_data": {
    "status": "success",
    "proxy_path": "videos/.../proxy/....mp4",
    "thumbnail_path": "thumbnails/.../....jpg",
    "metadata": { ... }
  }
}
```

4. **Verify outputs in S3/MinIO**:
```bash
# List proxy videos
mc ls minio/spatial-intel/videos/{mall_id}/proxy/

# List thumbnails
mc ls minio/spatial-intel/thumbnails/{mall_id}/
```

### Integration Tests (To Be Created)

- Test proxy generation with various video formats (MP4, MOV, AVI)
- Test proxy generation with different resolutions (720p, 1080p, 4K)
- Test thumbnail generation at different timestamps
- Test metadata extraction accuracy
- Test error handling (corrupt video, missing file, invalid format)
- Test retry mechanism on transient failures
- Test temp file cleanup

---

## Performance Considerations

### Processing Time Estimates

**For a 2-minute 1080p video**:
- Download from S3: ~5-10 seconds (depends on network)
- Metadata extraction: <1 second
- Proxy generation (480p @ 10fps): ~20-30 seconds
- Thumbnail generation: <2 seconds
- Upload to S3: ~3-5 seconds (proxy is much smaller)
- **Total**: ~30-50 seconds

### Optimization Strategies

1. **FFmpeg Preset**: Default is "medium"
   - Use "fast" for quicker processing (slightly larger file)
   - Use "slow" for better compression (longer processing)

2. **CRF Value**: Default is 28 (medium quality)
   - Lower CRF = better quality but larger file
   - For proxies, 28 is appropriate (good quality, small size)

3. **Parallel Processing**:
   - Run multiple workers: `./scripts/start_celery_worker.sh video_processing 2`
   - Each worker processes one video at a time (prefetch_multiplier=1)

4. **Resource Limits**:
   - Task time limit: 1 hour (configured in celery_app.py)
   - Worker max tasks per child: 10 (prevents memory leaks)

5. **Future Optimizations**:
   - Hardware acceleration: Use GPU encoding (`-hwaccel cuda`)
   - Conditional proxy: Skip if source is already 480p or lower
   - Progressive upload: Stream proxy to S3 during encoding (for very large files)

---

## Configuration

### Default Settings
```python
# FFmpeg Service Defaults (can be overridden in task calls)
PROXY_TARGET_HEIGHT = 480       # pixels
PROXY_TARGET_FPS = 10           # frames per second
PROXY_PRESET = "medium"         # FFmpeg preset
PROXY_CRF = 28                  # Quality (18-28)
THUMBNAIL_WIDTH = 320           # pixels
THUMBNAIL_TIMESTAMP = 5.0       # seconds (or midpoint if shorter)
THUMBNAIL_QSCALE = 2            # JPEG quality (1-31, lower=better)
```

### Environment Variables

No new environment variables required. Uses existing:
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` (Phase 2.2)
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (Phase 2.4)

---

## Error Scenarios & Handling

### 1. FFmpeg Not Installed
**Error**: `RuntimeError: FFmpeg is not installed`
**When**: FFmpegService initialization
**Fix**: Install FFmpeg system-wide (see Dependencies section)

### 2. Invalid Video File
**Error**: `ValueError: Invalid video file: No video stream found`
**When**: Validation step in generate_proxy_video
**Handling**:
- Job marked as failed
- Video.processing_status = 'failed'
- Error message stored in video.processing_error

### 3. S3 Download Failure
**Error**: `MinioError` from storage service
**When**: Downloading original video
**Handling**:
- Task retries (max 3 attempts)
- 5-minute delay between retries
- Job marked as failed after max retries

### 4. FFmpeg Encoding Failure
**Error**: `ffmpeg.Error` with stderr output
**When**: Proxy generation or thumbnail extraction
**Handling**:
- Partial output file cleaned up
- Error logged with FFmpeg stderr
- Task retries if transient error
- Job marked as failed after max retries

### 5. S3 Upload Failure
**Error**: `MinioError` during upload
**When**: Uploading proxy or thumbnail
**Handling**:
- Task retries
- Job marked as failed if persistent

### 6. Task Timeout
**Error**: Task exceeds 1-hour limit
**When**: Very large video (1+ hour of 4K footage)
**Handling**:
- Celery kills task with SoftTimeLimitExceeded
- Job marked as failed by stuck job watchdog
- Consider increasing time limit for specific malls

---

## Monitoring & Observability

### Celery Signals

All tasks emit lifecycle events (configured in celery_app.py):
- `task_prerun`: Log task start
- `task_postrun`: Log task completion
- `task_failure`: Log error with traceback
- `task_success`: Log result
- `task_retry`: Log retry reason

### Flower Dashboard

Access at `http://localhost:5555` (when running):
- Real-time task monitoring
- Worker status
- Task execution times
- Success/failure rates
- Task details with arguments and results

### Database Queries

```sql
-- Get processing statistics
SELECT
    v.processing_status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (v.processing_completed_at - pj.started_at))) as avg_duration_sec
FROM videos v
LEFT JOIN processing_jobs pj ON v.id = pj.video_id
WHERE pj.job_type = 'proxy_generation'
GROUP BY v.processing_status;

-- Get recent failures
SELECT
    v.id,
    v.filename,
    v.processing_error,
    pj.error_message,
    pj.started_at
FROM videos v
LEFT JOIN processing_jobs pj ON v.id = pj.video_id
WHERE v.processing_status = 'failed'
ORDER BY pj.started_at DESC
LIMIT 20;

-- Get slow jobs (>2 minutes)
SELECT
    pj.id,
    v.filename,
    EXTRACT(EPOCH FROM (pj.completed_at - pj.started_at)) as duration_sec,
    (pj.result_data->'metadata'->'original'->>'duration_seconds')::float as video_duration_sec
FROM processing_jobs pj
JOIN videos v ON pj.video_id = v.id
WHERE pj.status = 'completed'
  AND EXTRACT(EPOCH FROM (pj.completed_at - pj.started_at)) > 120
ORDER BY duration_sec DESC
LIMIT 20;
```

---

## Next Steps (Phase 2.6)

With proxy generation complete, Phase 2.6 will implement:

1. **Video Streaming & Management APIs**:
   - `GET /videos` - List videos with filters
   - `GET /videos/{video_id}` - Get video details
   - `GET /videos/{video_id}/proxy` - Stream proxy video (presigned URL)
   - `GET /videos/{video_id}/thumbnail` - Get thumbnail (presigned URL)
   - `DELETE /videos/{video_id}` - Delete video and all associated files

2. **Advanced Features**:
   - Presigned URL generation for secure video access
   - Video search and filtering (by mall, pin, date range, processing status)
   - Batch operations (delete multiple videos)
   - Video re-processing (regenerate proxy/thumbnail)

3. **Client Integration**:
   - JavaScript SDK for video upload and playback
   - Progress tracking during upload
   - Automatic retry on failure

---

## Acceptance Criteria

All Phase 2.5 acceptance criteria met:

- [x] ✅ FFmpeg service created with extract_metadata, generate_proxy, generate_thumbnail
- [x] ✅ Video validation function implemented
- [x] ✅ generate_proxy_video task fully implemented (no placeholders)
- [x] ✅ extract_video_metadata task fully implemented
- [x] ✅ generate_thumbnail task fully implemented
- [x] ✅ S3 integration for download/upload
- [x] ✅ Temp file management with automatic cleanup
- [x] ✅ Comprehensive error handling and retries
- [x] ✅ Metadata stored in Video record (width, height, fps, duration, codec)
- [x] ✅ Proxy and thumbnail paths stored in Video record
- [x] ✅ Job result_data includes all metadata
- [x] ✅ FFmpeg dependency added to requirements.txt
- [x] ✅ FFmpegService exported from services package

---

**Phase 2.5 Status**: ✅ CODE COMPLETE
**Action Required**: Install FFmpeg system dependency before running workers
**Ready for**: Phase 2.6 - Video Streaming & Management APIs

---

## Installation Checklist

Before deploying to production:

- [ ] Install FFmpeg on all worker machines
- [ ] Verify FFmpeg version ≥ 4.0 (`ffmpeg -version`)
- [ ] Test proxy generation with sample video
- [ ] Monitor first few jobs in Flower dashboard
- [ ] Verify S3 uploads are working correctly
- [ ] Check temp disk space is sufficient (at least 5GB free)
- [ ] Configure worker concurrency based on CPU/memory
- [ ] Set up log aggregation for FFmpeg errors

---

**Document Version**: 1.0
**Last Updated**: 2025-10-31
**Implementation Time**: ~2 hours (excluding FFmpeg installation)
