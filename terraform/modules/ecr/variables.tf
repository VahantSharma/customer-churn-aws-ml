# =============================================================================
# ECR Module — Variables
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

variable "kms_key_arn" {
  description = "ARN of KMS CMK for ECR image encryption (empty = AES256 default)"
  type        = string
  default     = ""
}

variable "image_tag_mutability" {
  description = "Tag mutability: MUTABLE (dev, allows overwriting tags) or IMMUTABLE (prod, prevents overwrites)"
  type        = string
  default     = "MUTABLE"

  validation {
    condition     = contains(["MUTABLE", "IMMUTABLE"], var.image_tag_mutability)
    error_message = "Must be MUTABLE or IMMUTABLE."
  }
}

variable "scan_on_push" {
  description = "Enable automatic vulnerability scan on every image push"
  type        = bool
  default     = true
}

variable "allowed_account_ids" {
  description = "List of AWS account IDs allowed to pull images (for cross-account access)"
  type        = list(string)
  default     = null
}
