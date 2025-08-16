"""Celery tasks for the dental backend worker service."""

import time
from typing import Any, Optional
from uuid import UUID

from celery import Task
from celery.utils.log import get_task_logger
from dental_backend_common.config import get_settings
from dental_backend_common.database import (
    Job,
    JobStatus,
    update_job_progress,
)
from dental_backend_common.geometry import (
    MeshFormat,
    MeshProcessor,
    ValidationLevel,
    run_round_trip_tests,
)
from dental_backend_common.session import SessionLocal
from dental_backend_common.tracing import trace_task

from dental_backend.worker.celery import celery

# Get settings
settings = get_settings()
logger = get_task_logger(__name__)


class BaseTask(Task):
    """Base task class with common functionality."""

    abstract = True

    def __init__(self) -> None:
        self.db: Optional[SessionLocal] = None

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Setup database session for task execution."""
        self.db = SessionLocal()
        try:
            return super().__call__(*args, **kwargs)
        finally:
            if self.db:
                self.db.close()

    def on_retry(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        """Handle task retry."""
        logger.warning(f"Task {task_id} retrying due to: {exc}")
        if self.db:
            try:
                # Update job retry count and status
                job = self.db.query(Job).filter(Job.celery_task_id == task_id).first()
                if job:
                    job.retry_count += 1
                    job.status = JobStatus.PENDING
                    job.error_message = str(exc)
                    self.db.commit()
                    logger.info(
                        f"Updated job {job.id} retry count to {job.retry_count}"
                    )
            except Exception as e:
                logger.error(f"Failed to update job retry count: {e}")
                self.db.rollback()

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, traceback: Any
    ) -> None:
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
        if self.db:
            try:
                # Update job status to failed
                job = self.db.query(Job).filter(Job.celery_task_id == task_id).first()
                if job:
                    job.status = JobStatus.FAILED
                    job.error_message = str(exc)
                    job.completed_at = time.time()
                    self.db.commit()
                    logger.info(f"Updated job {job.id} status to FAILED")
            except Exception as e:
                logger.error(f"Failed to update job failure status: {e}")
                self.db.rollback()

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")
        if self.db:
            try:
                # Update job status to completed
                job = self.db.query(Job).filter(Job.celery_task_id == task_id).first()
                if job:
                    job.status = JobStatus.COMPLETED
                    job.result = retval
                    job.completed_at = time.time()
                    job.progress = 100
                    self.db.commit()
                    logger.info(f"Updated job {job.id} status to COMPLETED")
            except Exception as e:
                logger.error(f"Failed to update job success status: {e}")
                self.db.rollback()


@celery.task(
    bind=True, base=BaseTask, name="dental_backend.worker.tasks.health_check_task"
)
@trace_task("health_check")
def health_check_task(self) -> dict[str, Any]:
    """Health check task for testing worker functionality."""
    task_id = self.request.id
    correlation_id = self.request.correlation_id or task_id

    logger.info(
        f"Starting health check task {task_id} with correlation ID {correlation_id}"
    )

    # Update job status to processing
    if self.db:
        try:
            job = self.db.query(Job).filter(Job.celery_task_id == task_id).first()
            if job:
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                job.progress = 10
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            self.db.rollback()

    # Simulate some work
    time.sleep(1)

    # Update progress
    if self.db:
        try:
            update_job_progress(self.db, task_id, 50)
        except Exception as e:
            logger.error(f"Failed to update progress: {e}")

    time.sleep(1)

    result = {
        "task_id": task_id,
        "correlation_id": correlation_id,
        "status": "completed",
        "message": "Worker is healthy",
        "environment": settings.environment,
        "timestamp": time.time(),
    }

    logger.info(f"Health check task {task_id} completed successfully")
    return result


@celery.task(
    bind=True,
    base=BaseTask,
    name="dental_backend.worker.tasks.process_mesh_file",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
@trace_task("process_mesh_file")
def process_mesh_file(
    self, file_path: str, file_type: str, job_id: Optional[str] = None
) -> dict[str, Any]:
    """Process a 3D mesh file with retry logic and progress tracking."""
    task_id = self.request.id
    correlation_id = self.request.correlation_id or task_id

    logger.info(f"Starting mesh processing task {task_id} for file {file_path}")

    # Update job status to processing
    if self.db and job_id:
        try:
            job = self.db.query(Job).filter(Job.id == UUID(job_id)).first()
            if job:
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                job.progress = 10
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            self.db.rollback()

    # Validate file type
    if file_type.lower() not in settings.allowed_file_types:
        error_msg = f"Unsupported file type: {file_type}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Simulate processing steps with progress updates
    processing_steps = [
        ("Validating file", 20),
        ("Loading mesh data", 40),
        ("Processing geometry", 60),
        ("Optimizing mesh", 80),
        ("Saving results", 90),
    ]

    for step_name, progress in processing_steps:
        logger.info(f"Processing step: {step_name}")
        time.sleep(0.5)  # Simulate work

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, progress)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

    result = {
        "task_id": task_id,
        "correlation_id": correlation_id,
        "status": "completed",
        "file_path": file_path,
        "file_type": file_type,
        "message": f"Processed {file_type} file successfully",
        "timestamp": time.time(),
        "processing_metadata": {
            "vertices_processed": 1000,
            "faces_processed": 2000,
            "processing_time_seconds": 2.5,
        },
    }

    logger.info(f"Mesh processing task {task_id} completed successfully")
    return result


@celery.task(
    bind=True,
    base=BaseTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
@trace_task("analyze_mesh_quality")
def analyze_mesh_quality(
    self, mesh_data: dict[str, Any], job_id: Optional[str] = None
) -> dict[str, Any]:
    """Analyze mesh quality with retry logic and progress tracking."""
    task_id = self.request.id
    correlation_id = self.request.correlation_id or task_id

    logger.info(f"Starting mesh quality analysis task {task_id}")

    # Update job status to processing
    if self.db and job_id:
        try:
            job = self.db.query(Job).filter(Job.id == UUID(job_id)).first()
            if job:
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                job.progress = 10
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            self.db.rollback()

    # Simulate analysis steps
    analysis_steps = [
        ("Loading mesh data", 20),
        ("Calculating vertex density", 40),
        ("Analyzing face quality", 60),
        ("Detecting defects", 80),
        ("Generating report", 90),
    ]

    for step_name, progress in analysis_steps:
        logger.info(f"Analysis step: {step_name}")
        time.sleep(0.6)  # Simulate work

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, progress)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

    # Mock analysis results
    analysis_results = {
        "vertices": 1000,
        "faces": 2000,
        "quality_score": 0.85,
        "defects_found": 2,
        "recommendations": ["Consider smoothing", "Check for holes"],
        "analysis_metadata": {
            "processing_time_seconds": 3.0,
            "algorithm_version": "1.0.0",
        },
    }

    result = {
        "task_id": task_id,
        "correlation_id": correlation_id,
        "status": "completed",
        "mesh_data": mesh_data,
        "analysis_results": analysis_results,
        "timestamp": time.time(),
    }

    logger.info(f"Mesh quality analysis task {task_id} completed successfully")
    return result


@celery.task(
    bind=True,
    base=BaseTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
@trace_task("convert_mesh_format")
def convert_mesh_format(
    self,
    input_path: str,
    output_format: str,
    output_path: str,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Convert mesh between formats with retry logic and progress tracking."""
    task_id = self.request.id
    correlation_id = self.request.correlation_id or task_id

    logger.info(f"Starting mesh format conversion task {task_id}")

    # Update job status to processing
    if self.db and job_id:
        try:
            job = self.db.query(Job).filter(Job.id == UUID(job_id)).first()
            if job:
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                job.progress = 10
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            self.db.rollback()

    # Validate output format
    if output_format.lower() not in settings.allowed_file_types:
        error_msg = f"Unsupported output format: {output_format}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Simulate conversion steps
    conversion_steps = [
        ("Reading input file", 20),
        ("Parsing mesh data", 40),
        ("Converting format", 60),
        ("Optimizing output", 80),
        ("Writing output file", 90),
    ]

    for step_name, progress in conversion_steps:
        logger.info(f"Conversion step: {step_name}")
        time.sleep(1.0)  # Simulate work

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, progress)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

    result = {
        "task_id": task_id,
        "correlation_id": correlation_id,
        "status": "completed",
        "input_path": input_path,
        "output_format": output_format,
        "output_path": output_path,
        "message": f"Converted to {output_format} format successfully",
        "timestamp": time.time(),
        "conversion_metadata": {
            "processing_time_seconds": 5.0,
            "input_size_bytes": 1024000,
            "output_size_bytes": 512000,
            "compression_ratio": 0.5,
        },
    }

    logger.info(f"Mesh format conversion task {task_id} completed successfully")
    return result


@celery.task(
    bind=True,
    base=BaseTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
@trace_task("segment_dental_scan")
def segment_dental_scan(
    self, file_id: str, case_id: str, job_id: Optional[str] = None
) -> dict[str, Any]:
    """Segment dental scan with retry logic and progress tracking."""
    task_id = self.request.id
    correlation_id = self.request.correlation_id or task_id

    logger.info(f"Starting dental scan segmentation task {task_id}")

    # Update job status to processing
    if self.db and job_id:
        try:
            job = self.db.query(Job).filter(Job.id == UUID(job_id)).first()
            if job:
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                job.progress = 10
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            self.db.rollback()

    # Simulate segmentation steps
    segmentation_steps = [
        ("Loading scan data", 15),
        ("Preprocessing mesh", 30),
        ("Detecting teeth", 50),
        ("Segmenting gums", 70),
        ("Identifying jaw structure", 85),
        ("Generating segments", 95),
    ]

    for step_name, progress in segmentation_steps:
        logger.info(f"Segmentation step: {step_name}")
        time.sleep(0.8)  # Simulate work

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, progress)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

    # Mock segmentation results
    segments = [
        {"type": "tooth", "number": 1, "confidence": 0.95},
        {"type": "tooth", "number": 2, "confidence": 0.92},
        {"type": "gums", "confidence": 0.88},
        {"type": "jaw", "confidence": 0.90},
    ]

    result = {
        "task_id": task_id,
        "correlation_id": correlation_id,
        "status": "completed",
        "file_id": file_id,
        "case_id": case_id,
        "segments": segments,
        "message": f"Segmented {len(segments)} anatomical parts",
        "timestamp": time.time(),
        "segmentation_metadata": {
            "processing_time_seconds": 4.8,
            "segments_found": len(segments),
            "average_confidence": 0.91,
            "algorithm_version": "2.1.0",
        },
    }

    logger.info(f"Dental scan segmentation task {task_id} completed successfully")
    return result


@celery.task(
    bind=True,
    base=BaseTask,
    name="dental_backend.worker.tasks.process_mesh_3d",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
@trace_task("process_mesh_3d")
def process_mesh_3d(
    self,
    input_path: str,
    output_path: str,
    validate: bool = True,
    normalize: bool = False,
    units: Optional[str] = None,
    output_format: Optional[str] = None,
    validation_level: str = "standard",
    memory_limit_mb: int = 1024,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Process 3D mesh with validation and normalization."""
    task_id = self.request.id
    correlation_id = self.request.correlation_id or task_id

    logger.info(f"Starting 3D mesh processing task {task_id} for {input_path}")

    # Update job status to processing
    if self.db and job_id:
        try:
            job = self.db.query(Job).filter(Job.id == UUID(job_id)).first()
            if job:
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                job.progress = 10
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            self.db.rollback()

    try:
        # Create mesh processor
        processor = MeshProcessor(
            memory_limit_mb=memory_limit_mb,
            validation_level=ValidationLevel(validation_level),
        )

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, 20)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

        # Process mesh
        validation_report = processor.process_mesh(
            input_path=input_path,
            output_path=output_path,
            validate=validate,
            normalize=normalize,
            units=units,
            output_format=MeshFormat(output_format) if output_format else None,
        )

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, 90)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

        result = {
            "task_id": task_id,
            "correlation_id": correlation_id,
            "status": "completed",
            "input_path": input_path,
            "output_path": output_path,
            "validation_report": {
                "is_valid": validation_report.is_valid,
                "issues": validation_report.issues,
                "warnings": validation_report.warnings,
                "repairs_applied": validation_report.repairs_applied,
                "mesh_info": {
                    "vertices": validation_report.mesh_info.vertices,
                    "faces": validation_report.mesh_info.faces,
                    "volume": validation_report.mesh_info.volume,
                    "surface_area": validation_report.mesh_info.surface_area,
                    "is_watertight": validation_report.mesh_info.is_watertight,
                    "is_manifold": validation_report.mesh_info.is_manifold,
                },
            },
            "timestamp": time.time(),
        }

        logger.info(f"3D mesh processing task {task_id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"3D mesh processing task {task_id} failed: {e}")
        raise


@celery.task(
    bind=True,
    base=BaseTask,
    name="dental_backend.worker.tasks.validate_mesh",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
@trace_task("validate_mesh")
def validate_mesh(
    self,
    file_path: str,
    validation_level: str = "standard",
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Validate a 3D mesh and return detailed report."""
    task_id = self.request.id
    correlation_id = self.request.correlation_id or task_id

    logger.info(f"Starting mesh validation task {task_id} for {file_path}")

    # Update job status to processing
    if self.db and job_id:
        try:
            job = self.db.query(Job).filter(Job.id == UUID(job_id)).first()
            if job:
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                job.progress = 10
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            self.db.rollback()

    try:
        # Create mesh processor
        processor = MeshProcessor(validation_level=ValidationLevel(validation_level))

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, 30)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

        # Load and validate mesh
        mesh, validation_report = processor.load_mesh(file_path, validate=True)

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, 90)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

        result = {
            "task_id": task_id,
            "correlation_id": correlation_id,
            "status": "completed",
            "file_path": file_path,
            "validation_report": {
                "is_valid": validation_report.is_valid,
                "issues": validation_report.issues,
                "warnings": validation_report.warnings,
                "repairs_applied": validation_report.repairs_applied,
                "validation_level": validation_report.validation_level.value,
                "mesh_info": {
                    "vertices": validation_report.mesh_info.vertices,
                    "faces": validation_report.mesh_info.faces,
                    "volume": validation_report.mesh_info.volume,
                    "surface_area": validation_report.mesh_info.surface_area,
                    "is_watertight": validation_report.mesh_info.is_watertight,
                    "is_manifold": validation_report.mesh_info.is_manifold,
                    "has_normals": validation_report.mesh_info.has_normals,
                },
                "validation_time": validation_report.validation_time,
            },
            "timestamp": time.time(),
        }

        logger.info(f"Mesh validation task {task_id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"Mesh validation task {task_id} failed: {e}")
        raise


@celery.task(
    bind=True,
    base=BaseTask,
    name="dental_backend.worker.tasks.test_mesh_formats",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
@trace_task("test_mesh_formats")
def test_mesh_formats(
    self,
    memory_limit_mb: int = 1024,
    job_id: Optional[str] = None,
) -> dict[str, Any]:
    """Test round-trip loading and saving for all supported mesh formats."""
    task_id = self.request.id
    correlation_id = self.request.correlation_id or task_id

    logger.info(f"Starting mesh format testing task {task_id}")

    # Update job status to processing
    if self.db and job_id:
        try:
            job = self.db.query(Job).filter(Job.id == UUID(job_id)).first()
            if job:
                job.status = JobStatus.PROCESSING
                job.started_at = time.time()
                job.progress = 10
                self.db.commit()
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            self.db.rollback()

    try:
        # Create mesh processor
        processor = MeshProcessor(memory_limit_mb=memory_limit_mb)

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, 30)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

        # Run round-trip tests
        test_results = run_round_trip_tests(processor)

        # Update progress
        if self.db and job_id:
            try:
                update_job_progress(self.db, job_id, 90)
            except Exception as e:
                logger.error(f"Failed to update progress: {e}")

        result = {
            "task_id": task_id,
            "correlation_id": correlation_id,
            "status": "completed",
            "test_results": {
                format.value: success for format, success in test_results.items()
            },
            "supported_formats": [
                format.value for format in processor.get_supported_formats()
            ],
            "timestamp": time.time(),
        }

        logger.info(f"Mesh format testing task {task_id} completed successfully")
        return result

    except Exception as e:
        logger.error(f"Mesh format testing task {task_id} failed: {e}")
        raise
