# =============================================================================
# Prod Environment — Outputs
# =============================================================================

# --- KMS ---
output "kms_s3_key_arn"        { value = module.kms.s3_key_arn }
output "kms_sagemaker_key_arn" { value = module.kms.sagemaker_key_arn }
output "kms_sns_key_arn"       { value = module.kms.sns_key_arn }

# --- Security ---
output "cloudtrail_arn"             { value = module.security.cloudtrail_arn }
output "cloudtrail_s3_bucket_name"  { value = module.security.cloudtrail_s3_bucket_name }

# --- Networking ---
output "vpc_id"             { value = module.networking.vpc_id }
output "private_subnet_ids" { value = module.networking.private_subnet_ids }
output "vpc_arn"            { value = module.networking.vpc_arn }

# --- IAM ---
output "sagemaker_role_arn"      { value = module.iam.sagemaker_execution_role_arn }
output "cicd_role_arn"           { value = module.iam.cicd_role_arn }
output "permission_boundary_arn" { value = module.iam.permission_boundary_arn }

# --- S3 ---
output "data_bucket_name"  { value = module.s3.data_bucket_name }
output "model_bucket_name" { value = module.s3.model_bucket_name }

# --- ECR ---
output "ecr_repository_url" { value = module.ecr.repository_url }

# --- SageMaker ---
output "endpoint_name"           { value = module.sagemaker.endpoint_name }
output "endpoint_arn"            { value = module.sagemaker.endpoint_arn }
output "model_package_group"     { value = module.sagemaker.model_package_group_name }
output "model_package_group_arn" { value = module.sagemaker.model_package_group_arn }

# --- Monitoring ---
output "sns_topic_arn"       { value = module.monitoring.sns_topic_arn }
output "dashboard_name"      { value = module.monitoring.dashboard_name }
output "dashboard_arn"       { value = module.monitoring.dashboard_arn }
output "composite_alarm_arn" { value = module.monitoring.composite_alarm_arn }
output "alarm_arns"          { value = module.monitoring.alarm_arns }
