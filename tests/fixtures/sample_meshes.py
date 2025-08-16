"""Sample mesh fixtures for testing 3D geometry utilities."""

from pathlib import Path

import numpy as np
import trimesh


def create_cube_mesh() -> trimesh.Trimesh:
    """Create a simple cube mesh."""
    vertices = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
            [0, 1, 0],  # bottom face
            [0, 0, 1],
            [1, 0, 1],
            [1, 1, 1],
            [0, 1, 1],  # top face
        ]
    )

    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],  # bottom
            [4, 7, 6],
            [4, 6, 5],  # top
            [0, 4, 5],
            [0, 5, 1],  # front
            [1, 5, 6],
            [1, 6, 2],  # right
            [2, 6, 7],
            [2, 7, 3],  # back
            [3, 7, 4],
            [3, 4, 0],  # left
        ]
    )

    return trimesh.Trimesh(vertices=vertices, faces=faces)


def create_sphere_mesh(radius: float = 1.0, subdivisions: int = 2) -> trimesh.Trimesh:
    """Create a sphere mesh using icosphere."""
    return trimesh.creation.icosphere(radius=radius, subdivisions=subdivisions)


def create_cylinder_mesh(radius: float = 1.0, height: float = 2.0) -> trimesh.Trimesh:
    """Create a cylinder mesh."""
    return trimesh.creation.cylinder(radius=radius, height=height)


def create_torus_mesh(radius: float = 1.0, thickness: float = 0.3) -> trimesh.Trimesh:
    """Create a torus mesh."""
    return trimesh.creation.annulus(radius=radius, thickness=thickness)


def create_degenerate_mesh() -> trimesh.Trimesh:
    """Create a mesh with degenerate faces for testing validation."""
    vertices = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
            [0, 0, 1],
            [0, 0, 0],  # Duplicate vertex
        ]
    )

    faces = np.array(
        [
            [0, 1, 2],  # Valid face
            [0, 2, 3],  # Valid face
            [0, 3, 1],  # Valid face
            [0, 0, 1],  # Degenerate face (same vertex twice)
            [0, 1, 4],  # Face with duplicate vertex
        ]
    )

    return trimesh.Trimesh(vertices=vertices, faces=faces)


def create_non_manifold_mesh() -> trimesh.Trimesh:
    """Create a non-manifold mesh for testing validation."""
    vertices = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],  # Triangle 1
            [0, 0, 1],
            [1, 0, 1],
            [0, 1, 1],  # Triangle 2
            [0.5, 0.5, 0.5],  # Shared vertex
        ]
    )

    faces = np.array(
        [
            [0, 1, 2],  # Triangle 1
            [3, 4, 5],  # Triangle 2
            [0, 1, 6],  # Triangle sharing edge with Triangle 1
            [3, 4, 6],  # Triangle sharing edge with Triangle 2
        ]
    )

    return trimesh.Trimesh(vertices=vertices, faces=faces)


def create_large_mesh(vertices_count: int = 10000) -> trimesh.Trimesh:
    """Create a large mesh for testing memory limits."""
    # Create a grid of vertices
    grid_size = int(np.sqrt(vertices_count))
    x = np.linspace(0, 1, grid_size)
    y = np.linspace(0, 1, grid_size)
    X, Y = np.meshgrid(x, y)

    # Add some height variation
    Z = 0.1 * np.sin(2 * np.pi * X) * np.cos(2 * np.pi * Y)

    vertices = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])

    # Create faces (triangles)
    faces = []
    for i in range(grid_size - 1):
        for j in range(grid_size - 1):
            # Calculate vertex indices
            v0 = i * grid_size + j
            v1 = i * grid_size + j + 1
            v2 = (i + 1) * grid_size + j
            v3 = (i + 1) * grid_size + j + 1

            # Add two triangles per grid cell
            faces.append([v0, v1, v2])
            faces.append([v1, v3, v2])

    return trimesh.Trimesh(vertices=vertices, faces=np.array(faces))


def save_sample_meshes(output_dir: Path) -> None:
    """Save sample meshes to files for testing."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create and save different mesh types
    meshes = {
        "cube": create_cube_mesh(),
        "sphere": create_sphere_mesh(),
        "cylinder": create_cylinder_mesh(),
        "torus": create_torus_mesh(),
        "degenerate": create_degenerate_mesh(),
        "non_manifold": create_non_manifold_mesh(),
        "large": create_large_mesh(1000),  # Smaller for testing
    }

    # Save in different formats
    formats = ["stl", "ply", "obj"]

    for name, mesh in meshes.items():
        for format in formats:
            output_file = output_dir / f"{name}.{format}"
            mesh.export(str(output_file))
            print(f"Saved {name}.{format}")


if __name__ == "__main__":
    # Create fixtures directory
    fixtures_dir = Path(__file__).parent / "meshes"
    save_sample_meshes(fixtures_dir)
