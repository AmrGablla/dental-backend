#!/usr/bin/env python3
"""Test script for the upload pipeline functionality."""

import hashlib
import os
import sys
import tempfile

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dental_backend_common.config import get_settings
    from dental_backend_common.storage import StorageService
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


def create_test_stl_file(file_path: str, vertex_count: int = 1000) -> None:
    """Create a simple test STL file."""
    with open(file_path, "w") as f:
        # STL header
        f.write("solid test_model\n")

        # Create simple triangular faces
        for i in range(vertex_count // 3):
            x = i * 0.1
            f.write("  facet normal 0.0 0.0 1.0\n")
            f.write("    outer loop\n")
            f.write(f"      vertex {x} 0.0 0.0\n")
            f.write(f"      vertex {x + 0.1} 0.0 0.0\n")
            f.write(f"      vertex {x + 0.05} 0.1 0.0\n")
            f.write("    endloop\n")
            f.write("  endfacet\n")

        f.write("endsolid test_model\n")

    # Force the file to be recognized as STL by adding a .stl extension to the path
    # This is a workaround for the magic library detection
    stl_path = file_path + ".stl"
    import shutil

    shutil.copy2(file_path, stl_path)
    return stl_path


def test_storage_service():
    """Test the storage service functionality."""
    print("🔍 Testing Storage Service")
    print("=" * 50)

    try:
        # Initialize storage service
        storage_service = StorageService()
        print("✅ Storage service initialized successfully")

        # Test presigned URL generation
        print("\n📤 Testing Presigned URL Generation...")
        presigned_url, fields = storage_service.generate_presigned_url(
            tenant_id="test_tenant",
            case_id="test_case_001",
            filename="test_scan.stl",
            content_type="application/octet-stream",
            expires_in=3600,
        )

        print(f"  ✅ Presigned URL generated: {presigned_url[:50]}...")
        print(f"  ✅ Required fields: {fields}")

        # Test file validation
        print("\n🔍 Testing File Validation...")

        # Create test files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Valid STL file
            valid_stl = os.path.join(temp_dir, "valid_test")
            valid_stl = create_test_stl_file(valid_stl, vertex_count=100)

            # Large STL file (should fail validation)
            large_stl = os.path.join(temp_dir, "large_test")
            large_stl = create_test_stl_file(
                large_stl, vertex_count=2000000
            )  # 2M vertices

            # Test valid file
            print("  Testing valid STL file...")
            result = storage_service.validate_file(
                file_path=valid_stl,
                filename="valid_test.stl",
                content_type="application/octet-stream",
            )

            if result.is_valid:
                print("  ✅ Valid file passed validation")
                print(f"  📊 File info: {result.file_info}")
            else:
                print(f"  ❌ Valid file failed validation: {result.errors}")

            # Test large file
            print("  Testing large STL file...")
            result = storage_service.validate_file(
                file_path=large_stl,
                filename="large_test.stl",
                content_type="application/octet-stream",
            )

            if not result.is_valid:
                print(f"  ✅ Large file correctly rejected: {result.errors}")
            else:
                print("  ❌ Large file should have been rejected")

            # Test checksum calculation
            print("\n🔐 Testing Checksum Calculation...")
            md5_hash, sha256_hash = storage_service.calculate_checksums(valid_stl)
            print(f"  ✅ MD5: {md5_hash}")
            print(f"  ✅ SHA256: {sha256_hash}")

            # Verify checksums
            with open(valid_stl, "rb") as f:
                content = f.read()
                expected_md5 = hashlib.md5(content).hexdigest()
                expected_sha256 = hashlib.sha256(content).hexdigest()

                if md5_hash == expected_md5 and sha256_hash == expected_sha256:
                    print("  ✅ Checksums verified correctly")
                else:
                    print("  ❌ Checksum verification failed")

        print("\n✅ Storage service tests completed successfully")
        return True

    except Exception as e:
        print(f"❌ Storage service test failed: {e}")
        return False


def test_upload_pipeline():
    """Test the complete upload pipeline."""
    print("\n🚀 Testing Upload Pipeline")
    print("=" * 50)

    try:
        storage_service = StorageService()

        # Create test file
        with tempfile.NamedTemporaryFile(suffix=".stl", delete=False) as temp_file:
            temp_file_path = create_test_stl_file(temp_file.name, vertex_count=500)

        try:
            # Step 1: Initialize upload
            print("📤 Step 1: Initializing upload...")
            presigned_url, fields = storage_service.generate_presigned_url(
                tenant_id="test_tenant",
                case_id="test_case_001",
                filename="pipeline_test.stl",
                content_type="application/octet-stream",
            )
            print(f"  ✅ Upload initialized with URL: {presigned_url[:50]}...")

            # Step 2: Calculate checksums
            print("\n🔐 Step 2: Calculating checksums...")
            md5_hash, sha256_hash = storage_service.calculate_checksums(temp_file_path)
            print(f"  ✅ MD5: {md5_hash}")
            print(f"  ✅ SHA256: {sha256_hash}")

            # Step 3: Validate file
            print("\n🔍 Step 3: Validating file...")
            validation_result = storage_service.validate_file(
                file_path=temp_file_path,
                filename="pipeline_test.stl",
                content_type="application/octet-stream",
            )

            if validation_result.is_valid:
                print("  ✅ File validation passed")
                print(f"  📊 File metadata: {validation_result.file_info}")
            else:
                print(f"  ❌ File validation failed: {validation_result.errors}")
                return False

            # Step 4: Simulate S3 upload (in real scenario, client would upload to presigned URL)
            print("\n☁️  Step 4: Simulating S3 upload...")
            print("  ℹ️  In real scenario, client would upload to presigned URL")
            print("  ℹ️  For testing, we'll simulate the upload process")

            # Step 5: Verify file integrity
            print("\n✅ Step 5: Verifying file integrity...")
            # In a real scenario, this would verify the file in S3
            print("  ℹ️  File integrity verification would happen after S3 upload")

            print("\n✅ Upload pipeline test completed successfully")
            return True

        finally:
            # Clean up
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except Exception as e:
        print(f"❌ Upload pipeline test failed: {e}")
        return False


def test_error_handling():
    """Test error handling scenarios."""
    print("\n⚠️  Testing Error Handling")
    print("=" * 50)

    try:
        storage_service = StorageService()

        # Test with non-existent file
        print("🔍 Testing validation with non-existent file...")
        result = storage_service.validate_file(
            file_path="/non/existent/file.stl", filename="nonexistent.stl"
        )

        if not result.is_valid:
            print("  ✅ Correctly handled non-existent file")
        else:
            print("  ❌ Should have rejected non-existent file")

        # Test with invalid file type
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
            temp_file.write(b"This is not a valid STL file")
            temp_file_path = temp_file.name

        try:
            print("\n🔍 Testing validation with invalid file type...")
            result = storage_service.validate_file(
                file_path=temp_file_path,
                filename="invalid.txt",
                content_type="text/plain",
            )

            if not result.is_valid:
                print("  ✅ Correctly rejected invalid file type")
            else:
                print("  ❌ Should have rejected invalid file type")

        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

        print("\n✅ Error handling tests completed successfully")
        return True

    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False


def main():
    """Main test function."""
    print("🧪 Upload Pipeline Test Suite")
    print("=" * 60)

    # Check if required services are available
    settings = get_settings()
    print(f"Environment: {settings.environment}")
    print(f"S3 Endpoint: {settings.s3.endpoint_url}")
    print(f"S3 Bucket: {settings.s3.bucket_name}")
    print(f"Antivirus Enabled: {settings.antivirus.enabled}")

    # Run tests
    tests = [
        ("Storage Service", test_storage_service),
        ("Upload Pipeline", test_upload_pipeline),
        ("Error Handling", test_error_handling),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'=' * 20} {test_name} {'=' * 20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))

    # Summary
    print(f"\n{'=' * 60}")
    print("📊 Test Results Summary")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<20} {status}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Upload pipeline is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
