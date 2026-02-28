# =============================================================================
# VPC Flow Logs — Network Traffic Audit
# =============================================================================
# Captures metadata about all network traffic in/out of the VPC.
# Required for SOC2, HIPAA, PCI-DSS compliance.
#
# Flow logs record: source IP, dest IP, port, protocol, action (ACCEPT/REJECT).
# They do NOT capture packet contents — no data exposure risk.
#
# Dev: CloudWatch Logs destination (cheaper, easier to query with Insights)
# Prod: Could also add S3 destination for long-term archival
# =============================================================================

# =============================================================================
# CloudWatch Log Group for Flow Logs
# =============================================================================

resource "aws_cloudwatch_log_group" "flow_logs" {
  count = var.enable_flow_logs ? 1 : 0

  name              = "/aws/vpc/flow-logs/${local.name_prefix}"
  retention_in_days = var.flow_logs_retention_days
  kms_key_id        = var.cloudwatch_kms_key_arn != "" ? var.cloudwatch_kms_key_arn : null

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-flow-logs"
  })
}

# =============================================================================
# IAM Role for VPC Flow Logs → CloudWatch Delivery
# =============================================================================

resource "aws_iam_role" "flow_logs" {
  count = var.enable_flow_logs ? 1 : 0

  name = "${local.name_prefix}-flow-logs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      },
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "flow_logs" {
  count = var.enable_flow_logs ? 1 : 0

  name = "${local.name_prefix}-flow-logs-policy"
  role = aws_iam_role.flow_logs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
        ]
        Resource = "${aws_cloudwatch_log_group.flow_logs[0].arn}:*"
      },
    ]
  })
}

# =============================================================================
# VPC Flow Log Resource
# =============================================================================

resource "aws_flow_log" "main" {
  count = var.enable_flow_logs ? 1 : 0

  vpc_id                   = aws_vpc.main.id
  traffic_type             = "ALL"
  log_destination_type     = "cloud-watch-logs"
  log_destination          = aws_cloudwatch_log_group.flow_logs[0].arn
  iam_role_arn             = aws_iam_role.flow_logs[0].arn
  max_aggregation_interval = 60

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-flow-log"
  })
}
