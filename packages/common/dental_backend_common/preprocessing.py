"""Pre-processing pipeline for dental scans (EPIC E8)."""

import hashlib
import json
import logging
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import trimesh
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

# Try to import Open3D, fallback to trimesh if not available
try:
    import open3d as o3d

    OPEN3D_AVAILABLE = True
except ImportError:
    OPEN3D_AVAILABLE = False
    logger.warning(
        "Open3D not available, using trimesh fallbacks for advanced algorithms"
    )


class PipelineStep(str, Enum):
    """Pre-processing pipeline steps."""

    DENOISE = "denoise"
    DECIMATE = "decimate"
    HOLE_FILL = "hole_fill"
    ALIGNMENT = "alignment"
    ROI_CROP = "roi_crop"
    TOOTH_ARCH_ISOLATION = "tooth_arch_isolation"


class AlgorithmType(str, Enum):
    """Types of algorithms for each step."""

    # Denoising
    BILATERAL_FILTER = "bilateral_filter"
    GAUSSIAN_FILTER = "gaussian_filter"
    STATISTICAL_OUTLIER_REMOVAL = "statistical_outlier_removal"

    # Decimation
    VOXEL_DOWN_SAMPLE = "voxel_down_sample"
    UNIFORM_DOWN_SAMPLE = "uniform_down_sample"

    # Hole filling
    POISSON_RECONSTRUCTION = "poisson_reconstruction"
    BALL_PIVOTING = "ball_pivoting"
    ALPHA_SHAPE = "alpha_shape"

    # Alignment
    ICP_ALIGNMENT = "icp_alignment"
    LANDMARK_ALIGNMENT = "landmark_alignment"
    FEATURE_BASED_ALIGNMENT = "feature_based_alignment"

    # ROI cropping
    BOUNDING_BOX_CROP = "bounding_box_crop"
    SPHERICAL_CROP = "spherical_crop"
    PLANAR_CROP = "planar_crop"

    # Tooth arch isolation
    CURVATURE_BASED_SEGMENTATION = "curvature_based_segmentation"
    CLUSTERING_SEGMENTATION = "clustering_segmentation"
    MACHINE_LEARNING_SEGMENTATION = "machine_learning_segmentation"


@dataclass
class PipelineMetrics:
    """Metrics for pipeline step evaluation."""

    input_vertices: int
    input_faces: int
    output_vertices: int
    output_faces: int
    processing_time: float
    memory_usage_mb: float
    quality_score: Optional[float] = None
    curvature_stats: Optional[Dict[str, float]] = None

    @property
    def vertex_reduction_ratio(self) -> float:
        """Calculate vertex reduction ratio."""
        if self.input_vertices == 0:
            return 0.0
        return (self.input_vertices - self.output_vertices) / self.input_vertices

    @property
    def face_reduction_ratio(self) -> float:
        """Calculate face reduction ratio."""
        if self.input_faces == 0:
            return 0.0
        return (self.input_faces - self.output_faces) / self.input_faces


@dataclass
class CacheEntry:
    """Cache entry for intermediate artifacts."""

    content_hash: str
    file_path: Path
    step_name: str
    parameters: Dict[str, Any]
    metrics: PipelineMetrics
    created_at: float
    accessed_at: float
    access_count: int = 0

    def update_access(self) -> None:
        """Update access statistics."""
        self.accessed_at = time.time()
        self.access_count += 1


class PipelineStepConfig(BaseModel):
    """Configuration for a single pipeline step."""

    step: PipelineStep = Field(..., description="Pipeline step to execute")
    algorithm: AlgorithmType = Field(..., description="Algorithm to use")
    enabled: bool = Field(default=True, description="Whether step is enabled")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Step parameters"
    )
    cache_enabled: bool = Field(
        default=True, description="Enable caching for this step"
    )

    @validator("parameters")
    def validate_parameters(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Validate step parameters."""
        # Add parameter validation logic here
        return v


class PipelineConfig(BaseModel):
    """Complete pipeline configuration."""

    name: str = Field(..., description="Pipeline name")
    version: str = Field(default="1.0.0", description="Pipeline version")
    description: str = Field(default="", description="Pipeline description")
    steps: List[PipelineStepConfig] = Field(..., description="Pipeline steps")
    cache_enabled: bool = Field(default=True, description="Enable pipeline caching")
    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours")

    @validator("steps")
    def validate_steps(cls, v: List[PipelineStepConfig]) -> List[PipelineStepConfig]:
        """Validate pipeline steps."""
        if not v:
            raise ValueError("Pipeline must have at least one step")

        # Check for duplicate steps
        step_names = [step.step for step in v]
        if len(step_names) != len(set(step_names)):
            raise ValueError("Duplicate pipeline steps not allowed")

        return v

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return self.dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineConfig":
        """Create from dictionary."""
        return cls(**data)

    def get_step_config(self, step: PipelineStep) -> Optional[PipelineStepConfig]:
        """Get configuration for a specific step."""
        for step_config in self.steps:
            if step_config.step == step:
                return step_config
        return None


class PipelineStepProcessor(ABC):
    """Abstract base class for pipeline step processors."""

    def __init__(self, config: PipelineStepConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def process(
        self, mesh: trimesh.Trimesh, **kwargs
    ) -> Tuple[trimesh.Trimesh, PipelineMetrics]:
        """Process the mesh and return processed mesh with metrics."""
        pass

    @abstractmethod
    def get_cache_key(self, mesh: trimesh.Trimesh, **kwargs) -> str:
        """Generate cache key for this step."""
        pass


class DenoiseProcessor(PipelineStepProcessor):
    """Denoising step processor."""

    def process(
        self, mesh: trimesh.Trimesh, **kwargs
    ) -> Tuple[trimesh.Trimesh, PipelineMetrics]:
        """Apply denoising to the mesh."""
        start_time = time.time()

        if OPEN3D_AVAILABLE:
            # Use Open3D for advanced denoising
            o3d_mesh = self._trimesh_to_o3d(mesh)

            # Apply denoising based on algorithm
            if self.config.algorithm == AlgorithmType.BILATERAL_FILTER:
                processed_mesh = self._bilateral_filter(o3d_mesh)
            elif self.config.algorithm == AlgorithmType.GAUSSIAN_FILTER:
                processed_mesh = self._gaussian_filter(o3d_mesh)
            elif self.config.algorithm == AlgorithmType.STATISTICAL_OUTLIER_REMOVAL:
                processed_mesh = self._statistical_outlier_removal(o3d_mesh)
            else:
                raise ValueError(
                    f"Unsupported denoising algorithm: {self.config.algorithm}"
                )

            # Convert back to trimesh
            result_mesh = self._o3d_to_trimesh(processed_mesh)
        else:
            # Fallback to trimesh-based denoising
            result_mesh = self._trimesh_denoise_fallback(mesh)

        processing_time = time.time() - start_time

        metrics = PipelineMetrics(
            input_vertices=len(mesh.vertices),
            input_faces=len(mesh.faces),
            output_vertices=len(result_mesh.vertices),
            output_faces=len(result_mesh.faces),
            processing_time=processing_time,
            memory_usage_mb=self._get_memory_usage(),
        )

        return result_mesh, metrics

    def get_cache_key(self, mesh: trimesh.Trimesh, **kwargs) -> str:
        """Generate cache key for denoising step."""
        # Create hash from mesh properties and parameters
        content = f"{len(mesh.vertices)}_{len(mesh.faces)}_{self.config.algorithm}_{json.dumps(self.config.parameters, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _trimesh_to_o3d(self, mesh: trimesh.Trimesh) -> Any:
        """Convert trimesh to Open3D mesh."""
        if not OPEN3D_AVAILABLE:
            raise ImportError("Open3D is not available")

        o3d_mesh = o3d.geometry.TriangleMesh()
        o3d_mesh.vertices = o3d.utility.Vector3dVector(mesh.vertices)
        o3d_mesh.triangles = o3d.utility.Vector3iVector(mesh.faces)
        if hasattr(mesh, "vertex_normals") and len(mesh.vertex_normals) > 0:
            o3d_mesh.vertex_normals = o3d.utility.Vector3dVector(mesh.vertex_normals)
        return o3d_mesh

    def _o3d_to_trimesh(self, o3d_mesh: Any) -> trimesh.Trimesh:
        """Convert Open3D mesh to trimesh."""
        if not OPEN3D_AVAILABLE:
            raise ImportError("Open3D is not available")

        vertices = np.asarray(o3d_mesh.vertices)
        faces = np.asarray(o3d_mesh.triangles)
        return trimesh.Trimesh(vertices=vertices, faces=faces)

    def _bilateral_filter(self, mesh: Any) -> Any:
        """Apply bilateral filter."""
        params = self.config.parameters
        sigma_s = params.get("sigma_s", 1.0)
        sigma_r = params.get("sigma_r", 0.1)
        iterations = params.get("iterations", 1)

        for _ in range(iterations):
            mesh = mesh.filter_bilateral(sigma_s, sigma_r)

        return mesh

    def _gaussian_filter(self, mesh: Any) -> Any:
        """Apply Gaussian filter."""
        params = self.config.parameters
        sigma = params.get("sigma", 1.0)
        iterations = params.get("iterations", 1)

        for _ in range(iterations):
            mesh = mesh.filter_gaussian(sigma)

        return mesh

    def _statistical_outlier_removal(self, mesh: Any) -> Any:
        """Apply statistical outlier removal."""
        params = self.config.parameters
        nb_neighbors = params.get("nb_neighbors", 20)
        std_ratio = params.get("std_ratio", 2.0)

        mesh, _ = mesh.remove_statistical_outlier(nb_neighbors, std_ratio)
        return mesh

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    def _trimesh_decimate_fallback(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Fallback decimation using trimesh when Open3D is not available."""
        params = self.config.parameters

        if self.config.algorithm == AlgorithmType.VOXEL_DOWN_SAMPLE:
            # Simple voxel-based decimation using trimesh
            # Use a simple approach: reduce mesh by removing vertices
            target_vertices = max(100, int(len(mesh.vertices) * 0.5))
            return mesh.simplify_quadric_decimation(target_vertices)
        elif self.config.algorithm == AlgorithmType.UNIFORM_DOWN_SAMPLE:
            # Uniform decimation
            target_vertices = params.get("target_vertices", len(mesh.vertices) // 2)
            return mesh.simplify_quadric_decimation(target_vertices)
        else:
            # Default to 50% reduction
            return mesh.simplify_quadric_decimation(len(mesh.vertices) // 2)

    def _trimesh_denoise_fallback(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Fallback denoising using trimesh when Open3D is not available."""
        # Simple denoising using trimesh's built-in methods
        denoised_mesh = mesh.copy()

        # Remove duplicate vertices
        if hasattr(denoised_mesh, "deduplicate_vertices"):
            denoised_mesh = denoised_mesh.deduplicate_vertices()

        # Fix normals
        denoised_mesh.fix_normals()

        # Remove degenerate faces
        areas = denoised_mesh.area_faces
        valid_faces = areas > 1e-10
        if not np.all(valid_faces):
            denoised_mesh = denoised_mesh.submesh([valid_faces])

        return denoised_mesh


class DecimateProcessor(PipelineStepProcessor):
    """Decimation step processor."""

    def process(
        self, mesh: trimesh.Trimesh, **kwargs
    ) -> Tuple[trimesh.Trimesh, PipelineMetrics]:
        """Apply decimation to the mesh."""
        start_time = time.time()

        if OPEN3D_AVAILABLE:
            # Use Open3D for advanced decimation
            o3d_mesh = self._trimesh_to_o3d(mesh)

            # Apply decimation based on algorithm
            if self.config.algorithm == AlgorithmType.VOXEL_DOWN_SAMPLE:
                processed_mesh = self._voxel_down_sample(o3d_mesh)
            elif self.config.algorithm == AlgorithmType.UNIFORM_DOWN_SAMPLE:
                processed_mesh = self._uniform_down_sample(o3d_mesh)
            else:
                raise ValueError(
                    f"Unsupported decimation algorithm: {self.config.algorithm}"
                )

            # Convert back to trimesh
            result_mesh = self._o3d_to_trimesh(processed_mesh)
        else:
            # Fallback to trimesh-based decimation
            result_mesh = self._trimesh_decimate_fallback(mesh)

        processing_time = time.time() - start_time

        metrics = PipelineMetrics(
            input_vertices=len(mesh.vertices),
            input_faces=len(mesh.faces),
            output_vertices=len(result_mesh.vertices),
            output_faces=len(result_mesh.faces),
            processing_time=processing_time,
            memory_usage_mb=self._get_memory_usage(),
        )

        return result_mesh, metrics

    def get_cache_key(self, mesh: trimesh.Trimesh, **kwargs) -> str:
        """Generate cache key for decimation step."""
        content = f"{len(mesh.vertices)}_{len(mesh.faces)}_{self.config.algorithm}_{json.dumps(self.config.parameters, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _trimesh_to_o3d(self, mesh: trimesh.Trimesh) -> Any:
        """Convert trimesh to Open3D mesh."""
        if not OPEN3D_AVAILABLE:
            raise ImportError("Open3D is not available")

        o3d_mesh = o3d.geometry.TriangleMesh()
        o3d_mesh.vertices = o3d.utility.Vector3dVector(mesh.vertices)
        o3d_mesh.triangles = o3d.utility.Vector3iVector(mesh.faces)
        return o3d_mesh

    def _o3d_to_trimesh(self, o3d_mesh: Any) -> trimesh.Trimesh:
        """Convert Open3D mesh to trimesh."""
        if not OPEN3D_AVAILABLE:
            raise ImportError("Open3D is not available")

        vertices = np.asarray(o3d_mesh.vertices)
        faces = np.asarray(o3d_mesh.triangles)
        return trimesh.Trimesh(vertices=vertices, faces=faces)

    def _voxel_down_sample(self, mesh: Any) -> Any:
        """Apply voxel down sampling."""
        params = self.config.parameters
        voxel_size = params.get("voxel_size", 0.05)

        # Convert to point cloud for voxel down sampling
        pcd = mesh.sample_points_uniformly(number_of_points=len(mesh.vertices) * 10)
        downsampled_pcd = pcd.voxel_down_sample(voxel_size)

        # Reconstruct mesh from point cloud
        mesh_reconstructed = (
            o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(
                downsampled_pcd
            )
        )
        return mesh_reconstructed

    def _uniform_down_sample(self, mesh: Any) -> Any:
        """Apply uniform down sampling."""
        params = self.config.parameters
        target_vertices = params.get("target_vertices", len(mesh.vertices) // 2)

        # Use trimesh's decimation
        trimesh_mesh = self._o3d_to_trimesh(mesh)
        decimated_mesh = trimesh_mesh.simplify_quadric_decimation(target_vertices)
        return self._trimesh_to_o3d(decimated_mesh)

    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    def _trimesh_decimate_fallback(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Fallback decimation using trimesh when Open3D is not available."""
        params = self.config.parameters

        # Simple decimation by removing every other vertex (simplified approach)
        if self.config.algorithm == AlgorithmType.VOXEL_DOWN_SAMPLE:
            # Simple voxel-based decimation using trimesh
            # Use a simple approach: reduce mesh by removing vertices
            target_vertices = max(100, int(len(mesh.vertices) * 0.5))
        elif self.config.algorithm == AlgorithmType.UNIFORM_DOWN_SAMPLE:
            # Uniform decimation
            target_vertices = params.get("target_vertices", len(mesh.vertices) // 2)
        else:
            # Default to 50% reduction
            target_vertices = len(mesh.vertices) // 2

        # Simple decimation: keep every nth vertex
        if target_vertices >= len(mesh.vertices):
            return mesh

        # Calculate step size to achieve target vertex count
        step = max(1, len(mesh.vertices) // target_vertices)

        # Create new mesh with reduced vertices
        new_vertices = mesh.vertices[::step]
        new_faces = []

        # Remap face indices to new vertex indices
        vertex_map = {
            old_idx: new_idx
            for new_idx, old_idx in enumerate(range(0, len(mesh.vertices), step))
        }

        for face in mesh.faces:
            # Check if all vertices in face are in the new vertex set
            if all(v in vertex_map for v in face):
                new_face = [vertex_map[v] for v in face]
                new_faces.append(new_face)

        if len(new_faces) == 0:
            # If no faces remain, return original mesh
            return mesh

        return trimesh.Trimesh(vertices=new_vertices, faces=new_faces)


class PipelineCache:
    """Cache for pipeline intermediate artifacts."""

    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Statistics
        self.hit_count = 0
        self.miss_count = 0

    def get(self, cache_key: str) -> Optional[CacheEntry]:
        """Get cached entry if valid."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        mesh_file = self.cache_dir / f"{cache_key}.ply"

        if not cache_file.exists() or not mesh_file.exists():
            self.miss_count += 1
            return None

        try:
            # Load cache metadata
            with open(cache_file) as f:
                metadata = json.load(f)

            # Check TTL
            if time.time() - metadata["created_at"] > self.ttl_seconds:
                self.logger.info(f"Cache entry {cache_key} expired")
                self._remove_entry(cache_key)
                self.miss_count += 1
                return None

            # Load mesh
            _ = trimesh.load(str(mesh_file))

            entry = CacheEntry(
                content_hash=cache_key,
                file_path=mesh_file,
                step_name=metadata["step_name"],
                parameters=metadata["parameters"],
                metrics=PipelineMetrics(**metadata["metrics"]),
                created_at=metadata["created_at"],
                accessed_at=metadata["accessed_at"],
                access_count=metadata["access_count"],
            )

            entry.update_access()
            self.hit_count += 1

            self.logger.info(f"Cache hit for {cache_key}")
            return entry

        except Exception as e:
            self.logger.error(f"Error loading cache entry {cache_key}: {e}")
            self._remove_entry(cache_key)
            self.miss_count += 1
            return None

    def put(
        self,
        cache_key: str,
        mesh: trimesh.Trimesh,
        step_name: str,
        parameters: Dict[str, Any],
        metrics: PipelineMetrics,
    ) -> None:
        """Store mesh and metadata in cache."""
        try:
            # Save mesh
            mesh_file = self.cache_dir / f"{cache_key}.ply"
            mesh.export(str(mesh_file))

            # Save metadata
            cache_file = self.cache_dir / f"{cache_key}.json"
            metadata = {
                "step_name": step_name,
                "parameters": parameters,
                "metrics": {
                    "input_vertices": metrics.input_vertices,
                    "input_faces": metrics.input_faces,
                    "output_vertices": metrics.output_vertices,
                    "output_faces": metrics.output_faces,
                    "processing_time": metrics.processing_time,
                    "memory_usage_mb": metrics.memory_usage_mb,
                    "quality_score": metrics.quality_score,
                    "curvature_stats": metrics.curvature_stats,
                },
                "created_at": time.time(),
                "accessed_at": time.time(),
                "access_count": 1,
            }

            with open(cache_file, "w") as f:
                json.dump(metadata, f, indent=2)

            self.logger.info(f"Cached result for {cache_key}")

        except Exception as e:
            self.logger.error(f"Error caching entry {cache_key}: {e}")

    def _remove_entry(self, cache_key: str) -> None:
        """Remove cache entry."""
        cache_file = self.cache_dir / f"{cache_key}.json"
        mesh_file = self.cache_dir / f"{cache_key}.ply"

        if cache_file.exists():
            cache_file.unlink()
        if mesh_file.exists():
            mesh_file.unlink()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": self.hit_count / (self.hit_count + self.miss_count)
            if (self.hit_count + self.miss_count) > 0
            else 0.0,
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl_seconds / 3600,
        }


class PreprocessingPipeline:
    """Main preprocessing pipeline class."""

    def __init__(self, config: PipelineConfig, cache_dir: Optional[Path] = None):
        self.config = config
        self.cache = PipelineCache(
            cache_dir or Path(tempfile.gettempdir()) / "dental_pipeline_cache",
            self.config.cache_ttl_hours,
        )
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Initialize processors
        self.processors = self._initialize_processors()

    def _initialize_processors(self) -> Dict[PipelineStep, PipelineStepProcessor]:
        """Initialize processors for each step."""
        processors = {}

        for step_config in self.config.steps:
            if step_config.step == PipelineStep.DENOISE:
                processors[step_config.step] = DenoiseProcessor(step_config)
            elif step_config.step == PipelineStep.DECIMATE:
                processors[step_config.step] = DecimateProcessor(step_config)
            # Add other processors as needed
            else:
                self.logger.warning(
                    f"No processor implemented for step: {step_config.step}"
                )

        return processors

    def process(
        self, input_mesh: trimesh.Trimesh, **kwargs
    ) -> Tuple[trimesh.Trimesh, Dict[str, PipelineMetrics]]:
        """Process mesh through the pipeline."""
        self.logger.info(f"Starting pipeline processing: {self.config.name}")

        current_mesh = input_mesh
        all_metrics = {}

        for step_config in self.config.steps:
            if not step_config.enabled:
                self.logger.info(f"Skipping disabled step: {step_config.step}")
                continue

            self.logger.info(f"Processing step: {step_config.step}")

            # Check cache
            if step_config.cache_enabled and self.config.cache_enabled:
                processor = self.processors.get(step_config.step)
                if processor:
                    cache_key = processor.get_cache_key(current_mesh, **kwargs)
                    cached_entry = self.cache.get(cache_key)

                    if cached_entry:
                        self.logger.info(f"Using cached result for {step_config.step}")
                        current_mesh = trimesh.load(str(cached_entry.file_path))
                        all_metrics[step_config.step.value] = cached_entry.metrics
                        continue

            # Process step
            processor = self.processors.get(step_config.step)
            if not processor:
                self.logger.warning(
                    f"No processor for step {step_config.step}, skipping"
                )
                continue

            try:
                processed_mesh, metrics = processor.process(current_mesh, **kwargs)
                current_mesh = processed_mesh
                all_metrics[step_config.step.value] = metrics

                # Cache result
                if step_config.cache_enabled and self.config.cache_enabled:
                    cache_key = processor.get_cache_key(input_mesh, **kwargs)
                    self.cache.put(
                        cache_key,
                        processed_mesh,
                        step_config.step.value,
                        step_config.parameters,
                        metrics,
                    )

                self.logger.info(
                    f"Completed step {step_config.step}: "
                    f"{metrics.input_vertices}->{metrics.output_vertices} vertices, "
                    f"{metrics.processing_time:.2f}s"
                )

            except Exception as e:
                self.logger.error(f"Error in step {step_config.step}: {e}")
                raise

        # Log cache statistics
        cache_stats = self.cache.get_stats()
        self.logger.info(f"Pipeline completed. Cache stats: {cache_stats}")

        return current_mesh, all_metrics

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()


# Pydantic models for API integration
class PipelineStepRequest(BaseModel):
    """Request model for pipeline step configuration."""

    step: PipelineStep = Field(..., description="Pipeline step")
    algorithm: AlgorithmType = Field(..., description="Algorithm to use")
    enabled: bool = Field(default=True, description="Whether step is enabled")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Step parameters"
    )
    cache_enabled: bool = Field(
        default=True, description="Enable caching for this step"
    )


class PipelineRequest(BaseModel):
    """Request model for pipeline configuration."""

    name: str = Field(..., description="Pipeline name")
    description: str = Field(default="", description="Pipeline description")
    steps: List[PipelineStepRequest] = Field(..., description="Pipeline steps")
    cache_enabled: bool = Field(default=True, description="Enable pipeline caching")
    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours")


class PipelineResponse(BaseModel):
    """Response model for pipeline processing."""

    success: bool = Field(..., description="Processing success status")
    input_vertices: int = Field(..., description="Input mesh vertices")
    input_faces: int = Field(..., description="Input mesh faces")
    output_vertices: int = Field(..., description="Output mesh vertices")
    output_faces: int = Field(..., description="Output mesh faces")
    processing_time: float = Field(..., description="Total processing time")
    step_metrics: Dict[str, PipelineMetrics] = Field(
        ..., description="Metrics for each step"
    )
    cache_stats: Dict[str, Any] = Field(..., description="Cache statistics")
    error_message: Optional[str] = Field(
        default=None, description="Error message if failed"
    )


# Utility functions
def create_default_pipeline() -> PipelineConfig:
    """Create a default preprocessing pipeline."""
    return PipelineConfig(
        name="Default Dental Preprocessing",
        description="Standard preprocessing pipeline for dental scans",
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


def load_pipeline_config(config_path: Path) -> PipelineConfig:
    """Load pipeline configuration from file."""
    with open(config_path) as f:
        config_data = json.load(f)
    return PipelineConfig.from_dict(config_data)


def save_pipeline_config(config: PipelineConfig, config_path: Path) -> None:
    """Save pipeline configuration to file."""
    with open(config_path, "w") as f:
        json.dump(config.to_dict(), f, indent=2)
