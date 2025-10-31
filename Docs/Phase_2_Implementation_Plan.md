# Phase 2: Video Management - Implementation Plan

**Version**: 1.0
**Created**: 2025-10-31
**Status**: Ready to Execute
**Estimated Duration**: 2 weeks (10 business days)

---

## Overview

This document breaks down Phase 2 into 10 commit-worthy subphases. Each subphase represents a complete, testable unit of work that can be committed and pushed to the repository independently.

---

## Subphase Breakdown

### **Phase 2.1: Database Schema & Migrations**
**Duration**: 4-6 hours
**Commit Message**: `feat(phase-2.1): Add video management database schema with multipart upload support`

#### Tasks
- [ ] Create Alembic migration file for Phase 2
- [ ] Define `videos` table with extended metadata fields:
  - [ ] Core fields: id, mall_id, pin_id, filename, file_size_bytes, duration_seconds
  - [ ] File paths: original_path, proxy_path
  - [ ] Deduplication: checksum_sha256 (VARCHAR(64))
  - [ ] Operator metadata: recorded_at, operator_notes, uploaded_by_user_id
  - [ ] Video properties: width, height, fps, codec
  - [ ] Status tracking: upload_status, processing_status, processing_job_id, processing_error
  - [ ] Timestamps: uploaded_at, processing_started_at, processing_completed_at, created_at, updated_at
- [ ] Add indexes:
  - [ ] idx_videos_pin_id
  - [ ] idx_videos_mall_id
  - [ ] idx_videos_status (processing_status)
  - [ ] idx_videos_uploaded_at DESC
  - [ ] idx_videos_checksum (checksum_sha256)
  - [ ] idx_videos_recorded_at DESC
- [ ] Add unique constraint: UNIQUE (checksum_sha256, pin_id)
- [ ] Define `processing_jobs` table:
  - [ ] Core fields: id, video_id, job_type, status
  - [ ] Celery tracking: celery_task_id, worker_hostname
  - [ ] Results: result_data (JSONB), error_message
  - [ ] Timestamps: queued_at, started_at, completed_at
- [ ] Add indexes:
  - [ ] idx_jobs_video_id
  - [ ] idx_jobs_status
  - [ ] idx_jobs_celery_task_id
- [ ] Run migration on local database
- [ ] Verify schema with `\d videos` and `\d processing_jobs`

#### Acceptance Criteria
- ✅ Migration runs without errors
- ✅ All tables and indexes created correctly
- ✅ Unique constraint on (checksum_sha256, pin_id) enforced
- ✅ Foreign key relationships validated

#### Testing
```bash
# Run migration
alembic upgrade head

# Verify tables exist
psql -d spatial_intel -c "\dt"
psql -d spatial_intel -c "\d videos"
psql -d spatial_intel -c "\d processing_jobs"

# Test unique constraint
psql -d spatial_intel -c "INSERT INTO videos (mall_id, pin_id, filename, checksum_sha256, file_size_bytes) VALUES ('test-mall', 'test-pin', 'test.mp4', 'abc123', 1000);"
# Should fail on duplicate:
psql -d spatial_intel -c "INSERT INTO videos (mall_id, pin_id, filename, checksum_sha256, file_size_bytes) VALUES ('test-mall', 'test-pin', 'test2.mp4', 'abc123', 1000);"
```

---

### **Phase 2.2: Object Storage Infrastructure (MinIO/S3)**
**Duration**: 4-6 hours
**Commit Message**: `feat(phase-2.2): Set up MinIO object storage with S3-compatible API`

#### Tasks
- [ ] Add MinIO service to docker-compose.yml:
  - [ ] MinIO server container (port 9000)
  - [ ] MinIO console container (port 9001)
  - [ ] Persistent volume for data
  - [ ] Environment variables: MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
- [ ] Create backend/storage/s3_client.py wrapper:
  - [ ] Initialize boto3 S3 client with MinIO endpoint
  - [ ] `upload_file(local_path, s3_key)` → upload to S3
  - [ ] `download_file(s3_key, local_path)` → download from S3
  - [ ] `delete_file(s3_key)` → delete from S3
  - [ ] `generate_presigned_url(s3_key, method='GET', expires=3600)` → signed URL
  - [ ] `initiate_multipart_upload(s3_key)` → return upload_id
  - [ ] `generate_presigned_part_url(s3_key, upload_id, part_number)` → presigned PUT URL
  - [ ] `complete_multipart_upload(s3_key, upload_id, parts)` → finalize upload
  - [ ] `abort_multipart_upload(s3_key, upload_id)` → cancel upload
  - [ ] `get_file_metadata(s3_key)` → size, etag, last_modified
- [ ] Create backend/storage/__init__.py with S3Client singleton
- [ ] Add environment variables to .env:
  - [ ] S3_ENDPOINT=http://localhost:9000
  - [ ] S3_ACCESS_KEY=minioadmin
  - [ ] S3_SECRET_KEY=minioadmin
  - [ ] S3_BUCKET=spatial-intel-videos
  - [ ] S3_REGION=us-east-1
- [ ] Create bucket initialization script (backend/scripts/init_storage.py):
  - [ ] Connect to MinIO
  - [ ] Create bucket if not exists
  - [ ] Set bucket policy (private)
- [ ] Write unit tests (backend/tests/test_s3_client.py):
  - [ ] Test upload/download roundtrip
  - [ ] Test presigned URL generation and validation
  - [ ] Test multipart upload flow
  - [ ] Test delete operation
  - [ ] Test file not found errors

#### Acceptance Criteria
- ✅ MinIO running and accessible at http://localhost:9000
- ✅ MinIO console accessible at http://localhost:9001
- ✅ Bucket `spatial-intel-videos` created
- ✅ S3Client wrapper can upload, download, delete files
- ✅ Presigned URLs work for GET and PUT operations
- ✅ Multipart upload flow works (initiate → upload parts → complete)
- ✅ All unit tests pass

#### Testing
```bash
# Start MinIO
docker-compose up -d minio

# Initialize bucket
python backend/scripts/init_storage.py

# Run unit tests
pytest backend/tests/test_s3_client.py -v

# Manual test
python -c "
from backend.storage import s3_client
s3_client.upload_file('test.txt', 'test/test.txt')
print(s3_client.generate_presigned_url('test/test.txt'))
"
```

---

### **Phase 2.3: Multipart Upload API (Initiate/Complete/Abort)**
**Duration**: 6-8 hours
**Commit Message**: `feat(phase-2.3): Implement multipart upload API with checksum deduplication`

#### Tasks
- [ ] Create backend/api/videos/upload.py:
  - [ ] `POST /malls/{mall_id}/pins/{pin_id}/uploads/initiate`
    - [ ] Validate mall_id and pin_id exist
    - [ ] Validate user has access to mall
    - [ ] Validate filename is .mp4
    - [ ] Validate file_size_bytes ≤ 2GB
    - [ ] Check for duplicate via checksum_sha256
      - [ ] If duplicate found, return existing video_id with 200 OK
    - [ ] Create video record with upload_status='uploading'
    - [ ] Calculate part_size (10MB default) and total_parts
    - [ ] Call S3 initiate_multipart_upload()
    - [ ] Generate presigned PUT URLs for first 100 parts
    - [ ] Store multipart state in Redis:
      - [ ] Key: `upload:{video_id}`
      - [ ] Value: {upload_id, mall_id, pin_id, total_parts, expires_at}
      - [ ] TTL: 6 hours
    - [ ] Return {video_id, upload_id, part_size_bytes, total_parts, presigned_urls, expires_at}
  - [ ] `POST /malls/{mall_id}/pins/{pin_id}/uploads/{video_id}/complete`
    - [ ] Validate video exists and upload_status='uploading'
    - [ ] Validate user has access to mall
    - [ ] Retrieve multipart state from Redis
    - [ ] Call S3 complete_multipart_upload() with parts array
    - [ ] Update video record: upload_status='uploaded'
    - [ ] Verify checksum if provided (optional)
    - [ ] Extract video metadata with ffprobe
    - [ ] Update video record with width, height, fps, codec, duration_seconds
    - [ ] Create processing_job record with status='pending'
    - [ ] Enqueue proxy generation task (Celery)
    - [ ] Clean up Redis state
    - [ ] Return {video_id, upload_status, processing_status, job_id, uploaded_at}
  - [ ] `DELETE /malls/{mall_id}/pins/{pin_id}/uploads/{video_id}`
    - [ ] Validate video exists
    - [ ] Validate user has access to mall
    - [ ] Retrieve multipart state from Redis
    - [ ] Call S3 abort_multipart_upload()
    - [ ] Delete video record from database
    - [ ] Clean up Redis state
    - [ ] Return 204 No Content
- [ ] Create backend/utils/video_validation.py:
  - [ ] `validate_mp4_file(filename)` → check extension
  - [ ] `validate_file_size(size_bytes, max_size=2GB)` → check size
  - [ ] `compute_sha256(file_path)` → calculate checksum (for testing)
- [ ] Create backend/utils/ffprobe.py:
  - [ ] `extract_metadata(file_path)` → {width, height, fps, codec, duration_seconds}
- [ ] Add Redis client to backend/storage/redis_client.py:
  - [ ] `set_multipart_state(video_id, state, ttl=21600)` → store upload state
  - [ ] `get_multipart_state(video_id)` → retrieve upload state
  - [ ] `delete_multipart_state(video_id)` → cleanup
- [ ] Write integration tests (backend/tests/test_upload_api.py):
  - [ ] Test initiate upload (success)
  - [ ] Test initiate upload (duplicate checksum returns existing video)
  - [ ] Test initiate upload (invalid mall_id returns 404)
  - [ ] Test initiate upload (file too large returns 400)
  - [ ] Test complete upload (success)
  - [ ] Test complete upload (invalid video_id returns 404)
  - [ ] Test abort upload (success)

#### Acceptance Criteria
- ✅ Initiate endpoint returns presigned URLs
- ✅ Duplicate checksum detection works (returns existing video_id)
- ✅ Complete endpoint finalizes upload and enqueues processing job
- ✅ Abort endpoint cleans up S3 and database
- ✅ Redis state management works correctly
- ✅ All integration tests pass
- ✅ FFprobe metadata extraction works

#### Testing
```bash
# Run integration tests
pytest backend/tests/test_upload_api.py -v

# Manual API test
curl -X POST http://localhost:8000/malls/{mall_id}/pins/{pin_id}/uploads/initiate \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test.mp4",
    "file_size_bytes": 1073741824,
    "checksum_sha256": "abc123...",
    "metadata": {"recorded_at": "2025-10-30T14:00:00Z"}
  }'
```

---

### **Phase 2.4: Background Job Queue (Celery + Redis)**
**Duration**: 4-6 hours
**Commit Message**: `feat(phase-2.4): Set up Celery background job queue with Redis backend`

#### Tasks
- [ ] Add Celery and Redis to docker-compose.yml:
  - [ ] Redis service (port 6379)
  - [ ] Celery worker service (queue: video_processing, concurrency: 2)
  - [ ] Celery Beat service (for scheduled tasks)
- [ ] Create backend/celeryconfig.py:
  - [ ] broker_url = redis://redis:6379/0
  - [ ] result_backend = redis://redis:6379/0
  - [ ] task_serializer = 'json'
  - [ ] task_routes (video_processing queue)
  - [ ] task_time_limit = 3600 (1 hour)
  - [ ] worker_prefetch_multiplier = 1
  - [ ] worker_max_tasks_per_child = 10
  - [ ] beat_schedule (for watchdog task - empty for now)
- [ ] Create backend/tasks/__init__.py with Celery app
- [ ] Create backend/tasks/base.py with VideoProcessingTask base class:
  - [ ] on_failure() → update processing_jobs.status='failed'
  - [ ] on_success() → update processing_jobs.status='completed'
- [ ] Create backend/tasks/video.py with skeleton tasks:
  - [ ] `generate_proxy(video_id, input_path, output_path)` → placeholder
    - [ ] Update job status to 'running'
    - [ ] Log start time
    - [ ] Return {success: True} (no actual processing yet)
- [ ] Create backend/api/jobs/status.py:
  - [ ] `GET /analysis/jobs/{job_id}`
    - [ ] Query processing_jobs table
    - [ ] Return {job_id, video_id, job_type, status, started_at, completed_at, error_message}
- [ ] Write integration tests (backend/tests/test_celery.py):
  - [ ] Test task enqueue and execution
  - [ ] Test job status retrieval
  - [ ] Test task failure handling

#### Acceptance Criteria
- ✅ Redis running and accessible
- ✅ Celery worker starts and connects to Redis
- ✅ Tasks can be enqueued and executed
- ✅ Job status API returns correct information
- ✅ Task failure updates database correctly
- ✅ All integration tests pass

#### Testing
```bash
# Start services
docker-compose up -d redis celery-worker

# Check Celery worker logs
docker-compose logs -f celery-worker

# Test task execution
python -c "
from backend.tasks.video import generate_proxy
result = generate_proxy.delay('test-video-id', 'input.mp4', 'output.mp4')
print(result.get(timeout=10))
"

# Run integration tests
pytest backend/tests/test_celery.py -v
```

---

### **Phase 2.5: FFmpeg Proxy Generation Pipeline**
**Duration**: 6-8 hours
**Commit Message**: `feat(phase-2.5): Implement FFmpeg proxy generation with 480p/10fps encoding`

#### Tasks
- [ ] Install FFmpeg in worker Docker image:
  - [ ] Update backend/Dockerfile
  - [ ] `RUN apt-get update && apt-get install -y ffmpeg`
- [ ] Implement backend/tasks/video.py `generate_proxy()` task:
  - [ ] Update job status to 'running'
  - [ ] Download original from S3 to /tmp/{video_id}_input.mp4
  - [ ] Extract metadata with ffprobe
  - [ ] Run FFmpeg command:
    ```bash
    ffmpeg -i input.mp4 \
      -vf "scale=854:480:force_original_aspect_ratio=decrease,fps=10" \
      -c:v libx264 -preset medium -crf 23 \
      -c:a aac -b:a 128k \
      -movflags +faststart \
      -y output.mp4
    ```
  - [ ] Upload proxy to S3 at {mall_id}/{pin_id}/{video_id}/proxy.mp4
  - [ ] Update video record: proxy_path, processing_status='completed'
  - [ ] Get proxy file size from S3
  - [ ] Store result_data in processing_jobs table
  - [ ] Clean up temp files (/tmp/{video_id}_*.mp4)
  - [ ] Return {success: True, proxy_path, proxy_size_bytes, duration_seconds}
  - [ ] On error:
    - [ ] Update video.processing_status='failed'
    - [ ] Update video.processing_error with error message
    - [ ] Raise exception to trigger on_failure()
- [ ] Create backend/utils/ffmpeg.py wrapper:
  - [ ] `generate_proxy(input_path, output_path)` → run FFmpeg command
  - [ ] `extract_metadata(input_path)` → ffprobe wrapper
  - [ ] Handle FFmpeg errors gracefully
- [ ] Write integration tests (backend/tests/test_proxy_generation.py):
  - [ ] Test proxy generation with sample 10-second clip
  - [ ] Test proxy generation with sample 1-minute clip
  - [ ] Test error handling (corrupted input)
  - [ ] Test cleanup of temp files
  - [ ] Verify proxy properties (480p, 10fps, h264)

#### Acceptance Criteria
- ✅ FFmpeg installed in worker container
- ✅ Proxy generation task completes successfully
- ✅ Generated proxy is 480p, 10fps, H.264 codec
- ✅ Proxy file size is 10-15% of original
- ✅ Temp files cleaned up after processing
- ✅ Error handling works (updates status to 'failed')
- ✅ All integration tests pass

#### Testing
```bash
# Build worker with FFmpeg
docker-compose build celery-worker

# Test with sample video
python -c "
from backend.tasks.video import generate_proxy
from backend.storage import s3_client

# Upload test video
s3_client.upload_file('test_videos/sample_1080p.mp4', 'test-mall/test-pin/test-video/original.mp4')

# Generate proxy
result = generate_proxy.delay(
  'test-video-id',
  'test-mall/test-pin/test-video/original.mp4',
  'test-mall/test-pin/test-video/proxy.mp4'
)
print(result.get(timeout=300))
"

# Verify proxy properties
ffprobe test-mall/test-pin/test-video/proxy.mp4

# Run integration tests
pytest backend/tests/test_proxy_generation.py -v
```

---

### **Phase 2.6: Video Streaming & Management APIs**
**Duration**: 4-6 hours
**Commit Message**: `feat(phase-2.6): Add video streaming with signed URLs and management endpoints`

#### Tasks
- [ ] Create backend/api/videos/streaming.py:
  - [ ] `GET /videos/{video_id}/stream-url`
    - [ ] Validate video exists
    - [ ] Validate user has access to mall
    - [ ] Validate processing_status='completed' and proxy_path exists
    - [ ] Generate signed URL with 1-hour expiry
    - [ ] Return {url, expires_at}
  - [ ] `GET /videos/{video_id}/proxy?expires={ts}&signature={sig}`
    - [ ] Validate signature and expiry
    - [ ] Stream proxy file from S3
    - [ ] Support HTTP Range requests for seeking
    - [ ] Set appropriate headers (Content-Type: video/mp4, Accept-Ranges: bytes)
- [ ] Create backend/api/videos/management.py:
  - [ ] `GET /videos/{video_id}`
    - [ ] Query video record with JOIN on camera_pins
    - [ ] Return full video details including metadata
  - [ ] `GET /malls/{mall_id}/pins/{pin_id}/videos`
    - [ ] Query videos for pin with filters (status, date range)
    - [ ] Support pagination (limit, offset)
    - [ ] Return list of videos with has_proxy flag
  - [ ] `DELETE /videos/{video_id}`
    - [ ] Validate user has access to mall
    - [ ] Delete original and proxy from S3
    - [ ] Cancel running processing job (if any)
    - [ ] Delete video record (cascade to processing_jobs)
    - [ ] Return 204 No Content
- [ ] Create backend/utils/signed_urls.py:
  - [ ] `generate_signed_url(video_id, expires_in_seconds=3600)` → URL with HMAC signature
  - [ ] `validate_signature(video_id, expires_ts, signature)` → bool
- [ ] Write integration tests (backend/tests/test_video_api.py):
  - [ ] Test stream URL generation
  - [ ] Test proxy streaming with Range requests
  - [ ] Test signed URL expiry
  - [ ] Test signed URL tampering detection
  - [ ] Test video details retrieval
  - [ ] Test video listing with filters
  - [ ] Test video deletion

#### Acceptance Criteria
- ✅ Signed URLs generated correctly
- ✅ Proxy streaming works with HTTP Range requests
- ✅ Expired URLs rejected
- ✅ Tampered signatures rejected
- ✅ Video listing supports filters and pagination
- ✅ Video deletion cascades correctly
- ✅ All integration tests pass

#### Testing
```bash
# Test streaming
curl -I "http://localhost:8000/videos/{video_id}/stream-url"
curl -I "http://localhost:8000/videos/{video_id}/proxy?expires=...&signature=..."

# Test Range request
curl -H "Range: bytes=0-1023" "http://localhost:8000/videos/{video_id}/proxy?expires=...&signature=..."

# Run integration tests
pytest backend/tests/test_video_api.py -v
```

---

### **Phase 2.7: Stuck Job Watchdog & Monitoring**
**Duration**: 4-6 hours
**Commit Message**: `feat(phase-2.7): Add stuck job watchdog with Celery Beat and alerting`

#### Tasks
- [ ] Create backend/tasks/watchdog.py:
  - [ ] `clean_stuck_jobs()` Celery Beat task:
    - [ ] Find uploads stuck in 'uploading' >6 hours
    - [ ] Abort S3 multipart uploads
    - [ ] Mark as 'failed' with error message
    - [ ] Send alert (Sentry + Slack)
    - [ ] Find processing jobs stuck in 'running' >4 hours
    - [ ] Mark as 'failed' with error message
    - [ ] Update video.processing_status='failed'
    - [ ] Send alert (Sentry + Slack)
    - [ ] Return {stuck_uploads_cleaned, stuck_jobs_cleaned}
- [ ] Update backend/celeryconfig.py:
  - [ ] Add beat_schedule:
    ```python
    beat_schedule = {
      'clean-stuck-jobs-daily': {
        'task': 'tasks.watchdog.clean_stuck_jobs',
        'schedule': crontab(hour=3, minute=0),
      }
    }
    ```
- [ ] Create backend/utils/alerts.py:
  - [ ] `send_alert(type, **details)` → Sentry + Slack
  - [ ] Configure Sentry SDK
  - [ ] Configure Slack webhook (optional)
- [ ] Create backend/api/admin/cleanup.py:
  - [ ] `POST /admin/cleanup-stuck-jobs` (admin-only)
    - [ ] Validate user has admin role
    - [ ] Call clean_stuck_jobs() synchronously
    - [ ] Return {stuck_uploads_cleaned, stuck_jobs_cleaned, cleaned_at}
- [ ] Add environment variables:
  - [ ] SENTRY_DSN (optional)
  - [ ] SLACK_WEBHOOK_URL (optional)
  - [ ] STUCK_UPLOAD_THRESHOLD_HOURS=6
  - [ ] STUCK_JOB_THRESHOLD_HOURS=4
- [ ] Write unit tests (backend/tests/test_watchdog.py):
  - [ ] Test stuck upload detection and cleanup
  - [ ] Test stuck job detection and cleanup
  - [ ] Test alert sending
  - [ ] Test manual cleanup endpoint

#### Acceptance Criteria
- ✅ Celery Beat starts and schedules watchdog task
- ✅ Stuck uploads detected and cleaned
- ✅ Stuck jobs detected and cleaned
- ✅ S3 multipart uploads aborted correctly
- ✅ Alerts sent to Sentry (if configured)
- ✅ Manual cleanup endpoint works
- ✅ All unit tests pass

#### Testing
```bash
# Start Celery Beat
docker-compose up -d celery-beat

# Create stuck upload for testing
python -c "
from backend.models import Video
from datetime import datetime, timedelta
video = Video(
  mall_id='test-mall',
  pin_id='test-pin',
  filename='stuck.mp4',
  upload_status='uploading',
  created_at=datetime.utcnow() - timedelta(hours=7)
)
db.session.add(video)
db.session.commit()
"

# Manually trigger watchdog
python -c "
from backend.tasks.watchdog import clean_stuck_jobs
result = clean_stuck_jobs()
print(result)
"

# Run unit tests
pytest backend/tests/test_watchdog.py -v
```

---

### **Phase 2.8: Frontend Upload Components**
**Duration**: 6-8 hours
**Commit Message**: `feat(phase-2.8): Build video upload UI with multipart upload and checksum verification`

#### Tasks
- [ ] Create frontend/src/utils/checksum.js:
  - [ ] `computeSHA256(file)` → Promise<string>
  - [ ] Use SubtleCrypto API or library (crypto-js)
- [ ] Create frontend/src/utils/multipartUpload.js:
  - [ ] `uploadVideoMultipart(mallId, pinId, file, metadata, onProgress)` → Promise<video_id>
    - [ ] Compute SHA256 checksum
    - [ ] Call initiate endpoint
    - [ ] Upload parts to presigned URLs
    - [ ] Track progress (parts completed / total parts)
    - [ ] Call complete endpoint
    - [ ] Return video_id
- [ ] Create frontend/src/components/VideoUploader.jsx:
  - [ ] File input with drag-and-drop (react-dropzone)
  - [ ] File validation (MP4 only, max 2GB)
  - [ ] Metadata form fields:
    - [ ] Recorded at (datetime picker)
    - [ ] Operator notes (textarea)
  - [ ] Upload button (disabled during upload)
  - [ ] Progress display:
    - [ ] Checksum calculation: "Calculating checksum..."
    - [ ] Upload progress: "Uploading: 45%"
    - [ ] Processing status: "Processing queued..." / "Processing video..." / "✅ Complete" / "❌ Failed"
  - [ ] Error handling and display
  - [ ] Success message with link to video player
- [ ] Create frontend/src/hooks/useJobStatus.js:
  - [ ] `useJobStatus(jobId)` → {status, loading, error}
  - [ ] Poll job status API every 3 seconds
  - [ ] Stop polling on completed/failed
- [ ] Create frontend/src/api/videos.js:
  - [ ] `initiateUpload(mallId, pinId, data)` → {video_id, upload_id, presigned_urls, ...}
  - [ ] `completeUpload(mallId, pinId, videoId, data)` → {job_id, ...}
  - [ ] `abortUpload(mallId, pinId, videoId)` → void
  - [ ] `getJobStatus(jobId)` → {status, ...}
- [ ] Write component tests (frontend/tests/VideoUploader.test.jsx):
  - [ ] Test file selection
  - [ ] Test validation errors
  - [ ] Test upload flow (mock API)
  - [ ] Test progress display
  - [ ] Test error handling

#### Acceptance Criteria
- ✅ User can select MP4 file via drag-and-drop or file picker
- ✅ SHA256 checksum calculated correctly
- ✅ Multipart upload works with progress percentage
- ✅ Metadata fields captured (recorded_at, operator_notes)
- ✅ Upload progress displayed accurately
- ✅ Job status polling shows processing progress
- ✅ Error messages displayed to user
- ✅ Success message with navigation to video player
- ✅ All component tests pass

#### Testing
```bash
# Run component tests
npm test -- VideoUploader.test.jsx

# Manual UI test
npm run dev
# Navigate to /malls/{mall_id}/pins/{pin_id}/upload
# Upload a sample video and verify:
# - Checksum calculation shows
# - Upload progress updates
# - Processing status updates
# - Success message appears
```

---

### **Phase 2.9: Frontend Video Player & Management UI**
**Duration**: 6-8 hours
**Commit Message**: `feat(phase-2.9): Build video player with signed URLs and video management interface`

#### Tasks
- [ ] Create frontend/src/components/VideoPlayer.jsx:
  - [ ] HTML5 <video> element with controls
  - [ ] Load signed URL on mount
  - [ ] Display video metadata (filename, duration, uploaded_at, recorded_at)
  - [ ] Playback controls:
    - [ ] Play/pause
    - [ ] Seeking (progress bar)
    - [ ] Volume control
    - [ ] Playback speed (0.5x, 1x, 2x)
    - [ ] Fullscreen toggle
  - [ ] Loading state while fetching signed URL
  - [ ] Error handling (video not found, processing failed)
- [ ] Create frontend/src/components/VideoList.jsx:
  - [ ] Table view of videos for a camera pin
  - [ ] Columns:
    - [ ] Thumbnail (placeholder for now)
    - [ ] Filename
    - [ ] Duration (formatted as HH:MM:SS)
    - [ ] Recorded at
    - [ ] Uploaded at
    - [ ] Status (pending/processing/completed/failed)
    - [ ] Actions (view, delete)
  - [ ] Filters:
    - [ ] Status dropdown (all, completed, processing, failed)
    - [ ] Date range picker (from, to)
  - [ ] Pagination (limit 50 per page)
  - [ ] Click row to navigate to video player
  - [ ] Delete button with confirmation modal
- [ ] Create frontend/src/hooks/useSignedUrl.js:
  - [ ] `useSignedUrl(videoId)` → {url, loading, error}
  - [ ] Fetch signed URL from API
  - [ ] Refresh URL before expiry (45 minutes)
- [ ] Create frontend/src/api/videos.js (additions):
  - [ ] `getStreamUrl(videoId)` → {url, expires_at}
  - [ ] `getVideo(videoId)` → {id, filename, duration, ...}
  - [ ] `getVideos(mallId, pinId, filters)` → {videos, total}
  - [ ] `deleteVideo(videoId)` → void
- [ ] Create frontend/src/pages/VideoPlayerPage.jsx:
  - [ ] Route: `/videos/:videoId`
  - [ ] Render VideoPlayer component
  - [ ] Breadcrumb navigation (Mall > Pin > Video)
- [ ] Create frontend/src/pages/VideoListPage.jsx:
  - [ ] Route: `/malls/:mallId/pins/:pinId/videos`
  - [ ] Render VideoList component
  - [ ] "Upload Video" button → navigate to uploader
- [ ] Write component tests:
  - [ ] VideoPlayer.test.jsx
  - [ ] VideoList.test.jsx

#### Acceptance Criteria
- ✅ Video player loads and plays proxy video
- ✅ Signed URL refreshes before expiry
- ✅ Seeking works (HTTP Range requests)
- ✅ Playback speed control works
- ✅ Video list displays all videos for pin
- ✅ Filters work (status, date range)
- ✅ Pagination works
- ✅ Delete confirmation modal works
- ✅ All component tests pass

#### Testing
```bash
# Run component tests
npm test -- VideoPlayer.test.jsx
npm test -- VideoList.test.jsx

# Manual UI test
npm run dev
# Navigate to /videos/{video_id}
# Verify:
# - Video loads and plays
# - Seeking works smoothly
# - Playback speed changes
# - Fullscreen works

# Navigate to /malls/{mall_id}/pins/{pin_id}/videos
# Verify:
# - Video list displays
# - Filters work
# - Pagination works
# - Delete button works
```

---

### **Phase 2.10: Integration Testing & Performance Validation**
**Duration**: 4-6 hours
**Commit Message**: `test(phase-2.10): Add end-to-end tests and performance benchmarks for video pipeline`

#### Tasks
- [ ] Create backend/tests/integration/test_video_pipeline_e2e.py:
  - [ ] Test full flow: Initiate → Upload Parts → Complete → Process → Stream
  - [ ] Test duplicate upload detection (same checksum)
  - [ ] Test concurrent uploads (5 videos simultaneously)
  - [ ] Test stuck upload cleanup (simulate 6+ hour old upload)
  - [ ] Test stuck job cleanup (simulate 4+ hour old job)
  - [ ] Test video deletion (verify S3 cleanup)
- [ ] Create backend/tests/performance/test_proxy_benchmarks.py:
  - [ ] Benchmark 10-minute 1080p/30fps clip
    - [ ] Target: <20 minutes processing time
    - [ ] Measure: actual time, CPU usage, memory usage
  - [ ] Benchmark 30-minute 1080p/30fps clip
    - [ ] Target: <1 hour processing time
    - [ ] Measure: actual time, CPU usage, memory usage
  - [ ] Verify proxy properties:
    - [ ] Resolution: 480p
    - [ ] FPS: 10
    - [ ] File size: 10-15% of original
    - [ ] Codec: H.264
- [ ] Create frontend/tests/e2e/video-upload.spec.js (Playwright/Cypress):
  - [ ] Test upload flow from UI
  - [ ] Test progress updates
  - [ ] Test navigation to video player after upload
  - [ ] Test video playback
  - [ ] Test video deletion
- [ ] Create backend/tests/load/test_concurrent_uploads.py (optional):
  - [ ] Simulate 10 concurrent uploads
  - [ ] Verify no resource contention
  - [ ] Verify all uploads complete successfully
  - [ ] Measure throughput (GB/minute)
- [ ] Document test results in Docs/Phase_2_Test_Results.md:
  - [ ] Performance benchmarks
  - [ ] Test coverage percentage
  - [ ] Known issues / limitations
  - [ ] Next steps for optimization

#### Acceptance Criteria
- ✅ End-to-end tests pass
- ✅ 10-minute clip processed in <20 minutes
- ✅ 30-minute clip processed in <1 hour
- ✅ Proxy properties verified (480p, 10fps, H.264)
- ✅ Concurrent uploads work without errors
- ✅ Stuck job cleanup works in integration
- ✅ Frontend E2E tests pass
- ✅ Test results documented

#### Testing
```bash
# Run integration tests
pytest backend/tests/integration/test_video_pipeline_e2e.py -v

# Run performance benchmarks
pytest backend/tests/performance/test_proxy_benchmarks.py -v --benchmark

# Run frontend E2E tests
npm run test:e2e

# Generate test coverage report
pytest --cov=backend --cov-report=html
open htmlcov/index.html

# Document results
# Edit Docs/Phase_2_Test_Results.md with findings
```

---

## Commit Strategy

### Commit Message Format
```
<type>(phase-X.Y): <summary>

<optional detailed description>

Tests:
- <test coverage summary>

Performance:
- <benchmark results if applicable>
```

### Example Commits
```bash
# Phase 2.1
git add backend/alembic/versions/002_video_management.py
git commit -m "feat(phase-2.1): Add video management database schema with multipart upload support

- Added videos table with checksum_sha256 for deduplication
- Added processing_jobs table for Celery task tracking
- Added indexes for performance optimization
- Added unique constraint on (checksum_sha256, pin_id)

Tests:
- Verified migration runs successfully
- Tested unique constraint enforcement"

git push origin main

# Phase 2.2
git add backend/storage/ docker-compose.yml backend/tests/test_s3_client.py
git commit -m "feat(phase-2.2): Set up MinIO object storage with S3-compatible API

- Added MinIO service to docker-compose
- Implemented S3Client wrapper with multipart upload support
- Added presigned URL generation for GET and PUT
- Created bucket initialization script

Tests:
- All S3Client unit tests passing (12/12)
- Verified multipart upload flow works"

git push origin main

# ... and so on for each phase
```

---

## Quality Gates

Before committing each subphase, verify:

1. **Code Quality**
   - [ ] No linting errors (`flake8`, `eslint`)
   - [ ] No type errors (`mypy` for Python, TypeScript for frontend)
   - [ ] Code formatted (`black`, `prettier`)

2. **Testing**
   - [ ] All unit tests pass
   - [ ] All integration tests pass (if applicable)
   - [ ] Test coverage ≥80% for new code

3. **Documentation**
   - [ ] Code comments for complex logic
   - [ ] API endpoints documented (docstrings)
   - [ ] README updated if needed

4. **Functionality**
   - [ ] Manual testing completed
   - [ ] Acceptance criteria met
   - [ ] No known critical bugs

---

## Risk Mitigation Per Subphase

| Subphase | Risk | Mitigation |
|----------|------|------------|
| 2.1 | Migration fails in production | Test migration on copy of production data first |
| 2.2 | MinIO performance issues | Benchmark early; consider AWS S3 if issues arise |
| 2.3 | Multipart upload complexity | Implement retry logic; test with poor network conditions |
| 2.4 | Celery worker crashes | Add health checks; implement task retries |
| 2.5 | FFmpeg too slow | Benchmark with 10min clips first; adjust settings if needed |
| 2.6 | Signed URL security | Penetration test before production |
| 2.7 | Watchdog false positives | Start with conservative thresholds (6hr, 4hr) |
| 2.8 | Frontend upload UX issues | User testing with real operators |
| 2.9 | Video playback issues | Test on multiple browsers/devices |
| 2.10 | Performance regressions | Set up CI benchmarks to detect regressions |

---

## Progress Tracking

Use the TodoWrite tool to track progress:

```bash
# Mark subphase as in_progress
TodoWrite: Phase 2.1 → in_progress

# Mark subphase as completed after commit
TodoWrite: Phase 2.1 → completed

# Move to next subphase
TodoWrite: Phase 2.2 → in_progress
```

---

## Rollback Plan

If a subphase causes critical issues:

1. **Immediate Rollback**
   ```bash
   git revert HEAD
   git push origin main
   ```

2. **Database Rollback** (if migration applied)
   ```bash
   alembic downgrade -1
   ```

3. **Investigate & Fix**
   - Create hotfix branch
   - Fix issue
   - Re-test thoroughly
   - Re-commit

---

**Document Version**: 1.0
**Created**: 2025-10-31
**Status**: Ready for Execution
**Next Step**: Begin Phase 2.1 (Database Schema & Migrations)