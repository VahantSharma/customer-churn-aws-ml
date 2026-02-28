# =============================================================================
# Networking Module — Variables
# =============================================================================

variable "project_name" {
  description = "Project name for resource naming"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,28}[a-z0-9]$", var.project_name))
    error_message = "Project name must be 4-30 chars, lowercase alphanumeric with hyphens, start with letter."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC. Use /16 for sufficient IP space."
  type        = string
  default     = "10.0.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0))
    error_message = "Must be a valid CIDR block (e.g., 10.0.0.0/16)."
  }
}

variable "availability_zones" {
  description = "List of availability zones. Minimum 2 for HA."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "At least 2 availability zones required for HA."
  }
}

variable "enable_vpc_endpoints" {
  description = "Enable VPC Interface endpoints (SageMaker, ECR, CloudWatch). Costs ~$0.01/hr each. Disable for dev."
  type        = bool
  default     = false
}

variable "single_nat_gateway" {
  description = "Use a single NAT Gateway (saves ~$32/month, less HA). True for dev, false for prod."
  type        = bool
  default     = true
}

# --- Flow Logs (Compliance) ---

variable "enable_flow_logs" {
  description = "Enable VPC Flow Logs for network traffic auditing. Required for compliance."
  type        = bool
  default     = true
}

variable "flow_logs_retention_days" {
  description = "CloudWatch log retention for VPC Flow Logs"
  type        = number
  default     = 14

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.flow_logs_retention_days)
    error_message = "Must be a valid CloudWatch log retention period."
  }
}

variable "cloudwatch_kms_key_arn" {
  description = "KMS key ARN for encrypting CloudWatch Logs (flow logs). Empty string uses default encryption."
  type        = string
  default     = ""
}
