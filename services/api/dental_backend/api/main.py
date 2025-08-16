"""Main FastAPI application for the dental backend API service."""

import logging
from datetime import datetime

from dental_backend_common.auth import User
from dental_backend_common.config import get_settings
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dental_backend.api.auth import router as auth_router
from dental_backend.api.cases import router as cases_router
from dental_backend.api.compliance import router as compliance_router
from dental_backend.api.dependencies import (
    require_admin,
    require_operator,
    require_service,
)
from dental_backend.api.files import router as files_router
from dental_backend.api.jobs import router as jobs_router
from dental_backend.api.segments import router as segments_router
from dental_backend.api.uploads import router as uploads_router

logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="Dental Backend API",
    description="A headless backend system for processing and analyzing 3D dental scan data",
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add security middleware (simplified for now)
# app.add_middleware(SecurityHeadersMiddleware)
# app.add_middleware(AuditMiddleware)
# app.middleware("http")(rate_limiter)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(compliance_router)
app.include_router(uploads_router)
app.include_router(cases_router)
app.include_router(files_router)
app.include_router(jobs_router)
app.include_router(segments_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": str(request.url),
        },
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Dental Backend API",
        "version": "0.1.0",
        "environment": settings.environment,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker health checks."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "debug": settings.debug,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Kubernetes readiness probes."""
    try:
        # Check database connection
        from dental_backend_common.session import check_db_connection

        db_healthy = check_db_connection()

        # Check Redis connection
        import redis

        r = redis.from_url(settings.redis.url)
        r.ping()
        redis_healthy = True
    except Exception as e:
        db_healthy = False
        redis_healthy = False
        logger.error(f"Readiness check failed: {e}")

    is_ready = db_healthy and redis_healthy

    return {
        "status": "ready" if is_ready else "not_ready",
        "database": "healthy" if db_healthy else "unhealthy",
        "redis": "healthy" if redis_healthy else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/version")
async def version_info():
    """Version information endpoint."""
    return {
        "version": "0.1.0",
        "api_version": "v1",
        "build_date": "2024-01-01T00:00:00Z",
        "git_commit": "development",
        "environment": settings.environment,
    }


@app.get("/config")
async def get_config():
    """Get current configuration (development only)."""
    if not settings.debug:
        return {"error": "Configuration endpoint not available in production"}

    return {
        "environment": settings.environment,
        "debug": settings.debug,
        "database": {
            "url": settings.database.url.split("@")[-1]
            if "@" in settings.database.url
            else "***",
            "pool_size": settings.database.pool_size,
        },
        "redis": {
            "url": settings.redis.url.split("@")[-1]
            if "@" in settings.redis.url
            else "***",
        },
        "s3": {
            "endpoint_url": settings.s3.endpoint_url,
            "bucket_name": settings.s3.bucket_name,
        },
        "api": {
            "host": settings.api.host,
            "port": settings.api.port,
            "workers": settings.api.workers,
        },
    }


@app.get("/protected/admin")
async def admin_only_endpoint(current_user: User = Depends(require_admin)):
    """Admin-only endpoint for testing RBAC."""
    return {
        "message": "Admin access granted",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role.value,
        },
    }


@app.get("/protected/operator")
async def operator_endpoint(current_user: User = Depends(require_operator)):
    """Operator endpoint for testing RBAC."""
    return {
        "message": "Operator access granted",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role.value,
        },
    }


@app.get("/protected/service")
async def service_endpoint(current_user: User = Depends(require_service)):
    """Service endpoint for testing RBAC."""
    return {
        "message": "Service access granted",
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "role": current_user.role.value,
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "dental_backend.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        workers=settings.api.workers,
    )
