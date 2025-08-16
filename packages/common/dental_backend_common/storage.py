"""Storage service for handling file uploads, validation, and S3 operations."""

import hashlib
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3
import magic
import trimesh
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet
from dental_backend_common.config import get_settings
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
settings = get_settings()


class UploadInitRequest(BaseModel):
    """Request model for initializing file upload."""

    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    case_id: str = Field(..., description="Case ID")
    tenant_id: str = Field(..., description="Tenant ID")
    content_type: Optional[str] = Field(None, description="Content type")


class UploadInitResponse(BaseModel):
    """Response model for upload initialization."""

    upload_id: str = Field(..., description="Unique upload ID")
    presigned_url: str = Field(..., description="Presigned URL for upload")
    expires_at: datetime = Field(..., description="URL expiration time")
    fields: Dict[str, str] = Field(..., description="Required form fields")


class UploadCompleteRequest(BaseModel):
    """Request model for completing file upload."""

    upload_id: str = Field(..., description="Upload ID from init")
    case_id: str = Field(..., description="Case ID")
    tenant_id: str = Field(..., description="Tenant ID")
    checksum_md5: str = Field(..., description="MD5 checksum")
    checksum_sha256: str = Field(..., description="SHA256 checksum")


class FileValidationResult(BaseModel):
    """Result of file validation."""

    is_valid: bool = Field(..., description="Whether file is valid")
    errors: List[str] = Field(default_factory=list, description="Validation errors")
    warnings: List[str] = Field(default_factory=list, description="Validation warnings")
    file_info: Dict[str, Any] = Field(default_factory=dict, description="File metadata")


class StorageService:
    """Service for handling file storage operations."""

    def __init__(self):
        """Initialize the storage service."""
        self.s3_client = self._create_s3_client()
        self.bucket_name = settings.s3.bucket_name
        self.encryption_key = self._get_encryption_key()

    def _create_s3_client(self) -> boto3.client:
        """Create S3 client with proper configuration."""
        try:
            return boto3.client(
                "s3",
                endpoint_url=settings.s3.endpoint_url,
                aws_access_key_id=settings.s3.access_key_id,
                aws_secret_access_key=settings.s3.secret_access_key,
                region_name=settings.s3.region_name,
                use_ssl=settings.s3.use_ssl,
            )
        except Exception as e:
            logger.error(f"Failed to create S3 client: {e}")
            raise

    def _get_encryption_key(self) -> Optional[bytes]:
        """Get encryption key for server-side encryption."""
        if settings.security.encryption_enabled and settings.security.kms_key_id:
            # In production, use AWS KMS
            return None
        elif settings.security.encryption_enabled:
            # For development, use a simple key
            key = os.getenv("ENCRYPTION_KEY")
            if not key:
                key = Fernet.generate_key()
                logger.warning("Using generated encryption key for development")
            return key
        return None

    def generate_presigned_url(
        self,
        tenant_id: str,
        case_id: str,
        filename: str,
        content_type: str,
        expires_in: int = 3600,
    ) -> Tuple[str, Dict[str, str]]:
        """Generate presigned URL for file upload."""
        try:
            # Generate unique upload ID
            upload_id = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(f'{tenant_id}_{case_id}_{filename}'.encode()).hexdigest()[:8]}"

            # Create S3 key
            s3_key = f"{tenant_id}/cases/{case_id}/raw/{upload_id}/{filename}"

            # Generate presigned URL
            presigned_url = self.s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self.bucket_name,
                    "Key": s3_key,
                    "ContentType": content_type,
                    "ServerSideEncryption": "AES256" if self.encryption_key else None,
                },
                ExpiresIn=expires_in,
            )

            # Required form fields
            fields = {
                "key": s3_key,
                "Content-Type": content_type,
            }

            if self.encryption_key:
                fields["x-amz-server-side-encryption"] = "AES256"

            return presigned_url, fields

        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def validate_file(
        self, file_path: str, filename: str, content_type: Optional[str] = None
    ) -> FileValidationResult:
        """Validate uploaded file for security and integrity."""
        result = FileValidationResult(is_valid=True)

        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            max_size = settings.validation.max_file_size_mb * 1024 * 1024

            if file_size > max_size:
                result.is_valid = False
                result.errors.append(
                    f"File size {file_size} exceeds maximum {max_size}"
                )

            # Validate file extension first
            file_ext = Path(filename).suffix.lower().lstrip(".")
            allowed_extensions = settings.allowed_file_types

            if file_ext not in allowed_extensions:
                result.is_valid = False
                result.errors.append(f"File extension {file_ext} not allowed")

            # Detect MIME type
            detected_type = magic.from_file(file_path, mime=True)
            result.file_info["detected_mime_type"] = detected_type

            # Validate MIME type
            allowed_types = settings.validation.allowed_mime_types
            if detected_type not in allowed_types:
                # In development, be more lenient with file type detection
                if (
                    settings.environment == "development"
                    and detected_type == "text/plain"
                ):
                    # Check if it's actually an STL file by extension
                    if file_ext in ["stl", "ply", "obj"]:
                        result.warnings.append(
                            f"File type detected as {detected_type} but extension suggests {file_ext}"
                        )
                    else:
                        result.is_valid = False
                        result.errors.append(f"File type {detected_type} not allowed")
                else:
                    result.is_valid = False
                    result.errors.append(f"File type {detected_type} not allowed")

            # 3D model validation
            if settings.validation.scan_3d_models and file_ext in ["stl", "ply", "obj"]:
                mesh_validation = self._validate_3d_model(file_path)
                if not mesh_validation["is_valid"]:
                    result.is_valid = False
                    result.errors.extend(mesh_validation["errors"])
                else:
                    result.file_info.update(mesh_validation["info"])

            # Antivirus scan
            if settings.antivirus.enabled:
                av_result = self._scan_antivirus(file_path)
                if not av_result["is_clean"]:
                    result.is_valid = False
                    result.errors.append(
                        f"Antivirus scan failed: {av_result['reason']}"
                    )

            return result

        except Exception as e:
            logger.error(f"File validation failed: {e}")
            result.is_valid = False
            result.errors.append(f"Validation error: {str(e)}")
            return result

    def _validate_3d_model(self, file_path: str) -> Dict[str, Any]:
        """Validate 3D model file."""
        try:
            mesh = trimesh.load(file_path)

            # Check vertex count
            if (
                hasattr(mesh, "vertices")
                and len(mesh.vertices) > settings.validation.max_vertices
            ):
                return {
                    "is_valid": False,
                    "errors": [
                        f"Vertex count {len(mesh.vertices)} exceeds maximum {settings.validation.max_vertices}"
                    ],
                }

            # Check face count
            if (
                hasattr(mesh, "faces")
                and len(mesh.faces) > settings.validation.max_faces
            ):
                return {
                    "is_valid": False,
                    "errors": [
                        f"Face count {len(mesh.faces)} exceeds maximum {settings.validation.max_faces}"
                    ],
                }

            return {
                "is_valid": True,
                "info": {
                    "vertex_count": len(mesh.vertices)
                    if hasattr(mesh, "vertices")
                    else 0,
                    "face_count": len(mesh.faces) if hasattr(mesh, "faces") else 0,
                    "bounds": mesh.bounds.tolist() if hasattr(mesh, "bounds") else None,
                    "volume": mesh.volume if hasattr(mesh, "volume") else None,
                },
            }

        except Exception as e:
            return {
                "is_valid": False,
                "errors": [f"3D model validation failed: {str(e)}"],
            }

    def _scan_antivirus(self, file_path: str) -> Dict[str, Any]:
        """Scan file with ClamAV."""
        try:
            import clamd

            cd = clamd.ClamdNetworkSocket(
                host=settings.antivirus.clamav_host,
                port=settings.antivirus.clamav_port,
                timeout=settings.antivirus.scan_timeout,
            )

            scan_result = cd.instream(open(file_path, "rb"))

            if scan_result["stream"][0] == "OK":
                return {"is_clean": True, "reason": "Clean"}
            else:
                return {
                    "is_clean": False,
                    "reason": f"Virus detected: {scan_result['stream'][1]}",
                }

        except Exception as e:
            logger.warning(f"Antivirus scan failed: {e}")
            # In development, allow files if antivirus is not available
            if settings.environment == "development":
                return {"is_clean": True, "reason": "Skipped in development"}
            else:
                return {"is_clean": False, "reason": f"Scan error: {str(e)}"}

    def calculate_checksums(self, file_path: str) -> Tuple[str, str]:
        """Calculate MD5 and SHA256 checksums of file."""
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                md5_hash.update(chunk)
                sha256_hash.update(chunk)

        return md5_hash.hexdigest(), sha256_hash.hexdigest()

    def verify_file_in_s3(
        self,
        tenant_id: str,
        case_id: str,
        upload_id: str,
        filename: str,
        expected_md5: str,
        expected_sha256: str,
    ) -> bool:
        """Verify file exists in S3 and checksums match."""
        try:
            s3_key = f"{tenant_id}/cases/{case_id}/raw/{upload_id}/{filename}"

            # Check if file exists
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)

            # Download file temporarily for checksum verification
            with tempfile.NamedTemporaryFile() as temp_file:
                self.s3_client.download_file(self.bucket_name, s3_key, temp_file.name)

                # Calculate checksums
                actual_md5, actual_sha256 = self.calculate_checksums(temp_file.name)

                # Verify checksums
                if actual_md5 != expected_md5:
                    logger.error(
                        f"MD5 checksum mismatch: expected {expected_md5}, got {actual_md5}"
                    )
                    return False

                if actual_sha256 != expected_sha256:
                    logger.error(
                        f"SHA256 checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
                    )
                    return False

                return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.error(f"File not found in S3: {s3_key}")
            else:
                logger.error(f"S3 error: {e}")
            return False
        except Exception as e:
            logger.error(f"File verification failed: {e}")
            return False

    def move_to_processed(
        self, tenant_id: str, case_id: str, upload_id: str, filename: str, file_id: str
    ) -> str:
        """Move file from raw to processed location."""
        try:
            source_key = f"{tenant_id}/cases/{case_id}/raw/{upload_id}/{filename}"
            dest_key = f"{tenant_id}/cases/{case_id}/processed/{file_id}/{filename}"

            # Copy to processed location
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={"Bucket": self.bucket_name, "Key": source_key},
                Key=dest_key,
                ServerSideEncryption="AES256" if self.encryption_key else None,
            )

            # Delete from raw location
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=source_key)

            return dest_key

        except Exception as e:
            logger.error(f"Failed to move file to processed: {e}")
            raise

    def get_file_url(
        self,
        tenant_id: str,
        case_id: str,
        file_id: str,
        filename: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate presigned URL for file download."""
        try:
            s3_key = f"{tenant_id}/cases/{case_id}/processed/{file_id}/{filename}"

            return self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expires_in,
            )

        except Exception as e:
            logger.error(f"Failed to generate download URL: {e}")
            raise

    def delete_file(
        self, tenant_id: str, case_id: str, file_id: str, filename: str
    ) -> bool:
        """Delete file from S3."""
        try:
            s3_key = f"{tenant_id}/cases/{case_id}/processed/{file_id}/{filename}"
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True

        except Exception as e:
            logger.error(f"Failed to delete file: {e}")
            return False
