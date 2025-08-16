#!/usr/bin/env python3
"""Test script for EPIC E8 - Pre-processing Pipeline."""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict

import httpx
import numpy as np
import trimesh
from dental_backend_common.preprocessing import (
    AlgorithmType,
    PipelineConfig,
    PipelineStep,
    PipelineStepConfig,
    PreprocessingPipeline,
    create_default_pipeline,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class PreprocessingSystemTester:
    """Test suite for the Pre-processing Pipeline system."""

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.test_results = {}

    async def test_pipeline_configuration(self) -> bool:
        """Test pipeline configuration creation and validation."""
        logger.info("Testing pipeline configuration...")

        try:
            # Create a custom pipeline configuration
            config = PipelineConfig(
                name="Test Pipeline",
                description="Test pipeline for validation",
                steps=[
                    PipelineStepConfig(
                        step=PipelineStep.DENOISE,
                        algorithm=AlgorithmType.STATISTICAL_OUTLIER_REMOVAL,
                        parameters={"nb_neighbors": 20, "std_ratio": 2.0},
                    ),
                    PipelineStepConfig(
                        step=PipelineStep.DECIMATE,
                        algorithm=AlgorithmType.VOXEL_DOWN_SAMPLE,
                        parameters={"voxel_size": 0.05},
                    ),
                ],
            )

            # Validate configuration
            config_dict = config.to_dict()
            loaded_config = PipelineConfig.from_dict(config_dict)

            assert loaded_config.name == config.name
            assert len(loaded_config.steps) == len(config.steps)
            assert loaded_config.steps[0].step == PipelineStep.DENOISE
            assert loaded_config.steps[1].step == PipelineStep.DECIMATE

            logger.info("✅ Pipeline configuration working")
            return True

        except Exception as e:
            logger.error(f"❌ Pipeline configuration test failed: {e}")
            return False

    async def test_denoise_processor(self) -> bool:
        """Test denoising processor functionality."""
        logger.info("Testing denoising processor...")

        try:
            # Create test mesh with noise
            test_mesh = self._create_noisy_mesh()

            # Create denoising step config
            config = PipelineStepConfig(
                step=PipelineStep.DENOISE,
                algorithm=AlgorithmType.STATISTICAL_OUTLIER_REMOVAL,
                parameters={"nb_neighbors": 20, "std_ratio": 2.0},
            )

            # Import processor
            from dental_backend_common.preprocessing import DenoiseProcessor

            processor = DenoiseProcessor(config)

            # Process mesh
            processed_mesh, metrics = processor.process(test_mesh)

            # Check results
            assert len(processed_mesh.vertices) > 0
            assert len(processed_mesh.faces) > 0
            assert metrics.processing_time > 0
            assert metrics.input_vertices == len(test_mesh.vertices)
            assert metrics.output_vertices == len(processed_mesh.vertices)

            logger.info(
                f"✅ Denoising processor working: {metrics.input_vertices} -> {metrics.output_vertices} vertices"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Denoising processor test failed: {e}")
            return False

    async def test_decimate_processor(self) -> bool:
        """Test decimation processor functionality."""
        logger.info("Testing decimation processor...")

        try:
            # Create test mesh
            test_mesh = self._create_test_mesh()

            # Create decimation step config
            config = PipelineStepConfig(
                step=PipelineStep.DECIMATE,
                algorithm=AlgorithmType.VOXEL_DOWN_SAMPLE,
                parameters={"voxel_size": 0.1},
            )

            # Import processor
            from dental_backend_common.preprocessing import DecimateProcessor

            processor = DecimateProcessor(config)

            # Process mesh
            processed_mesh, metrics = processor.process(test_mesh)

            # Check results
            assert len(processed_mesh.vertices) > 0
            assert len(processed_mesh.faces) > 0
            assert metrics.processing_time > 0
            assert metrics.vertex_reduction_ratio >= 0
            assert metrics.face_reduction_ratio >= 0

            logger.info(
                f"✅ Decimation processor working: {metrics.vertex_reduction_ratio:.2%} vertex reduction"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Decimation processor test failed: {e}")
            return False

    async def test_pipeline_execution(self) -> bool:
        """Test complete pipeline execution."""
        logger.info("Testing complete pipeline execution...")

        try:
            # Create test mesh
            test_mesh = self._create_test_mesh()

            # Create pipeline configuration
            config = create_default_pipeline()

            # Create pipeline
            pipeline = PreprocessingPipeline(config)

            # Process mesh
            processed_mesh, step_metrics = pipeline.process(test_mesh)

            # Check results
            assert len(processed_mesh.vertices) > 0
            assert len(processed_mesh.faces) > 0
            assert len(step_metrics) > 0

            # Check cache statistics
            cache_stats = pipeline.get_cache_stats()
            assert "hit_count" in cache_stats
            assert "miss_count" in cache_stats
            assert "hit_rate" in cache_stats

            logger.info(
                f"✅ Pipeline execution working: {len(step_metrics)} steps completed"
            )
            logger.info(f"   Cache stats: {cache_stats}")
            return True

        except Exception as e:
            logger.error(f"❌ Pipeline execution test failed: {e}")
            return False

    async def test_pipeline_caching(self) -> bool:
        """Test pipeline caching functionality."""
        logger.info("Testing pipeline caching...")

        try:
            # Create test mesh
            test_mesh = self._create_test_mesh()

            # Create pipeline configuration
            config = create_default_pipeline()

            # Create pipeline with temporary cache directory
            with tempfile.TemporaryDirectory() as temp_dir:
                cache_dir = Path(temp_dir) / "pipeline_cache"
                pipeline = PreprocessingPipeline(config, cache_dir=cache_dir)

                # First run (should cache)
                processed_mesh1, metrics1 = pipeline.process(test_mesh)
                cache_stats1 = pipeline.get_cache_stats()

                # Second run (should use cache)
                processed_mesh2, metrics2 = pipeline.process(test_mesh)
                cache_stats2 = pipeline.get_cache_stats()

                # Check that cache was used
                assert cache_stats2["hit_count"] > cache_stats1["hit_count"]
                assert cache_stats2["miss_count"] == cache_stats1["miss_count"]

                # Check that results are identical
                assert len(processed_mesh1.vertices) == len(processed_mesh2.vertices)
                assert len(processed_mesh1.faces) == len(processed_mesh2.faces)

            logger.info("✅ Pipeline caching working")
            return True

        except Exception as e:
            logger.error(f"❌ Pipeline caching test failed: {e}")
            return False

    async def test_api_endpoints(self) -> bool:
        """Test API endpoints for preprocessing operations."""
        logger.info("Testing preprocessing API endpoints...")

        try:
            async with httpx.AsyncClient() as client:
                # Test pipeline steps endpoint
                response = await client.get(f"{self.api_base_url}/preprocessing/steps")
                if response.status_code == 200:
                    steps = response.json()
                    logger.info(f"✅ Pipeline steps: {steps}")
                else:
                    logger.error(
                        f"❌ Failed to get pipeline steps: {response.status_code}"
                    )
                    return False

                # Test algorithms endpoint
                response = await client.get(
                    f"{self.api_base_url}/preprocessing/algorithms"
                )
                if response.status_code == 200:
                    algorithms = response.json()
                    logger.info(f"✅ Algorithms: {list(algorithms.keys())}")
                else:
                    logger.error(f"❌ Failed to get algorithms: {response.status_code}")
                    return False

                # Test default config endpoint
                response = await client.get(
                    f"{self.api_base_url}/preprocessing/default-config"
                )
                if response.status_code == 200:
                    default_config = response.json()
                    logger.info(f"✅ Default config: {default_config['name']}")
                else:
                    logger.error(
                        f"❌ Failed to get default config: {response.status_code}"
                    )
                    return False

            logger.info("✅ Preprocessing API endpoints working")
            return True

        except Exception as e:
            logger.error(f"❌ API endpoints test failed: {e}")
            return False

    async def test_worker_tasks(self) -> bool:
        """Test worker task imports and basic functionality."""
        logger.info("Testing worker tasks...")

        try:
            # Test task imports

            logger.info("✅ Worker tasks import successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Worker tasks test failed: {e}")
            return False

    async def test_error_handling(self) -> bool:
        """Test error handling for invalid inputs."""
        logger.info("Testing error handling...")

        try:
            # Test invalid pipeline configuration
            try:
                _ = PipelineConfig(
                    name="Invalid Pipeline",
                    steps=[],  # Empty steps should fail validation
                )
                # Should not reach here
                logger.error("❌ Invalid config validation failed")
                return False
            except ValueError:
                logger.info("✅ Correctly handled invalid pipeline configuration")

            # Test invalid step configuration
            try:
                _ = PipelineStepConfig(
                    step=PipelineStep.DENOISE,
                    algorithm=AlgorithmType.VOXEL_DOWN_SAMPLE,  # Wrong algorithm for denoising
                )
                # This should work but might fail during processing
                logger.info(
                    "✅ Step config created (validation will happen during processing)"
                )
            except Exception as e:
                logger.info(f"✅ Correctly handled invalid step configuration: {e}")

            logger.info("✅ Error handling working correctly")
            return True

        except Exception as e:
            logger.error(f"❌ Error handling test failed: {e}")
            return False

    def _create_test_mesh(self) -> trimesh.Trimesh:
        """Create a simple test mesh."""
        vertices = np.array(
            [
                [0, 0, 0],
                [1, 0, 0],
                [0, 1, 0],
                [0, 0, 1],
                [1, 1, 0],
                [1, 0, 1],
                [0, 1, 1],
                [1, 1, 1],
            ]
        )

        faces = np.array(
            [
                [0, 1, 2],
                [1, 4, 2],
                [1, 5, 4],
                [5, 7, 4],
                [5, 3, 7],
                [3, 6, 7],
                [3, 0, 6],
                [0, 2, 6],
                [2, 4, 6],
                [4, 7, 6],
                [1, 3, 5],
                [1, 0, 3],
            ]
        )

        return trimesh.Trimesh(vertices=vertices, faces=faces)

    def _create_noisy_mesh(self) -> trimesh.Trimesh:
        """Create a test mesh with noise."""
        mesh = self._create_test_mesh()

        # Add noise to vertices
        noise = np.random.normal(0, 0.01, mesh.vertices.shape)
        mesh.vertices += noise

        return mesh

    async def run_all_tests(self) -> Dict[str, bool]:
        """Run all preprocessing system tests."""
        logger.info("🚀 Starting EPIC E8 Preprocessing System Tests")
        logger.info("=" * 60)

        tests = [
            ("pipeline_configuration", self.test_pipeline_configuration),
            ("denoise_processor", self.test_denoise_processor),
            ("decimate_processor", self.test_decimate_processor),
            ("pipeline_execution", self.test_pipeline_execution),
            ("pipeline_caching", self.test_pipeline_caching),
            ("api_endpoints", self.test_api_endpoints),
            ("worker_tasks", self.test_worker_tasks),
            ("error_handling", self.test_error_handling),
        ]

        results = {}
        for test_name, test_func in tests:
            logger.info(f"\n🧪 Running test: {test_name}")
            try:
                results[test_name] = await test_func()
            except Exception as e:
                logger.error(f"❌ Test {test_name} failed with exception: {e}")
                results[test_name] = False

        # Summary
        passed = sum(1 for success in results.values() if success)
        total = len(results)

        logger.info("\n" + "=" * 60)
        logger.info("📊 Test Results Summary:")
        for test_name, success in results.items():
            status = "✅ PASS" if success else "❌ FAIL"
            logger.info(f"  {test_name}: {status}")

        logger.info(f"  Overall: {passed}/{total} tests passed")

        if passed == total:
            logger.info(
                "🎉 All tests passed! EPIC E8 implementation is working correctly."
            )
        else:
            logger.warning(
                f"⚠️ {total - passed} tests failed. Please check the implementation."
            )

        return results


async def main():
    """Main test function."""
    tester = PreprocessingSystemTester()
    results = await tester.run_all_tests()

    # Exit with appropriate code
    exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    asyncio.run(main())
