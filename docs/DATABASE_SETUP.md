# Database Setup Guide

## Overview

The dental backend uses PostgreSQL with Alembic for database migrations. The schema includes comprehensive tables for managing dental cases, files, jobs, segments, models, and audit logs with full HIPAA/GDPR compliance.

## Database Schema

### Core Tables

1. **users** - User authentication and authorization
2. **cases** - Patient case management
3. **files** - Dental scan file management
4. **jobs** - Background task processing
5. **segments** - Anatomical part segmentation
6. **models** - ML model management
7. **audit_logs** - Compliance and security auditing

### Key Features

- **UUID Primary Keys** - For distributed systems
- **JSONB Fields** - For flexible metadata storage
- **GIN Indices** - For efficient JSONB queries
- **Soft Deletes** - For data recovery and compliance
- **Comprehensive Audit Logging** - For HIPAA/GDPR compliance
- **Role-Based Access Control** - For security

## Setup Instructions

### 1. Prerequisites

- PostgreSQL 13+ with PostGIS extension
- Python 3.11+ with virtual environment
- Docker (optional, for local development)

### 2. Database Connection

The system uses the following default connection:
```
postgresql://dental_user:dental_password@localhost:5432/dental_backend
```

You can override this using environment variables:
```bash
export DATABASE_URL="postgresql://user:password@host:port/database"
```

### 3. Using Docker (Recommended for Development)

```bash
# Start the database
cd infrastructure
docker-compose up -d postgres

# Wait for database to be ready
sleep 10
```

### 4. Manual PostgreSQL Setup

```bash
# Create database and user
sudo -u postgres psql

CREATE DATABASE dental_backend;
CREATE USER dental_user WITH PASSWORD 'dental_password';
GRANT ALL PRIVILEGES ON DATABASE dental_backend TO dental_user;
\q
```

### 5. Running Migrations

```bash
# Build packages first
make build

# Run migrations
make migrate

# Or manually
alembic upgrade head
```

### 6. Database Commands

```bash
# View migration history
make db-show

# Create new migration
make db-revision message="Description of changes"

# Rollback last migration
make db-rollback

# Reset database (drop all and recreate)
make resetdb

# Check current migration
make db-current
```

## Testing the Database

### 1. Run Database Tests

```bash
# Test database connection and operations
python scripts/test_database.py
```

### 2. Test API with Database

```bash
# Start the API
make run

# Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/config
```

## Schema Details

### Users Table
- **Primary Key**: `id` (UUID)
- **Unique Constraints**: `username`, `email`
- **Roles**: `admin`, `operator`, `service`
- **Audit Fields**: `created_at`, `updated_at`, `last_login`

### Cases Table
- **Primary Key**: `id` (UUID)
- **Unique Constraints**: `case_number`
- **Foreign Keys**: `created_by` → `users.id`
- **Indices**: `case_number`, `patient_id`, `status`, `created_at`
- **JSONB**: `tags`, `case_metadata`

### Files Table
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `case_id` → `cases.id`, `uploaded_by` → `users.id`
- **Indices**: `case_id`, `status`, `file_type`, `checksum`
- **JSONB**: `tags`, `file_metadata`, `processing_metadata`

### Jobs Table
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `case_id` → `cases.id`, `file_id` → `files.id`, `created_by` → `users.id`
- **Status**: `pending`, `processing`, `completed`, `failed`, `cancelled`
- **Indices**: `case_id`, `status`, `job_type`, `priority`

### Segments Table
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `case_id` → `cases.id`, `file_id` → `files.id`, `created_by_job` → `jobs.id`
- **Types**: `tooth`, `gums`, `jaw`, `implant`, `crown`, `bridge`, `other`
- **JSONB**: `properties`, `segment_metadata`, `bounding_box`, `mesh_data`

### Models Table
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `case_id` → `cases.id` (optional)
- **Types**: `segmentation`, `quality_assessment`, `format_conversion`, `anatomical_detection`
- **Unique Constraint**: `(model_name, model_version)`

### Audit Logs Table
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `user_id` → `users.id`
- **Event Types**: `login_success`, `login_failure`, `data_access`, `data_create`, `data_update`, `data_delete`, `data_retention_purge`, `right_to_erasure`, `client_authentication`
- **Indices**: `timestamp`, `event_type`, `user_id`, `resource_type`

## Performance Optimization

### Indices Strategy

1. **Primary Indices**: All primary keys and foreign keys
2. **Performance Indices**: Status + timestamp combinations
3. **JSONB Indices**: GIN indices on all JSONB fields
4. **Composite Indices**: For common query patterns

### Query Optimization

- Use indexed fields for filtering
- Leverage JSONB for flexible metadata queries
- Use composite indices for status + time queries
- Implement pagination for large result sets

## Compliance Features

### HIPAA Compliance
- Comprehensive audit logging
- Data encryption at rest and in transit
- Role-based access control
- Data retention policies

### GDPR Compliance
- Right to erasure support
- Data portability
- Consent management
- PII/PHI scrubbing in audit logs

### Security Features
- Soft deletes for data recovery
- Comprehensive audit trail
- Encrypted sensitive data
- Access control and authentication

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure PostgreSQL is running
   - Check connection string
   - Verify firewall settings

2. **Migration Errors**
   - Check database permissions
   - Ensure PostgreSQL version compatibility
   - Review migration files for syntax errors

3. **Performance Issues**
   - Check index usage with `EXPLAIN ANALYZE`
   - Monitor query performance
   - Optimize slow queries

### Useful Commands

```bash
# Check database connection
python -c "from dental_backend_common.session import check_db_connection; print(check_db_connection())"

# View table structure
psql -d dental_backend -c "\d+ users"

# Check indices
psql -d dental_backend -c "\di"

# Monitor queries
psql -d dental_backend -c "SELECT * FROM pg_stat_activity;"
```

## Development Workflow

1. **Schema Changes**: Modify models in `packages/common/dental_backend_common/database.py`
2. **Generate Migration**: `make db-revision message="Description"`
3. **Review Migration**: Check generated migration file
4. **Apply Migration**: `make migrate`
5. **Test Changes**: Run database tests
6. **Update Documentation**: Update ERD and schema docs

## Production Deployment

1. **Backup Strategy**: Regular database backups
2. **Migration Strategy**: Test migrations in staging first
3. **Monitoring**: Database performance monitoring
4. **Security**: Regular security audits
5. **Compliance**: Regular compliance checks
