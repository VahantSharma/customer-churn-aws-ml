# =============================================================================
# KMS Module — Customer-Managed Encryption Keys
# =============================================================================
# Creates dedicated CMK keys for each service category:
#   - S3 (training data + model artifacts)
#   - CloudWatch Logs (log group encryption)
#   - SNS (alert topic encryption)
#   - SageMaker (volume + output encryption)
#
# Key policies follow least-privilege: only specified roles can use keys.
# All keys have automatic rotation enabled (compliance requirement).
# =============================================================================

data "aws_caller_identity" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Principals that need key access (filter out empty strings)
  service_principals = compact([
    var.sagemaker_role_arn,
    var.cicd_role_arn,
  ])

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "kms"
  }
}

# =============================================================================
# S3 Encryption Key — Training Data + Model Artifacts
# =============================================================================

resource "aws_kms_key" "s3" {
  description             = "CMK for S3 bucket encryption — ${local.name_prefix}"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = var.enable_key_rotation
  multi_region            = false

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "${local.name_prefix}-s3-key-policy"
    Statement = [
      {
        Sid    = "EnableRootAccountFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.aws_account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowS3ServiceUsage"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowServiceRoles"
        Effect = "Allow"
        Principal = {
          AWS = length(local.service_principals) > 0 ? local.service_principals : ["arn:aws:iam::${var.aws_account_id}:root"]
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*",
        ]
        Resource = "*"
      },
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-s3-key"
    Purpose = "S3 bucket encryption"
  })
}

resource "aws_kms_alias" "s3" {
  name          = "alias/${local.name_prefix}-s3"
  target_key_id = aws_kms_key.s3.key_id
}

# =============================================================================
# CloudWatch Logs Encryption Key
# =============================================================================

resource "aws_kms_key" "cloudwatch" {
  description             = "CMK for CloudWatch Logs encryption — ${local.name_prefix}"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "${local.name_prefix}-cw-key-policy"
    Statement = [
      {
        Sid    = "EnableRootAccountFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.aws_account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Principal = {
          Service = "logs.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*",
        ]
        Resource = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:*:${var.aws_account_id}:log-group:*"
          }
        }
      },
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-cloudwatch-key"
    Purpose = "CloudWatch Logs encryption"
  })
}

resource "aws_kms_alias" "cloudwatch" {
  name          = "alias/${local.name_prefix}-cloudwatch"
  target_key_id = aws_kms_key.cloudwatch.key_id
}

# =============================================================================
# SNS Encryption Key — Alert Notifications
# =============================================================================

resource "aws_kms_key" "sns" {
  description             = "CMK for SNS topic encryption — ${local.name_prefix}"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "${local.name_prefix}-sns-key-policy"
    Statement = [
      {
        Sid    = "EnableRootAccountFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.aws_account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowSNSServiceUsage"
        Effect = "Allow"
        Principal = {
          Service = "sns.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowCloudWatchAlarms"
        Effect = "Allow"
        Principal = {
          Service = "cloudwatch.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey*",
        ]
        Resource = "*"
      },
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-sns-key"
    Purpose = "SNS topic encryption"
  })
}

resource "aws_kms_alias" "sns" {
  name          = "alias/${local.name_prefix}-sns"
  target_key_id = aws_kms_key.sns.key_id
}

# =============================================================================
# SageMaker Encryption Key — Volume + Output Encryption
# =============================================================================

resource "aws_kms_key" "sagemaker" {
  description             = "CMK for SageMaker volume/output encryption — ${local.name_prefix}"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = var.enable_key_rotation

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "${local.name_prefix}-sagemaker-key-policy"
    Statement = [
      {
        Sid    = "EnableRootAccountFullAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.aws_account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowSageMakerUsage"
        Effect = "Allow"
        Principal = {
          AWS = var.sagemaker_role_arn != "" ? var.sagemaker_role_arn : "arn:aws:iam::${var.aws_account_id}:root"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:ReEncrypt*",
          "kms:CreateGrant",
          "kms:ListGrants",
          "kms:RevokeGrant",
        ]
        Resource = "*"
      },
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-sagemaker-key"
    Purpose = "SageMaker volume and output encryption"
  })
}

resource "aws_kms_alias" "sagemaker" {
  name          = "alias/${local.name_prefix}-sagemaker"
  target_key_id = aws_kms_key.sagemaker.key_id
}
