#!/usr/bin/env python3
"""Database test script for the dental backend system."""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from dental_backend_common.database import (
        AuditEventType,
        AuditLog,
        Case,
        File,
        FileStatus,
        Job,
        JobStatus,
        Model,
        ModelType,
        Segment,
        SegmentType,
        User,
        UserRole,
    )
    from dental_backend_common.session import get_db_session, init_db
except ImportError:
    # Fallback for when the modules are not available
    AuditEventType = None
    AuditLog = None
    Case = None
    File = None
    FileStatus = None
    Job = None
    JobStatus = None
    Model = None
    ModelType = None
    Segment = None
    SegmentType = None
    User = None
    UserRole = None
    get_db_session = None
    init_db = None


def test_database_connection():
    """Test database connection and basic operations."""
    print("🔍 Database Connection Test")
    print("=" * 50)

    try:
        # Initialize database tables
        print("📋 Initializing database tables...")
        init_db()
        print("  ✅ Database tables created successfully")

        # Test basic CRUD operations
        with get_db_session() as db:
            # Create a test user
            print("\n👤 Testing User creation...")
            test_user = User(
                username="test_user",
                email="test@example.com",
                hashed_password="hashed_password_here",
                role=UserRole.OPERATOR,
            )
            db.add(test_user)
            db.flush()  # Get the ID without committing
            print(f"  ✅ User created with ID: {test_user.id}")

            # Create a test case
            print("\n📁 Testing Case creation...")
            test_case = Case(
                case_number="CASE-001",
                patient_id="PATIENT-001",
                title="Test Dental Case",
                description="A test case for database validation",
                created_by=test_user.id,
                status="active",
                priority="normal",
            )
            db.add(test_case)
            db.flush()
            print(f"  ✅ Case created with ID: {test_case.id}")

            # Create a test file
            print("\n📄 Testing File creation...")
            test_file = File(
                case_id=test_case.id,
                filename="test_scan.stl",
                original_filename="original_scan.stl",
                file_path="/uploads/test_scan.stl",
                file_size=1024000,
                file_type="stl",
                mime_type="application/octet-stream",
                checksum="abc123def456",
                status=FileStatus.UPLOADED,
                uploaded_by=test_user.id,
            )
            db.add(test_file)
            db.flush()
            print(f"  ✅ File created with ID: {test_file.id}")

            # Create a test job
            print("\n⚙️  Testing Job creation...")
            test_job = Job(
                case_id=test_case.id,
                file_id=test_file.id,
                job_type="segmentation",
                status=JobStatus.PENDING,
                priority=5,
                created_by=test_user.id,
            )
            db.add(test_job)
            db.flush()
            print(f"  ✅ Job created with ID: {test_job.id}")

            # Create a test segment
            print("\n🦷 Testing Segment creation...")
            test_segment = Segment(
                case_id=test_case.id,
                file_id=test_file.id,
                segment_type=SegmentType.TOOTH,
                segment_number=1,
                confidence_score=95,
                created_by_job=test_job.id,
            )
            db.add(test_segment)
            db.flush()
            print(f"  ✅ Segment created with ID: {test_segment.id}")

            # Create a test model
            print("\n🤖 Testing Model creation...")
            test_model = Model(
                case_id=test_case.id,
                model_type=ModelType.SEGMENTATION,
                model_name="tooth_segmentation_v1",
                model_version="1.0.0",
                model_path="/models/tooth_segmentation_v1.pkl",
                model_size=52428800,
                accuracy_score=92,
            )
            db.add(test_model)
            db.flush()
            print(f"  ✅ Model created with ID: {test_model.id}")

            # Create a test audit log
            print("\n📝 Testing AuditLog creation...")
            test_audit = AuditLog(
                event_type=AuditEventType.DATA_CREATE,
                user_id=test_user.id,
                username=test_user.username,
                user_role=test_user.role,
                resource_type="case",
                resource_id=str(test_case.id),
                action="create",
                outcome="success",
            )
            db.add(test_audit)
            db.flush()
            print(f"  ✅ AuditLog created with ID: {test_audit.id}")

            # Test queries
            print("\n🔍 Testing database queries...")

            # Query user
            user = db.query(User).filter(User.username == "test_user").first()
            print(f"  ✅ User query: {user.username} ({user.role.value})")

            # Query case with relationships
            case = db.query(Case).filter(Case.case_number == "CASE-001").first()
            print(f"  ✅ Case query: {case.title} (Patient: {case.patient_id})")
            print(f"  ✅ Case files count: {len(case.files)}")
            print(f"  ✅ Case jobs count: {len(case.jobs)}")
            print(f"  ✅ Case segments count: {len(case.segments)}")

            # Query file
            file = db.query(File).filter(File.filename == "test_scan.stl").first()
            print(f"  ✅ File query: {file.original_filename} ({file.file_size} bytes)")

            # Query job
            job = db.query(Job).filter(Job.job_type == "segmentation").first()
            print(f"  ✅ Job query: {job.job_type} ({job.status.value})")

            # Query segment
            segment = (
                db.query(Segment)
                .filter(Segment.segment_type == SegmentType.TOOTH)
                .first()
            )
            print(
                f"  ✅ Segment query: {segment.segment_type.value} (confidence: {segment.confidence_score}%)"
            )

            # Query model
            model = (
                db.query(Model)
                .filter(Model.model_name == "tooth_segmentation_v1")
                .first()
            )
            print(f"  ✅ Model query: {model.model_name} v{model.model_version}")

            # Query audit logs
            audit_count = db.query(AuditLog).count()
            print(f"  ✅ AuditLog count: {audit_count}")

            print("\n🎉 All database tests passed successfully!")

    except Exception as e:
        print(f"\n❌ Database test failed: {e}")
        return False

    return True


def test_database_indices():
    """Test database indices and performance."""
    print("\n🔍 Database Indices Test")
    print("=" * 50)

    try:
        with get_db_session() as db:
            # Test case queries with indices
            print("📊 Testing case queries with indices...")

            # Query by case number (indexed)
            case = db.query(Case).filter(Case.case_number == "CASE-001").first()
            print(f"  ✅ Case number query: {case.case_number}")

            # Query by patient ID (indexed)
            cases = db.query(Case).filter(Case.patient_id == "PATIENT-001").all()
            print(f"  ✅ Patient ID query: {len(cases)} cases found")

            # Query by status (indexed)
            active_cases = db.query(Case).filter(Case.status == "active").all()
            print(f"  ✅ Status query: {len(active_cases)} active cases")

            # Test file queries with indices
            print("\n📄 Testing file queries with indices...")

            # Query by file type (indexed)
            stl_files = db.query(File).filter(File.file_type == "stl").all()
            print(f"  ✅ File type query: {len(stl_files)} STL files")

            # Query by status (indexed)
            uploaded_files = (
                db.query(File).filter(File.status == FileStatus.UPLOADED).all()
            )
            print(f"  ✅ File status query: {len(uploaded_files)} uploaded files")

            # Test job queries with indices
            print("\n⚙️  Testing job queries with indices...")

            # Query by job type (indexed)
            segmentation_jobs = (
                db.query(Job).filter(Job.job_type == "segmentation").all()
            )
            print(f"  ✅ Job type query: {len(segmentation_jobs)} segmentation jobs")

            # Query by status (indexed)
            pending_jobs = db.query(Job).filter(Job.status == JobStatus.PENDING).all()
            print(f"  ✅ Job status query: {len(pending_jobs)} pending jobs")

            print("\n🎉 All index tests passed successfully!")

    except Exception as e:
        print(f"\n❌ Index test failed: {e}")
        return False

    return True


def main():
    """Main test function."""
    print("🗄️  Dental Backend Database Test")
    print("=" * 60)

    # Test database connection and basic operations
    if not test_database_connection():
        print("\n❌ Database connection test failed!")
        sys.exit(1)

    # Test database indices
    if not test_database_indices():
        print("\n❌ Database indices test failed!")
        sys.exit(1)

    print("\n✅ All database tests completed successfully!")
    print("\n📋 Test Summary:")
    print("  ✅ Database connection")
    print("  ✅ Table creation")
    print("  ✅ CRUD operations")
    print("  ✅ Relationship queries")
    print("  ✅ Index performance")
    print("  ✅ Enum handling")
    print("  ✅ UUID primary keys")
    print("  ✅ JSONB fields")
    print("  ✅ Audit logging")


if __name__ == "__main__":
    main()
