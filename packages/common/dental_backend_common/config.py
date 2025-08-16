"""Configuration management for the dental backend system."""

import os

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    url: str = Field(
        default="postgresql://dental_user:dental_password@localhost:5432/dental_backend",
        description="Database connection URL",
    )
    pool_size: int = Field(default=10, description="Database connection pool size")
    max_overflow: int = Field(
        default=20, description="Maximum database connection overflow"
    )
    echo: bool = Field(default=False, description="Enable SQL query logging")

    model_config = SettingsConfigDict(env_prefix="DATABASE_")


class RedisSettings(BaseSettings):
    """Redis configuration settings."""

    url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    max_connections: int = Field(default=10, description="Maximum Redis connections")

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class S3Settings(BaseSettings):
    """S3-compatible storage configuration settings."""

    endpoint_url: str = Field(
        default="http://localhost:9000", description="S3 endpoint URL"
    )
    access_key_id: str = Field(default="minioadmin", description="S3 access key ID")
    secret_access_key: str = Field(
        default="minioadmin", description="S3 secret access key"
    )
    bucket_name: str = Field(
        default="dental-scans", description="S3 bucket name for dental scans"
    )
    region_name: str = Field(default="us-east-1", description="S3 region name")
    use_ssl: bool = Field(default=False, description="Use SSL for S3 connections")

    model_config = SettingsConfigDict(env_prefix="S3_")


class SecuritySettings(BaseSettings):
    """Security configuration settings."""

    secret_key: str = Field(
        default="your-secret-key-here-change-in-production",
        description="Secret key for JWT token signing",
    )
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(
        default=30, description="JWT access token expiration time in minutes"
    )
    refresh_token_expire_days: int = Field(
        default=7, description="JWT refresh token expiration time in days"
    )

    # KMS and encryption settings
    kms_key_id: str | None = Field(
        default=None, description="AWS KMS key ID for encryption"
    )
    encryption_enabled: bool = Field(
        default=True, description="Enable encryption for sensitive data"
    )

    # TLS settings
    tls_cert_file: str | None = Field(
        default=None, description="TLS certificate file path"
    )
    tls_key_file: str | None = Field(
        default=None, description="TLS private key file path"
    )

    # Rate limiting
    rate_limit_requests: int = Field(
        default=100, description="Rate limit requests per minute"
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds"
    )

    model_config = SettingsConfigDict(env_prefix="SECURITY_")

    @validator("secret_key")
    def validate_secret_key(cls, v: str) -> str:
        """Validate that secret key is not the default value in production."""
        if v == "your-secret-key-here-change-in-production":
            if os.getenv("ENVIRONMENT") == "production":
                raise ValueError("Secret key must be changed in production")
        return v


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="json", description="Logging format (json or text)")
    file_path: str | None = Field(default=None, description="Log file path (optional)")

    model_config = SettingsConfigDict(env_prefix="LOG_")


class TracingSettings(BaseSettings):
    """OpenTelemetry tracing configuration settings."""

    enabled: bool = Field(default=True, description="Enable OpenTelemetry tracing")
    service_name: str = Field(
        default="dental-backend", description="Service name for traces"
    )
    service_version: str = Field(
        default="0.1.0", description="Service version for traces"
    )

    # OTLP exporter configuration
    otlp_endpoint: str = Field(
        default="http://localhost:4317", description="OTLP exporter endpoint"
    )
    otlp_protocol: str = Field(
        default="http/protobuf", description="OTLP protocol (http/protobuf or grpc)"
    )

    # Sampling configuration
    sampling_rate: float = Field(default=1.0, description="Sampling rate (0.0 to 1.0)")

    # Jaeger configuration (alternative to OTLP)
    jaeger_enabled: bool = Field(default=False, description="Enable Jaeger exporter")
    jaeger_endpoint: str = Field(
        default="http://localhost:14268/api/traces", description="Jaeger endpoint"
    )

    # Correlation ID configuration
    correlation_id_header: str = Field(
        default="X-Correlation-ID", description="HTTP header for correlation ID"
    )
    correlation_id_generate: bool = Field(
        default=True, description="Generate correlation ID if not provided"
    )

    model_config = SettingsConfigDict(env_prefix="TRACING_")


class APISettings(BaseSettings):
    """API configuration settings."""

    host: str = Field(default="0.0.0.0", description="API host address")
    port: int = Field(default=8000, description="API port number")
    workers: int = Field(default=1, description="Number of API workers")
    reload: bool = Field(default=True, description="Enable auto-reload in development")
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")

    model_config = SettingsConfigDict(env_prefix="API_")


class WorkerSettings(BaseSettings):
    """Background worker configuration settings."""

    # Broker configuration
    broker_url: str = Field(
        default="redis://localhost:6379/0", description="Celery broker URL"
    )
    result_backend: str = Field(
        default="redis://localhost:6379/0", description="Celery result backend URL"
    )

    # Alternative broker options
    use_rabbitmq: bool = Field(
        default=False, description="Use RabbitMQ instead of Redis as broker"
    )
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost:5672//",
        description="RabbitMQ connection URL",
    )

    # Serialization
    task_serializer: str = Field(default="json", description="Celery task serializer")
    result_serializer: str = Field(
        default="json", description="Celery result serializer"
    )
    accept_content: list[str] = Field(
        default=["json"], description="Celery accepted content types"
    )

    # Time and timezone
    timezone: str = Field(default="UTC", description="Celery timezone")
    enable_utc: bool = Field(default=True, description="Enable UTC in Celery")

    # Task configuration
    task_track_started: bool = Field(default=True, description="Track started tasks")
    task_time_limit: int = Field(
        default=30 * 60,
        description="Task time limit in seconds",  # 30 minutes
    )
    task_soft_time_limit: int = Field(
        default=25 * 60,
        description="Task soft time limit in seconds",  # 25 minutes
    )

    # Worker concurrency and performance
    worker_concurrency: int = Field(
        default=4, description="Number of worker processes/threads"
    )
    worker_prefetch_multiplier: int = Field(
        default=1, description="Worker prefetch multiplier"
    )
    worker_disable_rate_limits: bool = Field(
        default=True, description="Disable rate limits for workers"
    )
    task_acks_late: bool = Field(default=True, description="Acknowledge tasks late")

    # Graceful shutdown
    worker_shutdown_timeout: int = Field(
        default=30, description="Worker shutdown timeout in seconds"
    )
    task_always_eager: bool = Field(
        default=False, description="Execute tasks synchronously (for testing)"
    )

    # Retry and backoff configuration
    task_default_retry_delay: int = Field(
        default=60, description="Default retry delay in seconds"
    )
    task_max_retries: int = Field(
        default=3, description="Maximum number of retries per task"
    )
    task_retry_backoff: bool = Field(
        default=True, description="Enable exponential backoff for retries"
    )
    task_retry_backoff_max: int = Field(
        default=600, description="Maximum backoff delay in seconds"
    )

    # Dead letter queue configuration
    task_reject_on_worker_lost: bool = Field(
        default=True, description="Reject tasks when worker is lost"
    )
    task_ignore_result: bool = Field(default=False, description="Ignore task results")

    # Queue configuration
    task_default_queue: str = Field(default="default", description="Default queue name")
    task_default_exchange: str = Field(
        default="default", description="Default exchange name"
    )
    task_default_routing_key: str = Field(
        default="default", description="Default routing key"
    )

    # Result backend configuration
    result_expires: int = Field(
        default=3600, description="Result expiration time in seconds"
    )
    result_persistent: bool = Field(default=True, description="Make results persistent")

    # Monitoring and visibility
    worker_send_task_events: bool = Field(
        default=True, description="Send task events for monitoring"
    )
    task_send_sent_event: bool = Field(
        default=True, description="Send sent events for tasks"
    )

    # Security
    broker_connection_retry_on_startup: bool = Field(
        default=True, description="Retry broker connection on startup"
    )
    broker_connection_max_retries: int = Field(
        default=10, description="Maximum broker connection retries"
    )

    model_config = SettingsConfigDict(env_prefix="WORKER_")

    @property
    def effective_broker_url(self) -> str:
        """Get the effective broker URL based on configuration."""
        if self.use_rabbitmq:
            return self.rabbitmq_url
        return self.broker_url


class UploadSettings(BaseSettings):
    """File upload configuration settings."""

    presigned_url_expiry: int = Field(
        default=3600, description="Presigned URL expiration time in seconds"
    )
    max_concurrent_uploads: int = Field(
        default=5, description="Maximum concurrent uploads per user"
    )
    chunk_size_mb: int = Field(
        default=10, description="Chunk size for large file uploads in MB"
    )
    validation_timeout: int = Field(
        default=300, description="File validation timeout in seconds"
    )

    model_config = SettingsConfigDict(env_prefix="UPLOAD_")


class AntivirusSettings(BaseSettings):
    """Antivirus configuration settings."""

    enabled: bool = Field(default=True, description="Enable antivirus scanning")
    clamav_host: str = Field(default="localhost", description="ClamAV daemon host")
    clamav_port: int = Field(default=3310, description="ClamAV daemon port")
    scan_timeout: int = Field(
        default=30, description="Antivirus scan timeout in seconds"
    )
    max_file_size_scan_mb: int = Field(
        default=100, description="Maximum file size for antivirus scanning in MB"
    )

    model_config = SettingsConfigDict(env_prefix="ANTIVIRUS_")


class ValidationSettings(BaseSettings):
    """File validation configuration settings."""

    max_vertices: int = Field(
        default=1000000, description="Maximum vertices for 3D models"
    )
    max_faces: int = Field(default=2000000, description="Maximum faces for 3D models")
    max_file_size_mb: int = Field(default=100, description="Maximum file size in MB")
    allowed_mime_types: list[str] = Field(
        default=[
            "application/octet-stream",
            "model/stl",
            "model/ply",
            "model/obj",
            "model/gltf+json",
            "model/gltf-binary",
        ],
        description="Allowed MIME types for upload",
    )
    scan_3d_models: bool = Field(default=True, description="Enable 3D model validation")

    model_config = SettingsConfigDict(env_prefix="VALIDATION_")


class Settings(BaseSettings):
    """Main application settings."""

    # Environment
    environment: str = Field(
        default="development", description="Application environment"
    )
    debug: bool = Field(default=True, description="Enable debug mode")

    # Service configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    s3: S3Settings = Field(default_factory=S3Settings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    tracing: TracingSettings = Field(default_factory=TracingSettings)
    api: APISettings = Field(default_factory=APISettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    upload: UploadSettings = Field(default_factory=UploadSettings)
    antivirus: AntivirusSettings = Field(default_factory=AntivirusSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)

    # File processing
    max_file_size_mb: int = Field(default=100, description="Maximum file size in MB")
    allowed_file_types: list[str] = Field(
        default=["stl", "ply", "obj", "gltf", "glb"],
        description="Allowed file types for upload",
    )
    temp_dir: str = Field(
        default="/tmp/dental-backend",
        description="Temporary directory for file processing",
    )

    # HIPAA/GDPR compliance
    data_retention_days: int = Field(
        default=2555,
        description="Data retention period in days",  # 7 years for HIPAA
    )
    audit_log_enabled: bool = Field(default=True, description="Enable audit logging")
    encryption_enabled: bool = Field(default=True, description="Enable data encryption")

    # PII and PHI handling
    pii_encryption_enabled: bool = Field(
        default=True, description="Enable PII encryption"
    )
    phi_logging_enabled: bool = Field(
        default=False, description="Enable PHI logging (should be False in production)"
    )
    pseudonymization_enabled: bool = Field(
        default=True, description="Enable patient identifier pseudonymization"
    )

    # Data retention and deletion
    soft_delete_enabled: bool = Field(
        default=True, description="Enable soft delete for data retention"
    )
    data_purge_enabled: bool = Field(
        default=True, description="Enable automatic data purge"
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        allowed = ["development", "staging", "production", "testing"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v

    @validator("debug")
    def validate_debug(cls, v: bool, values: dict) -> bool:
        """Ensure debug is False in production."""
        if values.get("environment") == "production" and v:
            return False
        return v

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == "testing"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings
