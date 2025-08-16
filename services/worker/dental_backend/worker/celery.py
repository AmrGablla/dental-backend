"""Celery configuration for the dental backend worker service."""

import logging
import signal
import sys
from typing import Any

from celery import Celery
from celery.signals import celeryd_after_setup, worker_process_init, worker_shutdown
from dental_backend_common.config import get_settings
from dental_backend_common.tracing import instrument_celery, setup_tracing

# Setup tracing first
setup_tracing()

# Get settings
settings = get_settings()
logger = logging.getLogger(__name__)

# Create Celery app with effective broker URL
celery = Celery(
    "dental_backend",
    broker=settings.worker.effective_broker_url,
    backend=settings.worker.result_backend,
    include=["dental_backend.worker.tasks"],
)

# Configure Celery with comprehensive settings
celery.conf.update(
    # Serialization
    task_serializer=settings.worker.task_serializer,
    result_serializer=settings.worker.result_serializer,
    accept_content=settings.worker.accept_content,
    # Time and timezone
    timezone=settings.worker.timezone,
    enable_utc=settings.worker.enable_utc,
    # Task configuration
    task_track_started=settings.worker.task_track_started,
    task_time_limit=settings.worker.task_time_limit,
    task_soft_time_limit=settings.worker.task_soft_time_limit,
    # Worker concurrency and performance
    worker_prefetch_multiplier=settings.worker.worker_prefetch_multiplier,
    task_acks_late=settings.worker.task_acks_late,
    worker_disable_rate_limits=settings.worker.worker_disable_rate_limits,
    # Graceful shutdown
    worker_shutdown_timeout=settings.worker.worker_shutdown_timeout,
    task_always_eager=settings.worker.task_always_eager,
    # Retry and backoff configuration
    task_default_retry_delay=settings.worker.task_default_retry_delay,
    task_max_retries=settings.worker.task_max_retries,
    task_retry_backoff=settings.worker.task_retry_backoff,
    task_retry_backoff_max=settings.worker.task_retry_backoff_max,
    # Dead letter queue configuration
    task_reject_on_worker_lost=settings.worker.task_reject_on_worker_lost,
    task_ignore_result=settings.worker.task_ignore_result,
    # Queue configuration
    task_default_queue=settings.worker.task_default_queue,
    task_default_exchange=settings.worker.task_default_exchange,
    task_default_routing_key=settings.worker.task_default_routing_key,
    # Result backend configuration
    result_expires=settings.worker.result_expires,
    result_persistent=settings.worker.result_persistent,
    # Monitoring and visibility
    worker_send_task_events=settings.worker.worker_send_task_events,
    task_send_sent_event=settings.worker.task_send_sent_event,
    # Security
    broker_connection_retry_on_startup=settings.worker.broker_connection_retry_on_startup,
    broker_connection_max_retries=settings.worker.broker_connection_max_retries,
)

# Optional: Configure result backend
if settings.worker.result_backend:
    celery.conf.result_backend = settings.worker.result_backend


@celeryd_after_setup.connect
def setup_worker_logging(sender: Any, instance: Any, **kwargs: Any) -> None:
    """Setup worker logging after initialization."""
    logger.info(f"Worker {sender} initialized successfully")
    logger.info(f"Broker URL: {settings.worker.effective_broker_url}")
    logger.info(f"Result Backend: {settings.worker.result_backend}")
    logger.info(f"Concurrency: {settings.worker.worker_concurrency}")

    # Instrument Celery for tracing
    instrument_celery()


@worker_process_init.connect
def init_worker_process(sender: Any, **kwargs: Any) -> None:
    """Initialize worker process."""
    logger.info(f"Worker process {sender} initialized")

    # Setup graceful shutdown signal handlers
    def signal_handler(signum: int, frame: Any) -> None:
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


@worker_shutdown.connect
def worker_shutdown_handler(sender: Any, **kwargs: Any) -> None:
    """Handle worker shutdown."""
    logger.info(f"Worker {sender} shutting down gracefully")


def setup_graceful_shutdown() -> None:
    """Setup graceful shutdown handlers for the main process."""

    def shutdown_handler(signum: int, frame: Any) -> None:
        logger.info("Received shutdown signal, stopping Celery worker")
        celery.control.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)


if __name__ == "__main__":
    setup_graceful_shutdown()
    celery.start()
