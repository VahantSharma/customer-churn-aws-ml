# =============================================================================
# IAM Module — Local Values
# =============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Module      = "iam"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Account-level resource ARN prefix (avoids repetition in policies)
  sagemaker_arn_prefix = "arn:aws:sagemaker:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}"
  logs_arn_prefix      = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}"
}
