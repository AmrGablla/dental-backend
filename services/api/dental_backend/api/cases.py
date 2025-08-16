"""Case management API endpoints."""

import logging
from typing import List, Optional
from uuid import UUID

from dental_backend_common.auth import get_current_user
from dental_backend_common.database import Case, User
from dental_backend_common.session import get_db_session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseCreateRequest(BaseModel):
    """Request model for creating a case."""

    case_number: str = Field(..., description="Unique case number")
    patient_id: str = Field(..., description="Patient identifier")
    title: str = Field(..., description="Case title")
    description: Optional[str] = Field(None, description="Case description")
    status: str = Field(default="active", description="Case status")
    priority: str = Field(default="normal", description="Case priority")
    tags: Optional[dict] = Field(None, description="Case tags")
    case_metadata: Optional[dict] = Field(None, description="Additional metadata")


class CaseUpdateRequest(BaseModel):
    """Request model for updating a case."""

    title: Optional[str] = Field(None, description="Case title")
    description: Optional[str] = Field(None, description="Case description")
    status: Optional[str] = Field(None, description="Case status")
    priority: Optional[str] = Field(None, description="Case priority")
    tags: Optional[dict] = Field(None, description="Case tags")
    case_metadata: Optional[dict] = Field(None, description="Additional metadata")


class CaseResponse(BaseModel):
    """Response model for case data."""

    id: str = Field(..., description="Case ID")
    case_number: str = Field(..., description="Case number")
    patient_id: str = Field(..., description="Patient ID")
    title: str = Field(..., description="Case title")
    description: Optional[str] = Field(None, description="Case description")
    status: str = Field(..., description="Case status")
    priority: str = Field(..., description="Case priority")
    created_by: str = Field(..., description="Creator user ID")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    completed_at: Optional[str] = Field(None, description="Completion timestamp")
    tags: Optional[dict] = Field(None, description="Case tags")
    case_metadata: Optional[dict] = Field(None, description="Additional metadata")
    file_count: int = Field(0, description="Number of files in case")
    job_count: int = Field(0, description="Number of jobs in case")
    segment_count: int = Field(0, description="Number of segments in case")

    class Config:
        from_attributes = True


class CaseListResponse(BaseModel):
    """Response model for paginated case list."""

    cases: List[CaseResponse] = Field(..., description="List of cases")
    total: int = Field(..., description="Total number of cases")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")


@router.post("/", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    request: CaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> CaseResponse:
    """Create a new dental case."""
    try:
        # Check if case number already exists
        existing_case = (
            db_session.query(Case)
            .filter(Case.case_number == request.case_number, Case.is_deleted is False)
            .first()
        )

        if existing_case:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Case with number {request.case_number} already exists",
            )

        # Create new case
        case = Case(
            case_number=request.case_number,
            patient_id=request.patient_id,
            title=request.title,
            description=request.description,
            status=request.status,
            priority=request.priority,
            created_by=current_user.id,
            tags=request.tags,
            case_metadata=request.case_metadata,
        )

        db_session.add(case)
        db_session.commit()
        db_session.refresh(case)

        logger.info(f"Case created: {case.id} by user {current_user.id}")

        return CaseResponse(
            id=str(case.id),
            case_number=case.case_number,
            patient_id=case.patient_id,
            title=case.title,
            description=case.description,
            status=case.status,
            priority=case.priority,
            created_by=str(case.created_by),
            created_at=case.created_at.isoformat(),
            updated_at=case.updated_at.isoformat(),
            completed_at=case.completed_at.isoformat() if case.completed_at else None,
            tags=case.tags,
            case_metadata=case.case_metadata,
            file_count=len(case.files),
            job_count=len(case.jobs),
            segment_count=len(case.segments),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create case: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create case",
        ) from e


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> CaseResponse:
    """Get a specific case by ID."""
    try:
        case = (
            db_session.query(Case)
            .filter(Case.id == UUID(case_id), Case.is_deleted is False)
            .first()
        )

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
            )

        return CaseResponse(
            id=str(case.id),
            case_number=case.case_number,
            patient_id=case.patient_id,
            title=case.title,
            description=case.description,
            status=case.status,
            priority=case.priority,
            created_by=str(case.created_by),
            created_at=case.created_at.isoformat(),
            updated_at=case.updated_at.isoformat(),
            completed_at=case.completed_at.isoformat() if case.completed_at else None,
            tags=case.tags,
            case_metadata=case.case_metadata,
            file_count=len(case.files),
            job_count=len(case.jobs),
            segment_count=len(case.segments),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get case",
        ) from e


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: str,
    request: CaseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> CaseResponse:
    """Update a case."""
    try:
        case = (
            db_session.query(Case)
            .filter(Case.id == UUID(case_id), Case.is_deleted is False)
            .first()
        )

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
            )

        # Update fields if provided
        if request.title is not None:
            case.title = request.title
        if request.description is not None:
            case.description = request.description
        if request.status is not None:
            case.status = request.status
        if request.priority is not None:
            case.priority = request.priority
        if request.tags is not None:
            case.tags = request.tags
        if request.case_metadata is not None:
            case.case_metadata = request.case_metadata

        # Set completion time if status is completed
        if request.status == "completed" and case.completed_at is None:
            from datetime import datetime

            case.completed_at = datetime.utcnow()

        db_session.commit()
        db_session.refresh(case)

        logger.info(f"Case updated: {case.id} by user {current_user.id}")

        return CaseResponse(
            id=str(case.id),
            case_number=case.case_number,
            patient_id=case.patient_id,
            title=case.title,
            description=case.description,
            status=case.status,
            priority=case.priority,
            created_by=str(case.created_by),
            created_at=case.created_at.isoformat(),
            updated_at=case.updated_at.isoformat(),
            completed_at=case.completed_at.isoformat() if case.completed_at else None,
            tags=case.tags,
            case_metadata=case.case_metadata,
            file_count=len(case.files),
            job_count=len(case.jobs),
            segment_count=len(case.segments),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update case",
        ) from e


@router.get("/", response_model=CaseListResponse)
async def list_cases(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    case_number: Optional[str] = Query(None, description="Filter by case number"),
    created_by: Optional[str] = Query(None, description="Filter by creator"),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> CaseListResponse:
    """List cases with filtering and pagination."""
    try:
        # Build query
        query = db_session.query(Case).filter(Case.is_deleted is False)

        # Apply filters
        if status:
            query = query.filter(Case.status == status)
        if priority:
            query = query.filter(Case.priority == priority)
        if patient_id:
            query = query.filter(Case.patient_id.contains(patient_id))
        if case_number:
            query = query.filter(Case.case_number.contains(case_number))
        if created_by:
            query = query.filter(Case.created_by == UUID(created_by))

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        cases = (
            query.order_by(Case.created_at.desc()).offset(offset).limit(per_page).all()
        )

        # Calculate pages
        pages = (total + per_page - 1) // per_page

        # Convert to response models
        case_responses = []
        for case in cases:
            case_responses.append(
                CaseResponse(
                    id=str(case.id),
                    case_number=case.case_number,
                    patient_id=case.patient_id,
                    title=case.title,
                    description=case.description,
                    status=case.status,
                    priority=case.priority,
                    created_by=str(case.created_by),
                    created_at=case.created_at.isoformat(),
                    updated_at=case.updated_at.isoformat(),
                    completed_at=case.completed_at.isoformat()
                    if case.completed_at
                    else None,
                    tags=case.tags,
                    case_metadata=case.case_metadata,
                    file_count=len(case.files),
                    job_count=len(case.jobs),
                    segment_count=len(case.segments),
                )
            )

        return CaseListResponse(
            cases=case_responses,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )

    except Exception as e:
        logger.error(f"Failed to list cases: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list cases",
        ) from e


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> None:
    """Soft delete a case."""
    try:
        case = (
            db_session.query(Case)
            .filter(Case.id == UUID(case_id), Case.is_deleted is False)
            .first()
        )

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
            )

        # Soft delete
        case.is_deleted = True
        db_session.commit()

        logger.info(f"Case deleted: {case_id} by user {current_user.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete case",
        ) from e
