"""Job orchestration API endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from dental_backend_common.auth import get_current_user
from dental_backend_common.database import Case, File, Job, JobStatus, User
from dental_backend_common.session import get_db_session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    """Request model for creating a job."""

    file_id: str = Field(..., description="File ID to process")
    job_type: str = Field(..., description="Type of job (segmentation, etc.)")
    priority: int = Field(default=5, ge=1, le=10, description="Job priority (1-10)")
    parameters: Optional[dict] = Field(None, description="Job parameters")
    request_key: Optional[str] = Field(None, description="Idempotency key")


class JobResponse(BaseModel):
    """Response model for job data."""

    id: str = Field(..., description="Job ID")
    case_id: str = Field(..., description="Case ID")
    file_id: str = Field(..., description="File ID")
    job_type: str = Field(..., description="Job type")
    status: str = Field(..., description="Job status")
    priority: int = Field(..., description="Job priority")
    created_by: str = Field(..., description="Creator user ID")
    created_at: str = Field(..., description="Creation timestamp")
    started_at: Optional[str] = Field(None, description="Start timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    progress: int = Field(..., description="Progress percentage")
    result: Optional[dict] = Field(None, description="Job result")
    error_message: Optional[str] = Field(None, description="Error message")
    retry_count: int = Field(..., description="Retry count")
    max_retries: int = Field(..., description="Maximum retries")
    parameters: Optional[dict] = Field(None, description="Job parameters")
    job_metadata: Optional[dict] = Field(None, description="Additional metadata")

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Response model for paginated job list."""

    jobs: List[JobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")


@router.post(
    "/{case_id}/segment",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_segmentation_job(
    case_id: str,
    request: JobCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> JobResponse:
    """Create a segmentation job for a case."""
    try:
        # Verify case exists
        case = (
            db_session.query(Case)
            .filter(Case.id == UUID(case_id), Case.is_deleted is False)
            .first()
        )

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
            )

        # Verify file exists and belongs to the case
        file_record = (
            db_session.query(File)
            .filter(
                File.id == UUID(request.file_id),
                File.case_id == UUID(case_id),
                File.is_deleted is False,
            )
            .first()
        )

        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found in case"
            )

        # Check for existing job with same request key (idempotency)
        if request.request_key:
            existing_job = (
                db_session.query(Job)
                .filter(
                    Job.case_id == UUID(case_id),
                    Job.file_id == UUID(request.file_id),
                    Job.job_type == request.job_type,
                    Job.job_metadata.contains({"request_key": request.request_key}),
                    Job.is_deleted is False,
                )
                .first()
            )

            if existing_job:
                logger.info(
                    f"Idempotent job request: returning existing job {existing_job.id}"
                )
                return JobResponse(
                    id=str(existing_job.id),
                    case_id=str(existing_job.case_id),
                    file_id=str(existing_job.file_id),
                    job_type=existing_job.job_type,
                    status=existing_job.status.value,
                    priority=existing_job.priority,
                    created_by=str(existing_job.created_by),
                    created_at=existing_job.created_at.isoformat(),
                    started_at=existing_job.started_at.isoformat()
                    if existing_job.started_at
                    else None,
                    completed_at=existing_job.completed_at.isoformat()
                    if existing_job.completed_at
                    else None,
                    progress=existing_job.progress,
                    result=existing_job.result,
                    error_message=existing_job.error_message,
                    retry_count=existing_job.retry_count,
                    max_retries=existing_job.max_retries,
                    parameters=existing_job.parameters,
                    job_metadata=existing_job.job_metadata,
                )

        # Create new job
        job = Job(
            case_id=UUID(case_id),
            file_id=UUID(request.file_id),
            job_type=request.job_type,
            status=JobStatus.PENDING,
            priority=request.priority,
            created_by=current_user.id,
            parameters=request.parameters,
            job_metadata={"request_key": request.request_key}
            if request.request_key
            else None,
        )

        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        # TODO: Enqueue job to Celery/background worker
        # from dental_backend_worker.tasks import process_segmentation_job
        # task = process_segmentation_job.delay(str(job.id))
        # job.celery_task_id = task.id
        # db_session.commit()

        logger.info(
            f"Segmentation job created: {job.id} for case {case_id} by user {current_user.id}"
        )

        return JobResponse(
            id=str(job.id),
            case_id=str(job.case_id),
            file_id=str(job.file_id),
            job_type=job.job_type,
            status=job.status.value,
            priority=job.priority,
            created_by=str(job.created_by),
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            progress=job.progress,
            result=job.result,
            error_message=job.error_message,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            parameters=job.parameters,
            job_metadata=job.job_metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create segmentation job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create segmentation job",
        ) from e


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> JobResponse:
    """Get a specific job by ID."""
    try:
        job = (
            db_session.query(Job)
            .filter(Job.id == UUID(job_id), Job.is_deleted is False)
            .first()
        )

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )

        return JobResponse(
            id=str(job.id),
            case_id=str(job.case_id),
            file_id=str(job.file_id),
            job_type=job.job_type,
            status=job.status.value,
            priority=job.priority,
            created_by=str(job.created_by),
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            progress=job.progress,
            result=job.result,
            error_message=job.error_message,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            parameters=job.parameters,
            job_metadata=job.job_metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job",
        ) from e


@router.get("/{case_id}/jobs", response_model=JobListResponse)
async def list_case_jobs(
    case_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> JobListResponse:
    """List jobs for a specific case with filtering and pagination."""
    try:
        # Verify case exists
        case = (
            db_session.query(Case)
            .filter(Case.id == UUID(case_id), Case.is_deleted is False)
            .first()
        )

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
            )

        # Build query
        query = db_session.query(Job).filter(
            Job.case_id == UUID(case_id), Job.is_deleted is False
        )

        # Apply filters
        if status:
            query = query.filter(Job.status == status)
        if job_type:
            query = query.filter(Job.job_type == job_type)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        jobs = (
            query.order_by(Job.created_at.desc()).offset(offset).limit(per_page).all()
        )

        # Calculate pages
        pages = (total + per_page - 1) // per_page

        # Convert to response models
        job_responses = []
        for job in jobs:
            job_responses.append(
                JobResponse(
                    id=str(job.id),
                    case_id=str(job.case_id),
                    file_id=str(job.file_id),
                    job_type=job.job_type,
                    status=job.status.value,
                    priority=job.priority,
                    created_by=str(job.created_by),
                    created_at=job.created_at.isoformat(),
                    started_at=job.started_at.isoformat() if job.started_at else None,
                    completed_at=job.completed_at.isoformat()
                    if job.completed_at
                    else None,
                    progress=job.progress,
                    result=job.result,
                    error_message=job.error_message,
                    retry_count=job.retry_count,
                    max_retries=job.max_retries,
                    parameters=job.parameters,
                    job_metadata=job.job_metadata,
                )
            )

        return JobListResponse(
            jobs=job_responses,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list jobs for case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list jobs",
        ) from e


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> JobResponse:
    """Cancel a running job."""
    try:
        job = (
            db_session.query(Job)
            .filter(Job.id == UUID(job_id), Job.is_deleted is False)
            .first()
        )

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )

        # Check if job can be cancelled
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job cannot be cancelled in status {job.status.value}",
            )

        # Cancel job
        job.status = JobStatus.CANCELLED

        # TODO: Cancel Celery task if running
        # if job.celery_task_id:
        #     from celery import current_app
        #     current_app.control.revoke(job.celery_task_id, terminate=True)

        db_session.commit()
        db_session.refresh(job)

        logger.info(f"Job cancelled: {job_id} by user {current_user.id}")

        return JobResponse(
            id=str(job.id),
            case_id=str(job.case_id),
            file_id=str(job.file_id),
            job_type=job.job_type,
            status=job.status.value,
            priority=job.priority,
            created_by=str(job.created_by),
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            progress=job.progress,
            result=job.result,
            error_message=job.error_message,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            parameters=job.parameters,
            job_metadata=job.job_metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel job",
        ) from e


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> JobResponse:
    """Retry a failed job."""
    try:
        job = (
            db_session.query(Job)
            .filter(Job.id == UUID(job_id), Job.is_deleted is False)
            .first()
        )

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )

        # Check if job can be retried
        if job.status != JobStatus.FAILED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job cannot be retried in status {job.status.value}",
            )

        if job.retry_count >= job.max_retries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Job has exceeded maximum retry attempts",
            )

        # Reset job for retry
        job.status = JobStatus.PENDING
        job.progress = 0
        job.error_message = None
        job.retry_count += 1

        # TODO: Enqueue retry job to Celery
        # from dental_backend_worker.tasks import process_segmentation_job
        # task = process_segmentation_job.delay(str(job.id))
        # job.celery_task_id = task.id

        db_session.commit()
        db_session.refresh(job)

        logger.info(f"Job retry initiated: {job_id} by user {current_user.id}")

        return JobResponse(
            id=str(job.id),
            case_id=str(job.case_id),
            file_id=str(job.file_id),
            job_type=job.job_type,
            status=job.status.value,
            priority=job.priority,
            created_by=str(job.created_by),
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            progress=job.progress,
            result=job.result,
            error_message=job.error_message,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            parameters=job.parameters,
            job_metadata=job.job_metadata,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retry job",
        ) from e
