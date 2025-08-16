"""Main FastAPI application for the dental backend API service."""

from dental_backend_common.config import get_settings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "dental_backend.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.reload,
        workers=settings.api.workers,
    )
