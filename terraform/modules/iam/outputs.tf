# =============================================================================
# IAM Module — Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# Permission Boundary
# -----------------------------------------------------------------------------

output "permission_boundary_arn" {
  description = "ARN of the IAM permission boundary policy"
  value       = aws_iam_policy.permission_boundary.arn
}

# -----------------------------------------------------------------------------
# SageMaker Role
# -----------------------------------------------------------------------------

output "sagemaker_execution_role_arn" {
  description = "ARN of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_execution.arn
}

output "sagemaker_execution_role_name" {
  description = "Name of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_execution.name
}

output "sagemaker_execution_role_id" {
  description = "Unique ID of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_execution.unique_id
}

# -----------------------------------------------------------------------------
# CI/CD Role
# -----------------------------------------------------------------------------

output "cicd_role_arn" {
  description = "ARN of the GitHub Actions CI/CD role (OIDC)"
  value       = aws_iam_role.cicd.arn
}

output "cicd_role_name" {
  description = "Name of the CI/CD role"
  value       = aws_iam_role.cicd.name
}

# -----------------------------------------------------------------------------
# Monitoring Role
# -----------------------------------------------------------------------------

output "monitoring_role_arn" {
  description = "ARN of the monitoring read-only role"
  value       = aws_iam_role.monitoring.arn
}

output "monitoring_role_name" {
  description = "Name of the monitoring role"
  value       = aws_iam_role.monitoring.name
}

# -----------------------------------------------------------------------------
# OIDC Provider
# -----------------------------------------------------------------------------

output "github_oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider"
  value       = aws_iam_openid_connect_provider.github.arn
}
