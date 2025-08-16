"""Job orchestration API endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from dental_backend_common.database import (
    Case,
    File,
    Job,
    JobStatus,
    User,
    cancel_job,
    create_job,
    retry_job,
)
from dental_backend_common.session import get_db_session
from dental_backend_common.tracing import generate_correlation_id, get_correlation_id
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from dental_backend.api.dependencies import get_current_user
from dental_backend.worker.tasks import (
    process_mesh_file,
    segment_dental_scan,
)

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


@router.get("/{job_id}/progress", response_model=dict)
async def stream_job_progress(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream job progress updates via Server-Sent Events."""

    # Validate job exists and user has access
    try:
        job_uuid = UUID(job_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid job ID format") from err

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if user has access to the case
    case = db.query(Case).filter(Case.id == job.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # For now, return current progress (in a real implementation, this would stream updates)
    async def generate_progress():
        """Generate progress updates."""
        import asyncio
        import json

        # Send initial progress
        progress_data = {
            "job_id": str(job.id),
            "status": job.status.value,
            "progress": job.progress,
            "message": f"Job {job.job_type} is {job.status.value}",
            "timestamp": job.updated_at.isoformat() if job.updated_at else None,
        }

        if job.error_message:
            progress_data["error"] = job.error_message

        if job.result:
            progress_data["result"] = job.result

        yield f"data: {json.dumps(progress_data)}\n\n"

        # In a real implementation, you would:
        # 1. Subscribe to job progress updates (Redis pub/sub, WebSocket, etc.)
        # 2. Stream updates as they occur
        # 3. Handle client disconnection gracefully

        # For demo purposes, simulate some updates
        if job.status == JobStatus.PROCESSING:
            for i in range(5):
                await asyncio.sleep(2)
                progress_data["progress"] = min(100, job.progress + (i + 1) * 20)
                progress_data["timestamp"] = (
                    job.updated_at.isoformat() if job.updated_at else None
                )
                yield f"data: {json.dumps(progress_data)}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        },
    )


@router.post("/{case_id}/segment", response_model=JobResponse)
async def create_segmentation_job(
    case_id: str,
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Create a segmentation job for a case."""

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

    # Validate file exists and belongs to case
    try:
        file_uuid = UUID(request.file_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid file ID format") from err

    file = (
        db.query(File).filter(File.id == file_uuid, File.case_id == case_uuid).first()
    )
    if not file:
        raise HTTPException(
            status_code=404, detail="File not found or does not belong to case"
        )

    # Check for existing job with same request key (idempotency)
    if request.request_key:
        existing_job = (
            db.query(Job)
            .filter(
                Job.case_id == case_uuid,
                Job.job_type == "segmentation",
                Job.parameters.contains({"request_key": request.request_key}),
            )
            .first()
        )

        if existing_job:
            logger.info(
                f"Returning existing job {existing_job.id} for request key {request.request_key}"
            )
            return JobResponse.from_orm(existing_job)

    # Create job record
    job = create_job(
        db_session=db,
        case_id=case_id,
        job_type="segmentation",
        created_by=str(current_user.id),
        file_id=request.file_id,
        priority=request.priority,
        parameters={
            "request_key": request.request_key,
            "correlation_id": correlation_id,
            **(request.parameters or {}),
        },
    )

    # Submit Celery task
    task = segment_dental_scan.delay(
        file_id=request.file_id,
        case_id=case_id,
        job_id=str(job.id),
        correlation_id=correlation_id,
    )

    # Update job with Celery task ID
    job.celery_task_id = task.id
    db.commit()

    logger.info(
        f"Created segmentation job {job.id} with task {task.id} and correlation ID {correlation_id}"
    )

    return JobResponse.from_orm(job)


@router.post("/{case_id}/process", response_model=JobResponse)
async def create_processing_job(
    case_id: str,
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Create a file processing job for a case."""

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

    # Validate file exists and belongs to case
    try:
        file_uuid = UUID(request.file_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid file ID format") from err

    file = (
        db.query(File).filter(File.id == file_uuid, File.case_id == case_uuid).first()
    )
    if not file:
        raise HTTPException(
            status_code=404, detail="File not found or does not belong to case"
        )

    # Create job record
    job = create_job(
        db_session=db,
        case_id=case_id,
        job_type="file_processing",
        created_by=str(current_user.id),
        file_id=request.file_id,
        priority=request.priority,
        parameters={
            "request_key": request.request_key,
            "correlation_id": correlation_id,
            **(request.parameters or {}),
        },
    )

    # Submit Celery task
    task = process_mesh_file.delay(
        file_path=file.file_path,
        file_type=file.file_type,
        job_id=str(job.id),
        correlation_id=correlation_id,
    )

    # Update job with Celery task ID
    job.celery_task_id = task.id
    db.commit()

    logger.info(
        f"Created processing job {job.id} with task {task.id} and correlation ID {correlation_id}"
    )

    return JobResponse.from_orm(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Get a specific job by ID."""
    try:
        job_uuid = UUID(job_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid job ID format") from err

    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Verify user has access to the case
    case = db.query(Case).filter(Case.id == job.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return JobResponse.from_orm(job)


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
async def cancel_job_endpoint(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Cancel a running job."""
    try:
        job_uuid = UUID(job_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid job ID format") from err

    # Use the database function to cancel the job
    success = cancel_job(db, job_id)
    if not success:
        raise HTTPException(
            status_code=400, detail="Job cannot be cancelled in its current status"
        )

    # Get the updated job
    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"Job cancelled: {job_id} by user {current_user.id}")

    return JobResponse.from_orm(job)


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job_endpoint(
    job_id: str,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Retry a failed job."""
    try:
        job_uuid = UUID(job_id)
    except ValueError as err:
        raise HTTPException(status_code=400, detail="Invalid job ID format") from err

    # Use the database function to retry the job
    success = retry_job(db, job_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Job cannot be retried in its current status or has exceeded max retries",
        )

    # Get the updated job
    job = db.query(Job).filter(Job.id == job_uuid).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info(f"Job retry initiated: {job_id} by user {current_user.id}")

    return JobResponse.from_orm(job)
