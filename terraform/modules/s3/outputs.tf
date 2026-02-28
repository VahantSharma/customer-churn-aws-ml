# =============================================================================
# S3 Module — Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# Data Bucket
# -----------------------------------------------------------------------------

output "data_bucket_name" {
  description = "Name of the training data bucket"
  value       = aws_s3_bucket.data.id
}

output "data_bucket_arn" {
  description = "ARN of the training data bucket"
  value       = aws_s3_bucket.data.arn
}

output "data_bucket_regional_domain" {
  description = "Regional domain name of the data bucket"
  value       = aws_s3_bucket.data.bucket_regional_domain_name
}

# -----------------------------------------------------------------------------
# Model Artifacts Bucket
# -----------------------------------------------------------------------------

output "model_bucket_name" {
  description = "Name of the model artifacts bucket"
  value       = aws_s3_bucket.models.id
}

output "model_bucket_arn" {
  description = "ARN of the model artifacts bucket"
  value       = aws_s3_bucket.models.arn
}

output "model_bucket_regional_domain" {
  description = "Regional domain name of the model bucket"
  value       = aws_s3_bucket.models.bucket_regional_domain_name
}

# -----------------------------------------------------------------------------
# Access Logs Bucket
# -----------------------------------------------------------------------------

output "access_logs_bucket_name" {
  description = "Name of the S3 access logging bucket"
  value       = aws_s3_bucket.access_logs.id
}

output "access_logs_bucket_arn" {
  description = "ARN of the S3 access logging bucket"
  value       = aws_s3_bucket.access_logs.arn
}

# -----------------------------------------------------------------------------
# Encryption
# -----------------------------------------------------------------------------

output "encryption_type" {
  description = "Type of encryption used (AES256 or aws:kms)"
  value       = local.sse_algorithm
}
