# =============================================================================
# Backend Bootstrap Outputs
# =============================================================================
# Use these values in environment backend.tf files:
#   backend "s3" {
#     bucket         = "<state_bucket_name>"
#     dynamodb_table = "<dynamodb_table_name>"
#   }
# =============================================================================

output "state_bucket_name" {
  description = "Name of the S3 bucket storing Terraform state"
  value       = aws_s3_bucket.terraform_state.id
}

output "state_bucket_arn" {
  description = "ARN of the S3 bucket storing Terraform state"
  value       = aws_s3_bucket.terraform_state.arn
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table for state locking"
  value       = aws_dynamodb_table.terraform_locks.name
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for state encryption"
  value       = aws_kms_key.terraform_state.arn
}

output "kms_key_alias" {
  description = "Alias of the state encryption KMS key"
  value       = aws_kms_alias.terraform_state.name
}
