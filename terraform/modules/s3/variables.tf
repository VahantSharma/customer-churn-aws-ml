# =============================================================================
# S3 Module — Variables
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

variable "aws_account_id" {
  description = "AWS Account ID for globally unique bucket names"
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit number."
  }
}

# -----------------------------------------------------------------------------
# Encryption
# -----------------------------------------------------------------------------

variable "kms_key_arn" {
  description = "ARN of KMS CMK for S3 encryption (empty = AES256 default)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Features
# -----------------------------------------------------------------------------

variable "enable_versioning" {
  description = "Enable S3 versioning on data bucket. Always enabled on model bucket."
  type        = bool
  default     = true
}

variable "access_log_expiration_days" {
  description = "Number of days to retain S3 access logs"
  type        = number
  default     = 90

  validation {
    condition     = var.access_log_expiration_days >= 30 && var.access_log_expiration_days <= 365
    error_message = "access_log_expiration_days must be between 30 and 365."
  }
}

# -----------------------------------------------------------------------------
# Access Control
# -----------------------------------------------------------------------------

variable "force_destroy" {
  description = "Allow Terraform to destroy non-empty S3 buckets. Enable in dev for easy teardown, never in prod."
  type        = bool
  default     = false
}

variable "sagemaker_role_arn" {
  description = "ARN of the SageMaker execution role for bucket policy (empty = no SageMaker access grant)"
  type        = string
  default     = ""
}
