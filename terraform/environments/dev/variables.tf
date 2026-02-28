# =============================================================================
# Dev Environment — Variables
# =============================================================================

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"

  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-\\d$", var.aws_region))
    error_message = "Must be a valid AWS region (e.g. us-east-1)."
  }
}

variable "project_name" {
  description = "Project name used in all resource naming"
  type        = string
  default     = "customer-churn"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,29}$", var.project_name))
    error_message = "Project name must be 3-30 lowercase alphanumeric characters or hyphens."
  }
}

variable "availability_zones" {
  description = "Availability zones for subnet placement"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least 2 availability zones are required."
  }
}

variable "github_repo" {
  description = "GitHub repository for OIDC federation (owner/repo format)"
  type        = string
  default     = "VahantSharma/customer-churn-aws-ml"

  validation {
    condition     = can(regex("^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$", var.github_repo))
    error_message = "Must be in owner/repo format."
  }
}

variable "alert_email" {
  description = "Email address for alarm notifications (optional)"
  type        = string
  default     = ""
}

variable "deploy_endpoint" {
  description = "Whether to deploy a SageMaker inference endpoint in dev"
  type        = bool
  default     = false
}

variable "model_artifact_s3_uri" {
  description = "S3 URI of the trained model artifact (s3://bucket/path/model.tar.gz)"
  type        = string
  default     = ""
}

variable "inference_image_uri" {
  description = "Docker image URI for inference. Leave empty to use ECR repo latest tag."
  type        = string
  default     = ""
}

variable "terraform_state_bucket_arn" {
  description = "ARN of the Terraform state S3 bucket (for CI/CD role permissions)"
  type        = string
  default     = ""
}

variable "terraform_lock_table_arn" {
  description = "ARN of the DynamoDB table for Terraform state locking"
  type        = string
  default     = ""
}
