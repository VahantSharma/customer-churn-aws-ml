# =============================================================================
# Dev Environment — Outputs
# =============================================================================

# --- KMS ---
output "kms_s3_key_arn" {
  description = "KMS key ARN for S3 encryption"
  value       = module.kms.s3_key_arn
}

output "kms_sagemaker_key_arn" {
  description = "KMS key ARN for SageMaker encryption"
  value       = module.kms.sagemaker_key_arn
}

# --- Networking ---
output "vpc_id" {
  description = "VPC ID"
  value       = module.networking.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.networking.private_subnet_ids
}

# --- IAM ---
output "sagemaker_role_arn" {
  description = "SageMaker execution role ARN"
  value       = module.iam.sagemaker_execution_role_arn
}

output "cicd_role_arn" {
  description = "CI/CD role ARN (for GitHub Actions OIDC)"
  value       = module.iam.cicd_role_arn
}

output "permission_boundary_arn" {
  description = "ARN of the IAM permission boundary"
  value       = module.iam.permission_boundary_arn
}

# --- S3 ---
output "data_bucket_name" {
  description = "Training data bucket name"
  value       = module.s3.data_bucket_name
}

output "model_bucket_name" {
  description = "Model artifacts bucket name"
  value       = module.s3.model_bucket_name
}

# --- ECR ---
output "ecr_repository_url" {
  description = "ECR repository URL (for docker push)"
  value       = module.ecr.repository_url
}

# --- SageMaker ---
output "notebook_url" {
  description = "SageMaker notebook URL"
  value       = module.sagemaker.notebook_instance_url
}

output "endpoint_name" {
  description = "SageMaker endpoint name"
  value       = module.sagemaker.endpoint_name
}

output "model_package_group" {
  description = "Model package group name"
  value       = module.sagemaker.model_package_group_name
}

output "model_package_group_arn" {
  description = "Model package group ARN"
  value       = module.sagemaker.model_package_group_arn
}

# --- Monitoring ---
output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = module.monitoring.sns_topic_arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name"
  value       = module.monitoring.dashboard_name
}
