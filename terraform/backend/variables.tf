# =============================================================================
# Backend Bootstrap Variables
# =============================================================================

variable "aws_region" {
  description = "AWS region for the Terraform state resources"
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-\\d+$", var.aws_region))
    error_message = "Must be a valid AWS region (e.g., us-east-1, eu-west-2)."
  }
}

variable "project_name" {
  description = "Project name used for resource naming. Must be lowercase with hyphens."
  type        = string
  default     = "customer-churn"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,28}[a-z0-9]$", var.project_name))
    error_message = "Project name must be 4-30 chars, lowercase alphanumeric with hyphens, start with letter."
  }
}

variable "aws_account_id" {
  description = "AWS Account ID (ensures globally unique bucket names)"
  type        = string
  default     = "231284356634"

  validation {
    condition     = can(regex("^\\d{12}$", var.aws_account_id))
    error_message = "AWS Account ID must be exactly 12 digits."
  }
}
