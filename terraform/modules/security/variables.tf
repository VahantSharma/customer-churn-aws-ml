# =============================================================================
# Security Module — Variables
# =============================================================================

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "aws_account_id" {
  description = "AWS Account ID for resource policies"
  type        = string
}

variable "enable_cloudtrail" {
  description = "Enable CloudTrail for API audit logging. Required for prod compliance."
  type        = bool
  default     = true
}

variable "cloudtrail_s3_kms_key_arn" {
  description = "KMS key ARN for encrypting CloudTrail S3 logs"
  type        = string
  default     = ""
}

variable "cloudwatch_kms_key_arn" {
  description = "KMS key ARN for CloudWatch Logs encryption"
  type        = string
  default     = ""
}

variable "cloudtrail_log_retention_days" {
  description = "CloudWatch log retention for CloudTrail events"
  type        = number
  default     = 90

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.cloudtrail_log_retention_days)
    error_message = "Must be a valid CloudWatch log retention period."
  }
}

variable "trail_s3_bucket_expiration_days" {
  description = "Days before CloudTrail S3 logs are expired"
  type        = number
  default     = 365
}

variable "enable_data_events" {
  description = "Enable S3 data event logging in CloudTrail (captures object-level API calls). Adds cost."
  type        = bool
  default     = false
}

variable "monitored_s3_bucket_arns" {
  description = "List of S3 bucket ARNs for data event logging (only if enable_data_events=true)"
  type        = list(string)
  default     = []
}
