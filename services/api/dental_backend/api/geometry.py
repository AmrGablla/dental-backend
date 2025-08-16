"""3D Geometry API endpoints for mesh processing and validation."""

import logging
import tempfile
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from dental_backend_common.database import Case, User, create_job
from dental_backend_common.geometry import (
    MeshFormat,
    MeshProcessingRequest,
    ValidationLevel,
)
from dental_backend_common.session import get_db_session
from dental_backend_common.tracing import generate_correlation_id, get_correlation_id
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from dental_backend.api.dependencies import get_current_user

# Import JobResponse at the top to avoid circular imports
from dental_backend.api.jobs import JobResponse
from dental_backend.worker.tasks import (
    process_mesh_3d,
    test_mesh_formats,
    validate_mesh,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/geometry", tags=["3D Geometry"])


@router.post("/process", response_model=JobResponse)
async def process_mesh(
    request: MeshProcessingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Process a 3D mesh with validation and normalization."""

    # Generate correlation ID
    correlation_id = get_correlation_id() or generate_correlation_id()

    # Create job record
    job = create_job(
        db_session=db,
        case_id=None,  # No case association for general processing
        job_type="mesh_processing",
        created_by=str(current_user.id),
        file_id=None,
        priority=5,
        parameters={
            "input_path": request.input_path,
            "output_path": request.output_path,
            "validate": request.should_validate,
            "normalize": request.normalize,
            "units": request.units,
            "output_format": request.output_format.value
            if request.output_format
            else None,
            "validation_level": request.validation_level.value,
            "memory_limit_mb": request.memory_limit_mb,
            "correlation_id": correlation_id,
        },
    )

    # Submit Celery task
    task = process_mesh_3d.delay(
        input_path=request.input_path,
        output_path=request.output_path,
        validate=request.should_validate,
        normalize=request.normalize,
        units=request.units,
        output_format=request.output_format.value if request.output_format else None,
        validation_level=request.validation_level.value,
        memory_limit_mb=request.memory_limit_mb,
        job_id=str(job.id),
        correlation_id=correlation_id,
    )

    # Update job with Celery task ID
    job.celery_task_id = task.id
    db.commit()

    logger.info(
        f"Created mesh processing job {job.id} with task {task.id} and correlation ID {correlation_id}"
    )

    return JobResponse.from_orm(job)


@router.post("/validate", response_model=JobResponse)
async def validate_mesh_file(
    file_path: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    validation_level: ValidationLevel = ValidationLevel.STANDARD,
) -> JobResponse:
    """Validate a 3D mesh file and return detailed report."""

    # Generate correlation ID
    correlation_id = get_correlation_id() or generate_correlation_id()

    # Create job record
    job = create_job(
        db_session=db,
        case_id=None,  # No case association for general validation
        job_type="mesh_validation",
        created_by=str(current_user.id),
        file_id=None,
        priority=5,
        parameters={
            "file_path": file_path,
            "validation_level": validation_level.value,
            "correlation_id": correlation_id,
        },
    )

    # Submit Celery task
    task = validate_mesh.delay(
        file_path=file_path,
        validation_level=validation_level.value,
        job_id=str(job.id),
        correlation_id=correlation_id,
    )

    # Update job with Celery task ID
    job.celery_task_id = task.id
    db.commit()

    logger.info(
        f"Created mesh validation job {job.id} with task {task.id} and correlation ID {correlation_id}"
    )

    return JobResponse.from_orm(job)


@router.post("/test-formats", response_model=JobResponse)
async def test_mesh_formats_endpoint(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    memory_limit_mb: int = 1024,
) -> JobResponse:
    """Test round-trip loading and saving for all supported mesh formats."""

    # Generate correlation ID
    correlation_id = get_correlation_id() or generate_correlation_id()

    # Create job record
    job = create_job(
        db_session=db,
        case_id=None,  # No case association for format testing
        job_type="mesh_format_testing",
        created_by=str(current_user.id),
        file_id=None,
        priority=3,
        parameters={
            "memory_limit_mb": memory_limit_mb,
            "correlation_id": correlation_id,
        },
    )

    # Submit Celery task
    task = test_mesh_formats.delay(
        memory_limit_mb=memory_limit_mb,
        job_id=str(job.id),
        correlation_id=correlation_id,
    )

    # Update job with Celery task ID
    job.celery_task_id = task.id
    db.commit()

    logger.info(
        f"Created mesh format testing job {job.id} with task {task.id} and correlation ID {correlation_id}"
    )

    return JobResponse.from_orm(job)


@router.get("/formats", response_model=List[str])
async def get_supported_formats() -> List[str]:
    """Get list of supported mesh file formats."""
    return [format.value for format in MeshFormat]


@router.get("/validation-levels", response_model=List[str])
async def get_validation_levels() -> List[str]:
    """Get list of available validation levels."""
    return [level.value for level in ValidationLevel]


@router.post("/upload-and-process", response_model=JobResponse)
async def upload_and_process_mesh(
    file: UploadFile,
    case_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    validate: bool = True,
    normalize: bool = False,
    units: Optional[str] = None,
    output_format: Optional[MeshFormat] = None,
    validation_level: ValidationLevel = ValidationLevel.STANDARD,
    memory_limit_mb: int = 1024,
) -> JobResponse:
    """Upload a mesh file and process it."""

    # Generate correlation ID
    correlation_id = get_correlation_id() or generate_correlation_id()

    # Validate case exists
    try:
        case_uuid = UUID(case_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid case ID format") from err

    case = db.query(Case).filter(Case.id == case_uuid).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Validate file format
    file_extension = Path(file.filename).suffix.lower().lstrip(".")
    if file_extension not in [format.value for format in MeshFormat]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {file_extension}. Supported formats: {[format.value for format in MeshFormat]}",
        )

    # Save uploaded file
    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / f"input.{file_extension}"

    try:
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Generate output path
        output_filename = f"processed_{Path(file.filename).stem}"
        if output_format:
            output_filename += f".{output_format.value}"
        else:
            output_filename += f".{file_extension}"

        output_path = temp_dir / output_filename

        # Create job record
        job = create_job(
            db_session=db,
            case_id=case_id,
            job_type="mesh_upload_processing",
            created_by=str(current_user.id),
            file_id=None,
            priority=5,
            parameters={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original_filename": file.filename,
                "validate": validate,
                "normalize": normalize,
                "units": units,
                "output_format": output_format.value if output_format else None,
                "validation_level": validation_level.value,
                "memory_limit_mb": memory_limit_mb,
                "correlation_id": correlation_id,
            },
        )

        # Submit Celery task
        task = process_mesh_3d.delay(
            input_path=str(input_path),
            output_path=str(output_path),
            validate=validate,
            normalize=normalize,
            units=units,
            output_format=output_format.value if output_format else None,
            validation_level=validation_level.value,
            memory_limit_mb=memory_limit_mb,
            job_id=str(job.id),
            correlation_id=correlation_id,
        )

        # Update job with Celery task ID
        job.celery_task_id = task.id
        db.commit()

        logger.info(
            f"Created mesh upload processing job {job.id} with task {task.id} and correlation ID {correlation_id}"
        )

        return JobResponse.from_orm(job)

    except Exception as e:
        logger.error(f"Failed to process uploaded mesh: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process mesh: {str(e)}"
        ) from e
