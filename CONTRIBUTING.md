# Contributing to Dental Backend

## Code Style & Standards

### Python Version
- **Minimum**: Python 3.10+
- **Target**: Python 3.11+ for new features

### Code Formatting
We use **Black** for code formatting with the following configuration:
```toml
[tool.black]
line-length = 88
target-version = ['py310']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''
```

### Linting with Ruff
```toml
[tool.ruff]
target-version = "py310"
line-length = 88
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    "UP", # pyupgrade
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
    "C901",  # too complex
]

[tool.ruff.isort]
known-first-party = ["dental_backend"]
```

### Type Checking with MyPy
```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[[tool.mypy.overrides]]
module = [
    "celery.*",
    "redis.*",
    "boto3.*",
    "psycopg2.*",
]
ignore_missing_imports = true
```

## Docstring Style
We use **Google-style docstrings** with type hints:

```python
def process_mesh(file_path: str, format_type: MeshFormat) -> ProcessedMesh:
    """Process a 3D mesh file and return analysis results.

    Args:
        file_path: Path to the mesh file to process.
        format_type: The format of the input file (STL, PLY, OBJ, glTF).

    Returns:
        ProcessedMesh object containing analysis results and metadata.

    Raises:
        MeshProcessingError: If the file cannot be processed.
        ValidationError: If the mesh fails validation checks.

    Example:
        >>> mesh = process_mesh("scan.stl", MeshFormat.STL)
        >>> print(mesh.vertex_count)
        1000
    """
    pass
```

## Logging Levels
Use structured logging with the following levels:

- **DEBUG**: Detailed information for debugging
- **INFO**: General information about program execution
- **WARNING**: Something unexpected happened but the program can continue
- **ERROR**: A serious problem occurred
- **CRITICAL**: A critical error that may prevent the program from running

```python
import structlog

logger = structlog.get_logger()

# Good examples
logger.info("Processing mesh file", file_path=path, format=format_type)
logger.warning("Mesh validation failed", file_path=path, errors=errors)
logger.error("Failed to process mesh", file_path=path, error=str(e))
```

## Error Taxonomy

### Core Error Classes
```python
class DentalBackendError(Exception):
    """Base exception for all dental backend errors."""
    pass

class ValidationError(DentalBackendError):
    """Raised when data validation fails."""
    pass

class ProcessingError(DentalBackendError):
    """Raised when mesh processing fails."""
    pass

class StorageError(DentalBackendError):
    """Raised when storage operations fail."""
    pass

class AuthenticationError(DentalBackendError):
    """Raised when authentication fails."""
    pass

class AuthorizationError(DentalBackendError):
    """Raised when authorization fails."""
    pass
```

### Error Codes
- `VAL001`: Invalid file format
- `VAL002`: Mesh validation failed
- `PROC001`: Processing timeout
- `PROC002`: Insufficient memory
- `STOR001`: File not found
- `STOR002`: Storage quota exceeded
- `AUTH001`: Invalid credentials
- `AUTH002`: Token expired
- `AUTH003`: Insufficient permissions

## File Naming Conventions
- **Python files**: `snake_case.py`
- **Test files**: `test_snake_case.py`
- **Configuration files**: `snake_case.toml` or `snake_case.yaml`
- **Docker files**: `Dockerfile`, `docker-compose.yml`

## Import Organization
```python
# Standard library imports
import os
import sys
from typing import Optional, List

# Third-party imports
import fastapi
import structlog
from pydantic import BaseModel

# Local imports
from dental_backend.core import models
from dental_backend.services import mesh_processor
```

## Testing Standards
- **Coverage**: Minimum 80% code coverage
- **Framework**: pytest
- **Fixtures**: Use pytest fixtures for common test data
- **Mocking**: Use unittest.mock for external dependencies

## Git Commit Messages
Use conventional commits format:
```
feat: add STL file processing support
fix: resolve memory leak in mesh validation
docs: update API documentation
test: add integration tests for PLY format
refactor: extract mesh validation logic
```

## Security Guidelines
- Never log sensitive data (PII, PHI)
- Use environment variables for secrets
- Validate all input data
- Implement proper authentication and authorization
- Follow HIPAA/GDPR requirements for data handling

## Performance Guidelines
- Use async/await for I/O operations
- Implement proper connection pooling
- Cache frequently accessed data
- Monitor memory usage for large mesh processing
- Use background tasks for long-running operations
