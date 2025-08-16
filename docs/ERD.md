# Database Schema - Entity Relationship Diagram (ERD)

## Overview

The dental backend database schema is designed to support a comprehensive dental scan processing system with HIPAA/GDPR compliance, audit logging, and scalable architecture.

## Core Tables

### 1. Users
**Purpose**: User authentication and authorization
- **Primary Key**: `id` (UUID)
- **Unique Constraints**: `username`, `email`
- **Indices**: `username`, `email`, `role`, `created_at`
- **Relationships**:
  - One-to-Many with `cases` (created_by)
  - One-to-Many with `jobs` (created_by)
  - One-to-Many with `audit_logs` (user_id)

### 2. Cases
**Purpose**: Patient case management
- **Primary Key**: `id` (UUID)
- **Unique Constraints**: `case_number`
- **Indices**: `case_number`, `patient_id`, `status`, `created_at`, `priority`
- **GIN Indices**: `tags`, `metadata`
- **Composite Indices**: `(status, created_at)`
- **Relationships**:
  - Many-to-One with `users` (created_by)
  - One-to-Many with `files`
  - One-to-Many with `jobs`
  - One-to-Many with `segments`
  - One-to-Many with `models`

### 3. Files
**Purpose**: Dental scan file management
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `case_id`, `uploaded_by`
- **Indices**: `case_id`, `status`, `file_type`, `checksum`, `uploaded_at`, `processed_at`
- **GIN Indices**: `tags`, `metadata`
- **Composite Indices**: `(status, uploaded_at)`
- **Relationships**:
  - Many-to-One with `cases`
  - Many-to-One with `users` (uploaded_by)
  - One-to-Many with `jobs`
  - One-to-Many with `segments`

### 4. Jobs
**Purpose**: Background task processing
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `case_id`, `file_id`, `created_by`
- **Indices**: `case_id`, `file_id`, `status`, `job_type`, `priority`, `created_at`, `celery_task_id`
- **Composite Indices**: `(status, created_at)`, `(priority, created_at)`
- **Relationships**:
  - Many-to-One with `cases`
  - Many-to-One with `files` (optional)
  - Many-to-One with `users` (created_by)
  - One-to-Many with `segments` (created_by_job)

### 5. Segments
**Purpose**: Anatomical part segmentation
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `case_id`, `file_id`, `created_by_job`
- **Indices**: `case_id`, `file_id`, `segment_type`, `created_at`, `confidence_score`
- **GIN Indices**: `properties`, `metadata`
- **Relationships**:
  - Many-to-One with `cases`
  - Many-to-One with `files`
  - Many-to-One with `jobs` (created_by_job)

### 6. Models
**Purpose**: ML model management
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `case_id` (optional)
- **Unique Constraints**: `(model_name, model_version)`
- **Indices**: `case_id`, `model_type`, `model_name`, `model_version`, `created_at`, `is_active`
- **GIN Indices**: `metadata`
- **Relationships**:
  - Many-to-One with `cases` (optional)

### 7. Audit Logs
**Purpose**: Compliance and security auditing
- **Primary Key**: `id` (UUID)
- **Foreign Keys**: `user_id`
- **Indices**: `timestamp`, `event_type`, `user_id`, `username`, `resource_type`, `resource_id`, `outcome`
- **GIN Indices**: `details`
- **Composite Indices**: `(event_type, timestamp)`, `(user_id, timestamp)`
- **Relationships**:
  - Many-to-One with `users` (user_id)

## Enums

### UserRole
- `admin`: Full system access
- `operator`: Standard user access
- `service`: Service account access

### JobStatus
- `pending`: Job queued
- `processing`: Job in progress
- `completed`: Job finished successfully
- `failed`: Job failed
- `cancelled`: Job cancelled

### FileStatus
- `uploaded`: File uploaded
- `processing`: File being processed
- `processed`: File processing complete
- `failed`: File processing failed
- `deleted`: File marked for deletion

### SegmentType
- `tooth`: Individual tooth
- `gums`: Gum tissue
- `jaw`: Jaw structure
- `implant`: Dental implant
- `crown`: Dental crown
- `bridge`: Dental bridge
- `other`: Other anatomical parts

### ModelType
- `segmentation`: Anatomical segmentation models
- `quality_assessment`: Quality assessment models
- `format_conversion`: Format conversion models
- `anatomical_detection`: Anatomical detection models

### AuditEventType
- `login_success`: Successful login
- `login_failure`: Failed login attempt
- `data_access`: Data access event
- `data_create`: Data creation event
- `data_update`: Data update event
- `data_delete`: Data deletion event
- `data_retention_purge`: Data retention purge
- `right_to_erasure`: Right to erasure request
- `client_authentication`: Client authentication

## Key Design Principles

### 1. Soft Deletes
- `is_deleted` boolean flags on `cases`, `files`, and `segments`
- Enables data recovery and compliance with retention policies

### 2. Audit Trail
- Comprehensive audit logging for all data operations
- PII/PHI scrubbing in audit logs
- Compliance with HIPAA/GDPR requirements

### 3. Performance Optimization
- Strategic indexing for common query patterns
- GIN indices for JSONB fields (tags, metadata)
- Composite indices for status + timestamp queries

### 4. Scalability
- UUID primary keys for distributed systems
- JSONB fields for flexible metadata storage
- Proper foreign key relationships

### 5. Security
- Encrypted sensitive data fields
- Role-based access control
- Comprehensive audit logging

## Index Strategy

### Primary Indices
- All primary keys (UUID)
- Foreign key relationships
- Unique constraints

### Performance Indices
- Status-based queries: `(status, created_at)`
- Priority-based queries: `(priority, created_at)`
- Time-based queries: `created_at`, `updated_at`, `timestamp`

### JSONB Indices (GIN)
- `tags`: For tag-based filtering
- `metadata`: For flexible metadata queries
- `properties`: For segment property queries
- `details`: For audit log detail queries

## Data Retention

- **Audit Logs**: 7 years (HIPAA requirement)
- **Cases**: Configurable retention period
- **Files**: Configurable retention period
- **Segments**: Configurable retention period
- **Jobs**: Configurable retention period
- **Models**: Permanent (versioned)

## Compliance Features

- **HIPAA Compliance**: Audit logging, data encryption, access controls
- **GDPR Compliance**: Right to erasure, data portability, consent management
- **Data Privacy**: PII/PHI scrubbing, pseudonymization support
- **Security**: Role-based access, comprehensive audit trail
