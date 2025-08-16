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

    broker_url: str = Field(
        default="redis://localhost:6379/0", description="Celery broker URL"
    )
    result_backend: str = Field(
        default="redis://localhost:6379/0", description="Celery result backend URL"
    )
    task_serializer: str = Field(default="json", description="Celery task serializer")
    result_serializer: str = Field(
        default="json", description="Celery result serializer"
    )
    accept_content: list[str] = Field(
        default=["json"], description="Celery accepted content types"
    )
    timezone: str = Field(default="UTC", description="Celery timezone")
    enable_utc: bool = Field(default=True, description="Enable UTC in Celery")
    task_track_started: bool = Field(default=True, description="Track started tasks")
    task_time_limit: int = Field(
        default=30 * 60,
        description="Task time limit in seconds",  # 30 minutes
    )
    task_soft_time_limit: int = Field(
        default=25 * 60,
        description="Task soft time limit in seconds",  # 25 minutes
    )

    model_config = SettingsConfigDict(env_prefix="WORKER_")


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
    api: APISettings = Field(default_factory=APISettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)

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
