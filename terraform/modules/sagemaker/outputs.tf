# =============================================================================
# SageMaker Module — Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# Notebook
# -----------------------------------------------------------------------------

output "notebook_instance_name" {
  description = "Name of the SageMaker notebook instance"
  value       = var.create_notebook ? aws_sagemaker_notebook_instance.main[0].name : null
}

output "notebook_instance_url" {
  description = "URL of the SageMaker notebook instance"
  value       = var.create_notebook ? aws_sagemaker_notebook_instance.main[0].url : null
}

# -----------------------------------------------------------------------------
# Model Registry
# -----------------------------------------------------------------------------

output "model_package_group_name" {
  description = "Name of the model package group (model registry)"
  value       = aws_sagemaker_model_package_group.main.model_package_group_name
}

output "model_package_group_arn" {
  description = "ARN of the model package group"
  value       = aws_sagemaker_model_package_group.main.arn
}

# -----------------------------------------------------------------------------
# Endpoint
# -----------------------------------------------------------------------------

output "endpoint_name" {
  description = "Name of the SageMaker inference endpoint"
  value       = var.deploy_endpoint ? aws_sagemaker_endpoint.main[0].name : null
}

output "endpoint_arn" {
  description = "ARN of the SageMaker inference endpoint"
  value       = var.deploy_endpoint ? aws_sagemaker_endpoint.main[0].arn : null
}

output "endpoint_config_name" {
  description = "Name of the active endpoint configuration"
  value       = var.deploy_endpoint ? aws_sagemaker_endpoint_configuration.main[0].name : null
}

# -----------------------------------------------------------------------------
# Model
# -----------------------------------------------------------------------------

output "model_name" {
  description = "Name of the registered SageMaker model"
  value       = var.deploy_endpoint ? aws_sagemaker_model.main[0].name : null
}
