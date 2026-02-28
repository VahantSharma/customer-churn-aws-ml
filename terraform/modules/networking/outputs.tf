# =============================================================================
# Networking Module — Outputs
# =============================================================================

# -----------------------------------------------------------------------------
# VPC
# -----------------------------------------------------------------------------

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_arn" {
  description = "ARN of the VPC"
  value       = aws_vpc.main.arn
}

output "vpc_cidr" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

# -----------------------------------------------------------------------------
# Subnets
# -----------------------------------------------------------------------------

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "public_subnet_cidrs" {
  description = "CIDR blocks of the public subnets"
  value       = aws_subnet.public[*].cidr_block
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "private_subnet_cidrs" {
  description = "CIDR blocks of the private subnets"
  value       = aws_subnet.private[*].cidr_block
}

# -----------------------------------------------------------------------------
# Security Groups
# -----------------------------------------------------------------------------

output "sagemaker_security_group_id" {
  description = "Security group ID for SageMaker resources"
  value       = aws_security_group.sagemaker.id
}

output "vpc_endpoint_security_group_id" {
  description = "Security group ID for VPC endpoints"
  value       = aws_security_group.vpc_endpoints.id
}

# -----------------------------------------------------------------------------
# NAT Gateway
# -----------------------------------------------------------------------------

output "nat_gateway_ids" {
  description = "IDs of the NAT Gateways"
  value       = aws_nat_gateway.main[*].id
}

output "nat_gateway_ips" {
  description = "Elastic IPs of the NAT Gateways"
  value       = aws_eip.nat[*].public_ip
}

# -----------------------------------------------------------------------------
# VPC Flow Logs
# -----------------------------------------------------------------------------

output "flow_log_id" {
  description = "ID of the VPC Flow Log"
  value       = var.enable_flow_logs ? aws_flow_log.main[0].id : null
}

output "flow_logs_log_group_name" {
  description = "CloudWatch Log Group name for VPC Flow Logs"
  value       = var.enable_flow_logs ? aws_cloudwatch_log_group.flow_logs[0].name : null
}

output "flow_logs_log_group_arn" {
  description = "CloudWatch Log Group ARN for VPC Flow Logs"
  value       = var.enable_flow_logs ? aws_cloudwatch_log_group.flow_logs[0].arn : null
}

# -----------------------------------------------------------------------------
# VPC Endpoints
# -----------------------------------------------------------------------------

output "s3_endpoint_id" {
  description = "ID of the S3 VPC Gateway Endpoint"
  value       = aws_vpc_endpoint.s3.id
}

output "sagemaker_api_endpoint_id" {
  description = "ID of the SageMaker API VPC Endpoint"
  value       = var.enable_vpc_endpoints ? aws_vpc_endpoint.sagemaker_api[0].id : null
}
