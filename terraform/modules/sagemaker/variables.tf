# =============================================================================
# SageMaker Module — Variables
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
# IAM
# -----------------------------------------------------------------------------

variable "sagemaker_execution_role_arn" {
  description = "ARN of the SageMaker execution IAM role"
  type        = string

  validation {
    condition     = can(regex("^arn:aws:iam::", var.sagemaker_execution_role_arn))
    error_message = "Must be a valid IAM role ARN."
  }
}

# -----------------------------------------------------------------------------
# Encryption
# -----------------------------------------------------------------------------

variable "kms_key_arn" {
  description = "ARN of KMS CMK for SageMaker volume/output encryption (empty = no encryption)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Model
# -----------------------------------------------------------------------------

variable "model_artifact_s3_uri" {
  description = "S3 URI of the trained model artifact (e.g., s3://bucket/model.tar.gz)"
  type        = string
  default     = ""
}

variable "inference_image_uri" {
  description = "Docker image URI for inference (ECR URL or SageMaker built-in)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Networking
# -----------------------------------------------------------------------------

variable "vpc_id" {
  description = "VPC ID for SageMaker resources"
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs for SageMaker VPC config"
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 1
    error_message = "At least one private subnet ID is required."
  }
}

variable "security_group_ids" {
  description = "List of security group IDs for SageMaker resources"
  type        = list(string)

  validation {
    condition     = length(var.security_group_ids) >= 1
    error_message = "At least one security group ID is required."
  }
}

# -----------------------------------------------------------------------------
# Notebook Configuration
# -----------------------------------------------------------------------------

variable "create_notebook" {
  description = "Whether to create a SageMaker notebook instance"
  type        = bool
  default     = true
}

variable "notebook_instance_type" {
  description = "Instance type for the notebook"
  type        = string
  default     = "ml.t3.medium"
}

variable "notebook_volume_size" {
  description = "EBS volume size in GB for the notebook instance"
  type        = number
  default     = 10

  validation {
    condition     = var.notebook_volume_size >= 5 && var.notebook_volume_size <= 16384
    error_message = "notebook_volume_size must be between 5 and 16384 GB."
  }
}

variable "notebook_idle_timeout" {
  description = "Idle timeout in seconds before auto-stopping the notebook"
  type        = number
  default     = 3600

  validation {
    condition     = var.notebook_idle_timeout >= 600 && var.notebook_idle_timeout <= 86400
    error_message = "notebook_idle_timeout must be between 600 (10min) and 86400 (24hr) seconds."
  }
}

variable "enable_direct_internet" {
  description = "Enable direct internet access for notebook (should be false in prod)"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Endpoint Configuration
# -----------------------------------------------------------------------------

variable "deploy_endpoint" {
  description = "Whether to deploy a SageMaker inference endpoint"
  type        = bool
  default     = false
}

variable "instance_type" {
  description = "Instance type for the SageMaker endpoint"
  type        = string
  default     = "ml.t2.medium"
}

variable "endpoint_volume_size" {
  description = "Storage volume size in GB attached to each endpoint instance"
  type        = number
  default     = 20

  validation {
    condition     = var.endpoint_volume_size >= 1 && var.endpoint_volume_size <= 512
    error_message = "endpoint_volume_size must be between 1 and 512 GB."
  }
}

variable "min_instance_count" {
  description = "Minimum number of endpoint instances"
  type        = number
  default     = 1

  validation {
    condition     = var.min_instance_count >= 1
    error_message = "min_instance_count must be at least 1."
  }
}

variable "max_instance_count" {
  description = "Maximum number of endpoint instances"
  type        = number
  default     = 1

  validation {
    condition     = var.max_instance_count >= 1
    error_message = "max_instance_count must be at least 1."
  }
}

# -----------------------------------------------------------------------------
# Data Capture
# -----------------------------------------------------------------------------

variable "enable_data_capture" {
  description = "Enable data capture on the endpoint for model monitoring"
  type        = bool
  default     = false
}

variable "data_capture_sampling_percentage" {
  description = "Percentage of requests to capture (1-100)"
  type        = number
  default     = 100

  validation {
    condition     = var.data_capture_sampling_percentage >= 1 && var.data_capture_sampling_percentage <= 100
    error_message = "data_capture_sampling_percentage must be between 1 and 100."
  }
}

variable "model_bucket_name" {
  description = "Name of the S3 bucket for model artifacts (used for data capture destination)"
  type        = string
  default     = ""
}

# -----------------------------------------------------------------------------
# Auto-Scaling
# -----------------------------------------------------------------------------

variable "enable_auto_scaling" {
  description = "Enable auto-scaling for the endpoint"
  type        = bool
  default     = false
}

variable "scaling_target_invocations" {
  description = "Target number of invocations per instance per minute for scaling"
  type        = number
  default     = 70

  validation {
    condition     = var.scaling_target_invocations >= 1
    error_message = "scaling_target_invocations must be at least 1."
  }
}

variable "scale_in_cooldown" {
  description = "Cooldown period (seconds) before scaling in"
  type        = number
  default     = 300
}

variable "scale_out_cooldown" {
  description = "Cooldown period (seconds) before scaling out"
  type        = number
  default     = 60
}

# -----------------------------------------------------------------------------
# Scheduled Scaling
# -----------------------------------------------------------------------------

variable "enable_scheduled_scaling" {
  description = "Enable scheduled scaling (scale down at night, up in the morning)"
  type        = bool
  default     = false
}
