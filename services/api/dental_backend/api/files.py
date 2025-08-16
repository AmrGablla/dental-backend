"""File management API endpoints."""

import logging
import tempfile
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from dental_backend_common.auth import get_current_user
from dental_backend_common.database import Case, File, FileStatus, User
from dental_backend_common.session import get_db_session
from dental_backend_common.storage import StorageService
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


class FileInitiateRequest(BaseModel):
    """Request model for initiating file upload."""

    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    content_type: Optional[str] = Field(None, description="Content type")
    file_type: str = Field(..., description="File type (stl, ply, obj, etc.)")
    tags: Optional[dict] = Field(None, description="File tags")
    file_metadata: Optional[dict] = Field(None, description="Additional metadata")


class FileInitiateResponse(BaseModel):
    """Response model for file upload initiation."""

    upload_id: str = Field(..., description="Upload ID")
    presigned_url: str = Field(..., description="Presigned URL for upload")
    expires_at: str = Field(..., description="URL expiration time")
    fields: Dict[str, str] = Field(..., description="Required form fields")


class FileCompleteRequest(BaseModel):
    """Request model for completing file upload."""

    upload_id: str = Field(..., description="Upload ID from initiation")
    checksum_md5: str = Field(..., description="MD5 checksum")
    checksum_sha256: str = Field(..., description="SHA256 checksum")


class FileResponse(BaseModel):
    """Response model for file data."""

    id: str = Field(..., description="File ID")
    case_id: str = Field(..., description="Case ID")
    filename: str = Field(..., description="File name")
    original_filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="File type")
    mime_type: str = Field(..., description="MIME type")
    checksum: str = Field(..., description="File checksum")
    status: str = Field(..., description="File status")
    uploaded_by: str = Field(..., description="Uploader user ID")
    uploaded_at: str = Field(..., description="Upload timestamp")
    processed_at: Optional[str] = Field(None, description="Processing timestamp")
    processing_metadata: Optional[dict] = Field(None, description="Processing metadata")
    tags: Optional[dict] = Field(None, description="File tags")
    file_metadata: Optional[dict] = Field(None, description="Additional metadata")
    download_url: Optional[str] = Field(None, description="Download URL (if available)")

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Response model for paginated file list."""

    files: List[FileResponse] = Field(..., description="List of files")
    total: int = Field(..., description="Total number of files")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")


@router.post("/{case_id}/files:initiate", response_model=FileInitiateResponse)
async def initiate_file_upload(
    case_id: str,
    request: FileInitiateRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> FileInitiateResponse:
    """Initiate file upload for a specific case."""
    try:
        # Verify case exists and user has access
        case = (
            db_session.query(Case)
            .filter(Case.id == UUID(case_id), Case.is_deleted is False)
            .first()
        )

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Case not found"
            )

        # Initialize storage service
        storage_service = StorageService()

        # Generate presigned URL
        content_type = request.content_type or "application/octet-stream"
        presigned_url, fields = storage_service.generate_presigned_url(
            tenant_id="default",  # Should come from user context
            case_id=case_id,
            filename=request.filename,
            content_type=content_type,
            expires_in=3600,  # 1 hour
        )

        # Extract upload ID from the URL or generate one
        upload_id = (
            fields.get("key", "").split("/")[-2]
            if "key" in fields
            else f"upload_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        )

        logger.info(
            f"File upload initiated: {upload_id} for case {case_id} by user {current_user.id}"
        )

        return FileInitiateResponse(
            upload_id=upload_id,
            presigned_url=presigned_url,
            expires_at=datetime.utcnow().replace(microsecond=0).isoformat(),
            fields=fields,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to initiate file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate file upload",
        ) from e


@router.post("/{case_id}/files:complete", response_model=FileResponse)
async def complete_file_upload(
    case_id: str,
    request: FileCompleteRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> FileResponse:
    """Complete file upload and validate file."""
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

        # Initialize storage service
        storage_service = StorageService()

        # Verify file exists in S3 and checksums match
        s3_key = f"default/cases/{case_id}/raw/{request.upload_id}/"

        # Download file temporarily for validation
        with tempfile.NamedTemporaryFile() as temp_file:
            try:
                # Download from S3
                storage_service.s3_client.download_file(
                    storage_service.bucket_name,
                    f"{s3_key}{request.upload_id}",
                    temp_file.name,
                )
            except Exception as e:
                logger.error(f"Failed to download file from S3: {e}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="File not found in S3"
                ) from e

            # Verify checksums
            actual_md5, actual_sha256 = storage_service.calculate_checksums(
                temp_file.name
            )

            if actual_md5 != request.checksum_md5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"MD5 checksum mismatch: expected {request.checksum_md5}, got {actual_md5}",
                )

            if actual_sha256 != request.checksum_sha256:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"SHA256 checksum mismatch: expected {request.checksum_sha256}, got {actual_sha256}",
                )

            # Validate file
            validation_result = storage_service.validate_file(
                file_path=temp_file.name,
                filename=request.upload_id,
                content_type="application/octet-stream",
            )

            if not validation_result.is_valid:
                # Delete invalid file from S3
                try:
                    storage_service.s3_client.delete_object(
                        Bucket=storage_service.bucket_name,
                        Key=f"{s3_key}{request.upload_id}",
                    )
                except Exception as e:
                    logger.warning(f"Failed to delete invalid file: {e}")

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File validation failed: {', '.join(validation_result.errors)}",
                ) from None

            # Create file record in database
            file_record = File(
                case_id=UUID(case_id),
                filename=request.upload_id,
                original_filename=request.upload_id,
                file_path=s3_key,
                file_size=len(temp_file.read()),
                file_type="stl",  # Default, should be detected
                mime_type="application/octet-stream",
                checksum=request.checksum_sha256,
                status=FileStatus.UPLOADED,
                uploaded_by=current_user.id,
                processing_metadata=validation_result.file_info,
            )

            db_session.add(file_record)
            db_session.flush()  # Get the ID

            # Move file to processed location
            processed_key = storage_service.move_to_processed(
                tenant_id="default",
                case_id=case_id,
                upload_id=request.upload_id,
                filename=request.upload_id,
                file_id=str(file_record.id),
            )

            # Update file record with processed path
            file_record.file_path = processed_key
            file_record.status = FileStatus.PROCESSED

            db_session.commit()

            logger.info(f"File upload completed: {file_record.id} for case {case_id}")

            return FileResponse(
                id=str(file_record.id),
                case_id=str(file_record.case_id),
                filename=file_record.filename,
                original_filename=file_record.original_filename,
                file_size=file_record.file_size,
                file_type=file_record.file_type,
                mime_type=file_record.mime_type,
                checksum=file_record.checksum,
                status=file_record.status.value,
                uploaded_by=str(file_record.uploaded_by),
                uploaded_at=file_record.uploaded_at.isoformat(),
                processed_at=file_record.processed_at.isoformat()
                if file_record.processed_at
                else None,
                processing_metadata=file_record.processing_metadata,
                tags=file_record.tags,
                file_metadata=file_record.file_metadata,
                download_url=None,  # Will be generated on demand
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete file upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete file upload",
        ) from e


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> FileResponse:
    """Get a specific file by ID."""
    try:
        file_record = (
            db_session.query(File)
            .filter(File.id == UUID(file_id), File.is_deleted is False)
            .first()
        )

        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Generate download URL
        storage_service = StorageService()
        download_url = storage_service.get_file_url(
            tenant_id="default",
            case_id=str(file_record.case_id),
            file_id=str(file_record.id),
            filename=file_record.filename,
            expires_in=3600,  # 1 hour
        )

        return FileResponse(
            id=str(file_record.id),
            case_id=str(file_record.case_id),
            filename=file_record.filename,
            original_filename=file_record.original_filename,
            file_size=file_record.file_size,
            file_type=file_record.file_type,
            mime_type=file_record.mime_type,
            checksum=file_record.checksum,
            status=file_record.status.value,
            uploaded_by=str(file_record.uploaded_by),
            uploaded_at=file_record.uploaded_at.isoformat(),
            processed_at=file_record.processed_at.isoformat()
            if file_record.processed_at
            else None,
            processing_metadata=file_record.processing_metadata,
            tags=file_record.tags,
            file_metadata=file_record.file_metadata,
            download_url=download_url,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file",
        ) from e


@router.get("/{case_id}/files", response_model=FileListResponse)
async def list_case_files(
    case_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> FileListResponse:
    """List files for a specific case with filtering and pagination."""
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
        query = db_session.query(File).filter(
            File.case_id == UUID(case_id), File.is_deleted is False
        )

        # Apply filters
        if status:
            query = query.filter(File.status == status)
        if file_type:
            query = query.filter(File.file_type == file_type)

        # Get total count
        total = query.count()

        # Apply pagination
        offset = (page - 1) * per_page
        files = (
            query.order_by(File.uploaded_at.desc()).offset(offset).limit(per_page).all()
        )

        # Calculate pages
        pages = (total + per_page - 1) // per_page

        # Convert to response models
        file_responses = []
        storage_service = StorageService()

        for file_record in files:
            # Generate download URL
            download_url = storage_service.get_file_url(
                tenant_id="default",
                case_id=str(file_record.case_id),
                file_id=str(file_record.id),
                filename=file_record.filename,
                expires_in=3600,  # 1 hour
            )

            file_responses.append(
                FileResponse(
                    id=str(file_record.id),
                    case_id=str(file_record.case_id),
                    filename=file_record.filename,
                    original_filename=file_record.original_filename,
                    file_size=file_record.file_size,
                    file_type=file_record.file_type,
                    mime_type=file_record.mime_type,
                    checksum=file_record.checksum,
                    status=file_record.status.value,
                    uploaded_by=str(file_record.uploaded_by),
                    uploaded_at=file_record.uploaded_at.isoformat(),
                    processed_at=file_record.processed_at.isoformat()
                    if file_record.processed_at
                    else None,
                    processing_metadata=file_record.processing_metadata,
                    tags=file_record.tags,
                    file_metadata=file_record.file_metadata,
                    download_url=download_url,
                )
            )

        return FileListResponse(
            files=file_responses,
            total=total,
            page=page,
            per_page=per_page,
            pages=pages,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files for case {case_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list files",
        ) from e


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> None:
    """Delete a file."""
    try:
        file_record = (
            db_session.query(File)
            .filter(File.id == UUID(file_id), File.is_deleted is False)
            .first()
        )

        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Check permissions (user can only delete their own files)
        if file_record.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this file",
            )

        # Delete from S3
        storage_service = StorageService()
        success = storage_service.delete_file(
            tenant_id="default",
            case_id=str(file_record.case_id),
            file_id=str(file_record.id),
            filename=file_record.filename,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete file from storage",
            )

        # Soft delete from database
        file_record.is_deleted = True
        db_session.commit()

        logger.info(f"File deleted: {file_id} by user {current_user.id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file {file_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        ) from e
