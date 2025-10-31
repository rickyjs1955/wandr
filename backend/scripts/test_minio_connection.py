#!/usr/bin/env python3
"""
Integration test for MinIO storage connectivity.

This script tests:
1. MinIO connection
2. Bucket creation/initialization
3. File upload
4. File download
5. Presigned URL generation
6. File deletion
"""

import sys
from pathlib import Path
import tempfile
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.storage_service import get_storage_service


def test_storage_integration():
    """Run comprehensive storage integration tests."""
    print("=" * 60)
    print("MinIO Storage Integration Test")
    print("=" * 60)

    try:
        # Step 1: Initialize storage service
        print("\n1️⃣  Initializing storage service...")
        storage = get_storage_service()
        print("   ✅ Storage service initialized")

        # Step 2: Test bucket initialization
        print("\n2️⃣  Testing bucket initialization...")
        storage.initialize_bucket()
        print(f"   ✅ Bucket '{storage.bucket_name}' ready")

        # Step 3: Test file upload
        print("\n3️⃣  Testing file upload...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            test_file = f.name
            f.write("Test content for MinIO integration test\n")
            f.write("This file will be uploaded, downloaded, and deleted.\n")

        object_name = "test/integration-test.txt"
        result = storage.upload_file(
            test_file,
            object_name,
            content_type="text/plain",
            metadata={"purpose": "integration-test"},
        )
        print(f"   ✅ File uploaded: {object_name}")
        print(f"      ETag: {result['etag']}")

        # Step 4: Test file existence
        print("\n4️⃣  Testing file existence check...")
        exists = storage.file_exists(object_name)
        assert exists is True, "File should exist"
        print(f"   ✅ File exists confirmed")

        # Step 5: Test file metadata
        print("\n5️⃣  Testing file metadata retrieval...")
        metadata = storage.get_file_metadata(object_name)
        print(f"   ✅ Metadata retrieved:")
        print(f"      Size: {metadata['size']} bytes")
        print(f"      Content-Type: {metadata['content_type']}")
        print(f"      Last Modified: {metadata['last_modified']}")

        # Step 6: Test presigned URL generation
        print("\n6️⃣  Testing presigned URL generation...")
        from datetime import timedelta
        url = storage.generate_presigned_get_url(object_name, expires=timedelta(minutes=5))
        print(f"   ✅ Presigned URL generated")
        print(f"      URL: {url[:80]}...")

        # Step 7: Test file download
        print("\n7️⃣  Testing file download...")
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            download_file = f.name

        storage.download_file(object_name, download_file)

        # Verify downloaded content
        with open(download_file, 'r') as f:
            content = f.read()
            assert "Test content" in content, "Downloaded content mismatch"

        print(f"   ✅ File downloaded and verified")

        # Step 8: Test path generation helper
        print("\n8️⃣  Testing object path generation...")
        path = storage.generate_object_path(
            "mall-001",
            "pin-002",
            "recording.mp4",
            path_type="original",
        )
        expected = "videos/mall-001/pin-002/original/recording.mp4"
        assert path == expected, f"Path mismatch: {path} != {expected}"
        print(f"   ✅ Path generation correct: {path}")

        # Step 9: Test file deletion
        print("\n9️⃣  Testing file deletion...")
        storage.delete_file(object_name)
        exists_after_delete = storage.file_exists(object_name)
        assert exists_after_delete is False, "File should not exist after deletion"
        print(f"   ✅ File deleted successfully")

        # Cleanup local files
        os.unlink(test_file)
        os.unlink(download_file)

        # Final result
        print("\n" + "=" * 60)
        print("✅✅✅ All storage integration tests PASSED")
        print("=" * 60)
        return 0

    except Exception as e:
        print(f"\n❌ Storage integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(test_storage_integration())
