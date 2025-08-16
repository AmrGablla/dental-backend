#!/usr/bin/env python3
"""Test script to verify the infrastructure setup."""

import asyncio
import sys
from pathlib import Path

import httpx
import redis
from dental_backend_common.config import get_settings
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError


def test_settings() -> bool:
    """Test that settings are loaded correctly."""
    print("🔧 Testing settings configuration...")

    try:
        settings = get_settings()
        print(f"  ✓ Environment: {settings.environment}")
        print(f"  ✓ Debug mode: {settings.debug}")
        print(
            f"  ✓ Database URL: {settings.database.url.split('@')[-1] if '@' in settings.database.url else '***'}"
        )
        print(
            f"  ✓ Redis URL: {settings.redis.url.split('@')[-1] if '@' in settings.redis.url else '***'}"
        )
        print(f"  ✓ S3 Endpoint: {settings.s3.endpoint_url}")
        print(f"  ✓ API Host: {settings.api.host}:{settings.api.port}")
        return True
    except Exception as e:
        print(f"  ✗ Settings test failed: {e}")
        return False


def test_database() -> bool:
    """Test database connection."""
    print("🗄️  Testing database connection...")

    try:
        settings = get_settings()
        engine = create_engine(settings.database.url)

        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"  ✓ Database connected: {version.split(',')[0]}")
        return True
    except OperationalError as e:
        print(f"  ✗ Database connection failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Database test failed: {e}")
        return False


def test_redis() -> bool:
    """Test Redis connection."""
    print("🔴 Testing Redis connection...")

    try:
        settings = get_settings()
        r = redis.from_url(settings.redis.url)

        # Test basic operations
        r.set("test_key", "test_value")
        value = r.get("test_key")
        r.delete("test_key")

        if value == b"test_value":
            print("  ✓ Redis connected and working")
            return True
        else:
            print("  ✗ Redis test failed: value mismatch")
            return False
    except Exception as e:
        print(f"  ✗ Redis test failed: {e}")
        return False


async def test_api() -> bool:
    """Test API service."""
    print("🌐 Testing API service...")

    try:
        settings = get_settings()
        # Use localhost for testing from host machine
        api_host = "localhost" if settings.api.host == "0.0.0.0" else settings.api.host
        api_url = f"http://{api_host}:{settings.api.port}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test health endpoint
            response = await client.get(f"{api_url}/health")

            if response.status_code == 200:
                data = response.json()
                print(f"  ✓ API health check passed: {data.get('status')}")

                # Test config endpoint (development only)
                if settings.debug:
                    config_response = await client.get(f"{api_url}/config")
                    if config_response.status_code == 200:
                        print("  ✓ API config endpoint working")
                    else:
                        print(
                            f"  ⚠️  API config endpoint failed: {config_response.status_code}"
                        )

                return True
            else:
                print(f"  ✗ API health check failed: {response.status_code}")
                return False
    except httpx.ConnectError as e:
        print(f"  ✗ API connection failed: {e}")
        return False
    except Exception as e:
        print(f"  ✗ API test failed: {e}")
        return False


def test_s3_minio() -> bool:
    """Test S3/MinIO connection."""
    print("📦 Testing S3/MinIO connection...")

    try:
        import boto3
        from botocore.exceptions import ClientError

        settings = get_settings()

        # Create S3 client
        s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3.endpoint_url,
            aws_access_key_id=settings.s3.access_key_id,
            aws_secret_access_key=settings.s3.secret_access_key,
            region_name=settings.s3.region_name,
            use_ssl=settings.s3.use_ssl,
        )

        # Test bucket operations
        try:
            s3_client.head_bucket(Bucket=settings.s3.bucket_name)
            print(f"  ✓ S3/MinIO bucket '{settings.s3.bucket_name}' accessible")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                print(
                    f"  ⚠️  S3/MinIO bucket '{settings.s3.bucket_name}' not found (will be created on first use)"
                )
                return True
            else:
                print(f"  ✗ S3/MinIO test failed: {error_code}")
                return False

    except ImportError:
        print("  ⚠️  boto3 not installed, skipping S3 test")
        return True
    except Exception as e:
        print(f"  ✗ S3/MinIO test failed: {e}")
        return False


def test_file_permissions() -> bool:
    """Test file permissions and directories."""
    print("📁 Testing file permissions...")

    try:
        settings = get_settings()
        temp_dir = Path(settings.temp_dir)

        # Create temp directory if it doesn't exist
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Test write permissions
        test_file = temp_dir / "test_write.txt"
        test_file.write_text("test")
        test_file.unlink()

        print(f"  ✓ Temp directory writable: {temp_dir}")
        return True
    except Exception as e:
        print(f"  ✗ File permissions test failed: {e}")
        return False


async def main():
    """Run all infrastructure tests."""
    print("🚀 Dental Backend Infrastructure Test")
    print("=" * 50)

    tests = [
        ("Settings", test_settings),
        ("Database", test_database),
        ("Redis", test_redis),
        ("API", test_api),
        ("S3/MinIO", test_s3_minio),
        ("File Permissions", test_file_permissions),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ✗ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
        print()

    # Summary
    print("📊 Test Results Summary")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All infrastructure tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
