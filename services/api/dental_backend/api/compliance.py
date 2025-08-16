"""Compliance endpoints for data retention and privacy rights."""

from datetime import datetime

from dental_backend_common.audit import (
    AuditEventType,
    audit_logger,
    data_retention_manager,
)
from dental_backend_common.auth import User
from dental_backend_common.config import get_settings
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from dental_backend.api.dependencies import require_admin, require_operator

# Get settings
settings = get_settings()

# Create router
router = APIRouter(prefix="/compliance", tags=["compliance"])


class DataRetentionRequest(BaseModel):
    """Data retention request model."""

    resource_type: str = Field(..., description="Type of resource to purge")
    dry_run: bool = Field(
        default=True, description="Perform dry run without actual deletion"
    )


class DataRetentionResponse(BaseModel):
    """Data retention response model."""

    resource_type: str
    expired_count: int
    expired_ids: list[str]
    dry_run: bool
    purged_count: int = 0
    message: str


class RightToErasureRequest(BaseModel):
    """Right to erasure request model."""

    patient_id: str = Field(..., description="Patient identifier")
    reason: str = Field(..., description="Reason for erasure request")
    dry_run: bool = Field(
        default=True, description="Perform dry run without actual deletion"
    )


class RightToErasureResponse(BaseModel):
    """Right to erasure response model."""

    patient_id: str
    pseudonymized_id: str
    affected_resources: list[str]
    affected_count: int
    dry_run: bool
    erased_count: int = 0
    message: str


class AuditLogExportRequest(BaseModel):
    """Audit log export request model."""

    start_date: datetime = Field(..., description="Start date for export")
    end_date: datetime = Field(..., description="End date for export")
    event_types: list[str] = Field(default=[], description="Filter by event types")
    user_id: str = Field(default="", description="Filter by user ID")


@router.post("/data-retention/purge", response_model=DataRetentionResponse)
async def purge_expired_data(
    request: Request,
    retention_request: DataRetentionRequest,
    current_user: User = Depends(require_admin),
) -> DataRetentionResponse:
    """Purge expired data based on retention policy."""

    # Mock data for demonstration
    # In production, this would query the actual database
    mock_data = [
        {"id": "case-001", "created_at": datetime(2020, 1, 1), "type": "dental_case"},
        {"id": "case-002", "created_at": datetime(2020, 1, 15), "type": "dental_case"},
        {"id": "scan-001", "created_at": datetime(2023, 1, 1), "type": "dental_scan"},
        {"id": "scan-002", "created_at": datetime(2023, 6, 1), "type": "dental_scan"},
    ]

    # Filter by resource type
    filtered_data = [
        item for item in mock_data if item["type"] == retention_request.resource_type
    ]

    # Get expired data
    expired_ids = data_retention_manager.get_expired_data_ids(filtered_data)

    # Log the purge event
    audit_logger.log_event(
        event_type=AuditEventType.DATA_RETENTION_PURGE,
        user=current_user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        resource_type=retention_request.resource_type,
        action="purge",
        details={
            "expired_count": len(expired_ids),
            "expired_ids": expired_ids,
            "dry_run": retention_request.dry_run,
            "retention_days": settings.data_retention_days,
        },
    )

    purged_count = 0
    message = (
        f"Found {len(expired_ids)} expired {retention_request.resource_type} records"
    )

    if not retention_request.dry_run and expired_ids:
        # In production, this would actually delete the data
        purged_count = len(expired_ids)
        message = f"Successfully purged {purged_count} expired {retention_request.resource_type} records"

    return DataRetentionResponse(
        resource_type=retention_request.resource_type,
        expired_count=len(expired_ids),
        expired_ids=expired_ids,
        dry_run=retention_request.dry_run,
        purged_count=purged_count,
        message=message,
    )


@router.post("/right-to-erasure", response_model=RightToErasureResponse)
async def process_right_to_erasure(
    request: Request,
    erasure_request: RightToErasureRequest,
    current_user: User = Depends(require_admin),
) -> RightToErasureResponse:
    """Process right to erasure request (GDPR Article 17)."""

    # Generate pseudonymized ID
    from dental_backend_common.auth import generate_pseudonym

    pseudonymized_id = generate_pseudonym(erasure_request.patient_id)

    # Mock data for demonstration
    # In production, this would query the actual database
    mock_affected_resources = [
        f"dental_case_{erasure_request.patient_id}",
        f"dental_scan_{erasure_request.patient_id}_001",
        f"dental_scan_{erasure_request.patient_id}_002",
        f"analysis_report_{erasure_request.patient_id}",
    ]

    # Log the right to erasure request
    audit_logger.log_event(
        event_type=AuditEventType.RIGHT_TO_ERASURE,
        user=current_user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        resource_type="patient_data",
        action="erasure_request",
        details={
            "patient_id": erasure_request.patient_id,
            "pseudonymized_id": pseudonymized_id,
            "reason": erasure_request.reason,
            "affected_count": len(mock_affected_resources),
            "affected_resources": mock_affected_resources,
            "dry_run": erasure_request.dry_run,
        },
    )

    erased_count = 0
    message = f"Right to erasure request processed for patient {pseudonymized_id}"

    if not erasure_request.dry_run:
        # In production, this would actually delete the data
        erased_count = len(mock_affected_resources)
        message = f"Successfully erased {erased_count} resources for patient {pseudonymized_id}"

    return RightToErasureResponse(
        patient_id=erasure_request.patient_id,
        pseudonymized_id=pseudonymized_id,
        affected_resources=mock_affected_resources,
        affected_count=len(mock_affected_resources),
        dry_run=erasure_request.dry_run,
        erased_count=erased_count,
        message=message,
    )


@router.get("/audit-logs")
async def get_audit_logs(
    request: Request,
    start_date: datetime,
    end_date: datetime,
    event_type: str = "",
    user_id: str = "",
    limit: int = 100,
    current_user: User = Depends(require_admin),
) -> dict:
    """Get audit logs with filtering."""

    # Log the audit log access
    audit_logger.log_event(
        event_type=AuditEventType.AUDIT_LOG_EXPORT,
        user=current_user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        action="audit_log_access",
        details={
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "limit": limit,
        },
    )

    # Mock audit log data
    # In production, this would query the actual audit log database
    mock_logs = [
        {
            "id": "audit-001",
            "timestamp": datetime(2024, 1, 15, 10, 30, 0),
            "event_type": "login_success",
            "user_id": "admin-001",
            "username": "admin",
            "ip_address": "192.168.1.100",
            "action": "login",
            "outcome": "success",
        },
        {
            "id": "audit-002",
            "timestamp": datetime(2024, 1, 15, 11, 0, 0),
            "event_type": "data_access",
            "user_id": "operator-001",
            "username": "operator",
            "ip_address": "192.168.1.101",
            "resource_type": "dental_case",
            "resource_id": "case-123",
            "action": "access",
            "outcome": "success",
        },
    ]

    # Apply filters
    filtered_logs = mock_logs

    if event_type:
        filtered_logs = [
            log for log in filtered_logs if log["event_type"] == event_type
        ]

    if user_id:
        filtered_logs = [log for log in filtered_logs if log["user_id"] == user_id]

    # Apply date range
    filtered_logs = [
        log for log in filtered_logs if start_date <= log["timestamp"] <= end_date
    ]

    # Apply limit
    filtered_logs = filtered_logs[:limit]

    return {
        "logs": filtered_logs,
        "total_count": len(filtered_logs),
        "filters": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "limit": limit,
        },
    }


@router.get("/compliance-status")
async def get_compliance_status(current_user: User = Depends(require_operator)) -> dict:
    """Get compliance status and configuration."""

    return {
        "hipaa_compliance": {
            "data_retention_days": settings.data_retention_days,
            "audit_logging_enabled": settings.audit_log_enabled,
            "encryption_enabled": settings.encryption_enabled,
            "pii_encryption_enabled": settings.pii_encryption_enabled,
            "pseudonymization_enabled": settings.pseudonymization_enabled,
        },
        "gdpr_compliance": {
            "right_to_erasure_enabled": True,
            "data_portability_enabled": True,
            "consent_management_enabled": True,
            "data_retention_policies": {
                "dental_cases": f"{settings.data_retention_days} days",
                "dental_scans": f"{settings.data_retention_days} days",
                "audit_logs": "7 years",
            },
        },
        "security_features": {
            "tls_enabled": bool(settings.security.tls_cert_file),
            "kms_encryption": bool(settings.security.kms_key_id),
            "rate_limiting": True,
            "rbac_enabled": True,
        },
    }
