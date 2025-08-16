"""Main FastAPI application for the dental backend API service."""

from dental_backend_common.auth import User
from dental_backend_common.config import get_settings
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dental_backend.api.auth import router as auth_router
from dental_backend.api.compliance import router as compliance_router
from dental_backend.api.dependencies import (
    require_admin,
    require_operator,
    require_service,
)
from dental_backend.api.uploads import router as uploads_router

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
