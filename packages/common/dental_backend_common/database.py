"""Database models and configuration for the dental backend system."""

import uuid
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class UserRole(str, Enum):
    """User roles for authorization."""

    ADMIN = "admin"
    OPERATOR = "operator"
    SERVICE = "service"


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileStatus(str, Enum):
    """File processing status."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    DELETED = "deleted"


class SegmentType(str, Enum):
    """Types of dental segments."""

    TOOTH = "tooth"
    GUMS = "gums"
    JAW = "jaw"
    IMPLANT = "implant"
    CROWN = "crown"
    BRIDGE = "bridge"
    OTHER = "other"


class ModelType(str, Enum):
    """Types of ML models."""

    SEGMENTATION = "segmentation"
    QUALITY_ASSESSMENT = "quality_assessment"
    FORMAT_CONVERSION = "format_conversion"
    ANATOMICAL_DETECTION = "anatomical_detection"


class AuditEventType(str, Enum):
    """Types of audit events."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    DATA_ACCESS = "data_access"
    DATA_CREATE = "data_create"
    DATA_UPDATE = "data_update"
    DATA_DELETE = "data_delete"
    DATA_RETENTION_PURGE = "data_retention_purge"
    RIGHT_TO_ERASURE = "right_to_erasure"
    CLIENT_AUTHENTICATION = "client_authentication"


class User(Base):
    """User model for authentication and authorization."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(
        SQLEnum(UserRole, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.OPERATOR,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
    last_login = Column(DateTime, nullable=True)
    user_metadata = Column(JSONB, nullable=True)

    # Relationships
    cases = relationship("Case", back_populates="created_by_user")
    jobs = relationship("Job", back_populates="created_by_user")
    audit_logs = relationship("AuditLog", back_populates="user")

    __table_args__ = (
        Index("idx_users_username", "username"),
        Index("idx_users_email", "email"),
        Index("idx_users_role", "role"),
        Index("idx_users_created_at", "created_at"),
    )


class Case(Base):
    """Dental case model representing a patient case."""

    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_number = Column(String(100), unique=True, nullable=False, index=True)
    patient_id = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="active", nullable=False, index=True)
    priority = Column(String(20), default="normal", nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at = Column(DateTime, nullable=True)
    tags = Column(JSONB, nullable=True)
    case_metadata = Column(JSONB, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    created_by_user = relationship("User", back_populates="cases")
    files = relationship("File", back_populates="case")
    jobs = relationship("Job", back_populates="case")
    segments = relationship("Segment", back_populates="case")
    models = relationship("Model", back_populates="case")

    __table_args__ = (
        Index("idx_cases_case_number", "case_number"),
        Index("idx_cases_patient_id", "patient_id"),
        Index("idx_cases_status", "status"),
        Index("idx_cases_created_at", "created_at"),
        Index("idx_cases_priority", "priority"),
        Index("idx_cases_tags", "tags", postgresql_using="gin"),
        Index("idx_cases_metadata", "case_metadata", postgresql_using="gin"),
        Index("idx_cases_status_created_at", "status", "created_at"),
    )


class File(Base):
    """File model for uploaded dental scan files."""

    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(50), nullable=False, index=True)
    mime_type = Column(String(100), nullable=False)
    checksum = Column(String(64), nullable=False, index=True)
    status = Column(
        SQLEnum(FileStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=FileStatus.UPLOADED,
        nullable=False,
        index=True,
    )
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=func.now(), nullable=False)
    processed_at = Column(DateTime, nullable=True)
    processing_metadata = Column(JSONB, nullable=True)
    tags = Column(JSONB, nullable=True)
    file_metadata = Column(JSONB, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    case = relationship("Case", back_populates="files")
    uploaded_by_user = relationship("User")
    jobs = relationship("Job", back_populates="file")
    segments = relationship("Segment", back_populates="file")

    __table_args__ = (
        Index("idx_files_case_id", "case_id"),
        Index("idx_files_status", "status"),
        Index("idx_files_file_type", "file_type"),
        Index("idx_files_checksum", "checksum"),
        Index("idx_files_uploaded_at", "uploaded_at"),
        Index("idx_files_processed_at", "processed_at"),
        Index("idx_files_tags", "tags", postgresql_using="gin"),
        Index("idx_files_metadata", "file_metadata", postgresql_using="gin"),
        Index("idx_files_status_uploaded_at", "status", "uploaded_at"),
    )


class Job(Base):
    """Background job model for processing tasks."""

    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    file_id = Column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=True, index=True
    )
    job_type = Column(String(100), nullable=False, index=True)
    status = Column(
        SQLEnum(JobStatus, values_callable=lambda obj: [e.value for e in obj]),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    priority = Column(Integer, default=5, nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    celery_task_id = Column(String(255), nullable=True, index=True)
    progress = Column(Integer, default=0, nullable=False)
    result = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    parameters = Column(JSONB, nullable=True)
    job_metadata = Column(JSONB, nullable=True)

    # Relationships
    case = relationship("Case", back_populates="jobs")
    file = relationship("File", back_populates="jobs")
    created_by_user = relationship("User", back_populates="jobs")

    __table_args__ = (
        Index("idx_jobs_case_id", "case_id"),
        Index("idx_jobs_file_id", "file_id"),
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_job_type", "job_type"),
        Index("idx_jobs_priority", "priority"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_celery_task_id", "celery_task_id"),
        Index("idx_jobs_status_created_at", "status", "created_at"),
        Index("idx_jobs_priority_created_at", "priority", "created_at"),
    )


class Segment(Base):
    """Dental segment model for anatomical parts."""

    __tablename__ = "segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    file_id = Column(
        UUID(as_uuid=True), ForeignKey("files.id"), nullable=False, index=True
    )
    segment_type = Column(
        SQLEnum(SegmentType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    segment_number = Column(Integer, nullable=True)
    confidence_score = Column(Integer, nullable=True)
    bounding_box = Column(JSONB, nullable=True)
    mesh_data = Column(JSONB, nullable=True)
    properties = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
    created_by_job = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    segment_metadata = Column(JSONB, nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    case = relationship("Case", back_populates="segments")
    file = relationship("File", back_populates="segments")
    created_by_job_rel = relationship("Job")

    __table_args__ = (
        Index("idx_segments_case_id", "case_id"),
        Index("idx_segments_file_id", "file_id"),
        Index("idx_segments_type", "segment_type"),
        Index("idx_segments_created_at", "created_at"),
        Index("idx_segments_confidence", "confidence_score"),
        Index("idx_segments_properties", "properties", postgresql_using="gin"),
        Index("idx_segments_metadata", "segment_metadata", postgresql_using="gin"),
    )


class Model(Base):
    """ML model model for trained models."""

    __tablename__ = "models"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True, index=True
    )
    model_type = Column(
        SQLEnum(ModelType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    model_name = Column(String(255), nullable=False)
    model_version = Column(String(50), nullable=False)
    model_path = Column(String(500), nullable=False)
    model_size = Column(Integer, nullable=True)
    accuracy_score = Column(Integer, nullable=True)
    training_data_info = Column(JSONB, nullable=True)
    hyperparameters = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    model_metadata = Column(JSONB, nullable=True)

    # Relationships
    case = relationship("Case", back_populates="models")

    __table_args__ = (
        Index("idx_models_case_id", "case_id"),
        Index("idx_models_type", "model_type"),
        Index("idx_models_name", "model_name"),
        Index("idx_models_version", "model_version"),
        Index("idx_models_created_at", "created_at"),
        Index("idx_models_active", "is_active"),
        Index("idx_models_metadata", "model_metadata", postgresql_using="gin"),
        UniqueConstraint("model_name", "model_version", name="uq_model_name_version"),
    )


class AuditLog(Base):
    """Audit log model for compliance and security."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    event_type = Column(
        SQLEnum(AuditEventType, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    username = Column(String(100), nullable=True, index=True)
    user_role = Column(
        SQLEnum(UserRole, values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(100), nullable=True, index=True)
    action = Column(String(100), nullable=True)
    details = Column(JSONB, nullable=True)
    outcome = Column(String(20), default="success", nullable=False, index=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_logs_timestamp", "timestamp"),
        Index("idx_audit_logs_event_type", "event_type"),
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_username", "username"),
        Index("idx_audit_logs_resource_type", "resource_type"),
        Index("idx_audit_logs_resource_id", "resource_id"),
        Index("idx_audit_logs_outcome", "outcome"),
        Index("idx_audit_logs_details", "details", postgresql_using="gin"),
        Index("idx_audit_logs_event_type_timestamp", "event_type", "timestamp"),
        Index("idx_audit_logs_user_id_timestamp", "user_id", "timestamp"),
    )


def get_database_url() -> str:
    """Get database URL from settings."""
    from dental_backend_common.config import get_settings

    settings = get_settings()
    return settings.database.url


def create_tables(engine) -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def drop_tables(engine) -> None:
    """Drop all database tables."""
    Base.metadata.drop_all(bind=engine)
