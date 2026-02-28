# =============================================================================
# IAM Module — Variables
# =============================================================================

variable "project_name" {
  description = "Project name for resource naming (lowercase, hyphens, 4-30 chars)"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{3,29}$", var.project_name))
    error_message = "project_name must be 4-30 lowercase alphanumeric characters or hyphens, starting with a letter."
  }
}

variable "environment" {
  description = "Deployment environment"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

# -----------------------------------------------------------------------------
# S3 Bucket ARNs (required — SageMaker needs data access)
# -----------------------------------------------------------------------------

variable "data_bucket_arn" {
  description = "ARN of the training data S3 bucket"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:s3:::", var.data_bucket_arn))
    error_message = "data_bucket_arn must be a valid S3 bucket ARN."
  }
}

variable "model_bucket_arn" {
  description = "ARN of the model artifacts S3 bucket"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:s3:::", var.model_bucket_arn))
    error_message = "model_bucket_arn must be a valid S3 bucket ARN."
  }
}

# -----------------------------------------------------------------------------
# ECR
# -----------------------------------------------------------------------------

variable "ecr_repository_arn" {
  description = "ARN of the ECR repository for Docker images (empty = allow all repos)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# KMS Key ARNs (for CMK encryption integration)
# -----------------------------------------------------------------------------

variable "kms_s3_key_arn" {
  description = "ARN of the KMS key used for S3 encryption (empty = skip KMS policy)"
  type        = string
  default     = ""
}

variable "kms_sagemaker_key_arn" {
  description = "ARN of the KMS key used for SageMaker volume/output encryption"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# GitHub Actions OIDC
# -----------------------------------------------------------------------------

variable "github_repo" {
  description = "GitHub repository in format 'owner/repo' for OIDC trust policy"
  type        = string
  default     = "VahantSharma/customer-churn-aws-ml"

  validation {
    condition     = can(regex("^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", var.github_repo))
    error_message = "github_repo must be in 'owner/repo' format."
  }
}

variable "github_oidc_thumbprint" {
  description = "GitHub OIDC provider certificate thumbprint (40-char hex)"
  type        = string
  default     = "6938fd4d98bab03faadb97b34396831e3780aea1"

  validation {
    condition     = can(regex("^[a-fA-F0-9]{40}$", var.github_oidc_thumbprint))
    error_message = "github_oidc_thumbprint must be a 40-character hex string."
  }
}

# -----------------------------------------------------------------------------
# Terraform State (for CI/CD role permissions)
# -----------------------------------------------------------------------------

variable "terraform_state_bucket_arn" {
  description = "ARN of the Terraform state S3 bucket (for CI/CD role access)"
  type        = string
  default     = ""
}

variable "terraform_lock_table_arn" {
  description = "ARN of the DynamoDB table for Terraform state locking"
  type        = string
  default     = ""
}
