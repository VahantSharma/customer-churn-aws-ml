# =============================================================================
# KMS Module — Variables
# =============================================================================
# Customer-managed encryption keys for all data at rest.
# Production mandates KMS CMK over default AES256 for:
#   1. Audit trail — CloudTrail logs every key usage
#   2. Key rotation — automatic annual rotation
#   3. Access control — key policies restrict who can encrypt/decrypt
#   4. Compliance — SOC2, HIPAA, PCI-DSS require CMK
# =============================================================================

variable "project_name" {
  description = "Project name for key alias naming"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,28}[a-z0-9]$", var.project_name))
    error_message = "Project name must be 4-30 chars, lowercase alphanumeric with hyphens, start with letter."
  }
}

variable "environment" {
  description = "Environment name for key alias naming"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_account_id" {
  description = "AWS Account ID for key policy principals"
  type        = string

  validation {
    condition     = can(regex("^\\d{12}$", var.aws_account_id))
    error_message = "AWS Account ID must be exactly 12 digits."
  }
}

variable "deletion_window_in_days" {
  description = "Waiting period before KMS key deletion (7-30 days). Production should use 30."
  type        = number
  default     = 30

  validation {
    condition     = var.deletion_window_in_days >= 7 && var.deletion_window_in_days <= 30
    error_message = "Deletion window must be between 7 and 30 days."
  }
}

variable "enable_key_rotation" {
  description = "Enable automatic annual key rotation. Should be true in production."
  type        = bool
  default     = true
}

variable "sagemaker_role_arn" {
  description = "ARN of the SageMaker execution role that needs encrypt/decrypt access"
  type        = string
  default     = ""
}

variable "cicd_role_arn" {
  description = "ARN of the CI/CD role that needs encrypt/decrypt access for deployments"
  type        = string
  default     = ""
}
