# =============================================================================
# Security Module — Outputs
# =============================================================================

output "cloudtrail_arn" {
  description = "ARN of the CloudTrail trail"
  value       = var.enable_cloudtrail ? aws_cloudtrail.main[0].arn : ""
}

output "cloudtrail_s3_bucket_name" {
  description = "Name of the S3 bucket storing CloudTrail logs"
  value       = var.enable_cloudtrail ? aws_s3_bucket.cloudtrail[0].id : ""
}

output "cloudtrail_log_group_name" {
  description = "CloudWatch Log Group for CloudTrail events"
  value       = var.enable_cloudtrail ? aws_cloudwatch_log_group.cloudtrail[0].name : ""
}

output "cloudtrail_log_group_arn" {
  description = "ARN of the CloudTrail CloudWatch Log Group"
  value       = var.enable_cloudtrail ? aws_cloudwatch_log_group.cloudtrail[0].arn : ""
}
