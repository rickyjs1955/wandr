"""
Unit tests for storage service.

Tests S3/MinIO operations including:
- Bucket initialization
- File upload/download
- Multipart upload workflow
- Presigned URL generation
- File management (exists, delete, metadata)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import timedelta
import uuid

from app.services.storage_service import StorageService, get_storage_service
from minio.error import S3Error


@pytest.fixture
def mock_minio_client():
    """Mock MinIO client for testing."""
    with patch("app.services.storage_service.Minio") as mock:
        client = Mock()
        mock.return_value = client
        yield client


@pytest.fixture
def storage_service(mock_minio_client):
    """Create storage service instance with mocked MinIO client."""
    service = StorageService()
    return service


class TestBucketInitialization:
    """Test bucket creation and initialization."""

    def test_initialize_new_bucket(self, storage_service, mock_minio_client):
        """Test creating a new bucket when it doesn't exist."""
        mock_minio_client.bucket_exists.return_value = False

        storage_service.initialize_bucket()

        mock_minio_client.bucket_exists.assert_called_once_with("spatial-intel-videos")
        mock_minio_client.make_bucket.assert_called_once_with("spatial-intel-videos")
        assert storage_service.initialized is True

    def test_initialize_existing_bucket(self, storage_service, mock_minio_client):
        """Test when bucket already exists."""
        mock_minio_client.bucket_exists.return_value = True

        storage_service.initialize_bucket()

        mock_minio_client.bucket_exists.assert_called_once()
        mock_minio_client.make_bucket.assert_not_called()
        assert storage_service.initialized is True

    def test_initialize_bucket_error(self, storage_service, mock_minio_client):
        """Test error handling during bucket creation."""
        mock_minio_client.bucket_exists.side_effect = S3Error(
            "TestError",
            "Bucket creation failed",
            "resource",
            "request_id",
            "host_id",
            Mock(),
        )

        with pytest.raises(RuntimeError, match="Storage initialization failed"):
            storage_service.initialize_bucket()

    def test_ensure_initialized(self, storage_service, mock_minio_client):
        """Test auto-initialization when not initialized."""
        mock_minio_client.bucket_exists.return_value = True
        assert storage_service.initialized is False

        storage_service.ensure_initialized()

        assert storage_service.initialized is True


class TestMultipartUpload:
    """Test multipart upload operations."""

    def test_initiate_multipart_upload(self, storage_service, mock_minio_client):
        """Test initiating a multipart upload session."""
        mock_minio_client.bucket_exists.return_value = True

        upload_id = storage_service.initiate_multipart_upload(
            "videos/test.mp4",
            content_type="video/mp4",
            metadata={"mall_id": "001"},
        )

        assert upload_id is not None
        assert isinstance(upload_id, str)
        # Should be a valid UUID
        uuid.UUID(upload_id)

    def test_generate_presigned_upload_url(self, storage_service, mock_minio_client):
        """Test generating presigned URL for part upload."""
        mock_minio_client.bucket_exists.return_value = True
        mock_minio_client.presigned_put_object.return_value = "https://minio.example.com/bucket/object?signature=xyz"

        upload_id = "test-upload-123"
        url = storage_service.generate_presigned_upload_url(
            "videos/test.mp4",
            upload_id=upload_id,
            part_number=1,
            expires=timedelta(hours=1),
        )

        assert url == "https://minio.example.com/bucket/object?signature=xyz"
        mock_minio_client.presigned_put_object.assert_called_once()
        call_args = mock_minio_client.presigned_put_object.call_args
        assert call_args[0][0] == "spatial-intel-videos"
        # Verify part object name includes upload_id for session isolation
        assert call_args[0][1] == f"videos/test.mp4.{upload_id}.part1"

    def test_complete_multipart_upload(self, storage_service, mock_minio_client):
        """Test completing a multipart upload."""
        mock_minio_client.bucket_exists.return_value = True

        # Mock compose_object result
        mock_result = Mock()
        mock_result.etag = "abc123"
        mock_result.version_id = "v1"
        mock_minio_client.compose_object.return_value = mock_result

        parts = [
            {"part_number": 1, "etag": "etag1"},
            {"part_number": 2, "etag": "etag2"},
        ]

        result = storage_service.complete_multipart_upload(
            "videos/test.mp4",
            "upload-123",
            parts,
        )

        assert result["object_name"] == "videos/test.mp4"
        assert result["etag"] == "abc123"
        assert result["version_id"] == "v1"
        mock_minio_client.compose_object.assert_called_once()

    def test_abort_multipart_upload(self, storage_service, mock_minio_client):
        """Test aborting a multipart upload."""
        mock_minio_client.bucket_exists.return_value = True

        upload_id = "upload-123"
        # Mock list_objects to return part objects with namespaced upload_id
        mock_obj1 = Mock()
        mock_obj1.object_name = f"videos/test.mp4.{upload_id}.part1"
        mock_obj2 = Mock()
        mock_obj2.object_name = f"videos/test.mp4.{upload_id}.part2"
        mock_minio_client.list_objects.return_value = [mock_obj1, mock_obj2]

        storage_service.abort_multipart_upload("videos/test.mp4", upload_id)

        # Should list objects with upload_id-namespaced prefix (session isolation)
        mock_minio_client.list_objects.assert_called_once()
        call_args = mock_minio_client.list_objects.call_args
        assert call_args[1]["prefix"] == f"videos/test.mp4.{upload_id}.part"
        # Should remove both part objects
        assert mock_minio_client.remove_object.call_count == 2


class TestDirectUpload:
    """Test direct file upload/download operations."""

    def test_upload_file(self, storage_service, mock_minio_client):
        """Test uploading a file directly."""
        mock_minio_client.bucket_exists.return_value = True

        mock_result = Mock()
        mock_result.object_name = "videos/test.mp4"
        mock_result.etag = "abc123"
        mock_result.version_id = "v1"
        mock_minio_client.fput_object.return_value = mock_result

        result = storage_service.upload_file(
            "/tmp/test.mp4",
            "videos/test.mp4",
            content_type="video/mp4",
            metadata={"mall_id": "001"},
        )

        assert result["object_name"] == "videos/test.mp4"
        assert result["etag"] == "abc123"
        mock_minio_client.fput_object.assert_called_once()

    def test_download_file(self, storage_service, mock_minio_client):
        """Test downloading a file."""
        mock_minio_client.bucket_exists.return_value = True

        path = storage_service.download_file(
            "videos/test.mp4",
            "/tmp/downloaded.mp4",
        )

        assert path == "/tmp/downloaded.mp4"
        mock_minio_client.fget_object.assert_called_once_with(
            "spatial-intel-videos",
            "videos/test.mp4",
            "/tmp/downloaded.mp4",
        )


class TestPresignedURLs:
    """Test presigned URL generation."""

    def test_generate_presigned_get_url(self, storage_service, mock_minio_client):
        """Test generating presigned URL for file access."""
        mock_minio_client.bucket_exists.return_value = True
        mock_minio_client.presigned_get_object.return_value = "https://minio.example.com/bucket/object?signature=xyz"

        url = storage_service.generate_presigned_get_url(
            "videos/test.mp4",
            expires=timedelta(hours=1),
        )

        assert url == "https://minio.example.com/bucket/object?signature=xyz"
        mock_minio_client.presigned_get_object.assert_called_once()


class TestFileManagement:
    """Test file management operations."""

    def test_delete_file(self, storage_service, mock_minio_client):
        """Test deleting a file."""
        mock_minio_client.bucket_exists.return_value = True

        storage_service.delete_file("videos/test.mp4")

        mock_minio_client.remove_object.assert_called_once_with(
            "spatial-intel-videos",
            "videos/test.mp4",
        )

    def test_file_exists_true(self, storage_service, mock_minio_client):
        """Test checking if file exists (exists)."""
        mock_minio_client.bucket_exists.return_value = True
        mock_minio_client.stat_object.return_value = Mock()

        exists = storage_service.file_exists("videos/test.mp4")

        assert exists is True

    def test_file_exists_false(self, storage_service, mock_minio_client):
        """Test checking if file exists (does not exist)."""
        mock_minio_client.bucket_exists.return_value = True
        mock_minio_client.stat_object.side_effect = S3Error(
            "NoSuchKey",
            "Object not found",
            "resource",
            "request_id",
            "host_id",
            Mock(),
        )

        exists = storage_service.file_exists("videos/test.mp4")

        assert exists is False

    def test_get_file_metadata(self, storage_service, mock_minio_client):
        """Test getting file metadata."""
        mock_minio_client.bucket_exists.return_value = True

        mock_stat = Mock()
        mock_stat.object_name = "videos/test.mp4"
        mock_stat.size = 1024000
        mock_stat.etag = "abc123"
        mock_stat.content_type = "video/mp4"
        mock_stat.last_modified = "2025-10-31T12:00:00Z"
        mock_stat.metadata = {"mall_id": "001"}
        mock_stat.version_id = "v1"
        mock_minio_client.stat_object.return_value = mock_stat

        metadata = storage_service.get_file_metadata("videos/test.mp4")

        assert metadata["object_name"] == "videos/test.mp4"
        assert metadata["size"] == 1024000
        assert metadata["etag"] == "abc123"
        assert metadata["content_type"] == "video/mp4"


class TestHelpers:
    """Test helper methods."""

    def test_generate_object_path_original(self, storage_service):
        """Test generating object path for original video."""
        path = storage_service.generate_object_path(
            "mall-001",
            "pin-002",
            "recording.mp4",
            path_type="original",
        )

        assert path == "videos/mall-001/pin-002/original/recording.mp4"

    def test_generate_object_path_proxy(self, storage_service):
        """Test generating object path for proxy video."""
        path = storage_service.generate_object_path(
            "mall-001",
            "pin-002",
            "recording.mp4",
            path_type="proxy",
        )

        assert path == "videos/mall-001/pin-002/proxy/recording.mp4"

    def test_generate_object_path_strips_directory(self, storage_service):
        """Test that directory components are stripped from filename."""
        path = storage_service.generate_object_path(
            "mall-001",
            "pin-002",
            "/tmp/uploads/recording.mp4",
            path_type="original",
        )

        assert path == "videos/mall-001/pin-002/original/recording.mp4"


class TestSingleton:
    """Test singleton pattern for storage service."""

    @patch("app.services.storage_service.StorageService")
    def test_get_storage_service_singleton(self, mock_storage_class):
        """Test that get_storage_service returns singleton instance."""
        # Reset singleton
        import app.services.storage_service
        app.services.storage_service._storage_service = None

        mock_instance = Mock()
        mock_storage_class.return_value = mock_instance

        # First call should create instance
        service1 = get_storage_service()

        # Second call should return same instance
        service2 = get_storage_service()

        assert service1 is service2
        mock_storage_class.assert_called_once()
        mock_instance.initialize_bucket.assert_called_once()
