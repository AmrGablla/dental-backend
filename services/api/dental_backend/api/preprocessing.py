"""Preprocessing pipeline API endpoints."""

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from dental_backend_common.database import Case, User, create_job
from dental_backend_common.preprocessing import (
    AlgorithmType,
    PipelineRequest,
    PipelineStep,
    create_default_pipeline,
)
from dental_backend_common.session import get_db_session
from dental_backend_common.tracing import generate_correlation_id, get_correlation_id
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from dental_backend.api.dependencies import get_current_user

# Import JobResponse at the top to avoid circular imports
from dental_backend.api.jobs import JobResponse
from dental_backend.worker.tasks import (
    create_pipeline_config,
    run_preprocessing_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preprocessing", tags=["Preprocessing Pipeline"])


@router.post("/pipeline", response_model=JobResponse)
async def run_pipeline(
    input_path: str,
    output_path: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    pipeline_config: Optional[PipelineRequest] = None,
) -> JobResponse:
    """Run preprocessing pipeline on a mesh file."""

    # Generate correlation ID
    correlation_id = get_correlation_id() or generate_correlation_id()

    # Create job record
    job = create_job(
        db_session=db,
        case_id=None,  # No case association for general preprocessing
        job_type="preprocessing_pipeline",
        created_by=str(current_user.id),
        file_id=None,
        priority=5,
        parameters={
            "input_path": input_path,
            "output_path": output_path,
            "pipeline_config": pipeline_config.dict() if pipeline_config else None,
            "correlation_id": correlation_id,
        },
    )

    # Submit Celery task
    task = run_preprocessing_pipeline.delay(
        input_path=input_path,
        output_path=output_path,
        pipeline_config=pipeline_config.dict() if pipeline_config else None,
        job_id=str(job.id),
        correlation_id=correlation_id,
    )

    # Update job with Celery task ID
    job.celery_task_id = task.id
    db.commit()

    logger.info(
        f"Created preprocessing pipeline job {job.id} with task {task.id} and correlation ID {correlation_id}"
    )

    return JobResponse.from_orm(job)


@router.post("/pipeline/upload", response_model=JobResponse)
async def upload_and_process(
    file: UploadFile,
    case_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
    pipeline_config: Optional[PipelineRequest] = None,
) -> JobResponse:
    """Upload a mesh file and process it through the preprocessing pipeline."""

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

    # Save uploaded file
    temp_dir = Path(tempfile.mkdtemp())
    input_path = temp_dir / f"input_{file.filename}"

    try:
        with open(input_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Generate output path
        output_filename = f"processed_{Path(file.filename).stem}.ply"
        output_path = temp_dir / output_filename

        # Create job record
        job = create_job(
            db_session=db,
            case_id=case_id,
            job_type="preprocessing_pipeline_upload",
            created_by=str(current_user.id),
            file_id=None,
            priority=5,
            parameters={
                "input_path": str(input_path),
                "output_path": str(output_path),
                "pipeline_config": pipeline_config.dict() if pipeline_config else None,
                "correlation_id": correlation_id,
            },
        )

        # Submit Celery task
        task = run_preprocessing_pipeline.delay(
            input_path=str(input_path),
            output_path=str(output_path),
            pipeline_config=pipeline_config.dict() if pipeline_config else None,
            job_id=str(job.id),
            correlation_id=correlation_id,
        )

        # Update job with Celery task ID
        job.celery_task_id = task.id
        db.commit()

        logger.info(
            f"Created preprocessing pipeline upload job {job.id} with task {task.id} and correlation ID {correlation_id}"
        )

        return JobResponse.from_orm(job)

    except Exception as e:
        logger.error(f"Failed to process uploaded mesh: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process mesh: {str(e)}"
        ) from e


@router.post("/config", response_model=JobResponse)
async def create_config(
    pipeline_request: PipelineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Create a new pipeline configuration."""

    # Generate correlation ID
    correlation_id = get_correlation_id() or generate_correlation_id()

    # Create job record
    job = create_job(
        db_session=db,
        case_id=None,  # No case association for config creation
        job_type="pipeline_config_creation",
        created_by=str(current_user.id),
        file_id=None,
        priority=3,
        parameters={
            "pipeline_request": pipeline_request.dict(),
            "correlation_id": correlation_id,
        },
    )

    # Submit Celery task
    task = create_pipeline_config.delay(
        pipeline_request=pipeline_request.dict(),
        job_id=str(job.id),
        correlation_id=correlation_id,
    )

    # Update job with Celery task ID
    job.celery_task_id = task.id
    db.commit()

    logger.info(
        f"Created pipeline config job {job.id} with task {task.id} and correlation ID {correlation_id}"
    )

    return JobResponse.from_orm(job)


@router.get("/steps", response_model=List[str])
async def get_pipeline_steps() -> List[str]:
    """Get available pipeline steps."""
    return [step.value for step in PipelineStep]


@router.get("/algorithms", response_model=Dict[str, List[str]])
async def get_algorithms() -> Dict[str, List[str]]:
    """Get available algorithms grouped by step."""
    algorithms = {
        "denoise": [
            AlgorithmType.BILATERAL_FILTER.value,
            AlgorithmType.GAUSSIAN_FILTER.value,
            AlgorithmType.STATISTICAL_OUTLIER_REMOVAL.value,
        ],
        "decimate": [
            AlgorithmType.VOXEL_DOWN_SAMPLE.value,
            AlgorithmType.UNIFORM_DOWN_SAMPLE.value,
        ],
        "hole_fill": [
            AlgorithmType.POISSON_RECONSTRUCTION.value,
            AlgorithmType.BALL_PIVOTING.value,
            AlgorithmType.ALPHA_SHAPE.value,
        ],
        "alignment": [
            AlgorithmType.ICP_ALIGNMENT.value,
            AlgorithmType.LANDMARK_ALIGNMENT.value,
            AlgorithmType.FEATURE_BASED_ALIGNMENT.value,
        ],
        "roi_crop": [
            AlgorithmType.BOUNDING_BOX_CROP.value,
            AlgorithmType.SPHERICAL_CROP.value,
            AlgorithmType.PLANAR_CROP.value,
        ],
        "tooth_arch_isolation": [
            AlgorithmType.CURVATURE_BASED_SEGMENTATION.value,
            AlgorithmType.CLUSTERING_SEGMENTATION.value,
            AlgorithmType.MACHINE_LEARNING_SEGMENTATION.value,
        ],
    }
    return algorithms


@router.get("/default-config", response_model=Dict)
async def get_default_config() -> Dict:
    """Get default pipeline configuration."""
    default_pipeline = create_default_pipeline()
    return default_pipeline.dict()
