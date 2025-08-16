"""Dental Backend Common Package."""

from dental_backend_common.audit import (
    AuditEventType,
    AuditLogger,
    DataRetentionManager,
    PIIFilter,
    audit_logger,
    data_retention_manager,
    log_request,
    log_response,
)
from dental_backend_common.auth import (
    User,
    authenticate_client,
    authenticate_user,
    check_permission,
    create_access_token,
    create_refresh_token,
    generate_pseudonym,
    get_password_hash,
    verify_password,
    verify_token,
)
from dental_backend_common.config import get_settings
from dental_backend_common.database import (
    AuditLog,
    Base,
    Case,
    File,
    FileStatus,
    Job,
    JobStatus,
    Model,
    ModelType,
    Segment,
    SegmentType,
    UserRole,
    create_tables,
    drop_tables,
    get_database_url,
)
from dental_backend_common.database import (
    User as DBUser,
)
from dental_backend_common.encryption import (
    EncryptionManager,
    db_encryption,
    decrypt_pii,
    encrypt_pii,
    encryption_manager,
    hash_sensitive_data,
)
from dental_backend_common.session import (
    SessionLocal,
    check_db_connection,
    drop_db,
    get_db,
    get_db_session,
    init_db,
)

__all__ = [
    # Audit
    "AuditEventType",
    "AuditLogger",
    "DataRetentionManager",
    "PIIFilter",
    "audit_logger",
    "data_retention_manager",
    "log_request",
    "log_response",
    # Auth
    "User",
    "authenticate_client",
    "authenticate_user",
    "create_access_token",
    "create_refresh_token",
    "get_password_hash",
    "verify_password",
    "verify_token",
    "check_permission",
    "generate_pseudonym",
    # Config
    "get_settings",
    # Database
    "AuditLog",
    "Base",
    "Case",
    "File",
    "FileStatus",
    "Job",
    "JobStatus",
    "Model",
    "ModelType",
    "Segment",
    "SegmentType",
    "DBUser",
    "UserRole",
    "create_tables",
    "drop_tables",
    "get_database_url",
    # Session
    "SessionLocal",
    "check_db_connection",
    "drop_db",
    "get_db",
    "get_db_session",
    "init_db",
    # Encryption
    "EncryptionManager",
    "db_encryption",
    "decrypt_pii",
    "encrypt_pii",
    "encryption_manager",
    "hash_sensitive_data",
]
