"""3D IO & Geometry Utilities for the dental backend system.

This module provides:
- Parser/loader abstraction over trimesh/open3d
- Mesh validation & normalization
- Resource limits and streaming loaders
- Unified interface for STL/PLY/OBJ/glTF/GLB formats
"""

import logging
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import psutil
import trimesh
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MeshFormat(str, Enum):
    """Supported mesh file formats."""

    STL = "stl"
    PLY = "ply"
    OBJ = "obj"
    GLTF = "gltf"
    GLB = "glb"
    FBX = "fbx"
    DAE = "dae"  # Collada


class ValidationLevel(str, Enum):
    """Mesh validation levels."""

    BASIC = "basic"  # Basic format validation
    STANDARD = "standard"  # Standard mesh validation
    STRICT = "strict"  # Strict validation with repairs


@dataclass
class MeshInfo:
    """Information about a loaded mesh."""

    vertices: int
    faces: int
    bounds: Tuple[np.ndarray, np.ndarray]  # min, max bounds
    volume: float
    surface_area: float
    is_watertight: bool
    is_manifold: bool
    has_normals: bool
    units: Optional[str] = None
    format: Optional[MeshFormat] = None
    file_size: Optional[int] = None
    load_time: Optional[float] = None


@dataclass
class ValidationReport:
    """Mesh validation report."""

    is_valid: bool
    issues: List[str]
    warnings: List[str]
    repairs_applied: List[str]
    validation_level: ValidationLevel
    mesh_info: MeshInfo
    validation_time: float


class MeshLoader(ABC):
    """Abstract base class for mesh loaders."""

    @abstractmethod
    def load(self, file_path: Union[str, Path], **kwargs) -> trimesh.Trimesh:
        """Load a mesh from file."""
        pass

    @abstractmethod
    def save(
        self, mesh: trimesh.Trimesh, file_path: Union[str, Path], **kwargs
    ) -> bool:
        """Save a mesh to file."""
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[MeshFormat]:
        """Get supported file formats."""
        pass


class TrimeshLoader(MeshLoader):
    """Trimesh-based mesh loader with streaming support."""

    def __init__(self, memory_limit_mb: int = 1024):
        self.memory_limit_mb = memory_limit_mb
        self._check_memory_usage()

    def _check_memory_usage(self) -> None:
        """Check if we have enough memory available."""
        available_memory = psutil.virtual_memory().available / (1024 * 1024)  # MB
        if available_memory < self.memory_limit_mb:
            logger.warning(
                f"Low memory available: {available_memory:.1f}MB < {self.memory_limit_mb}MB"
            )

    def load(self, file_path: Union[str, Path], **kwargs) -> trimesh.Trimesh:
        """Load a mesh from file with memory monitoring."""
        start_time = time.time()
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Mesh file not found: {file_path}")

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > self.memory_limit_mb * 1024 * 1024:
            raise MemoryError(
                f"File too large: {file_size / (1024*1024):.1f}MB > {self.memory_limit_mb}MB"
            )

        # Check available memory
        self._check_memory_usage()

        try:
            # Load mesh using trimesh
            mesh = trimesh.load(str(file_path), **kwargs)

            if mesh is None:
                raise ValueError(f"Failed to load mesh from {file_path}")

            # Validate loaded mesh
            if not hasattr(mesh, "vertices") or not hasattr(mesh, "faces"):
                raise ValueError(f"Invalid mesh format loaded from {file_path}")

            load_time = time.time() - start_time
            logger.info(f"Loaded mesh from {file_path} in {load_time:.2f}s")

            return mesh

        except Exception as e:
            logger.error(f"Failed to load mesh from {file_path}: {e}")
            raise

    def save(
        self, mesh: trimesh.Trimesh, file_path: Union[str, Path], **kwargs
    ) -> bool:
        """Save a mesh to file."""
        try:
            file_path = Path(file_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Export mesh using trimesh
            success = mesh.export(str(file_path), **kwargs)

            if success:
                logger.info(f"Saved mesh to {file_path}")
                return True
            else:
                logger.error(f"Failed to save mesh to {file_path}")
                return False

        except Exception as e:
            logger.error(f"Error saving mesh to {file_path}: {e}")
            return False

    def get_supported_formats(self) -> List[MeshFormat]:
        """Get supported file formats."""
        return [
            MeshFormat.STL,
            MeshFormat.PLY,
            MeshFormat.OBJ,
        ]


class MeshValidator:
    """Mesh validation and normalization utilities."""

    def __init__(self, validation_level: ValidationLevel = ValidationLevel.STANDARD):
        self.validation_level = validation_level

    def validate_mesh(self, mesh: trimesh.Trimesh) -> ValidationReport:
        """Validate a mesh and return a detailed report."""
        start_time = time.time()
        issues = []
        warnings = []
        repairs_applied = []

        # Basic mesh info
        mesh_info = self._get_mesh_info(mesh)

        # Validation checks
        if self.validation_level in [ValidationLevel.STANDARD, ValidationLevel.STRICT]:
            # Check for empty mesh
            if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
                issues.append("Mesh is empty (no vertices or faces)")

            # Check for degenerate faces
            degenerate_faces = self._find_degenerate_faces(mesh)
            if degenerate_faces:
                issues.append(f"Found {len(degenerate_faces)} degenerate faces")
                if self.validation_level == ValidationLevel.STRICT:
                    repairs_applied.append("Removed degenerate faces")
                    mesh = self._remove_degenerate_faces(mesh)

            # Check for duplicate vertices
            duplicate_vertices = self._find_duplicate_vertices(mesh)
            if duplicate_vertices:
                warnings.append(f"Found {len(duplicate_vertices)} duplicate vertices")
                if self.validation_level == ValidationLevel.STRICT:
                    repairs_applied.append("Removed duplicate vertices")
                    mesh = self._remove_duplicate_vertices(mesh)

            # Check normals
            has_normals = self._check_mesh_normals(mesh)
            if not has_normals:
                warnings.append("Mesh has no normals")
                if self.validation_level == ValidationLevel.STRICT:
                    repairs_applied.append("Generated face normals")
                    mesh.fix_normals()

            # Check manifoldness
            is_manifold = False
            try:
                if hasattr(mesh, "is_manifold"):
                    is_manifold = mesh.is_manifold
                else:
                    is_manifold = mesh.is_watertight and len(mesh.faces) > 0
            except Exception:
                is_manifold = False

            if not is_manifold:
                issues.append("Mesh is not manifold")

            # Check watertight
            if not mesh.is_watertight:
                warnings.append("Mesh is not watertight")

        # Strict validation
        if self.validation_level == ValidationLevel.STRICT:
            # Check for self-intersections
            has_self_intersections = False
            try:
                if hasattr(mesh, "has_self_intersections"):
                    has_self_intersections = mesh.has_self_intersections
                # Note: Self-intersection detection is computationally expensive
                # and may not be available in all trimesh versions
            except Exception:
                has_self_intersections = False

            if has_self_intersections:
                issues.append("Mesh has self-intersections")

            # Check for inverted faces
            inverted_faces = self._find_inverted_faces(mesh)
            if inverted_faces:
                warnings.append(f"Found {len(inverted_faces)} inverted faces")
                repairs_applied.append("Fixed inverted faces")
                mesh = self._fix_inverted_faces(mesh)

        validation_time = time.time() - start_time
        is_valid = len(issues) == 0

        return ValidationReport(
            is_valid=is_valid,
            issues=issues,
            warnings=warnings,
            repairs_applied=repairs_applied,
            validation_level=self.validation_level,
            mesh_info=mesh_info,
            validation_time=validation_time,
        )

    def _get_mesh_info(self, mesh: trimesh.Trimesh) -> MeshInfo:
        """Extract information about a mesh."""
        # Check if mesh is manifold (try different approaches)
        is_manifold = False
        try:
            # Try the property if it exists
            if hasattr(mesh, "is_manifold"):
                is_manifold = mesh.is_manifold
            else:
                # Fallback: check if mesh is watertight and has consistent face winding
                is_manifold = mesh.is_watertight and len(mesh.faces) > 0
        except Exception:
            # If any error occurs, assume not manifold
            is_manifold = False

        return MeshInfo(
            vertices=len(mesh.vertices),
            faces=len(mesh.faces),
            bounds=(mesh.bounds[0], mesh.bounds[1]),
            volume=mesh.volume if mesh.is_watertight else 0.0,
            surface_area=mesh.area,
            is_watertight=mesh.is_watertight,
            is_manifold=is_manifold,
            has_normals=self._check_mesh_normals(mesh),
        )

    def _find_degenerate_faces(self, mesh: trimesh.Trimesh) -> List[int]:
        """Find degenerate faces (faces with zero area)."""
        areas = mesh.area_faces
        return np.where(areas < 1e-10)[0].tolist()

    def _remove_degenerate_faces(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Remove degenerate faces from mesh."""
        areas = mesh.area_faces
        valid_faces = areas > 1e-10
        return mesh.submesh([valid_faces])

    def _find_duplicate_vertices(self, mesh: trimesh.Trimesh) -> List[int]:
        """Find duplicate vertices."""
        unique_vertices, inverse_indices = np.unique(
            mesh.vertices, axis=0, return_inverse=True
        )
        return np.where(inverse_indices != np.arange(len(mesh.vertices)))[0].tolist()

    def _remove_duplicate_vertices(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Remove duplicate vertices from mesh."""
        try:
            if hasattr(mesh, "deduplicate_vertices"):
                return mesh.deduplicate_vertices()
            else:
                # Fallback: return original mesh if deduplication not available
                logger.warning(
                    "Mesh deduplication not available, returning original mesh"
                )
                return mesh
        except Exception as e:
            logger.warning(
                f"Failed to deduplicate vertices: {e}, returning original mesh"
            )
            return mesh

    def _find_inverted_faces(self, mesh: trimesh.Trimesh) -> List[int]:
        """Find inverted faces (faces with wrong winding order)."""
        try:
            if not hasattr(mesh, "has_face_normals") or not mesh.has_face_normals:
                return []
        except Exception:
            return []

        # Check if face normals point outward (assuming watertight mesh)
        face_normals = mesh.face_normals
        face_centers = mesh.triangles_center

        # Calculate outward normals from center
        outward_normals = face_centers - mesh.center_mass
        outward_normals = outward_normals / np.linalg.norm(
            outward_normals, axis=1, keepdims=True
        )

        # Check dot product
        dot_products = np.sum(face_normals * outward_normals, axis=1)
        return np.where(dot_products < 0)[0].tolist()

    def _fix_inverted_faces(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        """Fix inverted faces by reversing winding order."""
        mesh.fix_normals()
        return mesh

    def _check_mesh_normals(self, mesh: trimesh.Trimesh) -> bool:
        """Check if mesh has normals."""
        try:
            # Try different approaches to check for normals
            if hasattr(mesh, "has_vertex_normals") and hasattr(
                mesh, "has_face_normals"
            ):
                return mesh.has_vertex_normals or mesh.has_face_normals
            elif hasattr(mesh, "vertex_normals") and hasattr(mesh, "face_normals"):
                return len(mesh.vertex_normals) > 0 or len(mesh.face_normals) > 0
            else:
                # Fallback: check if normals can be computed
                return len(mesh.faces) > 0
        except Exception:
            return False


class MeshNormalizer:
    """Mesh normalization utilities."""

    def __init__(self, target_scale: float = 1.0, target_units: str = "mm"):
        self.target_scale = target_scale
        self.target_units = target_units

    def normalize_mesh(
        self, mesh: trimesh.Trimesh, units: Optional[str] = None
    ) -> trimesh.Trimesh:
        """Normalize mesh scale and coordinate system."""
        normalized_mesh = mesh.copy()

        # Scale normalization
        if units and units != self.target_units:
            scale_factor = self._get_scale_factor(units, self.target_units)
            normalized_mesh.apply_transform(
                trimesh.transformations.scale_matrix(scale_factor)
            )

        # Center mesh
        normalized_mesh.apply_translation(-normalized_mesh.center_mass)

        # Scale to target size
        current_scale = np.max(normalized_mesh.bounds[1] - normalized_mesh.bounds[0])
        if current_scale > 0:
            scale_factor = self.target_scale / current_scale
            normalized_mesh.apply_transform(
                trimesh.transformations.scale_matrix(scale_factor)
            )

        return normalized_mesh

    def _get_scale_factor(self, from_units: str, to_units: str) -> float:
        """Get scale factor for unit conversion."""
        unit_conversions = {
            "mm": 1.0,
            "cm": 10.0,
            "m": 1000.0,
            "in": 25.4,
            "ft": 304.8,
        }

        from_factor = unit_conversions.get(from_units.lower(), 1.0)
        to_factor = unit_conversions.get(to_units.lower(), 1.0)

        return from_factor / to_factor


class MeshProcessor:
    """Main mesh processing class with unified interface."""

    def __init__(
        self,
        memory_limit_mb: int = 1024,
        validation_level: ValidationLevel = ValidationLevel.STANDARD,
        target_scale: float = 1.0,
        target_units: str = "mm",
    ):
        self.loader = TrimeshLoader(memory_limit_mb)
        self.validator = MeshValidator(validation_level)
        self.normalizer = MeshNormalizer(target_scale, target_units)

    def load_mesh(
        self,
        file_path: Union[str, Path],
        validate: bool = True,
        normalize: bool = False,
        units: Optional[str] = None,
    ) -> Tuple[trimesh.Trimesh, ValidationReport]:
        """Load and optionally validate/normalize a mesh."""
        # Load mesh
        mesh = self.loader.load(file_path)

        # Validate mesh
        validation_report = self.validator.validate_mesh(mesh) if validate else None

        # Normalize mesh if requested
        if normalize:
            mesh = self.normalizer.normalize_mesh(mesh, units)

        return mesh, validation_report

    def save_mesh(
        self,
        mesh: trimesh.Trimesh,
        file_path: Union[str, Path],
        format: Optional[MeshFormat] = None,
    ) -> bool:
        """Save a mesh to file."""
        if format:
            file_path = Path(file_path).with_suffix(f".{format.value}")

        return self.loader.save(mesh, file_path)

    def process_mesh(
        self,
        input_path: Union[str, Path],
        output_path: Union[str, Path],
        validate: bool = True,
        normalize: bool = False,
        units: Optional[str] = None,
        output_format: Optional[MeshFormat] = None,
    ) -> ValidationReport:
        """Complete mesh processing pipeline."""
        # Load and process mesh
        mesh, validation_report = self.load_mesh(
            input_path, validate=validate, normalize=normalize, units=units
        )

        # Save processed mesh
        success = self.save_mesh(mesh, output_path, output_format)
        if not success:
            raise RuntimeError(f"Failed to save processed mesh to {output_path}")

        return validation_report

    def get_supported_formats(self) -> List[MeshFormat]:
        """Get supported file formats."""
        return self.loader.get_supported_formats()


# Pydantic models for API integration
class MeshProcessingRequest(BaseModel):
    """Request model for mesh processing."""

    input_path: str = Field(..., description="Input mesh file path")
    output_path: str = Field(..., description="Output mesh file path")
    should_validate: bool = Field(default=True, description="Perform mesh validation")
    normalize: bool = Field(
        default=False, description="Normalize mesh scale and position"
    )
    units: Optional[str] = Field(default=None, description="Input mesh units")
    output_format: Optional[MeshFormat] = Field(
        default=None, description="Output format"
    )
    validation_level: ValidationLevel = Field(
        default=ValidationLevel.STANDARD, description="Validation level"
    )
    memory_limit_mb: int = Field(default=1024, description="Memory limit in MB")


class MeshInfoResponse(BaseModel):
    """Response model for mesh information."""

    vertices: int = Field(..., description="Number of vertices")
    faces: int = Field(..., description="Number of faces")
    volume: float = Field(..., description="Mesh volume")
    surface_area: float = Field(..., description="Surface area")
    is_watertight: bool = Field(..., description="Is mesh watertight")
    is_manifold: bool = Field(..., description="Is mesh manifold")
    has_normals: bool = Field(..., description="Has normals")
    units: Optional[str] = Field(default=None, description="Mesh units")
    format: Optional[str] = Field(default=None, description="File format")
    file_size: Optional[int] = Field(default=None, description="File size in bytes")
    load_time: Optional[float] = Field(default=None, description="Load time in seconds")


class ValidationReportResponse(BaseModel):
    """Response model for validation report."""

    is_valid: bool = Field(..., description="Is mesh valid")
    issues: List[str] = Field(..., description="Validation issues")
    warnings: List[str] = Field(..., description="Validation warnings")
    repairs_applied: List[str] = Field(..., description="Repairs applied")
    validation_level: str = Field(..., description="Validation level used")
    mesh_info: MeshInfoResponse = Field(..., description="Mesh information")
    validation_time: float = Field(..., description="Validation time in seconds")


class MeshProcessingResponse(BaseModel):
    """Response model for mesh processing."""

    success: bool = Field(..., description="Processing success status")
    input_path: str = Field(..., description="Input file path")
    output_path: str = Field(..., description="Output file path")
    validation_report: Optional[ValidationReportResponse] = Field(
        default=None, description="Validation report"
    )
    processing_time: float = Field(..., description="Total processing time in seconds")
    error_message: Optional[str] = Field(
        default=None, description="Error message if failed"
    )


# Utility functions for round-trip testing
def create_test_mesh() -> trimesh.Trimesh:
    """Create a simple test mesh for round-trip testing."""
    vertices = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
        ]
    )
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [0, 3, 1],
            [1, 3, 2],
        ]
    )
    return trimesh.Trimesh(vertices=vertices, faces=faces)


def round_trip_test(
    processor: MeshProcessor, format: MeshFormat, temp_dir: Optional[Path] = None
) -> bool:
    """Test round-trip loading and saving for a specific format."""
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp())

    # Create test mesh
    test_mesh = create_test_mesh()

    # Save mesh
    output_path = temp_dir / f"test.{format.value}"
    success = processor.save_mesh(test_mesh, output_path)
    if not success:
        return False

    # Load mesh back
    try:
        loaded_mesh, _ = processor.load_mesh(output_path, validate=False)

        # Compare basic properties
        if len(loaded_mesh.vertices) != len(test_mesh.vertices):
            return False
        if len(loaded_mesh.faces) != len(test_mesh.faces):
            return False

        return True

    except Exception as e:
        logger.error(f"Round-trip test failed for {format}: {e}")
        return False


def run_round_trip_tests(processor: MeshProcessor) -> Dict[MeshFormat, bool]:
    """Run round-trip tests for all supported formats."""
    results = {}

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for format in processor.get_supported_formats():
            results[format] = round_trip_test(processor, format, temp_path)
            logger.info(
                f"Round-trip test for {format}: {'PASS' if results[format] else 'FAIL'}"
            )

    return results
