# =============================================================================
# Monitoring Module — Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# SNS
# -----------------------------------------------------------------------------

output "sns_topic_arn" {
  description = "ARN of the SNS topic for alert notifications"
  value       = aws_sns_topic.alerts.arn
}

output "sns_topic_name" {
  description = "Name of the SNS topic"
  value       = aws_sns_topic.alerts.name
}

# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = local.has_endpoint ? aws_cloudwatch_dashboard.main[0].dashboard_name : null
}

output "dashboard_arn" {
  description = "ARN of the CloudWatch dashboard"
  value       = local.has_endpoint ? aws_cloudwatch_dashboard.main[0].dashboard_arn : null
}

# -----------------------------------------------------------------------------
# Log Groups
# -----------------------------------------------------------------------------

output "training_log_group_name" {
  description = "Name of the training log group"
  value       = aws_cloudwatch_log_group.sagemaker_training.name
}

output "training_log_group_arn" {
  description = "ARN of the training log group"
  value       = aws_cloudwatch_log_group.sagemaker_training.arn
}

output "endpoint_log_group_name" {
  description = "Name of the endpoint log group"
  value       = aws_cloudwatch_log_group.sagemaker_endpoints.name
}

output "endpoint_log_group_arn" {
  description = "ARN of the endpoint log group"
  value       = aws_cloudwatch_log_group.sagemaker_endpoints.arn
}

output "api_log_group_name" {
  description = "Name of the API log group"
  value       = aws_cloudwatch_log_group.api.name
}

output "api_log_group_arn" {
  description = "ARN of the API log group"
  value       = aws_cloudwatch_log_group.api.arn
}

# -----------------------------------------------------------------------------
# Alarms
# -----------------------------------------------------------------------------

output "composite_alarm_arn" {
  description = "ARN of the composite endpoint-health alarm"
  value       = local.create_alarms ? aws_cloudwatch_composite_alarm.endpoint_health[0].arn : null
}

output "alarm_arns" {
  description = "Map of individual alarm ARNs"
  value = local.create_alarms ? {
    high_error_rate    = aws_cloudwatch_metric_alarm.high_error_rate[0].arn
    high_latency       = aws_cloudwatch_metric_alarm.high_latency[0].arn
    no_invocations     = aws_cloudwatch_metric_alarm.no_invocations[0].arn
    high_cpu           = aws_cloudwatch_metric_alarm.high_cpu[0].arn
    high_memory        = aws_cloudwatch_metric_alarm.high_memory[0].arn
    high_disk          = aws_cloudwatch_metric_alarm.high_disk[0].arn
    invocation_anomaly = aws_cloudwatch_metric_alarm.invocation_anomaly[0].arn
  } : {}
}
