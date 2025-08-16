"""Segment results API endpoints."""

import logging
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from dental_backend_common.auth import get_current_user
from dental_backend_common.database import Case, Segment, User
from dental_backend_common.session import get_db_session
from dental_backend_common.storage import StorageService
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/segments", tags=["segments"])


class SegmentResponse(BaseModel):
    """Response model for segment data."""

    id: str = Field(..., description="Segment ID")
    case_id: str = Field(..., description="Case ID")
    file_id: str = Field(..., description="File ID")
    segment_type: str = Field(..., description="Segment type")
    segment_number: Optional[int] = Field(None, description="Segment number")
    confidence_score: Optional[int] = Field(None, description="Confidence score")
    bounding_box: Optional[dict] = Field(None, description="Bounding box coordinates")
    mesh_data: Optional[dict] = Field(None, description="Mesh data")
    properties: Optional[dict] = Field(None, description="Segment properties")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    created_by_job: Optional[str] = Field(None, description="Creating job ID")
    segment_metadata: Optional[dict] = Field(None, description="Additional metadata")
    download_urls: Dict[str, str] = Field(
        default_factory=dict, description="Download URLs for different formats"
    )

    class Config:
        from_attributes = True


class SegmentListResponse(BaseModel):
    """Response model for paginated segment list."""

    segments: List[SegmentResponse] = Field(..., description="List of segments")
    total: int = Field(..., description="Total number of segments")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")


class ExportFormat(str, Enum):
    """Supported export formats."""

    STL = "stl"
    PLY = "ply"
    GLB = "glb"
    OBJ = "obj"


@router.get("/{segment_id}", response_model=SegmentResponse)
async def get_segment(
    segment_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SegmentResponse:
    """Get a specific segment by ID."""
    try:
        segment = (
            db_session.query(Segment)
            .filter(Segment.id == UUID(segment_id), Segment.is_deleted is False)
            .first()
        )

        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found"
            )

        # Generate download URLs for different formats
        storage_service = StorageService()
        download_urls = {}

        # Generate URLs for available formats
        for format_type in [
            ExportFormat.STL,
            ExportFormat.PLY,
            ExportFormat.GLB,
            ExportFormat.OBJ,
        ]:
            try:
                download_url = storage_service.get_file_url(
                    tenant_id="default",
                    case_id=str(segment.case_id),
                    file_id=str(segment.id),
                    filename=f"segment_{segment.id}.{format_type.value}",
                    expires_in=3600,  # 1 hour
                )
                download_urls[format_type.value] = download_url
            except Exception:
                # Format not available, skip
                pass

        return SegmentResponse(
            id=str(segment.id),
            case_id=str(segment.case_id),
            file_id=str(segment.file_id),
            segment_type=segment.segment_type.value,
            segment_number=segment.segment_number,
            confidence_score=segment.confidence_score,
            bounding_box=segment.bounding_box,
            mesh_data=segment.mesh_data,
            properties=segment.properties,
            created_at=segment.created_at.isoformat(),
            updated_at=segment.updated_at.isoformat(),
            created_by_job=str(segment.created_by_job)
            if segment.created_by_job
            else None,
            segment_metadata=segment.segment_metadata,
            download_urls=download_urls,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get segment {segment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get segment",
        ) from e


@router.get("/{case_id}/segments", response_model=SegmentListResponse)
async def list_case_segments(
    case_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    segment_type: Optional[str] = Query(None, description="Filter by segment type"),
    min_confidence: Optional[int] = Query(
        None, ge=0, le=100, description="Minimum confidence score"
    ),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> SegmentListResponse:
    """List segments for a specific case with filtering and pagination."""
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
        query = db_session.query(Segment).filter(
            Segment.case_id == UUID(case_id), Segment.is_deleted is False
        )

        # Apply filters
        if segment_type:
            query = query.filter(Segment.segment_type == segment_type)
        if min_confidence is not None:
            query = query.filter(Segment.confidence_score >= min_confidence)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        segments = (
            query.order_by(Segment.created_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        # Calculate pages
        pages = (total + per_page - 1) // per_page

        # Convert to response models
        segment_responses = []
        storage_service = StorageService()

        for segment in segments:
            # Generate download URLs for different formats
            download_urls = {}

            # Generate URLs for available formats
            for format_type in [
                ExportFormat.STL,
                ExportFormat.PLY,
                ExportFormat.GLB,
                ExportFormat.OBJ,
            ]:
                try:
                    download_url = storage_service.get_file_url(
                        tenant_id="default",
                        case_id=str(segment.case_id),
                        file_id=str(segment.id),
                        filename=f"segment_{segment.id}.{format_type.value}",
                        expires_in=3600,  # 1 hour
                    )
                    download_urls[format_type.value] = download_url
                except Exception:
                    # Format not available, skip
                    pass

            segment_responses.append(
                SegmentResponse(
                    id=str(segment.id),
                    case_id=str(segment.case_id),
                    file_id=str(segment.file_id),
                    segment_type=segment.segment_type.value,
                    segment_number=segment.segment_number,
                    confidence_score=segment.confidence_score,
                    bounding_box=segment.bounding_box,
                    mesh_data=segment.mesh_data,
                    properties=segment.properties,
                    created_at=segment.created_at.isoformat(),
                    updated_at=segment.updated_at.isoformat(),
                    created_by_job=str(segment.created_by_job)
                    if segment.created_by_job
                    else None,
                    segment_metadata=segment.segment_metadata,
                    download_urls=download_urls,
                )
            )

        return SegmentListResponse(
            segments=segment_responses,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list segments for case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list segments",
        ) from e


@router.get("/{segment_id}/download/{format}")
async def download_segment(
    segment_id: str,
    format: ExportFormat,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Dict[str, str]:
    """Get signed download URL for a segment in specific format."""
    try:
        segment = (
            db_session.query(Segment)
            .filter(Segment.id == UUID(segment_id), Segment.is_deleted is False)
            .first()
        )

        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found"
            )

        # Generate download URL
        storage_service = StorageService()
        download_url = storage_service.get_file_url(
            tenant_id="default",
            case_id=str(segment.case_id),
            file_id=str(segment.id),
            filename=f"segment_{segment.id}.{format.value}",
            expires_in=3600,  # 1 hour
        )

        return {
            "download_url": download_url,
            "format": format.value,
            "segment_id": segment_id,
            "expires_in": 3600,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate download URL for segment {segment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        ) from e


@router.get("/{segment_id}/metadata")
async def get_segment_metadata(
    segment_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Dict:
    """Get detailed metadata for a segment."""
    try:
        segment = (
            db_session.query(Segment)
            .filter(Segment.id == UUID(segment_id), Segment.is_deleted is False)
            .first()
        )

        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found"
            )

        # Return comprehensive metadata
        metadata = {
            "id": str(segment.id),
            "case_id": str(segment.case_id),
            "file_id": str(segment.file_id),
            "segment_type": segment.segment_type.value,
            "segment_number": segment.segment_number,
            "confidence_score": segment.confidence_score,
            "bounding_box": segment.bounding_box,
            "properties": segment.properties,
            "created_at": segment.created_at.isoformat(),
            "updated_at": segment.updated_at.isoformat(),
            "created_by_job": str(segment.created_by_job)
            if segment.created_by_job
            else None,
            "segment_metadata": segment.segment_metadata,
        }

        # Add mesh-specific metadata if available
        if segment.mesh_data:
            mesh_info = segment.mesh_data.get("mesh_info", {})
            metadata.update(
                {
                    "vertex_count": mesh_info.get("vertex_count"),
                    "face_count": mesh_info.get("face_count"),
                    "volume": mesh_info.get("volume"),
                    "surface_area": mesh_info.get("surface_area"),
                    "center_of_mass": mesh_info.get("center_of_mass"),
                    "bounding_box_volume": mesh_info.get("bounding_box_volume"),
                }
            )

        return metadata

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get segment metadata {segment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get segment metadata",
        ) from e


@router.get("/{case_id}/segments/summary")
async def get_case_segments_summary(
    case_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> Dict:
    """Get summary statistics for segments in a case."""
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

        # Get all segments for the case
        segments = (
            db_session.query(Segment)
            .filter(Segment.case_id == UUID(case_id), Segment.is_deleted is False)
            .all()
        )

        # Calculate summary statistics
        total_segments = len(segments)
        segment_types = {}
        confidence_scores = []
        total_vertices = 0
        total_faces = 0
        total_volume = 0

        for segment in segments:
            # Count by type
            segment_type = segment.segment_type.value
            segment_types[segment_type] = segment_types.get(segment_type, 0) + 1

            # Collect confidence scores
            if segment.confidence_score:
                confidence_scores.append(segment.confidence_score)

            # Sum mesh statistics
            if segment.mesh_data:
                mesh_info = segment.mesh_data.get("mesh_info", {})
                total_vertices += mesh_info.get("vertex_count", 0)
                total_faces += mesh_info.get("face_count", 0)
                total_volume += mesh_info.get("volume", 0)

        # Calculate averages
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        )
        min_confidence = min(confidence_scores) if confidence_scores else 0
        max_confidence = max(confidence_scores) if confidence_scores else 0

        return {
            "case_id": case_id,
            "total_segments": total_segments,
            "segment_types": segment_types,
            "confidence_stats": {
                "average": round(avg_confidence, 2),
                "minimum": min_confidence,
                "maximum": max_confidence,
                "count": len(confidence_scores),
            },
            "mesh_stats": {
                "total_vertices": total_vertices,
                "total_faces": total_faces,
                "total_volume": round(total_volume, 6),
                "average_vertices_per_segment": round(
                    total_vertices / total_segments, 2
                )
                if total_segments > 0
                else 0,
                "average_faces_per_segment": round(total_faces / total_segments, 2)
                if total_segments > 0
                else 0,
            },
            "created_at": case.created_at.isoformat(),
            "updated_at": case.updated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get segments summary for case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get segments summary",
        ) from e


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> None:
    """Delete a segment."""
    try:
        segment = (
            db_session.query(Segment)
            .filter(Segment.id == UUID(segment_id), Segment.is_deleted is False)
            .first()
        )

        if not segment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found"
            )

        # Soft delete
        segment.is_deleted = True
        db_session.commit()

        logger.info(f"Segment deleted: {segment_id} by user {current_user.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete segment {segment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete segment",
        ) from e
