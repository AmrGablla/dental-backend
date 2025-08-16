"""Audit logging and compliance system for the dental backend."""

import re
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import structlog
from dental_backend_common.auth import User, UserRole
from dental_backend_common.config import get_settings
from dental_backend_common.encryption import hash_sensitive_data
from pydantic import BaseModel, Field

# Get settings
settings = get_settings()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"

    # Data access events
    DATA_ACCESS = "data_access"
    DATA_CREATE = "data_create"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"

    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CONFIGURATION_CHANGE = "configuration_change"

    # Compliance events
    DATA_RETENTION_PURGE = "data_retention_purge"
    RIGHT_TO_ERASURE = "right_to_erasure"
    AUDIT_LOG_EXPORT = "audit_log_export"


class AuditLogEntry(BaseModel):
    """Audit log entry model."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: AuditEventType
    user_id: str | None = None
    username: str | None = None
    user_role: UserRole | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    action: str | None = None
    details: dict[str, Any] | None = None
    outcome: str = "success"  # success, failure, error
    error_message: str | None = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UserRole: lambda v: v.value}


class PIIFilter:
    """Filters and scrubs PII/PHI from logs and data."""

    # Common PII patterns
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        "patient_id": r"\b(patient|pt|id)[\s:]*(\d+)\b",
        "medical_record": r"\b(mr|medical_record|record)[\s:]*(\d+)\b",
    }

    @classmethod
    def scrub_pii(cls, text: str) -> str:
        """Scrub PII from text."""
        if not text:
            return text

        scrubbed = text

        for pattern_name, pattern in cls.PII_PATTERNS.items():
            if pattern_name in ["email", "phone", "ssn", "credit_card"]:
                # Replace with [REDACTED]
                scrubbed = re.sub(pattern, "[REDACTED]", scrubbed, flags=re.IGNORECASE)
            else:
                # Replace with pseudonymized version
                scrubbed = re.sub(
                    pattern,
                    lambda m: f"{m.group(1)}:PSEUDO_{hash_sensitive_data(m.group(2))[:8]}",
                    scrubbed,
                    flags=re.IGNORECASE,
                )

        return scrubbed

    @classmethod
    def scrub_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Scrub PII from dictionary."""
        if not data:
            return data

        scrubbed = {}
        for key, value in data.items():
            if isinstance(value, str):
                scrubbed[key] = cls.scrub_pii(value)
            elif isinstance(value, dict):
                scrubbed[key] = cls.scrub_dict(value)
            elif isinstance(value, list):
                scrubbed[key] = [
                    cls.scrub_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                scrubbed[key] = value

        return scrubbed


class AuditLogger:
    """Audit logging system."""

    def __init__(self):
        self.logger = structlog.get_logger("audit")

    def log_event(
        self,
        event_type: AuditEventType,
        user: User | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        action: str | None = None,
        details: dict[str, Any] | None = None,
        outcome: str = "success",
        error_message: str | None = None,
    ) -> AuditLogEntry:
        """Log an audit event."""
        if not settings.audit_log_enabled:
            return None

        # Scrub PII from details
        scrubbed_details = None
        if details:
            scrubbed_details = PIIFilter.scrub_dict(details)

        # Create audit entry
        entry = AuditLogEntry(
            event_type=event_type,
            user_id=user.id if user else None,
            username=user.username if user else None,
            user_role=user.role if user else None,
            ip_address=ip_address,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            details=scrubbed_details,
            outcome=outcome,
            error_message=error_message,
        )

        # Log to structured logger
        log_data = entry.dict()
        if outcome == "success":
            self.logger.info("audit_event", **log_data)
        else:
            self.logger.warning("audit_event", **log_data)

        return entry

    def log_login_success(
        self, user: User, ip_address: str, user_agent: str
    ) -> AuditLogEntry:
        """Log successful login."""
        return self.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
            action="login",
        )

    def log_login_failure(
        self, username: str, ip_address: str, user_agent: str, error: str
    ) -> AuditLogEntry:
        """Log failed login attempt."""
        return self.log_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            ip_address=ip_address,
            user_agent=user_agent,
            action="login",
            outcome="failure",
            error_message=error,
            details={"attempted_username": username},
        )

    def log_data_access(
        self, user: User, resource_type: str, resource_id: str, ip_address: str
    ) -> AuditLogEntry:
        """Log data access."""
        return self.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            user=user,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            action="access",
        )

    def log_data_deletion(
        self, user: User, resource_type: str, resource_id: str, ip_address: str
    ) -> AuditLogEntry:
        """Log data deletion."""
        return self.log_event(
            event_type=AuditEventType.DATA_DELETE,
            user=user,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            action="delete",
        )


class DataRetentionManager:
    """Manages data retention and deletion policies."""

    def __init__(self):
        self.logger = structlog.get_logger("data_retention")

    def should_delete_data(self, created_at: datetime) -> bool:
        """Check if data should be deleted based on retention policy."""
        retention_days = settings.data_retention_days
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        return created_at < cutoff_date

    def get_expired_data_ids(self, data_records: list[dict[str, Any]]) -> list[str]:
        """Get IDs of data that should be deleted."""
        expired_ids = []
        for record in data_records:
            created_at = record.get("created_at")
            if created_at and self.should_delete_data(created_at):
                expired_ids.append(record["id"])
        return expired_ids

    def log_data_purge(
        self, user: User, resource_type: str, resource_ids: list[str]
    ) -> AuditLogEntry:
        """Log data purge event."""
        audit_logger = AuditLogger()
        return audit_logger.log_event(
            event_type=AuditEventType.DATA_RETENTION_PURGE,
            user=user,
            resource_type=resource_type,
            action="purge",
            details={
                "purged_count": len(resource_ids),
                "purged_ids": resource_ids,
                "retention_days": settings.data_retention_days,
            },
        )

    def log_right_to_erasure(
        self, user: User, patient_id: str, resource_ids: list[str]
    ) -> AuditLogEntry:
        """Log right to erasure request."""
        audit_logger = AuditLogger()
        return audit_logger.log_event(
            event_type=AuditEventType.RIGHT_TO_ERASURE,
            user=user,
            resource_type="patient_data",
            action="erasure_request",
            details={
                "patient_id": patient_id,
                "erased_count": len(resource_ids),
                "erased_ids": resource_ids,
            },
        )


# Global instances
audit_logger = AuditLogger()
data_retention_manager = DataRetentionManager()


def log_request(request_data: dict[str, Any], user: User | None = None) -> None:
    """Log incoming request with PII scrubbing."""
    if not settings.audit_log_enabled:
        return

    # Scrub PII from request data
    scrubbed_data = PIIFilter.scrub_dict(request_data)

    logger.info(
        "incoming_request",
        user_id=user.id if user else None,
        username=user.username if user else None,
        request_data=scrubbed_data,
    )


def log_response(response_data: dict[str, Any], user: User | None = None) -> None:
    """Log outgoing response with PII scrubbing."""
    if not settings.audit_log_enabled:
        return

    # Scrub PII from response data
    scrubbed_data = PIIFilter.scrub_dict(response_data)

    logger.info(
        "outgoing_response",
        user_id=user.id if user else None,
        username=user.username if user else None,
        response_data=scrubbed_data,
    )
