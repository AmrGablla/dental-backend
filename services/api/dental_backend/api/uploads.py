"""Upload API endpoints for secure file upload pipeline."""

import logging
import tempfile
from datetime import datetime
from typing import Dict, Optional
from uuid import UUID

from dental_backend_common.database import File, FileStatus, User
from dental_backend_common.session import get_db_session
from dental_backend_common.storage import (
    FileValidationResult,
    StorageService,
    UploadCompleteRequest,
    UploadInitRequest,
    UploadInitResponse,
)
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from dental_backend.api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/uploads", tags=["uploads"])


class UploadStatusResponse(BaseModel):
    """Response model for upload status."""

    upload_id: str = Field(..., description="Upload ID")
    status: str = Field(..., description="Upload status")
    progress: int = Field(..., description="Upload progress percentage")
    file_info: Optional[Dict] = Field(None, description="File information")


class FileUploadResponse(BaseModel):
    """Response model for completed file upload."""

    file_id: str = Field(..., description="File ID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    checksum_md5: str = Field(..., description="MD5 checksum")
    checksum_sha256: str = Field(..., description="SHA256 checksum")
    status: str = Field(..., description="File status")
    s3_key: str = Field(..., description="S3 storage key")
    validation_result: FileValidationResult = Field(
        ..., description="Validation result"
    )


@router.post("/init", response_model=UploadInitResponse)
async def init_upload(
    request: UploadInitRequest,
    current_user: User = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> UploadInitResponse:
    """Initialize file upload and return presigned URL."""
    try:
        # Validate file size
        max_size = 100 * 1024 * 1024  # 100MB
        if request.file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size {request.file_size} exceeds maximum {max_size}",
            )

        # Initialize storage service
        storage_service = StorageService()

        # Generate presigned URL
        content_type = request.content_type or "application/octet-stream"
        presigned_url, fields = storage_service.generate_presigned_url(
            tenant_id=request.tenant_id,
            case_id=request.case_id,
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

        # Calculate expiration time
        expires_at = datetime.utcnow().replace(microsecond=0)

        logger.info(f"Upload initialized: {upload_id} for case {request.case_id}")

        return UploadInitResponse(
            upload_id=upload_id,
            presigned_url=presigned_url,
            expires_at=expires_at,
            fields=fields,
        )

    except Exception as e:
        logger.error(f"Failed to initialize upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize upload",
        ) from e


@router.post("/complete", response_model=FileUploadResponse)
async def complete_upload(
    request: UploadCompleteRequest,
    current_user: User = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> FileUploadResponse:
    """Complete file upload and validate file."""
    try:
        # Initialize storage service
        storage_service = StorageService()

        # Verify file exists in S3 and checksums match
        s3_key = f"{request.tenant_id}/cases/{request.case_id}/raw/{request.upload_id}/"

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
                case_id=UUID(request.case_id),
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
                tenant_id=request.tenant_id,
                case_id=request.case_id,
                upload_id=request.upload_id,
                filename=request.upload_id,
                file_id=str(file_record.id),
            )

            # Update file record with processed path
            file_record.file_path = processed_key
            file_record.status = FileStatus.PROCESSED

            db_session.commit()

            logger.info(
                f"Upload completed: {file_record.id} for case {request.case_id}"
            )

            return FileUploadResponse(
                file_id=str(file_record.id),
                filename=file_record.original_filename,
                file_size=file_record.file_size,
                checksum_md5=request.checksum_md5,
                checksum_sha256=request.checksum_sha256,
                status=file_record.status.value,
                s3_key=processed_key,
                validation_result=validation_result,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to complete upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete upload",
        ) from e


@router.get("/status/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    case_id: str,
    tenant_id: str,
    current_user: User = Depends(get_current_user),
) -> UploadStatusResponse:
    """Get upload status."""
    try:
        storage_service = StorageService()
        s3_key = f"{tenant_id}/cases/{case_id}/raw/{upload_id}/"

        # Check if file exists in S3
        try:
            storage_service.s3_client.head_object(
                Bucket=storage_service.bucket_name, Key=f"{s3_key}{upload_id}"
            )
            status = "uploaded"
            progress = 100
        except Exception:
            status = "pending"
            progress = 0

        return UploadStatusResponse(
            upload_id=upload_id, status=status, progress=progress, file_info=None
        )

    except Exception as e:
        logger.error(f"Failed to get upload status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get upload status",
        ) from e


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> Dict[str, str]:
    """Delete uploaded file."""
    try:
        # Get file record
        file_record = db_session.query(File).filter(File.id == UUID(file_id)).first()
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
            tenant_id="default",  # Should come from user context
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

        return {"message": "File deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        ) from e


@router.get("/files/{file_id}/download")
async def get_download_url(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db_session=Depends(get_db_session),
) -> Dict[str, str]:
    """Get presigned download URL for file."""
    try:
        # Get file record
        file_record = db_session.query(File).filter(File.id == UUID(file_id)).first()
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Check if file is deleted
        if file_record.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Generate download URL
        storage_service = StorageService()
        download_url = storage_service.get_file_url(
            tenant_id="default",  # Should come from user context
            case_id=str(file_record.case_id),
            file_id=str(file_record.id),
            filename=file_record.filename,
            expires_in=3600,  # 1 hour
        )

        return {"download_url": download_url}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        ) from e
