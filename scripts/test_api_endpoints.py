#!/usr/bin/env python3
"""Test script for API endpoints functionality."""

import os
import sys
from datetime import datetime

import requests

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dental_backend_common.config import get_settings
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)


class APITester:
    """Test class for API endpoints."""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token = None

    def test_health_endpoints(self):
        """Test health, readiness, and version endpoints."""
        print("🔍 Testing Health Endpoints")
        print("=" * 50)

        # Test health endpoint
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health endpoint: {data['status']}")
                print(f"   Environment: {data['environment']}")
                print(f"   Timestamp: {data['timestamp']}")
            else:
                print(f"❌ Health endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Health endpoint error: {e}")

        # Test readiness endpoint
        try:
            response = self.session.get(f"{self.base_url}/ready")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Readiness endpoint: {data['status']}")
                print(f"   Database: {data['database']}")
                print(f"   Redis: {data['redis']}")
            else:
                print(f"❌ Readiness endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Readiness endpoint error: {e}")

        # Test version endpoint
        try:
            response = self.session.get(f"{self.base_url}/version")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Version endpoint: {data['version']}")
                print(f"   API Version: {data['api_version']}")
                print(f"   Environment: {data['environment']}")
            else:
                print(f"❌ Version endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Version endpoint error: {e}")

    def test_root_endpoint(self):
        """Test root endpoint."""
        print("\n🏠 Testing Root Endpoint")
        print("=" * 50)

        try:
            response = self.session.get(f"{self.base_url}/")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Root endpoint: {data['message']}")
                print(f"   Version: {data['version']}")
            else:
                print(f"❌ Root endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")

    def test_openapi_docs(self):
        """Test OpenAPI documentation endpoints."""
        print("\n📚 Testing OpenAPI Documentation")
        print("=" * 50)

        # Test OpenAPI JSON
        try:
            response = self.session.get(f"{self.base_url}/openapi.json")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ OpenAPI JSON: {data['info']['title']}")
                print(f"   Version: {data['info']['version']}")
                print(f"   Paths: {len(data['paths'])} endpoints")
            else:
                print(f"❌ OpenAPI JSON failed: {response.status_code}")
        except Exception as e:
            print(f"❌ OpenAPI JSON error: {e}")

        # Test Swagger UI
        try:
            response = self.session.get(f"{self.base_url}/docs")
            if response.status_code == 200:
                print("✅ Swagger UI: Available")
            else:
                print(f"❌ Swagger UI failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Swagger UI error: {e}")

        # Test ReDoc
        try:
            response = self.session.get(f"{self.base_url}/redoc")
            if response.status_code == 200:
                print("✅ ReDoc: Available")
            else:
                print(f"❌ ReDoc failed: {response.status_code}")
        except Exception as e:
            print(f"❌ ReDoc error: {e}")

    def test_authentication(self):
        """Test authentication endpoints."""
        print("\n🔐 Testing Authentication")
        print("=" * 50)

        # Test login endpoint
        try:
            login_data = {"username": "test_user", "password": "test_password"}
            response = self.session.post(f"{self.base_url}/auth/login", json=login_data)
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                print("✅ Login endpoint: Working")
                print(f"   Token type: {data.get('token_type')}")
            elif response.status_code == 401:
                print("⚠️  Login endpoint: Requires valid credentials")
            else:
                print(f"❌ Login endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Login endpoint error: {e}")

    def test_case_endpoints(self):
        """Test case management endpoints."""
        print("\n📁 Testing Case Endpoints")
        print("=" * 50)

        # Test case creation (requires authentication)
        if not self.auth_token:
            print("⚠️  Skipping case endpoints (no auth token)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Test case creation
        try:
            case_data = {
                "case_number": f"TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "patient_id": "TEST_PATIENT_001",
                "title": "Test Dental Case",
                "description": "Test case for API validation",
                "status": "active",
                "priority": "normal",
            }
            response = self.session.post(
                f"{self.base_url}/cases/", json=case_data, headers=headers
            )
            if response.status_code == 201:
                data = response.json()
                case_id = data["id"]
                print(f"✅ Case creation: {case_id}")
                print(f"   Case number: {data['case_number']}")
                print(f"   Patient ID: {data['patient_id']}")

                # Test case retrieval
                response = self.session.get(
                    f"{self.base_url}/cases/{case_id}", headers=headers
                )
                if response.status_code == 200:
                    print(f"✅ Case retrieval: {case_id}")
                else:
                    print(f"❌ Case retrieval failed: {response.status_code}")

                # Test case listing
                response = self.session.get(f"{self.base_url}/cases/", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Case listing: {data['total']} cases")
                else:
                    print(f"❌ Case listing failed: {response.status_code}")

            elif response.status_code == 401:
                print("⚠️  Case creation: Requires authentication")
            else:
                print(f"❌ Case creation failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Case endpoints error: {e}")

    def test_file_endpoints(self):
        """Test file management endpoints."""
        print("\n📄 Testing File Endpoints")
        print("=" * 50)

        if not self.auth_token:
            print("⚠️  Skipping file endpoints (no auth token)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Test file upload initiation
        try:
            file_data = {
                "filename": "test_scan.stl",
                "file_size": 1024,
                "content_type": "application/octet-stream",
                "file_type": "stl",
            }
            response = self.session.post(
                f"{self.base_url}/files/test_case_id/files:initiate",
                json=file_data,
                headers=headers,
            )
            if response.status_code == 200:
                data = response.json()
                print(f"✅ File upload initiation: {data['upload_id']}")
                print(f"   Presigned URL: {data['presigned_url'][:50]}...")
            elif response.status_code == 404:
                print("⚠️  File upload initiation: Case not found (expected)")
            else:
                print(f"❌ File upload initiation failed: {response.status_code}")
        except Exception as e:
            print(f"❌ File endpoints error: {e}")

    def test_job_endpoints(self):
        """Test job orchestration endpoints."""
        print("\n⚙️  Testing Job Endpoints")
        print("=" * 50)

        if not self.auth_token:
            print("⚠️  Skipping job endpoints (no auth token)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Test job creation
        try:
            job_data = {
                "file_id": "test_file_id",
                "job_type": "segmentation",
                "priority": 5,
                "request_key": "test_request_key",
            }
            response = self.session.post(
                f"{self.base_url}/jobs/test_case_id/segment",
                json=job_data,
                headers=headers,
            )
            if response.status_code == 201:
                data = response.json()
                job_id = data["id"]
                print(f"✅ Job creation: {job_id}")
                print(f"   Job type: {data['job_type']}")
                print(f"   Status: {data['status']}")
            elif response.status_code == 404:
                print("⚠️  Job creation: Case/File not found (expected)")
            else:
                print(f"❌ Job creation failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Job endpoints error: {e}")

    def test_segment_endpoints(self):
        """Test segment results endpoints."""
        print("\n🔬 Testing Segment Endpoints")
        print("=" * 50)

        if not self.auth_token:
            print("⚠️  Skipping segment endpoints (no auth token)")
            return

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        # Test segment listing
        try:
            response = self.session.get(
                f"{self.base_url}/segments/test_case_id/segments", headers=headers
            )
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Segment listing: {data['total']} segments")
            elif response.status_code == 404:
                print("⚠️  Segment listing: Case not found (expected)")
            else:
                print(f"❌ Segment listing failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Segment endpoints error: {e}")

    def run_all_tests(self):
        """Run all API tests."""
        print("🧪 API Endpoints Test Suite")
        print("=" * 60)

        settings = get_settings()
        print(f"Base URL: {self.base_url}")
        print(f"Environment: {settings.environment}")
        print(f"Debug: {settings.debug}")

        # Run tests
        self.test_health_endpoints()
        self.test_root_endpoint()
        self.test_openapi_docs()
        self.test_authentication()
        self.test_case_endpoints()
        self.test_file_endpoints()
        self.test_job_endpoints()
        self.test_segment_endpoints()

        print("\n" + "=" * 60)
        print("✅ API endpoints test completed!")
        print("📖 Check the results above for any issues.")


def main():
    """Main test function."""
    import argparse

    parser = argparse.ArgumentParser(description="Test API endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for the API (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    tester = APITester(args.base_url)
    tester.run_all_tests()


if __name__ == "__main__":
    main()
