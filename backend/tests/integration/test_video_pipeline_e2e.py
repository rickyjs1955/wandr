"""
End-to-End Integration Tests for Video Management Pipeline

Tests the complete video lifecycle:
1. Multipart upload initiation
2. Part upload to S3
3. Upload completion
4. Proxy generation (FFmpeg processing)
5. Video streaming URL generation
6. Video deletion with cleanup

Run with: pytest backend/tests/integration/test_video_pipeline_e2e.py -v
"""

import pytest
import os
import time
import hashlib
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.services.storage_service import get_storage_service
from app.services.upload_service import get_upload_service
from app.services.video_service import get_video_service
from app.services.ffmpeg_service import get_ffmpeg_service
from app.models import Video, ProcessingJob, Mall, CameraPin
from app.core.database import get_db


@pytest.fixture
def test_mall(db_session):
    """Create test mall."""
    mall = Mall(
        id="test-mall-e2e",
        name="Test Mall E2E",
        geojson_map={"type": "FeatureCollection", "features": []}
    )
    db_session.add(mall)
    db_session.commit()
    yield mall
    db_session.delete(mall)
    db_session.commit()


@pytest.fixture
def test_pin(db_session, test_mall):
    """Create test camera pin."""
    pin = CameraPin(
        id=uuid.uuid4(),
        mall_id=test_mall.id,
        name="Test Camera E2E",
        label="Entrance A",
        location_lat=1.3521,
        location_lng=103.8198,
        pin_type="entrance"
    )
    db_session.add(pin)
    db_session.commit()
    yield pin
    db_session.delete(pin)
    db_session.commit()


@pytest.fixture
def test_video_file(tmp_path):
    """
    Create a small test video file using FFmpeg.

    Creates a 10-second 480p test video with color bars.
    """
    video_path = tmp_path / "test_video.mp4"

    # Generate test video with FFmpeg (10 seconds, 480p, 10fps)
    import subprocess
    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", "testsrc=duration=10:size=854x480:rate=10",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=10",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-y",
        str(video_path)
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        pytest.skip(f"FFmpeg not available or failed: {e}")

    yield video_path

    # Cleanup
    if video_path.exists():
        video_path.unlink()


@pytest.fixture
def compute_checksum():
    """Helper function to compute SHA-256 checksum."""
    def _compute(file_path):
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()
    return _compute


class TestVideoPipelineE2E:
    """End-to-end tests for complete video pipeline."""

    def test_full_upload_process_stream_workflow(
        self,
        db_session,
        test_mall,
        test_pin,
        test_video_file,
        compute_checksum
    ):
        """
        Test complete workflow: Initiate → Upload → Complete → Process → Stream → Delete

        This is the primary happy-path test covering the entire video lifecycle.
        """
        storage = get_storage_service()
        upload_service = get_upload_service(db_session)
        video_service = get_video_service(db_session)

        # Step 1: Compute checksum
        checksum = compute_checksum(test_video_file)
        file_size = test_video_file.stat().st_size

        # Step 2: Initiate multipart upload
        init_response = upload_service.initiate_upload(
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            filename="test_video_e2e.mp4",
            file_size_bytes=file_size,
            checksum_sha256=checksum,
            metadata={
                "recorded_at": datetime.utcnow().isoformat(),
                "operator_notes": "E2E test video"
            }
        )

        video_id = init_response["video_id"]
        upload_id = init_response["upload_id"]
        presigned_urls = init_response["presigned_urls"]
        part_size = init_response["part_size_bytes"]

        assert video_id is not None
        assert upload_id is not None
        assert len(presigned_urls) > 0

        # Step 3: Upload parts to S3 (simulate frontend upload)
        parts = []
        with open(test_video_file, 'rb') as f:
            for url_info in presigned_urls:
                part_number = url_info["part_number"]
                presigned_url = url_info["url"]

                # Read chunk
                chunk = f.read(part_size)
                if not chunk:
                    break

                # Upload to S3 using presigned URL (simulate with storage service)
                # In real scenario, frontend does PUT request to presigned URL
                # For testing, we'll use storage service directly
                s3_path = f"{test_mall.id}/{test_pin.id}/{video_id}/original.mp4"

                # Upload entire file for testing (in production, parts are uploaded separately)
                if part_number == 1:
                    storage.upload_file(str(test_video_file), s3_path)

                # Simulate ETag (S3 returns this after successful upload)
                etag = f'"etag-{part_number}"'
                parts.append({"part_number": part_number, "etag": etag})

        # Step 4: Complete multipart upload
        complete_response = upload_service.complete_multipart_upload(
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            video_id=video_id,
            upload_id=upload_id,
            parts=parts
        )

        assert complete_response["upload_status"] == "uploaded"
        assert complete_response["processing_status"] == "pending"
        assert complete_response["processing_job_id"] is not None

        job_id = complete_response["processing_job_id"]

        # Step 5: Wait for processing to start and complete (or run synchronously for testing)
        # In production, Celery worker processes this asynchronously
        # For testing, we can run the task synchronously
        from app.tasks.video_tasks import generate_proxy_video

        # Get video record
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is not None
        assert video.upload_status == "uploaded"

        # Run proxy generation synchronously
        try:
            result = generate_proxy_video.apply(kwargs={
                "video_id": str(video_id),
                "job_id": str(job_id)
            }).get(timeout=60)  # 60 second timeout

            assert result["success"] is True
            assert "proxy_path" in result
        except Exception as e:
            pytest.fail(f"Proxy generation failed: {e}")

        # Refresh video from database
        db_session.refresh(video)

        # Verify processing completed
        assert video.processing_status == "completed"
        assert video.proxy_path is not None
        assert video.duration_seconds is not None
        assert video.width is not None
        assert video.height is not None

        # Step 6: Generate streaming URL
        stream_url, expires_at = video_service.generate_stream_url(
            video_id=video_id,
            stream_type="proxy",
            expires_minutes=60
        )

        assert stream_url is not None
        assert expires_at is not None
        assert expires_at > datetime.utcnow()

        # Step 7: Verify proxy file exists in storage
        assert storage.file_exists(video.proxy_path)

        # Step 8: Get thumbnail URL
        thumbnail_url, thumbnail_expires = video_service.generate_thumbnail_url(
            video_id=video_id,
            expires_minutes=60
        )

        assert thumbnail_url is not None

        # Step 9: Delete video (cascade cleanup)
        success, deleted_files = video_service.delete_video(
            video_id=video_id,
            delete_from_storage=True
        )

        assert success is True
        assert len(deleted_files) > 0

        # Verify video deleted from database
        video = db_session.query(Video).filter(Video.id == video_id).first()
        assert video is None

        # Verify processing job deleted (cascade)
        job = db_session.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        assert job is None

    def test_duplicate_upload_detection(
        self,
        db_session,
        test_mall,
        test_pin,
        test_video_file,
        compute_checksum
    ):
        """
        Test duplicate upload detection via checksum.

        Verifies that uploading the same file twice returns the existing video_id.
        """
        upload_service = get_upload_service(db_session)

        checksum = compute_checksum(test_video_file)
        file_size = test_video_file.stat().st_size

        # First upload
        init_response_1 = upload_service.initiate_multipart_upload(
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            filename="test_duplicate.mp4",
            file_size_bytes=file_size,
            checksum_sha256=checksum,
            metadata={}
        )

        video_id_1 = init_response_1["video_id"]

        # Second upload with same checksum (should detect duplicate)
        init_response_2 = upload_service.initiate_multipart_upload(
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            filename="test_duplicate_2.mp4",  # Different filename
            file_size_bytes=file_size,
            checksum_sha256=checksum,  # Same checksum
            metadata={}
        )

        video_id_2 = init_response_2["video_id"]

        # Should return same video ID
        assert video_id_1 == video_id_2
        assert init_response_2.get("duplicate") is True

    def test_stuck_upload_cleanup(self, db_session, test_mall, test_pin):
        """
        Test stuck upload cleanup (uploads that never complete).

        Simulates an upload that was initiated but never completed.
        """
        from app.tasks.maintenance_tasks import check_stuck_jobs

        # Create a video record in "uploading" state from 7 hours ago
        stuck_video = Video(
            id="stuck-video-123",
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            original_filename="stuck_upload.mp4",
            file_size_bytes=1000000,
            checksum_sha256="abc123",
            upload_status="uploading",
            processing_status="pending",
            created_at=datetime.utcnow() - timedelta(hours=7)
        )
        db_session.add(stuck_video)
        db_session.commit()

        # Run stuck job cleanup
        result = check_stuck_jobs.apply(kwargs={"stuck_threshold_minutes": 360}).get()

        assert result["status"] == "completed"
        assert result["stuck_count"] > 0

        # Verify video marked as failed
        db_session.refresh(stuck_video)
        assert stuck_video.upload_status == "failed"
        assert "timed out" in stuck_video.processing_error.lower()

    def test_video_list_with_filters(self, db_session, test_mall, test_pin):
        """
        Test video listing with status and date filters.
        """
        video_service = get_video_service(db_session)

        # Create test videos with different statuses
        videos = [
            Video(
                id=f"video-{i}",
                mall_id=test_mall.id,
                pin_id=test_pin.id,
                original_filename=f"test_{i}.mp4",
                file_size_bytes=1000000,
                processing_status=status,
                uploaded_at=datetime.utcnow() - timedelta(days=i)
            )
            for i, status in enumerate(["completed", "processing", "pending", "failed"])
        ]

        for video in videos:
            db_session.add(video)
        db_session.commit()

        # Test: List all videos
        all_videos, total = video_service.list_videos(
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            page=1,
            page_size=20
        )
        assert total == 4
        assert len(all_videos) == 4

        # Test: Filter by status
        completed_videos, count = video_service.list_videos(
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            processing_status="completed",
            page=1,
            page_size=20
        )
        assert count == 1
        assert completed_videos[0].processing_status == "completed"

        # Test: Filter by date range
        recent_videos, count = video_service.list_videos(
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            uploaded_after=datetime.utcnow() - timedelta(days=2),
            page=1,
            page_size=20
        )
        assert count == 2  # Videos 0 and 1

        # Cleanup
        for video in videos:
            db_session.delete(video)
        db_session.commit()

    def test_video_deletion_cascade(self, db_session, test_mall, test_pin):
        """
        Test that deleting a video cascades to processing jobs.
        """
        video_service = get_video_service(db_session)

        # Create video and processing job
        video = Video(
            id="video-delete-test",
            mall_id=test_mall.id,
            pin_id=test_pin.id,
            original_filename="delete_test.mp4",
            original_path="test/path/original.mp4",
            file_size_bytes=1000000,
            processing_status="completed"
        )
        db_session.add(video)
        db_session.commit()

        job = ProcessingJob(
            id="job-delete-test",
            video_id=video.id,
            job_type="proxy_generation",
            status="completed"
        )
        db_session.add(job)
        db_session.commit()

        # Delete video (without storage cleanup for testing)
        success, deleted_files = video_service.delete_video(
            video_id=video.id,
            delete_from_storage=False
        )

        assert success is True

        # Verify video deleted
        video_check = db_session.query(Video).filter(Video.id == video.id).first()
        assert video_check is None

        # Verify job deleted (cascade)
        job_check = db_session.query(ProcessingJob).filter(ProcessingJob.id == job.id).first()
        assert job_check is None


class TestFFmpegProcessing:
    """Tests for FFmpeg video processing."""

    def test_proxy_generation(self, test_video_file, tmp_path):
        """
        Test proxy video generation with FFmpeg.

        Verifies that:
        - Proxy is 480p
        - Frame rate is 10fps
        - Codec is H.264
        - File size is smaller than original
        """
        ffmpeg_service = get_ffmpeg_service()

        proxy_path = tmp_path / "proxy.mp4"

        # Generate proxy
        result = ffmpeg_service.generate_proxy(
            input_path=str(test_video_file),
            output_path=str(proxy_path),
            target_height=480,
            target_fps=10
        )

        assert result["success"] is True
        assert proxy_path.exists()

        # Extract metadata from proxy
        proxy_metadata = ffmpeg_service.extract_metadata(str(proxy_path))

        assert proxy_metadata["height"] == 480
        assert abs(proxy_metadata["fps"] - 10) < 1  # Allow small variance
        assert proxy_metadata["codec"] == "h264"

        # Verify file size reduction
        original_size = test_video_file.stat().st_size
        proxy_size = proxy_path.stat().st_size
        assert proxy_size < original_size

        # Cleanup
        proxy_path.unlink()

    def test_thumbnail_generation(self, test_video_file, tmp_path):
        """
        Test thumbnail generation at specified timestamp.
        """
        ffmpeg_service = get_ffmpeg_service()

        thumbnail_path = tmp_path / "thumbnail.jpg"

        # Generate thumbnail at 5 seconds
        result = ffmpeg_service.generate_thumbnail(
            input_path=str(test_video_file),
            output_path=str(thumbnail_path),
            timestamp_seconds=5.0,
            width=320
        )

        assert result["success"] is True
        assert thumbnail_path.exists()
        assert thumbnail_path.stat().st_size > 0

        # Cleanup
        thumbnail_path.unlink()

    def test_metadata_extraction(self, test_video_file):
        """
        Test video metadata extraction with FFprobe.
        """
        ffmpeg_service = get_ffmpeg_service()

        metadata = ffmpeg_service.extract_metadata(str(test_video_file))

        assert metadata["width"] > 0
        assert metadata["height"] > 0
        assert metadata["fps"] > 0
        assert metadata["duration_seconds"] > 0
        assert metadata["codec"] is not None
        assert metadata["file_size_bytes"] > 0


class TestStorageOperations:
    """Tests for S3/MinIO storage operations."""

    def test_upload_download_roundtrip(self, test_video_file, tmp_path):
        """
        Test upload to S3 and download back.
        """
        storage = get_storage_service()

        s3_path = "test/roundtrip/video.mp4"
        download_path = tmp_path / "downloaded.mp4"

        # Upload
        storage.upload_file(str(test_video_file), s3_path)

        # Verify file exists
        assert storage.file_exists(s3_path)

        # Download
        storage.download_file(s3_path, str(download_path))

        # Verify downloaded file matches original
        assert download_path.exists()
        assert download_path.stat().st_size == test_video_file.stat().st_size

        # Cleanup
        storage.delete_file(s3_path)
        download_path.unlink()

    def test_presigned_url_generation(self, test_video_file):
        """
        Test presigned URL generation for GET requests.
        """
        storage = get_storage_service()

        s3_path = "test/presigned/video.mp4"

        # Upload file
        storage.upload_file(str(test_video_file), s3_path)

        # Generate presigned URL
        presigned_url = storage.generate_presigned_get_url(
            s3_path,
            expires=timedelta(minutes=60)
        )

        assert presigned_url is not None
        assert "Signature" in presigned_url or "X-Amz-Signature" in presigned_url

        # Cleanup
        storage.delete_file(s3_path)


# Pytest configuration
@pytest.fixture(scope="session")
def db_session():
    """Create database session for tests."""
    # This should be configured in conftest.py
    # For now, use a placeholder
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
