# S3 Bucket for Dental Scans
resource "aws_s3_bucket" "dental_scans" {
  bucket = "dental-scans-${var.environment}-${random_string.bucket_suffix.result}"

  tags = {
    Name        = "dental-scans-${var.environment}"
    Environment = var.environment
    Project     = "dental-backend"
    Purpose     = "3d-scan-storage"
  }
}

# Random string for bucket name uniqueness
resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  upper   = false
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "dental_scans" {
  bucket = aws_s3_bucket.dental_scans.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Server-Side Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "dental_scans" {
  bucket = aws_s3_bucket.dental_scans.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "dental_scans" {
  bucket = aws_s3_bucket.dental_scans.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket Lifecycle Configuration
resource "aws_s3_bucket_lifecycle_configuration" "dental_scans" {
  bucket = aws_s3_bucket.dental_scans.id

  rule {
    id     = "transition_to_ia"
    status = "Enabled"

    filter {
      prefix = ""
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
  }

  rule {
    id     = "delete_old_versions"
    status = "Enabled"

    filter {
      prefix = ""
    }

    noncurrent_version_transition {
      noncurrent_days = 30
      storage_class   = "STANDARD_IA"
    }

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }

    noncurrent_version_expiration {
      noncurrent_days = 2555
    }
  }

  rule {
    id     = "delete_expired_objects"
    status = "Enabled"

    filter {
      prefix = ""
    }

    expiration {
      days = 2555
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "archive_processed_files"
    status = "Enabled"

    filter {
      prefix = "*/cases/*/processed/"
    }

    transition {
      days          = 7
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 30
      storage_class = "GLACIER"
    }
  }

  rule {
    id     = "delete_raw_files"
    status = "Enabled"

    filter {
      prefix = "*/cases/*/raw/"
    }

    expiration {
      days = 1
    }
  }
}

# S3 Bucket Policy
resource "aws_s3_bucket_policy" "dental_scans" {
  bucket = aws_s3_bucket.dental_scans.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnforceServerSideEncryption"
        Effect = "Deny"
        Principal = "*"
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.dental_scans.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "AES256"
          }
        }
      },
      {
        Sid    = "EnforceTLSRequestsOnly"
        Effect = "Deny"
        Principal = "*"
        Action   = "s3:*"
        Resource = [
          aws_s3_bucket.dental_scans.arn,
          "${aws_s3_bucket.dental_scans.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      },
      {
        Sid    = "DenyPublicAccess"
        Effect = "Deny"
        Principal = "*"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.dental_scans.arn}/*"
        Condition = {
          StringEquals = {
            "aws:PrincipalType" = "Anonymous"
          }
        }
      },
      {
        Sid    = "AllowServiceAccess"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.dental_backend_service_role.arn
        }
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.dental_scans.arn,
          "${aws_s3_bucket.dental_scans.arn}/*"
        ]
      }
    ]
  })
}

# IAM Role for Service Access
resource "aws_iam_role" "dental_backend_service_role" {
  name = "dental-backend-service-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "dental-backend-service-role-${var.environment}"
    Environment = var.environment
    Project     = "dental-backend"
  }
}

# IAM Policy for S3 Access
resource "aws_iam_role_policy" "dental_backend_s3_policy" {
  name = "dental-backend-s3-policy-${var.environment}"
  role = aws_iam_role.dental_backend_service_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.dental_scans.arn,
          "${aws_s3_bucket.dental_scans.arn}/*"
        ]
      }
    ]
  })
}

# Outputs
output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.dental_scans.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = aws_s3_bucket.dental_scans.arn
}

output "service_role_arn" {
  description = "ARN of the service role"
  value       = aws_iam_role.dental_backend_service_role.arn
}
