"""Initial database schema

Revision ID: 5c956ad7ccec
Revises:
Create Date: 2025-08-16 22:35:45.084803

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "5c956ad7ccec"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums will be created automatically by SQLAlchemy when creating tables

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM("admin", "operator", "service", name="userrole"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column(
            "user_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )

    # Create cases table
    op.create_table(
        "cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_number", sa.String(length=100), nullable=False),
        sa.Column("patient_id", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "case_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_number"),
    )

    # Create files table
    op.create_table(
        "files",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "uploaded",
                "processing",
                "processed",
                "failed",
                "deleted",
                name="filestatus",
            ),
            nullable=False,
        ),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "processing_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "file_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create jobs table
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "completed",
                "failed",
                "cancelled",
                name="jobstatus",
            ),
            nullable=False,
        ),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "job_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create segments table
    op.create_table(
        "segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "segment_type",
            postgresql.ENUM(
                "tooth",
                "gums",
                "jaw",
                "implant",
                "crown",
                "bridge",
                "other",
                name="segmenttype",
            ),
            nullable=False,
        ),
        sa.Column("segment_number", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=True),
        sa.Column(
            "bounding_box", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("mesh_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_job", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "segment_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.ForeignKeyConstraint(
            ["created_by_job"],
            ["jobs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create models table
    op.create_table(
        "models",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "model_type",
            postgresql.ENUM(
                "segmentation",
                "quality_assessment",
                "format_conversion",
                "anatomical_detection",
                name="modeltype",
            ),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("model_path", sa.String(length=500), nullable=False),
        sa.Column("model_size", sa.Integer(), nullable=True),
        sa.Column("accuracy_score", sa.Integer(), nullable=True),
        sa.Column(
            "training_data_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "hyperparameters", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "model_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "model_name", "model_version", name="uq_model_name_version"
        ),
    )

    # Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column(
            "event_type",
            postgresql.ENUM(
                "login_success",
                "login_failure",
                "data_access",
                "data_create",
                "data_update",
                "data_delete",
                "data_retention_purge",
                "right_to_erasure",
                "client_authentication",
                name="auditeventtype",
            ),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("username", sa.String(length=100), nullable=True),
        sa.Column(
            "user_role",
            postgresql.ENUM("admin", "operator", "service", name="userrole"),
            nullable=True,
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indices
    op.create_index("idx_users_username", "users", ["username"], unique=False)
    op.create_index("idx_users_email", "users", ["email"], unique=False)
    op.create_index("idx_users_role", "users", ["role"], unique=False)
    op.create_index("idx_users_created_at", "users", ["created_at"], unique=False)

    op.create_index("idx_cases_case_number", "cases", ["case_number"], unique=False)
    op.create_index("idx_cases_patient_id", "cases", ["patient_id"], unique=False)
    op.create_index("idx_cases_status", "cases", ["status"], unique=False)
    op.create_index("idx_cases_created_at", "cases", ["created_at"], unique=False)
    op.create_index("idx_cases_priority", "cases", ["priority"], unique=False)
    op.create_index(
        "idx_cases_tags", "cases", ["tags"], unique=False, postgresql_using="gin"
    )
    op.create_index(
        "idx_cases_metadata",
        "cases",
        ["case_metadata"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_cases_status_created_at", "cases", ["status", "created_at"], unique=False
    )
    op.create_index("idx_cases_is_deleted", "cases", ["is_deleted"], unique=False)

    op.create_index("idx_files_case_id", "files", ["case_id"], unique=False)
    op.create_index("idx_files_status", "files", ["status"], unique=False)
    op.create_index("idx_files_file_type", "files", ["file_type"], unique=False)
    op.create_index("idx_files_checksum", "files", ["checksum"], unique=False)
    op.create_index("idx_files_uploaded_at", "files", ["uploaded_at"], unique=False)
    op.create_index("idx_files_processed_at", "files", ["processed_at"], unique=False)
    op.create_index(
        "idx_files_tags", "files", ["tags"], unique=False, postgresql_using="gin"
    )
    op.create_index(
        "idx_files_metadata",
        "files",
        ["file_metadata"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_files_status_uploaded_at", "files", ["status", "uploaded_at"], unique=False
    )
    op.create_index("idx_files_is_deleted", "files", ["is_deleted"], unique=False)

    op.create_index("idx_jobs_case_id", "jobs", ["case_id"], unique=False)
    op.create_index("idx_jobs_file_id", "jobs", ["file_id"], unique=False)
    op.create_index("idx_jobs_status", "jobs", ["status"], unique=False)
    op.create_index("idx_jobs_job_type", "jobs", ["job_type"], unique=False)
    op.create_index("idx_jobs_priority", "jobs", ["priority"], unique=False)
    op.create_index("idx_jobs_created_at", "jobs", ["created_at"], unique=False)
    op.create_index("idx_jobs_celery_task_id", "jobs", ["celery_task_id"], unique=False)
    op.create_index(
        "idx_jobs_status_created_at", "jobs", ["status", "created_at"], unique=False
    )
    op.create_index(
        "idx_jobs_priority_created_at", "jobs", ["priority", "created_at"], unique=False
    )

    op.create_index("idx_segments_case_id", "segments", ["case_id"], unique=False)
    op.create_index("idx_segments_file_id", "segments", ["file_id"], unique=False)
    op.create_index("idx_segments_type", "segments", ["segment_type"], unique=False)
    op.create_index("idx_segments_created_at", "segments", ["created_at"], unique=False)
    op.create_index(
        "idx_segments_confidence", "segments", ["confidence_score"], unique=False
    )
    op.create_index(
        "idx_segments_properties",
        "segments",
        ["properties"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_segments_metadata",
        "segments",
        ["segment_metadata"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index("idx_segments_is_deleted", "segments", ["is_deleted"], unique=False)

    op.create_index("idx_models_case_id", "models", ["case_id"], unique=False)
    op.create_index("idx_models_type", "models", ["model_type"], unique=False)
    op.create_index("idx_models_name", "models", ["model_name"], unique=False)
    op.create_index("idx_models_version", "models", ["model_version"], unique=False)
    op.create_index("idx_models_created_at", "models", ["created_at"], unique=False)
    op.create_index("idx_models_active", "models", ["is_active"], unique=False)
    op.create_index(
        "idx_models_metadata",
        "models",
        ["model_metadata"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_index(
        "idx_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False
    )
    op.create_index(
        "idx_audit_logs_event_type", "audit_logs", ["event_type"], unique=False
    )
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)
    op.create_index("idx_audit_logs_username", "audit_logs", ["username"], unique=False)
    op.create_index(
        "idx_audit_logs_resource_type", "audit_logs", ["resource_type"], unique=False
    )
    op.create_index(
        "idx_audit_logs_resource_id", "audit_logs", ["resource_id"], unique=False
    )
    op.create_index("idx_audit_logs_outcome", "audit_logs", ["outcome"], unique=False)
    op.create_index(
        "idx_audit_logs_details",
        "audit_logs",
        ["details"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "idx_audit_logs_event_type_timestamp",
        "audit_logs",
        ["event_type", "timestamp"],
        unique=False,
    )
    op.create_index(
        "idx_audit_logs_user_id_timestamp",
        "audit_logs",
        ["user_id", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    # Drop indices
    op.drop_index("idx_audit_logs_user_id_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_event_type_timestamp", table_name="audit_logs")
    op.drop_index("idx_audit_logs_details", table_name="audit_logs")
    op.drop_index("idx_audit_logs_outcome", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("idx_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("idx_audit_logs_username", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("idx_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("idx_audit_logs_timestamp", table_name="audit_logs")

    op.drop_index("idx_models_metadata", table_name="models")
    op.drop_index("idx_models_active", table_name="models")
    op.drop_index("idx_models_created_at", table_name="models")
    op.drop_index("idx_models_version", table_name="models")
    op.drop_index("idx_models_name", table_name="models")
    op.drop_index("idx_models_type", table_name="models")
    op.drop_index("idx_models_case_id", table_name="models")

    op.drop_index("idx_segments_is_deleted", table_name="segments")
    op.drop_index("idx_segments_metadata", table_name="segments")
    op.drop_index("idx_segments_properties", table_name="segments")
    op.drop_index("idx_segments_confidence", table_name="segments")
    op.drop_index("idx_segments_created_at", table_name="segments")
    op.drop_index("idx_segments_type", table_name="segments")
    op.drop_index("idx_segments_file_id", table_name="segments")
    op.drop_index("idx_segments_case_id", table_name="segments")

    op.drop_index("idx_jobs_priority_created_at", table_name="jobs")
    op.drop_index("idx_jobs_status_created_at", table_name="jobs")
    op.drop_index("idx_jobs_celery_task_id", table_name="jobs")
    op.drop_index("idx_jobs_created_at", table_name="jobs")
    op.drop_index("idx_jobs_priority", table_name="jobs")
    op.drop_index("idx_jobs_job_type", table_name="jobs")
    op.drop_index("idx_jobs_status", table_name="jobs")
    op.drop_index("idx_jobs_file_id", table_name="jobs")
    op.drop_index("idx_jobs_case_id", table_name="jobs")

    op.drop_index("idx_files_is_deleted", table_name="files")
    op.drop_index("idx_files_status_uploaded_at", table_name="files")
    op.drop_index("idx_files_metadata", table_name="files")
    op.drop_index("idx_files_tags", table_name="files")
    op.drop_index("idx_files_processed_at", table_name="files")
    op.drop_index("idx_files_uploaded_at", table_name="files")
    op.drop_index("idx_files_checksum", table_name="files")
    op.drop_index("idx_files_file_type", table_name="files")
    op.drop_index("idx_files_status", table_name="files")
    op.drop_index("idx_files_case_id", table_name="files")

    op.drop_index("idx_cases_is_deleted", table_name="cases")
    op.drop_index("idx_cases_status_created_at", table_name="cases")
    op.drop_index("idx_cases_metadata", table_name="cases")
    op.drop_index("idx_cases_tags", table_name="cases")
    op.drop_index("idx_cases_priority", table_name="cases")
    op.drop_index("idx_cases_created_at", table_name="cases")
    op.drop_index("idx_cases_status", table_name="cases")
    op.drop_index("idx_cases_patient_id", table_name="cases")
    op.drop_index("idx_cases_case_number", table_name="cases")

    op.drop_index("idx_users_created_at", table_name="users")
    op.drop_index("idx_users_role", table_name="users")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_index("idx_users_username", table_name="users")

    # Drop tables
    op.drop_table("audit_logs")
    op.drop_table("models")
    op.drop_table("segments")
    op.drop_table("jobs")
    op.drop_table("files")
    op.drop_table("cases")
    op.drop_table("users")

    # Enums will be dropped automatically when tables are dropped
