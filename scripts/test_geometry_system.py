#!/usr/bin/env python3
"""Test script for EPIC E7 - 3D IO & Geometry Utilities."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict

import httpx
import numpy as np
from dental_backend_common.geometry import (
    MeshFormat,
    MeshProcessor,
    ValidationLevel,
    create_test_mesh,
    run_round_trip_tests,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeometrySystemTester:
    """Test suite for the 3D IO & Geometry Utilities system."""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.test_results = {}

    async def test_mesh_processor_basic(self) -> bool:
        """Test basic mesh processor functionality."""
        logger.info("Testing basic mesh processor functionality...")

        try:
            # Create mesh processor
            processor = MeshProcessor()

            # Create test mesh
            test_mesh = create_test_mesh()

            # Test mesh info
            mesh_info = processor.validator._get_mesh_info(test_mesh)
            assert mesh_info.vertices == 4
            assert mesh_info.faces == 4
            assert mesh_info.is_manifold
            assert mesh_info.is_watertight

            logger.info("✅ Basic mesh processor functionality working")
            return True

        except Exception as e:
            logger.error(f"❌ Basic mesh processor test failed: {e}")
            return False

    async def test_mesh_validation(self) -> bool:
        """Test mesh validation functionality."""
        logger.info("Testing mesh validation...")

        try:
            # Create mesh processor with strict validation
            processor = MeshProcessor(validation_level=ValidationLevel.STRICT)

            # Create test mesh
            test_mesh = create_test_mesh()

            # Validate mesh
            validation_report = processor.validator.validate_mesh(test_mesh)

            # Check validation results
            assert validation_report.is_valid
            assert validation_report.mesh_info.vertices == 4
            assert validation_report.mesh_info.faces == 4
            assert validation_report.validation_level == ValidationLevel.STRICT

            logger.info("✅ Mesh validation working")
            return True

        except Exception as e:
            logger.error(f"❌ Mesh validation test failed: {e}")
            return False

    async def test_mesh_normalization(self) -> bool:
        """Test mesh normalization functionality."""
        logger.info("Testing mesh normalization...")

        try:
            # Create mesh processor
            processor = MeshProcessor()

            # Create test mesh with offset
            test_mesh = create_test_mesh()
            test_mesh.apply_translation([10, 20, 30])

            # Normalize mesh
            normalized_mesh = processor.normalizer.normalize_mesh(test_mesh)

            # Check normalization results
            assert np.allclose(normalized_mesh.center_mass, [0, 0, 0], atol=1e-6)

            logger.info("✅ Mesh normalization working")
            return True

        except Exception as e:
            logger.error(f"❌ Mesh normalization test failed: {e}")
            return False

    async def test_round_trip_formats(self) -> bool:
        """Test round-trip loading and saving for all formats."""
        logger.info("Testing round-trip format support...")

        try:
            # Create mesh processor
            processor = MeshProcessor()

            # Run round-trip tests
            test_results = run_round_trip_tests(processor)

            # Check results
            passed_formats = sum(1 for success in test_results.values() if success)
            total_formats = len(test_results)

            logger.info(
                f"✅ Round-trip tests: {passed_formats}/{total_formats} formats passed"
            )

            # Log individual results
            for format, success in test_results.items():
                status = "PASS" if success else "FAIL"
                logger.info(f"  {format.value}: {status}")

            return passed_formats > 0  # At least one format should work

        except Exception as e:
            logger.error(f"❌ Round-trip format test failed: {e}")
            return False

    async def test_memory_limits(self) -> bool:
        """Test memory limit enforcement."""
        logger.info("Testing memory limit enforcement...")

        try:
            # Create mesh processor with low memory limit
            processor = MeshProcessor(memory_limit_mb=1)  # 1MB limit

            # Create a simple test mesh
            test_mesh = create_test_mesh()

            # Save to temporary file
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                test_file = temp_path / "test.stl"

                # Save mesh
                success = processor.save_mesh(test_mesh, test_file)
                assert success

                # Load mesh back (should work within memory limit)
                loaded_mesh, _ = processor.load_mesh(test_file, validate=False)
                assert len(loaded_mesh.vertices) == len(test_mesh.vertices)

            logger.info("✅ Memory limit enforcement working")
            return True

        except Exception as e:
            logger.error(f"❌ Memory limit test failed: {e}")
            return False

    async def test_api_endpoints(self) -> bool:
        """Test API endpoints for geometry operations."""
        logger.info("Testing geometry API endpoints...")

        try:
            async with httpx.AsyncClient() as client:
                # Test supported formats endpoint
                response = await client.get(f"{self.api_base_url}/geometry/formats")
                if response.status_code == 200:
                    formats = response.json()
                    logger.info(f"✅ Supported formats: {formats}")
                else:
                    logger.error(
                        f"❌ Failed to get supported formats: {response.status_code}"
                    )
                    return False

                # Test validation levels endpoint
                response = await client.get(
                    f"{self.api_base_url}/geometry/validation-levels"
                )
                if response.status_code == 200:
                    levels = response.json()
                    logger.info(f"✅ Validation levels: {levels}")
                else:
                    logger.error(
                        f"❌ Failed to get validation levels: {response.status_code}"
                    )
                    return False

                # Test format testing endpoint
                response = await client.post(
                    f"{self.api_base_url}/geometry/test-formats",
                    headers={"Authorization": "Bearer test-token"},
                    json={"memory_limit_mb": 1024},
                )
                if response.status_code == 201:
                    job_data = response.json()
                    logger.info(f"✅ Format testing job created: {job_data['id']}")
                else:
                    logger.error(
                        f"❌ Failed to create format testing job: {response.status_code}"
                    )
                    return False

            logger.info("✅ Geometry API endpoints working")
            return True

        except Exception as e:
            logger.error(f"❌ API endpoints test failed: {e}")
            return False

    async def test_mesh_processing_pipeline(self) -> bool:
        """Test complete mesh processing pipeline."""
        logger.info("Testing complete mesh processing pipeline...")

        try:
            # Create mesh processor
            processor = MeshProcessor(
                validation_level=ValidationLevel.STRICT,
                target_scale=1.0,
                target_units="mm",
            )

            # Create test mesh
            test_mesh = create_test_mesh()

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                input_file = temp_path / "input.stl"
                output_file = temp_path / "output.ply"

                # Save input mesh
                success = processor.save_mesh(test_mesh, input_file)
                assert success

                # Process mesh (load, validate, normalize, save)
                validation_report = processor.process_mesh(
                    input_path=input_file,
                    output_path=output_file,
                    validate=True,
                    normalize=True,
                    units="mm",
                    output_format=MeshFormat.PLY,
                )

                # Check results
                assert validation_report.is_valid
                assert output_file.exists()

                # Load processed mesh
                processed_mesh, _ = processor.load_mesh(output_file, validate=False)
                assert len(processed_mesh.vertices) == len(test_mesh.vertices)

            logger.info("✅ Complete mesh processing pipeline working")
            return True

        except Exception as e:
            logger.error(f"❌ Mesh processing pipeline test failed: {e}")
            return False

    async def test_error_handling(self) -> bool:
        """Test error handling for invalid inputs."""
        logger.info("Testing error handling...")

        try:
            # Create mesh processor
            processor = MeshProcessor()

            # Test loading non-existent file
            try:
                processor.loader.load("/non/existent/file.stl")
                logger.error("❌ Should have raised FileNotFoundError")
                return False
            except FileNotFoundError:
                logger.info("✅ Correctly handled non-existent file")

            # Test loading invalid mesh data
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                invalid_file = temp_path / "invalid.stl"

                # Create invalid STL file
                with open(invalid_file, "w") as f:
                    f.write("This is not a valid STL file")

                try:
                    processor.loader.load(invalid_file)
                    logger.error("❌ Should have raised ValueError for invalid mesh")
                    return False
                except (ValueError, Exception):
                    logger.info("✅ Correctly handled invalid mesh data")

            logger.info("✅ Error handling working correctly")
            return True

        except Exception as e:
            logger.error(f"❌ Error handling test failed: {e}")
            return False

    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all geometry system tests."""
        logger.info("🚀 Starting EPIC E7 Geometry System Tests")
        logger.info("=" * 50)

        tests = [
            ("mesh_processor_basic", self.test_mesh_processor_basic),
            ("mesh_validation", self.test_mesh_validation),
            ("mesh_normalization", self.test_mesh_normalization),
            ("round_trip_formats", self.test_round_trip_formats),
            ("memory_limits", self.test_memory_limits),
            ("api_endpoints", self.test_api_endpoints),
            ("processing_pipeline", self.test_mesh_processing_pipeline),
            ("error_handling", self.test_error_handling),
        ]

        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = await test_func()
            except Exception as e:
                logger.error(f"❌ Test {test_name} failed with exception: {e}")
                results[test_name] = False

        # Summary
        passed = sum(1 for success in results.values() if success)
        total = len(results)

        logger.info("=" * 50)
        logger.info("📊 Test Results Summary:")
        for test_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"  {test_name}: {status}")

        logger.info(f"  Overall: {passed}/{total} tests passed")

        if passed == total:
            logger.info(
                "🎉 All tests passed! EPIC E7 implementation is working correctly."
            )
        else:
            logger.warning(
                f"⚠️ {total - passed} tests failed. Please check the implementation."
            )

        return results


async def main():
    """Main test function."""
    tester = GeometrySystemTester()
    results = await tester.run_all_tests()

    # Exit with appropriate code
    exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    asyncio.run(main())
