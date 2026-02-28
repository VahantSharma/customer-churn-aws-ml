# =============================================================================
# Monitoring Module — Variables
# =============================================================================

# -----------------------------------------------------------------------------
# Identity
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Project name for resource naming (lowercase, hyphens allowed)"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,29}$", var.project_name))
    error_message = "Project name must be 3-30 lowercase alphanumeric characters or hyphens, starting with a letter."
  }
}

variable "environment" {
  description = "Environment name — controls alarm enablement defaults"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

# -----------------------------------------------------------------------------
# Encryption
# -----------------------------------------------------------------------------

variable "sns_kms_key_arn" {
  description = "ARN of the KMS key for SNS topic encryption. Leave empty for no encryption."
  type        = string
  default     = ""

  validation {
    condition     = var.sns_kms_key_arn == "" || can(regex("^arn:aws:kms:", var.sns_kms_key_arn))
    error_message = "Must be a valid KMS key ARN or empty string."
  }
}

variable "cloudwatch_kms_key_arn" {
  description = "ARN of the KMS key for CloudWatch log group encryption. Leave empty for no encryption."
  type        = string
  default     = ""

  validation {
    condition     = var.cloudwatch_kms_key_arn == "" || can(regex("^arn:aws:kms:", var.cloudwatch_kms_key_arn))
    error_message = "Must be a valid KMS key ARN or empty string."
  }
}

# -----------------------------------------------------------------------------
# Endpoint Monitoring Target
# -----------------------------------------------------------------------------

variable "endpoint_name" {
  description = "Name of the SageMaker endpoint to monitor. Leave empty if no endpoint is deployed."
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Notifications
# -----------------------------------------------------------------------------

variable "alert_email" {
  description = "Email address for alarm notifications (SNS subscription). Leave empty to skip."
  type        = string
  default     = ""

  validation {
    condition     = var.alert_email == "" || can(regex("^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$", var.alert_email))
    error_message = "Must be a valid email address or empty string."
  }
}

# -----------------------------------------------------------------------------
# Alarm Controls
# -----------------------------------------------------------------------------

variable "enable_alarms" {
  description = "Enable CloudWatch alarms. Disable for dev to avoid noise."
  type        = bool
  default     = false
}

variable "error_rate_threshold" {
  description = "5XX error count threshold per evaluation period (default: 1)"
  type        = number
  default     = 1

  validation {
    condition     = var.error_rate_threshold >= 0
    error_message = "Error rate threshold must be >= 0."
  }
}

variable "latency_threshold_us" {
  description = "P99 latency threshold in microseconds (SageMaker reports ModelLatency in μs). Default: 2000000 (2 seconds)."
  type        = number
  default     = 2000000

  validation {
    condition     = var.latency_threshold_us >= 100000
    error_message = "Latency threshold must be at least 100000 μs (100ms)."
  }
}

variable "cpu_threshold_percent" {
  description = "CPU utilization percentage threshold for alarm"
  type        = number
  default     = 80

  validation {
    condition     = var.cpu_threshold_percent > 0 && var.cpu_threshold_percent <= 100
    error_message = "CPU threshold must be between 1 and 100."
  }
}

variable "memory_threshold_percent" {
  description = "Memory utilization percentage threshold for alarm"
  type        = number
  default     = 85

  validation {
    condition     = var.memory_threshold_percent > 0 && var.memory_threshold_percent <= 100
    error_message = "Memory threshold must be between 1 and 100."
  }
}

variable "disk_threshold_percent" {
  description = "Disk utilization percentage threshold for alarm"
  type        = number
  default     = 80

  validation {
    condition     = var.disk_threshold_percent > 0 && var.disk_threshold_percent <= 100
    error_message = "Disk threshold must be between 1 and 100."
  }
}

# -----------------------------------------------------------------------------
# Log Retention
# -----------------------------------------------------------------------------

variable "log_retention_days" {
  description = "CloudWatch log retention period in days. Must be a valid CloudWatch retention value."
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Must be a valid CloudWatch log retention period: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, or 3653."
  }
}
