"""OpenTelemetry tracing configuration for the dental backend system."""

import logging
import uuid
from contextvars import ContextVar
from typing import Any, Optional

from dental_backend_common.config import get_settings
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio

logger = logging.getLogger(__name__)

# Context variable for correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in context."""
    correlation_id_var.set(correlation_id)


def generate_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())


def setup_tracing() -> None:
    """Setup OpenTelemetry tracing with configuration from settings."""
    settings = get_settings()

    if not settings.tracing.enabled:
        logger.info("Tracing is disabled")
        return

    try:
        # Create resource with service information
        resource = Resource.create(
            {
                "service.name": settings.tracing.service_name,
                "service.version": settings.tracing.service_version,
                "environment": settings.environment,
            }
        )

        # Create tracer provider with sampling
        sampler = ParentBasedTraceIdRatio(settings.tracing.sampling_rate)
        provider = TracerProvider(resource=resource, sampler=sampler)

        # Setup exporters based on configuration
        if settings.tracing.jaeger_enabled:
            # Jaeger exporter
            jaeger_exporter = JaegerExporter(
                collector_endpoint=settings.tracing.jaeger_endpoint,
            )
            provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
            logger.info(
                f"Jaeger exporter configured: {settings.tracing.jaeger_endpoint}"
            )
        else:
            # OTLP exporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.tracing.otlp_endpoint,
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP exporter configured: {settings.tracing.otlp_endpoint}")

        # Set the global tracer provider
        trace.set_tracer_provider(provider)

        logger.info("OpenTelemetry tracing setup completed")

    except Exception as e:
        logger.error(f"Failed to setup tracing: {e}")


def instrument_fastapi(app: Any) -> None:
    """Instrument FastAPI application with OpenTelemetry."""
    settings = get_settings()

    if not settings.tracing.enabled:
        return

    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")


def instrument_celery() -> None:
    """Instrument Celery with OpenTelemetry."""
    settings = get_settings()

    if not settings.tracing.enabled:
        return

    try:
        CeleryInstrumentor().instrument()
        logger.info("Celery instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument Celery: {e}")


def instrument_sqlalchemy(engine: Any) -> None:
    """Instrument SQLAlchemy engine with OpenTelemetry."""
    settings = get_settings()

    if not settings.tracing.enabled:
        return

    try:
        SQLAlchemyInstrumentor().instrument(engine=engine)
        logger.info("SQLAlchemy instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {e}")


def instrument_redis() -> None:
    """Instrument Redis with OpenTelemetry."""
    settings = get_settings()

    if not settings.tracing.enabled:
        return

    try:
        RedisInstrumentor().instrument()
        logger.info("Redis instrumented with OpenTelemetry")
    except Exception as e:
        logger.error(f"Failed to instrument Redis: {e}")


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance with the given name."""
    return trace.get_tracer(name)


def create_span(name: str, attributes: Optional[dict[str, Any]] = None) -> trace.Span:
    """Create a new span with the given name and attributes."""
    tracer = get_tracer("dental_backend")
    span = tracer.start_span(name, attributes=attributes or {})

    # Add correlation ID to span if available
    correlation_id = get_correlation_id()
    if correlation_id:
        span.set_attribute("correlation.id", correlation_id)

    return span


def add_correlation_id_to_span(span: trace.Span) -> None:
    """Add correlation ID to span if available."""
    correlation_id = get_correlation_id()
    if correlation_id:
        span.set_attribute("correlation.id", correlation_id)


class TracingMiddleware:
    """Middleware for handling correlation IDs in FastAPI."""

    def __init__(self, app: Any):
        self.app = app
        self.settings = get_settings()

    async def __call__(self, scope: dict, receive: Any, send: Any):
        # Extract correlation ID from headers
        headers = dict(scope.get("headers", []))
        correlation_id = None

        # Look for correlation ID in headers
        for header_name, header_value in headers:
            if (
                header_name.decode().lower()
                == self.settings.tracing.correlation_id_header.lower()
            ):
                correlation_id = header_value.decode()
                break

        # Generate correlation ID if not provided and generation is enabled
        if not correlation_id and self.settings.tracing.correlation_id_generate:
            correlation_id = generate_correlation_id()

        # Set correlation ID in context
        if correlation_id:
            set_correlation_id(correlation_id)

        # Add correlation ID to scope for logging
        scope["correlation_id"] = correlation_id

        await self.app(scope, receive, send)


def trace_task(task_name: str):
    """Decorator for tracing Celery tasks."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            settings = get_settings()
            if not settings.tracing.enabled:
                return func(*args, **kwargs)

            tracer = get_tracer("dental_backend.worker")

            # Extract correlation ID from task kwargs if available
            correlation_id = kwargs.get("correlation_id")
            if correlation_id:
                set_correlation_id(correlation_id)

            with tracer.start_as_current_span(
                f"task.{task_name}",
                attributes={
                    "task.name": task_name,
                    "correlation.id": correlation_id,
                },
            ) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("task.success", True)
                    return result
                except Exception as e:
                    span.set_attribute("task.success", False)
                    span.set_attribute("task.error", str(e))
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator
