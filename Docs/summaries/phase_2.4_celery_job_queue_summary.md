# Phase 2.4: Background Job Queue (Celery + Redis) - Completion Summary

**Date**: 2025-10-31
**Status**: ✅ COMPLETED

---

## Overview

Phase 2.4 implemented the background job queue infrastructure using Celery and Redis, enabling asynchronous video processing tasks. This provides the foundation for proxy generation (Phase 2.5), CV analysis (future), and system maintenance tasks.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                       FastAPI Application                     │
│  - Receives upload completion                                 │
│  - Queues proxy generation job                                │
│  - Returns job_id to client                                   │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Queue Job
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                      Redis (Message Broker)                   │
│  Queue: video_processing  →  [job1, job2, job3]              │
│  Queue: cv_analysis       →  [job4, job5]                    │
│  Queue: maintenance       →  [job6]                           │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Pull Jobs
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                      Celery Workers                           │
│  Worker 1: video_processing (concurrency=2)                  │
│  Worker 2: cv_analysis (concurrency=4)                       │
│  Worker 3: maintenance (concurrency=1)                       │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Execute Tasks
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                      Task Execution                           │
│  - Download video from S3                                     │
│  - Run FFmpeg for proxy generation                            │
│  - Upload proxy to S3                                         │
│  - Update database (processing_jobs, videos)                  │
└────────────────┬─────────────────────────────────────────────┘
                 │
                 │ Store Results
                 ▼
┌──────────────────────────────────────────────────────────────┐
│                   PostgreSQL Database                         │
│  processing_jobs: status, started_at, completed_at           │
│  videos: proxy_path, proxy_generated                          │
└──────────────────────────────────────────────────────────────┘
```

---

## Implemented Components

### 1. Celery Application (`app/core/celery_app.py`)

**Comprehensive Celery configuration** with production-ready settings:

#### Core Configuration
- Broker: Redis (database 1)
- Backend: Redis (database 2) for result storage
- Serialization: JSON (secure, compatible)
- Timezone: UTC with timezone awareness
- Task acknowledgment: Late ack (after completion)

#### Task Execution Settings
- **Time limits**: 1 hour hard limit, 55 minutes soft limit
- **Worker prefetch**: 1 task at a time (for video processing)
- **Max tasks per child**: 10 (restart worker for memory management)
- **Task tracking**: Started events enabled

#### Queue Routing
```python
task_routes = {
    "app.tasks.video_tasks.*": {"queue": "video_processing"},
    "app.tasks.analysis_tasks.*": {"queue": "cv_analysis"},
    "app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
}
```

#### Beat Schedule (Periodic Tasks)
- `cleanup-old-jobs`: Daily at 2 AM
- `check-stuck-jobs`: Every 15 minutes

#### Task Lifecycle Signals
- **prerun**: Log task start
- **postrun**: Log task completion
- **failure**: Log errors with traceback
- **success**: Log result
- **retry**: Log retry reason

**Lines of Code**: 143 lines

---

### 2. Video Processing Tasks (`app/tasks/video_tasks.py`)

**Task definitions** for video operations:

#### `generate_proxy_video`
- **Purpose**: Generate proxy video (480p, 10fps)
- **Queue**: video_processing
- **Max Retries**: 3
- **Retry Delay**: 5 minutes
- **Database**: Uses DatabaseTask base class with session management
- **Status**: Phase 2.4 placeholder (full implementation in Phase 2.5)

**Workflow**:
1. Get Video and ProcessingJob records
2. Update job status to 'running'
3. Store Celery task_id
4. [Phase 2.5] Download video, run FFmpeg, upload proxy
5. Update job status to 'completed'/'failed'
6. Store result_data in JSONB field

#### `extract_video_metadata`
- **Purpose**: Extract metadata using FFprobe
- **Status**: Phase 2.5 placeholder
- **Returns**: Width, height, fps, duration, codec

#### `generate_thumbnail`
- **Purpose**: Generate thumbnail image from video
- **Status**: Phase 2.5 placeholder
- **Args**: video_id, timestamp_seconds

**Base Class: DatabaseTask**
- Manages database session lifecycle
- Closes session after task completion
- Prevents connection leaks

**Lines of Code**: 186 lines

---

### 3. Maintenance Tasks (`app/tasks/maintenance_tasks.py`)

**Periodic tasks** for system health:

#### `cleanup_old_jobs`
- **Schedule**: Daily at 2 AM
- **Purpose**: Delete old completed/failed jobs
- **Default**: Keep jobs from last 30 days
- **Returns**: Deleted count, cutoff date

#### `check_stuck_jobs`
- **Schedule**: Every 15 minutes
- **Purpose**: Mark stuck jobs as failed
- **Threshold**: 120 minutes (2 hours)
- **Detects**:
  - Pending jobs queued too long
  - Running jobs with no progress
- **Action**: Mark as failed with watchdog message

#### `get_queue_stats`
- **Purpose**: Get job statistics
- **Returns**:
  - Status counts (pending, running, completed, failed)
  - Type counts (proxy_generation, cv_analysis)
  - Total count, timestamp

**Lines of Code**: 214 lines

---

### 4. Job Service (`app/services/job_service.py`)

**Service layer** for job management:

#### Job Creation
- `create_job()` - Create ProcessingJob record
- `queue_proxy_generation()` - Queue proxy gen task with Celery

#### Job Queries
- `get_job()` - Get job by ID
- `get_jobs_for_video()` - Get all jobs for a video
- `get_job_status()` - Get detailed status with duration
- `get_pending_jobs()` - Get pending jobs with filters

#### Job Cancellation
- `cancel_job()` - Cancel and revoke Celery task
- Revoke with SIGKILL signal
- Update job status to 'failed'
- Store cancellation reason

#### Job Cleanup
- `delete_old_jobs()` - Delete old jobs (called by maintenance task)

**Lines of Code**: 275 lines

---

### 5. Worker Management Scripts

#### `start_celery_worker.sh`
```bash
./scripts/start_celery_worker.sh [queue] [concurrency]

# Examples:
./scripts/start_celery_worker.sh                     # All queues, auto concurrency
./scripts/start_celery_worker.sh video_processing 2  # Video queue, 2 workers
./scripts/start_celery_worker.sh cv_analysis 4       # CV queue, 4 workers
```

#### `start_celery_beat.sh`
```bash
./scripts/start_celery_beat.sh

# Starts periodic task scheduler
# Runs cleanup and stuck job checks
```

#### `start_flower.sh`
```bash
./scripts/start_flower.sh [port]

# Starts Flower monitoring dashboard
# Default port: 5555
# Access at: http://localhost:5555
```

---

## Integration with Phase 2.3

### Upload Completion Flow

**Before Phase 2.4**:
```python
def complete_multipart_upload(...):
    result = upload_service.complete_upload(...)
    processing_job_id = None  # TODO
    return response
```

**After Phase 2.4**:
```python
def complete_multipart_upload(...):
    result = upload_service.complete_upload(...)

    # Queue proxy generation job
    processing_job = job_service.queue_proxy_generation(
        video_id=video_id,
        priority=5,
    )

    return MultipartUploadCompleteResponse(
        ...,
        processing_job_id=processing_job.id,  # Now returns actual job ID
    )
```

Client can now poll `/jobs/{job_id}/status` to track progress.

---

## Task Workflow Example

### Proxy Generation Task Lifecycle

```
1. Upload completes
   ├─> FastAPI endpoint calls job_service.queue_proxy_generation()
   └─> Creates ProcessingJob record with status='pending'

2. Celery queues task
   ├─> Task added to 'video_processing' queue in Redis
   └─> Updates ProcessingJob.celery_task_id

3. Worker picks up task
   ├─> Task status changes to 'running'
   ├─> Updates ProcessingJob.started_at
   └─> Stores worker info

4. Task executes
   ├─> Downloads video from S3
   ├─> Runs FFmpeg (Phase 2.5)
   ├─> Uploads proxy to S3
   └─> Extracts metadata

5. Task completes
   ├─> Updates ProcessingJob.status = 'completed'
   ├─> Sets ProcessingJob.completed_at
   ├─> Stores result_data (proxy_path, metadata)
   └─> Updates Video.proxy_generated = True

6. Client polls status
   ├─> GET /jobs/{job_id}/status
   └─> Returns completion details
```

---

## Configuration

### Environment Variables

Already configured in `.env`:
```env
# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

### Docker Compose

Redis service already running:
```yaml
redis:
  image: redis:7-alpine
  container_name: spatial-intel-redis
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
```

---

## Monitoring & Observability

### Flower Dashboard

Access at `http://localhost:5555` (when running):
- Real-time task monitoring
- Worker status and statistics
- Queue lengths
- Task execution times
- Task success/failure rates
- Task history

### Celery CLI Commands

```bash
# List active tasks
celery -A app.core.celery_app inspect active

# List registered tasks
celery -A app.core.celery_app inspect registered

# View queue stats
celery -A app.core.celery_app inspect stats

# Revoke a task
celery -A app.core.celery_app control revoke <task_id> --terminate

# Purge queue
celery -A app.core.celery_app purge -Q video_processing
```

### Database Queries

```sql
-- Get job statistics
SELECT status, COUNT(*)
FROM processing_jobs
GROUP BY status;

-- Get stuck jobs
SELECT id, job_type, status, queued_at, started_at
FROM processing_jobs
WHERE status IN ('pending', 'running')
  AND (
    (status = 'pending' AND queued_at < NOW() - INTERVAL '2 hours')
    OR (status = 'running' AND started_at < NOW() - INTERVAL '2 hours')
  );

-- Get average processing time
SELECT job_type,
       AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds
FROM processing_jobs
WHERE status = 'completed'
GROUP BY job_type;
```

---

## Error Handling

### Automatic Retries

Tasks with transient errors are automatically retried:
- **Max retries**: 3 (configurable per task)
- **Retry delay**: 5 minutes (exponential backoff optional)
- **Retry conditions**: Network errors, temporary S3 failures

### Stuck Job Detection

Watchdog task runs every 15 minutes:
1. Finds jobs pending/running > 2 hours
2. Marks them as failed
3. Stores watchdog message in error_message
4. Optionally revokes Celery task

### Dead Letter Handling

Failed tasks after max retries:
- Job status updated to 'failed'
- Error message stored in processing_jobs.error_message
- Client can query status and see error details
- Manual intervention required for resolution

---

## Performance Considerations

### Worker Configuration

**Video Processing Queue**:
- Concurrency: 2 (video processing is CPU/IO intensive)
- Prefetch: 1 task at a time
- Max tasks per child: 10 (prevent memory leaks)

**CV Analysis Queue** (future):
- Concurrency: 4 (parallelizable)
- Prefetch: 1
- Max tasks per child: 5 (memory intensive)

**Maintenance Queue**:
- Concurrency: 1 (sequential processing)
- Low priority

### Resource Management

- Workers restart after 10 tasks (memory cleanup)
- Task time limits prevent runaway processes
- Late acknowledgment ensures task completion
- Database sessions closed after each task

### Scaling Strategy

Horizontal scaling:
```bash
# Add more workers for video processing
./scripts/start_celery_worker.sh video_processing 2  # Worker 1
./scripts/start_celery_worker.sh video_processing 2  # Worker 2
./scripts/start_celery_worker.sh video_processing 2  # Worker 3

# Total: 6 concurrent video processing tasks
```

---

## Testing Strategy

### Manual Testing

1. **Queue a job**:
   ```python
   from app.services.job_service import get_job_service
   from app.core.database import SessionLocal

   db = SessionLocal()
   job_service = get_job_service(db)

   job = job_service.queue_proxy_generation(video_id=uuid.UUID("..."))
   print(f"Job queued: {job.id}")
   ```

2. **Start worker**:
   ```bash
   ./scripts/start_celery_worker.sh video_processing 1
   ```

3. **Monitor with Flower**:
   ```bash
   ./scripts/start_flower.sh
   # Open http://localhost:5555
   ```

4. **Check job status**:
   ```python
   status = job_service.get_job_status(job.id)
   print(status)
   ```

### Integration Tests (To Be Created)

- Test job creation
- Test job queueing
- Test task execution (mocked FFmpeg)
- Test error handling and retries
- Test job cancellation
- Test stuck job detection
- Test cleanup tasks

---

## Files Changed

### New Files
- ✅ `app/core/celery_app.py` (143 lines)
- ✅ `app/tasks/__init__.py` (15 lines)
- ✅ `app/tasks/video_tasks.py` (186 lines)
- ✅ `app/tasks/maintenance_tasks.py` (214 lines)
- ✅ `app/services/job_service.py` (275 lines)
- ✅ `scripts/start_celery_worker.sh` (executable)
- ✅ `scripts/start_celery_beat.sh` (executable)
- ✅ `scripts/start_flower.sh` (executable)
- ✅ `backend/docs/phase_2.4_celery_job_queue_summary.md` (this file)

### Modified Files
- ✅ `requirements.txt` (+2 lines: celery, flower)
- ✅ `app/services/__init__.py` (exported JobService)
- ✅ `app/api/v1/videos.py` (integrated job queueing in complete endpoint)

### Infrastructure
- ✅ Redis already running in Docker (Phase 1)
- ✅ ProcessingJob model already exists (Phase 2.1)

---

## Acceptance Criteria

All Phase 2.4 acceptance criteria met:

- [x] ✅ Celery application configured with production settings
- [x] ✅ Task routing to separate queues (video_processing, cv_analysis, maintenance)
- [x] ✅ Video processing tasks defined (placeholder for Phase 2.5)
- [x] ✅ Maintenance tasks (cleanup, stuck job detection)
- [x] ✅ Job service for job management
- [x] ✅ Worker management scripts (worker, beat, flower)
- [x] ✅ Integration with upload API (queue job on completion)
- [x] ✅ Beat scheduler for periodic tasks
- [x] ✅ Flower monitoring dashboard
- [x] ✅ Automatic retries with backoff
- [x] ✅ Stuck job watchdog
- [x] ✅ Comprehensive logging and signals

---

## Next Steps (Phase 2.5)

With background job queue in place, Phase 2.5 will implement:

1. **FFmpeg Integration**:
   - Install FFmpeg in Docker container
   - Create FFmpeg wrapper service
   - Implement proxy generation (480p, 10fps)
   - Implement metadata extraction (FFprobe)
   - Implement thumbnail generation

2. **Complete Video Tasks**:
   - Replace placeholder code in generate_proxy_video()
   - Implement extract_video_metadata()
   - Implement generate_thumbnail()

3. **Storage Integration**:
   - Download video from S3
   - Upload proxy to S3
   - Upload thumbnail to S3

4. **Testing**:
   - End-to-end proxy generation test
   - Performance benchmarks
   - Error handling tests

---

**Phase 2.4 Status**: ✅ COMPLETE

**Ready for**: Phase 2.5 - FFmpeg Proxy Generation Pipeline

---

**Document Version**: 1.0
**Last Updated**: 2025-10-31 21:30:00
