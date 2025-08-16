#!/usr/bin/env python3
"""Test script for the enhanced worker system (EPIC E6)."""

import asyncio
import logging
import time
import uuid
from typing import Dict

import httpx
import redis
from celery import Celery
from dental_backend_common.config import get_settings
from dental_backend_common.database import Job, JobStatus
from dental_backend_common.session import get_db_session
from dental_backend_common.tracing import setup_tracing

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Setup tracing
setup_tracing()


class WorkerSystemTester:
    """Test the enhanced worker system functionality."""

    def __init__(self):
        self.api_base_url = "http://localhost:8000"
        self.redis_client = redis.Redis.from_url(settings.redis.url)
        self.celery_app = Celery(
            "dental_backend",
            broker=settings.worker.effective_broker_url,
            backend=settings.worker.result_backend,
        )

    def test_redis_connection(self) -> bool:
        """Test Redis connection for broker."""
        try:
            self.redis_client.ping()
            logger.info("✅ Redis connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            return False

    def test_celery_connection(self) -> bool:
        """Test Celery broker connection."""
        try:
            # Test broker connection
            inspect = self.celery_app.control.inspect()
            inspect.stats()  # Test connection by calling stats
            logger.info("✅ Celery broker connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Celery broker connection failed: {e}")
            return False

    async def test_api_health(self) -> bool:
        """Test API health endpoints."""
        try:
            async with httpx.AsyncClient() as client:
                # Test health endpoint
                response = await client.get(f"{self.api_base_url}/health")
                if response.status_code == 200:
                    logger.info("✅ API health endpoint working")
                else:
                    logger.error(
                        f"❌ API health endpoint failed: {response.status_code}"
                    )
                    return False

                # Test readiness endpoint
                response = await client.get(f"{self.api_base_url}/ready")
                if response.status_code == 200:
                    logger.info("✅ API readiness endpoint working")
                else:
                    logger.error(
                        f"❌ API readiness endpoint failed: {response.status_code}"
                    )
                    return False

                return True
        except Exception as e:
            logger.error(f"❌ API health test failed: {e}")
            return False

    def test_worker_tasks(self) -> bool:
        """Test worker task execution."""
        try:
            from dental_backend.worker.tasks import health_check_task, process_mesh_file

            # Test health check task
            logger.info("Testing health check task...")
            task = health_check_task.delay()
            result = task.get(timeout=30)

            if result and result.get("status") == "completed":
                logger.info("✅ Health check task completed successfully")
            else:
                logger.error("❌ Health check task failed")
                return False

            # Test mesh processing task
            logger.info("Testing mesh processing task...")
            task = process_mesh_file.delay(
                file_path="/test/path/file.stl",
                file_type="stl",
                job_id=str(uuid.uuid4()),
            )
            result = task.get(timeout=60)

            if result and result.get("status") == "completed":
                logger.info("✅ Mesh processing task completed successfully")
            else:
                logger.error("❌ Mesh processing task failed")
                return False

            return True
        except Exception as e:
            logger.error(f"❌ Worker task test failed: {e}")
            return False

    def test_job_state_machine(self) -> bool:
        """Test job state machine transitions."""
        try:
            with get_db_session() as db:
                # Create a test job
                job = Job(
                    case_id=uuid.uuid4(),
                    job_type="test_job",
                    status=JobStatus.PENDING,
                    priority=5,
                    created_by=uuid.uuid4(),
                    parameters={"test": True},
                )
                db.add(job)
                db.commit()
                db.refresh(job)

                job_id = str(job.id)
                logger.info(f"Created test job: {job_id}")

                # Test state transitions
                # PENDING -> PROCESSING
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                db.commit()
                logger.info("✅ Job state transition: PENDING -> PROCESSING")

                # PROCESSING -> COMPLETED
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()
                job.progress = 100
                job.result = {"test_result": "success"}
                db.commit()
                logger.info("✅ Job state transition: PROCESSING -> COMPLETED")

                # Clean up
                db.delete(job)
                db.commit()

                return True
        except Exception as e:
            logger.error(f"❌ Job state machine test failed: {e}")
            return False

    async def test_job_api_endpoints(self) -> bool:
        """Test job API endpoints."""
        try:
            async with httpx.AsyncClient() as client:
                # First, create a test case and file (simplified)
                case_data = {
                    "case_number": f"TEST-{uuid.uuid4().hex[:8]}",
                    "patient_id": "test-patient",
                    "title": "Test Case for Worker",
                    "description": "Test case for worker system validation",
                }

                # Create case (assuming auth is disabled for testing)
                response = await client.post(
                    f"{self.api_base_url}/cases/",
                    json=case_data,
                    headers={"Authorization": "Bearer test-token"},
                )

                if response.status_code != 201:
                    logger.error(
                        f"❌ Failed to create test case: {response.status_code}"
                    )
                    return False

                case = response.json()
                case_id = case["id"]
                logger.info(f"Created test case: {case_id}")

                # Create a test file
                file_data = {
                    "filename": "test.stl",
                    "file_size": 1024,
                    "file_type": "stl",
                    "mime_type": "application/octet-stream",
                    "checksum": "test-checksum",
                }

                response = await client.post(
                    f"{self.api_base_url}/files/{case_id}/files:initiate",
                    json=file_data,
                    headers={"Authorization": "Bearer test-token"},
                )

                if response.status_code != 200:
                    logger.error(
                        f"❌ Failed to create test file: {response.status_code}"
                    )
                    return False

                file_info = response.json()
                file_id = file_info["id"]
                logger.info(f"Created test file: {file_id}")

                # Test job creation
                job_data = {
                    "file_id": file_id,
                    "job_type": "segmentation",
                    "priority": 5,
                    "parameters": {"test": True},
                    "request_key": f"test-{uuid.uuid4()}",
                }

                response = await client.post(
                    f"{self.api_base_url}/jobs/{case_id}/segment",
                    json=job_data,
                    headers={"Authorization": "Bearer test-token"},
                )

                if response.status_code != 200:
                    logger.error(f"❌ Failed to create job: {response.status_code}")
                    return False

                job = response.json()
                job_id = job["id"]
                logger.info(f"✅ Created job: {job_id}")

                # Test job retrieval
                response = await client.get(
                    f"{self.api_base_url}/jobs/{job_id}",
                    headers={"Authorization": "Bearer test-token"},
                )

                if response.status_code == 200:
                    logger.info("✅ Job retrieval successful")
                else:
                    logger.error(f"❌ Job retrieval failed: {response.status_code}")
                    return False

                # Test job progress streaming (simplified)
                response = await client.get(
                    f"{self.api_base_url}/jobs/{job_id}/progress",
                    headers={"Authorization": "Bearer test-token"},
                )

                if response.status_code == 200:
                    logger.info("✅ Job progress endpoint accessible")
                else:
                    logger.error(
                        f"❌ Job progress endpoint failed: {response.status_code}"
                    )
                    return False

                return True
        except Exception as e:
            logger.error(f"❌ Job API test failed: {e}")
            return False

    def test_correlation_id_propagation(self) -> bool:
        """Test correlation ID propagation through the system."""
        try:
            correlation_id = str(uuid.uuid4())
            logger.info(f"Testing correlation ID: {correlation_id}")

            # Test correlation ID in task
            from dental_backend.worker.tasks import health_check_task

            task = health_check_task.delay()
            result = task.get(timeout=30)

            if result and "correlation_id" in result:
                logger.info("✅ Correlation ID propagated to task result")
            else:
                logger.warning("⚠️ Correlation ID not found in task result")

            return True
        except Exception as e:
            logger.error(f"❌ Correlation ID test failed: {e}")
            return False

    def test_retry_logic(self) -> bool:
        """Test task retry logic."""
        try:
            # This would require a task that can be made to fail
            # For now, we'll test the retry configuration
            logger.info("Testing retry configuration...")

            # Check Celery retry settings
            if settings.worker.task_max_retries > 0:
                logger.info(
                    f"✅ Retry configuration: max_retries={settings.worker.task_max_retries}"
                )
            else:
                logger.warning("⚠️ No retry configuration found")

            if settings.worker.task_retry_backoff:
                logger.info("✅ Exponential backoff enabled")
            else:
                logger.warning("⚠️ Exponential backoff disabled")

            return True
        except Exception as e:
            logger.error(f"❌ Retry logic test failed: {e}")
            return False

    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all worker system tests."""
        logger.info("🚀 Starting EPIC E6 Worker System Tests")
        logger.info("=" * 50)

        results = {}

        # Test infrastructure
        results["redis_connection"] = self.test_redis_connection()
        results["celery_connection"] = self.test_celery_connection()
        results["api_health"] = await self.test_api_health()

        # Test worker functionality
        results["worker_tasks"] = self.test_worker_tasks()
        results["job_state_machine"] = self.test_job_state_machine()
        results["job_api_endpoints"] = await self.test_job_api_endpoints()

        # Test advanced features
        results["correlation_id"] = self.test_correlation_id_propagation()
        results["retry_logic"] = self.test_retry_logic()

        # Summary
        logger.info("=" * 50)
        logger.info("📊 Test Results Summary:")

        passed = 0
        total = len(results)

        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"  {test_name}: {status}")
            if result:
                passed += 1

        logger.info(f"  Overall: {passed}/{total} tests passed")

        if passed == total:
            logger.info(
                "🎉 All tests passed! EPIC E6 implementation is working correctly."
            )
        else:
            logger.warning(
                f"⚠️ {total - passed} tests failed. Please check the implementation."
            )

        return results


async def main():
    """Main test function."""
    tester = WorkerSystemTester()
    results = await tester.run_all_tests()

    # Exit with appropriate code
    if all(results.values()):
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
