#!/usr/bin/env python3
"""
Verification script for Phase 2.1 database schema.

This script validates that:
1. Videos table has all required Phase 2 columns
2. ProcessingJobs table exists with correct structure
3. All indexes are created properly
4. Unique constraint on (checksum_sha256, pin_id) works
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import inspect, text
from app.core.database import engine, SessionLocal
from app.models import Video, ProcessingJob

def check_table_columns(table_name, expected_columns):
    """Check if table has all expected columns."""
    inspector = inspect(engine)
    columns = {col['name']: col for col in inspector.get_columns(table_name)}

    print(f"\n📋 Checking {table_name} columns...")
    missing = []
    for col_name in expected_columns:
        if col_name in columns:
            print(f"  ✅ {col_name}")
        else:
            print(f"  ❌ {col_name} - MISSING")
            missing.append(col_name)

    return len(missing) == 0

def check_table_indexes(table_name, expected_indexes):
    """Check if table has all expected indexes."""
    inspector = inspect(engine)
    indexes = {idx['name']: idx for idx in inspector.get_indexes(table_name)}

    print(f"\n🔍 Checking {table_name} indexes...")
    missing = []
    for idx_name in expected_indexes:
        if idx_name in indexes:
            print(f"  ✅ {idx_name}")
        else:
            print(f"  ❌ {idx_name} - MISSING")
            missing.append(idx_name)

    return len(missing) == 0

def test_unique_constraint():
    """Test the unique constraint on (checksum_sha256, pin_id)."""
    print(f"\n🧪 Testing unique constraint on (checksum_sha256, pin_id)...")

    db = SessionLocal()
    try:
        # This query should work without errors
        query = text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'videos'
            AND indexname = 'ix_videos_unique_checksum_pin'
        """)
        result = db.execute(query).fetchone()

        if result:
            print(f"  ✅ Unique constraint index exists")
            print(f"     {result[1]}")
            return True
        else:
            print(f"  ❌ Unique constraint index NOT found")
            return False
    finally:
        db.close()

def verify_models_load():
    """Verify that SQLAlchemy models load correctly."""
    print(f"\n🏗️  Verifying SQLAlchemy models...")

    try:
        # Try to access model attributes
        video_columns = [c.name for c in Video.__table__.columns]
        job_columns = [c.name for c in ProcessingJob.__table__.columns]

        print(f"  ✅ Video model loaded ({len(video_columns)} columns)")
        print(f"  ✅ ProcessingJob model loaded ({len(job_columns)} columns)")
        return True
    except Exception as e:
        print(f"  ❌ Model loading failed: {e}")
        return False

def main():
    """Run all verification checks."""
    print("=" * 60)
    print("Phase 2.1 Database Schema Verification")
    print("=" * 60)

    all_passed = True

    # Check if models load
    all_passed &= verify_models_load()

    # Check videos table columns
    videos_columns = [
        'id', 'mall_id', 'pin_id', 'camera_pin_id',
        'filename', 'original_path', 'proxy_path',
        'file_size_bytes', 'duration_seconds', 'checksum_sha256',
        'width', 'height', 'fps', 'codec',
        'recorded_at', 'operator_notes', 'uploaded_by_user_id',
        'upload_status', 'processing_status', 'processing_job_id', 'processing_error',
        'uploaded_at', 'processing_started_at', 'processing_completed_at',
        'created_at', 'updated_at',
        # Legacy fields
        'file_path', 'original_filename', 'processed', 'upload_timestamp'
    ]
    all_passed &= check_table_columns('videos', videos_columns)

    # Check videos table indexes
    videos_indexes = [
        'ix_videos_camera_pin_id',
        'ix_videos_processing_status',
        'ix_videos_mall_id',
        'ix_videos_pin_id',
        'ix_videos_checksum',
        'ix_videos_uploaded_at',
        'ix_videos_recorded_at',
        'ix_videos_upload_status',
        'ix_videos_unique_checksum_pin'
    ]
    all_passed &= check_table_indexes('videos', videos_indexes)

    # Check processing_jobs table columns
    jobs_columns = [
        'id', 'video_id', 'job_type', 'status',
        'celery_task_id', 'worker_hostname',
        'result_data', 'error_message',
        'queued_at', 'started_at', 'completed_at'
    ]
    all_passed &= check_table_columns('processing_jobs', jobs_columns)

    # Check processing_jobs table indexes
    jobs_indexes = [
        'ix_jobs_video_id',
        'ix_jobs_status',
        'ix_jobs_celery_task_id',
        'ix_jobs_queued_at'
    ]
    all_passed &= check_table_indexes('processing_jobs', jobs_indexes)

    # Test unique constraint
    all_passed &= test_unique_constraint()

    # Final result
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ All Phase 2.1 schema checks PASSED")
        print("=" * 60)
        return 0
    else:
        print("❌ Some Phase 2.1 schema checks FAILED")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
