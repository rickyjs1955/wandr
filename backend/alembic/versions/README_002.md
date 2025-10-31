# Phase 2.1: Video Management Schema Migration

**Migration ID**: `002_phase_2_video_mgmt`
**Revises**: `839d4ee251e4` (Initial schema)
**Created**: 2025-10-31

---

## Overview

This migration extends the video management system to support Phase 2 features:
- ✅ Multipart upload with checksum deduplication
- ✅ Extended metadata (recorded_at, operator_notes, uploader tracking)
- ✅ Separate original and proxy video paths
- ✅ Enhanced status tracking (upload_status + processing_status)
- ✅ Background job tracking via processing_jobs table

---

## Changes Summary

### 1. Videos Table Extensions

**New Columns**:
- `mall_id` (UUID, NOT NULL) - Direct mall reference for queries
- `pin_id` (UUID, NOT NULL) - Direct pin reference (mirrors camera_pin_id)
- `filename` (VARCHAR(255), NOT NULL) - Original filename
- `original_path` (VARCHAR(512)) - S3 path to original video
- `proxy_path` (VARCHAR(512)) - S3 path to 480p/10fps proxy
- `checksum_sha256` (VARCHAR(64)) - SHA256 for deduplication
- `width`, `height`, `fps`, `codec` - Video properties from ffprobe
- `recorded_at` (TIMESTAMPTZ) - Actual CCTV recording time
- `operator_notes` (TEXT) - Context notes from uploader
- `uploaded_by_user_id` (UUID) - Audit trail
- `upload_status` (VARCHAR(20), NOT NULL) - uploading/uploaded/failed
- `processing_job_id` (VARCHAR(255)) - Link to Celery task
- `processing_error` (TEXT) - Error details if failed
- `uploaded_at` (TIMESTAMPTZ, NOT NULL) - Upload completion time
- `processing_started_at` (TIMESTAMPTZ) - When processing began
- `processing_completed_at` (TIMESTAMPTZ) - When processing finished
- `updated_at` (TIMESTAMPTZ, NOT NULL) - Last modification time

**Legacy Columns (Kept for Compatibility)**:
- `file_path` - Now use `original_path`
- `original_filename` - Now use `filename`
- `processed` - Now use `processing_status='completed'`
- `upload_timestamp` - Now use `uploaded_at`
- `camera_pin_id` - Now use `pin_id`

**New Indexes**:
- `ix_videos_mall_id` - Fast mall-level queries
- `ix_videos_pin_id` - Fast pin-level queries
- `ix_videos_checksum` - Duplicate detection
- `ix_videos_uploaded_at` (DESC) - Recent videos first
- `ix_videos_recorded_at` (DESC) - Chronological playback
- `ix_videos_upload_status` - Filter by upload state
- `ix_videos_unique_checksum_pin` (UNIQUE) - Prevent duplicate uploads per pin

**Foreign Keys**:
- `fk_videos_mall_id` → malls(id) CASCADE
- `fk_videos_pin_id` → camera_pins(id) CASCADE
- `fk_videos_uploaded_by` → users(id) SET NULL

---

### 2. Processing Jobs Table (New)

Tracks background Celery tasks for video processing.

**Columns**:
- `id` (UUID, PK) - Job identifier
- `video_id` (UUID, NOT NULL, FK) - Associated video
- `job_type` (VARCHAR(50), NOT NULL) - 'proxy_generation', 'cv_analysis', etc.
- `status` (VARCHAR(20), NOT NULL) - pending/running/completed/failed/cancelled
- `celery_task_id` (VARCHAR(255)) - Celery task UUID
- `worker_hostname` (VARCHAR(255)) - Which worker processed it
- `result_data` (JSONB) - Job-specific results
- `error_message` (TEXT) - Error details if failed
- `queued_at` (TIMESTAMPTZ, NOT NULL) - When job was created
- `started_at` (TIMESTAMPTZ) - When worker picked it up
- `completed_at` (TIMESTAMPTZ) - When job finished

**Indexes**:
- `ix_jobs_video_id` - Find jobs for video
- `ix_jobs_status` - Filter by status
- `ix_jobs_celery_task_id` - Celery task lookup
- `ix_jobs_queued_at` (DESC) - Recent jobs first

**Foreign Keys**:
- `video_id` → videos(id) CASCADE (delete jobs when video deleted)

---

## Running the Migration

### Prerequisites

1. **Backup database** (important!):
   ```bash
   pg_dump -U spatial_user spatial_intel > backup_before_phase2.sql
   ```

2. **Ensure PostgreSQL running**:
   ```bash
   docker ps | grep postgres  # or check local PostgreSQL
   ```

### Apply Migration

```bash
cd /Users/jinglitsoong/wandr/backend

# Check current migration status
alembic current

# Preview upgrade SQL (dry run)
alembic upgrade 002_phase_2_video_mgmt --sql

# Apply migration
alembic upgrade head

# Verify migration applied
alembic current
# Should show: 002_phase_2_video_mgmt
```

### Verify Schema

```bash
# Run verification script
python scripts/verify_phase2_schema.py

# Or manually check with psql
psql -U spatial_user -d spatial_intel -c "\d videos"
psql -U spatial_user -d spatial_intel -c "\d processing_jobs"
```

---

## Data Migration

The migration automatically migrates existing data:

```sql
UPDATE videos v
SET mall_id = cp.mall_id,
    pin_id = v.camera_pin_id,
    filename = v.original_filename,
    original_path = v.file_path,
    upload_status = 'uploaded',
    uploaded_at = v.upload_timestamp,
    updated_at = v.created_at
FROM camera_pins cp
WHERE v.camera_pin_id = cp.id
```

**What happens**:
- `mall_id` populated from camera_pins.mall_id
- `pin_id` mirrors camera_pin_id
- `filename` copies original_filename
- `original_path` copies file_path
- `upload_status` set to 'uploaded' (existing videos are already uploaded)
- `uploaded_at` copies upload_timestamp
- `updated_at` copies created_at

**Legacy columns remain unchanged** for backward compatibility.

---

## Rollback Plan

If you need to rollback:

```bash
# Downgrade to previous migration
alembic downgrade -1

# Or downgrade to specific revision
alembic downgrade 839d4ee251e4
```

**⚠️ WARNING**: Rollback will **delete**:
- All data in `processing_jobs` table
- All Phase 2 metadata (checksums, operator_notes, etc.)
- The table itself

**Legacy columns remain**, so Phase 1 functionality will work after rollback.

---

## Testing Checklist

After migration, test:

- [ ] Migration applied successfully (`alembic current` shows `002_phase_2_video_mgmt`)
- [ ] `videos` table has all new columns
- [ ] `processing_jobs` table exists
- [ ] All indexes created (run verification script)
- [ ] Unique constraint works (try inserting duplicate checksum)
- [ ] Foreign keys enforced (try inserting invalid mall_id)
- [ ] Existing videos migrated correctly (check mall_id, pin_id populated)
- [ ] SQLAlchemy models load (Python: `from app.models import Video, ProcessingJob`)
- [ ] Relationships work (`video.mall`, `video.processing_jobs`)

---

## Common Issues & Solutions

### Issue: Migration fails with "column already exists"

**Cause**: Migration was partially applied or schema manually modified.

**Solution**:
```bash
# Mark migration as applied without running SQL
alembic stamp 002_phase_2_video_mgmt

# Or rollback and re-apply
alembic downgrade -1
alembic upgrade head
```

### Issue: "violates foreign key constraint"

**Cause**: Existing videos have invalid camera_pin_id references.

**Solution**:
```sql
-- Find orphaned videos
SELECT id, camera_pin_id FROM videos v
WHERE NOT EXISTS (SELECT 1 FROM camera_pins cp WHERE cp.id = v.camera_pin_id);

-- Delete orphaned videos or fix references
DELETE FROM videos WHERE id IN (...);
```

### Issue: Unique constraint fails on NULL checksum

**Cause**: Unique index should allow NULL checksums (not duplicates).

**Solution**: Migration includes `WHERE checksum_sha256 IS NOT NULL` clause. Verify:
```sql
SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_videos_unique_checksum_pin';
-- Should see: WHERE (checksum_sha256 IS NOT NULL)
```

---

## Next Steps

After successful migration:

1. **Update API code** to use new fields:
   - Use `upload_status` instead of `processed`
   - Use `uploaded_at` instead of `upload_timestamp`
   - Use `pin_id` instead of `camera_pin_id`

2. **Update frontend** to populate new fields:
   - Send `checksum_sha256` during upload
   - Allow operators to enter `recorded_at` and `operator_notes`

3. **Proceed to Phase 2.2**: Object Storage Infrastructure (MinIO setup)

---

**Migration Author**: Phase 2 Development Team
**Review Date**: 2025-10-31
**Status**: ✅ Ready for Testing
