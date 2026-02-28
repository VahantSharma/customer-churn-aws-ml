# =============================================================================
# S3 Module — Data Bucket + Model Artifacts Bucket
# =============================================================================
# Creates two buckets:
#   1. Training Data — stores raw/processed CSV files
#   2. Model Artifacts — stores model.tar.gz from training output
#
# Security Features:
#   - KMS CMK encryption (falls back to AES256 if no key provided)
#   - TLS-only access enforcement (denies HTTP connections)
#   - S3 access logging to dedicated logging bucket
#   - Full public access block
#   - Bucket versioning
#   - Lifecycle policies for cost optimization
#
# Bug Fix (from original):
#   The old DenyUnencryptedUploads policy checked for s3:x-amz-server-side-
#   encryption != AES256, which BLOCKS valid uploads when:
#   (a) the bucket default handles encryption server-side, or
#   (b) KMS encryption is used instead of AES256.
#   Replaced with TLS-enforcement which is actually what matters.
# =============================================================================

# =============================================================================
# 0. Access Logging Bucket (all S3 access is audit-logged here)
# =============================================================================

resource "aws_s3_bucket" "access_logs" {
  bucket = "${local.name_prefix}-s3-access-logs-${var.aws_account_id}"

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-s3-access-logs"
    Purpose = "S3 access logging"
  })
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      # Access logs bucket must use AES256 — S3 log delivery doesn't support KMS
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    expiration {
      days = var.access_log_expiration_days
    }
  }
}

# =============================================================================
# 1. Training Data Bucket
# =============================================================================

resource "aws_s3_bucket" "data" {
  bucket = "${var.project_name}-data-${var.environment}-${var.aws_account_id}"

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-data"
    Purpose = "ML training data storage"
  })
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id

  versioning_configuration {
    status = var.enable_versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.sse_algorithm
      kms_master_key_id = local.use_kms ? var.kms_key_arn : null
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket = aws_s3_bucket.data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Access logging — every S3 request is logged for audit/forensics
resource "aws_s3_bucket_logging" "data" {
  bucket = aws_s3_bucket.data.id

  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "data-bucket/"
}

resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  # Raw data → Infrequent Access after 30 days → Glacier after 90 days
  rule {
    id     = "archive-raw-data"
    status = "Enabled"

    filter {
      prefix = "raw/"
    }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }

  # Processed data — keep recent, expire old versions
  rule {
    id     = "cleanup-processed-data"
    status = "Enabled"

    filter {
      prefix = "processed/"
    }

    noncurrent_version_expiration {
      noncurrent_days          = 60
      newer_noncurrent_versions = 5
    }
  }

  # Clean up incomplete multipart uploads
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# =============================================================================
# 2. Model Artifacts Bucket
# =============================================================================

resource "aws_s3_bucket" "models" {
  bucket = "${var.project_name}-models-${var.environment}-${var.aws_account_id}"

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-models"
    Purpose = "ML model artifacts storage"
  })
}

resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id

  # Always enable versioning on model bucket — every model version is precious
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = local.sse_algorithm
      kms_master_key_id = local.use_kms ? var.kms_key_arn : null
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "models" {
  bucket = aws_s3_bucket.models.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Access logging for model bucket
resource "aws_s3_bucket_logging" "models" {
  bucket = aws_s3_bucket.models.id

  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "models-bucket/"
}

resource "aws_s3_bucket_lifecycle_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  # Keep last N versions, expire older model artifacts
  rule {
    id     = "cleanup-old-model-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days           = 90
      newer_noncurrent_versions = 10
    }
  }

  # Clean up incomplete multipart uploads
  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 3
    }
  }
}

# =============================================================================
# Bucket Policies — TLS-only + SageMaker access
# =============================================================================
# NOTE: The old "DenyUnencryptedUploads" policy was removed because:
#   1. It checked s3:x-amz-server-side-encryption != AES256, which blocks
#      valid KMS-encrypted uploads
#   2. With bucket-default encryption enabled, S3 automatically encrypts
#      all objects — the policy was redundant and harmful
#   3. TLS enforcement is the actual security requirement (data in transit)
# =============================================================================

resource "aws_s3_bucket_policy" "data" {
  bucket = aws_s3_bucket.data.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid       = "EnforceTLSOnly"
          Effect    = "Deny"
          Principal = "*"
          Action    = "s3:*"
          Resource = [
            aws_s3_bucket.data.arn,
            "${aws_s3_bucket.data.arn}/*"
          ]
          Condition = {
            Bool = {
              "aws:SecureTransport" = "false"
            }
          }
        },
        {
          Sid       = "EnforceTLSVersion"
          Effect    = "Deny"
          Principal = "*"
          Action    = "s3:*"
          Resource = [
            aws_s3_bucket.data.arn,
            "${aws_s3_bucket.data.arn}/*"
          ]
          Condition = {
            NumericLessThan = {
              "s3:TlsVersion" = "1.2"
            }
          }
        }
      ],
      var.sagemaker_role_arn != "" ? [
        {
          Sid    = "AllowSageMakerAccess"
          Effect = "Allow"
          Principal = {
            AWS = var.sagemaker_role_arn
          }
          Action = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:ListBucket",
            "s3:GetBucketLocation"
          ]
          Resource = [
            aws_s3_bucket.data.arn,
            "${aws_s3_bucket.data.arn}/*"
          ]
        }
      ] : []
    )
  })
}

resource "aws_s3_bucket_policy" "models" {
  bucket = aws_s3_bucket.models.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid       = "EnforceTLSOnly"
          Effect    = "Deny"
          Principal = "*"
          Action    = "s3:*"
          Resource = [
            aws_s3_bucket.models.arn,
            "${aws_s3_bucket.models.arn}/*"
          ]
          Condition = {
            Bool = {
              "aws:SecureTransport" = "false"
            }
          }
        },
        {
          Sid       = "EnforceTLSVersion"
          Effect    = "Deny"
          Principal = "*"
          Action    = "s3:*"
          Resource = [
            aws_s3_bucket.models.arn,
            "${aws_s3_bucket.models.arn}/*"
          ]
          Condition = {
            NumericLessThan = {
              "s3:TlsVersion" = "1.2"
            }
          }
        }
      ],
      var.sagemaker_role_arn != "" ? [
        {
          Sid    = "AllowSageMakerAccess"
          Effect = "Allow"
          Principal = {
            AWS = var.sagemaker_role_arn
          }
          Action = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:ListBucket",
            "s3:GetBucketLocation"
          ]
          Resource = [
            aws_s3_bucket.models.arn,
            "${aws_s3_bucket.models.arn}/*"
          ]
        }
      ] : []
    )
  })
}
