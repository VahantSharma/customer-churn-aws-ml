# =============================================================================
# S3 Module — Local Values
# =============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Module      = "s3"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }

  # Determine encryption config based on whether KMS key is provided
  use_kms       = var.kms_key_arn != ""
  sse_algorithm = local.use_kms ? "aws:kms" : "AES256"
}
