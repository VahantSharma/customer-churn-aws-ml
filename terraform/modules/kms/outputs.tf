# =============================================================================
# KMS Module — Outputs
# =============================================================================

# --- S3 Key ---
output "s3_key_arn" {
  description = "ARN of the KMS key for S3 bucket encryption"
  value       = aws_kms_key.s3.arn
}

output "s3_key_id" {
  description = "ID of the KMS key for S3 bucket encryption"
  value       = aws_kms_key.s3.key_id
}

output "s3_key_alias" {
  description = "Alias of the S3 KMS key"
  value       = aws_kms_alias.s3.name
}

# --- CloudWatch Key ---
output "cloudwatch_key_arn" {
  description = "ARN of the KMS key for CloudWatch Logs encryption"
  value       = aws_kms_key.cloudwatch.arn
}

output "cloudwatch_key_id" {
  description = "ID of the KMS key for CloudWatch Logs encryption"
  value       = aws_kms_key.cloudwatch.key_id
}

# --- SNS Key ---
output "sns_key_arn" {
  description = "ARN of the KMS key for SNS topic encryption"
  value       = aws_kms_key.sns.arn
}

output "sns_key_id" {
  description = "ID of the KMS key for SNS topic encryption"
  value       = aws_kms_key.sns.key_id
}

# --- SageMaker Key ---
output "sagemaker_key_arn" {
  description = "ARN of the KMS key for SageMaker encryption"
  value       = aws_kms_key.sagemaker.arn
}

output "sagemaker_key_id" {
  description = "ID of the KMS key for SageMaker encryption"
  value       = aws_kms_key.sagemaker.key_id
}
