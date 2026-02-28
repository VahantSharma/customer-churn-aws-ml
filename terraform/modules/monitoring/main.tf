# =============================================================================
# Monitoring Module — CloudWatch Dashboard, Alarms, SNS, Log Groups
# =============================================================================
# Production-grade observability for the ML infrastructure:
#
# - KMS-encrypted SNS topic with restricted publishing policy
# - KMS-encrypted CloudWatch Log Groups with configurable retention
# - Dashboard with endpoint + infrastructure metrics
# - Individual alarms (5XX errors, latency, availability, CPU, memory, disk)
# - Composite alarm aggregating endpoint health signals
# - Anomaly detection alarm for invocation volume
# =============================================================================

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# =============================================================================
# SNS Topic for Alarm Notifications
# =============================================================================

resource "aws_sns_topic" "alerts" {
  name              = "${local.name_prefix}-alerts"
  kms_master_key_id = var.sns_kms_key_arn != "" ? var.sns_kms_key_arn : null

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-alerts"
  })
}

# Restrict who can publish to the SNS topic — only CloudWatch alarms from this account
resource "aws_sns_topic_policy" "alerts" {
  arn = aws_sns_topic.alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Id      = "${local.name_prefix}-alerts-policy"
    Statement = [
      {
        Sid       = "AllowCloudWatchAlarms"
        Effect    = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.alerts.arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid       = "AllowAccountOwner"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action = [
          "SNS:GetTopicAttributes",
          "SNS:SetTopicAttributes",
          "SNS:Subscribe",
          "SNS:ListSubscriptionsByTopic",
          "SNS:Publish"
        ]
        Resource = aws_sns_topic.alerts.arn
      },
      {
        Sid       = "DenyNonTLSAccess"
        Effect    = "Deny"
        Principal = "*"
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.alerts.arn
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      }
    ]
  })
}

resource "aws_sns_topic_subscription" "email" {
  count = var.alert_email != "" ? 1 : 0

  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# =============================================================================
# CloudWatch Log Groups (all KMS-encrypted when key provided)
# =============================================================================

resource "aws_cloudwatch_log_group" "sagemaker_training" {
  name              = "/aws/sagemaker/TrainingJobs/${local.name_prefix}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.cloudwatch_kms_key_arn != "" ? var.cloudwatch_kms_key_arn : null

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-training-logs"
    Purpose = "sagemaker-training"
  })
}

resource "aws_cloudwatch_log_group" "sagemaker_endpoints" {
  name              = "/aws/sagemaker/Endpoints/${local.name_prefix}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.cloudwatch_kms_key_arn != "" ? var.cloudwatch_kms_key_arn : null

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-endpoint-logs"
    Purpose = "sagemaker-inference"
  })
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/${var.project_name}/${var.environment}/api"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.cloudwatch_kms_key_arn != "" ? var.cloudwatch_kms_key_arn : null

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-api-logs"
    Purpose = "api-application"
  })
}

# =============================================================================
# CloudWatch Dashboard
# =============================================================================

resource "aws_cloudwatch_dashboard" "main" {
  count = local.has_endpoint ? 1 : 0

  dashboard_name = "${local.name_prefix}-ml-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      # -----------------------------------------------------------------------
      # Header
      # -----------------------------------------------------------------------
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 1
        properties = {
          markdown = "# ${var.project_name} — ${var.environment} — ML Endpoint Health"
        }
      },

      # -----------------------------------------------------------------------
      # Row 1: Invocations, Latency Percentiles, Error Rates
      # -----------------------------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 1
        width  = 8
        height = 6
        properties = {
          title   = "Invocations"
          region  = data.aws_region.current.name
          view    = "timeSeries"
          stacked = false
          period  = 60
          stat    = "Sum"
          metrics = [
            ["AWS/SageMaker", "Invocations", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic"]
          ]
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 1
        width  = 8
        height = 6
        properties = {
          title   = "Model Latency (μs)"
          region  = data.aws_region.current.name
          view    = "timeSeries"
          stacked = false
          period  = 60
          metrics = [
            ["AWS/SageMaker", "ModelLatency", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic", { stat = "p50", label = "p50" }],
            ["AWS/SageMaker", "ModelLatency", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic", { stat = "p90", label = "p90" }],
            ["AWS/SageMaker", "ModelLatency", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic", { stat = "p99", label = "p99" }]
          ]
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 1
        width  = 8
        height = 6
        properties = {
          title   = "Errors"
          region  = data.aws_region.current.name
          view    = "timeSeries"
          stacked = true
          period  = 60
          stat    = "Sum"
          metrics = [
            ["AWS/SageMaker", "Invocation4XXErrors", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic", { label = "4XX" }],
            ["AWS/SageMaker", "Invocation5XXErrors", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic", { label = "5XX" }],
            ["AWS/SageMaker", "ModelSetupTime",      "EndpointName", var.endpoint_name, "VariantName", "AllTraffic", { label = "Model Setup (μs)", stat = "Average" }]
          ]
        }
      },

      # -----------------------------------------------------------------------
      # Row 2: CPU, Memory, Disk, Overhead Latency
      # -----------------------------------------------------------------------
      {
        type   = "metric"
        x      = 0
        y      = 7
        width  = 6
        height = 6
        properties = {
          title   = "CPU Utilization (%)"
          region  = data.aws_region.current.name
          view    = "timeSeries"
          stacked = false
          period  = 300
          stat    = "Average"
          metrics = [
            ["AWS/SageMaker", "CPUUtilization", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic"]
          ]
          yAxis = { left = { min = 0, max = 100 } }
        }
      },
      {
        type   = "metric"
        x      = 6
        y      = 7
        width  = 6
        height = 6
        properties = {
          title   = "Memory Utilization (%)"
          region  = data.aws_region.current.name
          view    = "timeSeries"
          stacked = false
          period  = 300
          stat    = "Average"
          metrics = [
            ["AWS/SageMaker", "MemoryUtilization", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic"]
          ]
          yAxis = { left = { min = 0, max = 100 } }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 7
        width  = 6
        height = 6
        properties = {
          title   = "Disk Utilization (%)"
          region  = data.aws_region.current.name
          view    = "timeSeries"
          stacked = false
          period  = 300
          stat    = "Average"
          metrics = [
            ["AWS/SageMaker", "DiskUtilization", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic"]
          ]
          yAxis = { left = { min = 0, max = 100 } }
        }
      },
      {
        type   = "metric"
        x      = 18
        y      = 7
        width  = 6
        height = 6
        properties = {
          title   = "Overhead Latency (μs)"
          region  = data.aws_region.current.name
          view    = "timeSeries"
          stacked = false
          period  = 60
          stat    = "Average"
          metrics = [
            ["AWS/SageMaker", "OverheadLatency", "EndpointName", var.endpoint_name, "VariantName", "AllTraffic"]
          ]
        }
      },

      # -----------------------------------------------------------------------
      # Row 3: Alarm Status Summary
      # -----------------------------------------------------------------------
      {
        type   = "alarm"
        x      = 0
        y      = 13
        width  = 24
        height = 3
        properties = {
          title  = "Alarm Status"
          alarms = local.create_alarms ? [
            aws_cloudwatch_metric_alarm.high_error_rate[0].arn,
            aws_cloudwatch_metric_alarm.high_latency[0].arn,
            aws_cloudwatch_metric_alarm.no_invocations[0].arn,
            aws_cloudwatch_metric_alarm.high_cpu[0].arn,
            aws_cloudwatch_metric_alarm.high_memory[0].arn,
            aws_cloudwatch_metric_alarm.high_disk[0].arn
          ] : []
        }
      }
    ]
  })
}

# =============================================================================
# CloudWatch Alarms — Individual
# =============================================================================

# Alarm: High 5XX Error Rate (> configurable threshold for 5 minutes)
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  count = local.create_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-high-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 5
  threshold           = var.error_rate_threshold
  alarm_description   = "SageMaker endpoint 5XX errors exceed ${var.error_rate_threshold} per minute for 5 consecutive minutes"
  treat_missing_data  = "notBreaching"

  metric_name = "Invocation5XXErrors"
  namespace   = "AWS/SageMaker"
  period      = 60
  statistic   = "Sum"

  dimensions = {
    EndpointName = var.endpoint_name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-high-5xx-alarm"
    Severity = "critical"
  })
}

# Alarm: High P99 Latency (> configurable threshold)
resource "aws_cloudwatch_metric_alarm" "high_latency" {
  count = local.create_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.latency_threshold_us
  alarm_description   = "SageMaker endpoint P99 latency exceeds ${var.latency_threshold_us / 1000000}s for 3 consecutive minutes"
  treat_missing_data  = "notBreaching"

  metric_name        = "ModelLatency"
  namespace          = "AWS/SageMaker"
  period             = 60
  extended_statistic = "p99"

  dimensions = {
    EndpointName = var.endpoint_name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-high-latency-alarm"
    Severity = "high"
  })
}

# Alarm: No Invocations for 1 hour (endpoint may be down or unused)
resource "aws_cloudwatch_metric_alarm" "no_invocations" {
  count = local.create_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-no-invocations"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 12
  threshold           = 0
  alarm_description   = "SageMaker endpoint received zero invocations for 1 hour — endpoint may be down or not receiving traffic"
  treat_missing_data  = "breaching"

  metric_name = "Invocations"
  namespace   = "AWS/SageMaker"
  period      = 300
  statistic   = "Sum"

  dimensions = {
    EndpointName = var.endpoint_name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-no-invocations-alarm"
    Severity = "high"
  })
}

# Alarm: High CPU Utilization (> configurable threshold)
resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  count = local.create_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.cpu_threshold_percent
  alarm_description   = "SageMaker endpoint CPU utilization exceeds ${var.cpu_threshold_percent}% for 15 minutes — consider scaling"
  treat_missing_data  = "notBreaching"

  metric_name = "CPUUtilization"
  namespace   = "AWS/SageMaker"
  period      = 300
  statistic   = "Average"

  dimensions = {
    EndpointName = var.endpoint_name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-high-cpu-alarm"
    Severity = "medium"
  })
}

# Alarm: High Memory Utilization (> configurable threshold)
resource "aws_cloudwatch_metric_alarm" "high_memory" {
  count = local.create_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.memory_threshold_percent
  alarm_description   = "SageMaker endpoint memory utilization exceeds ${var.memory_threshold_percent}% for 15 minutes — risk of OOM"
  treat_missing_data  = "notBreaching"

  metric_name = "MemoryUtilization"
  namespace   = "AWS/SageMaker"
  period      = 300
  statistic   = "Average"

  dimensions = {
    EndpointName = var.endpoint_name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-high-memory-alarm"
    Severity = "high"
  })
}

# Alarm: High Disk Utilization (> configurable threshold)
resource "aws_cloudwatch_metric_alarm" "high_disk" {
  count = local.create_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-high-disk"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = var.disk_threshold_percent
  alarm_description   = "SageMaker endpoint disk utilization exceeds ${var.disk_threshold_percent}% for 15 minutes — model artifacts may fill disk"
  treat_missing_data  = "notBreaching"

  metric_name = "DiskUtilization"
  namespace   = "AWS/SageMaker"
  period      = 300
  statistic   = "Average"

  dimensions = {
    EndpointName = var.endpoint_name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-high-disk-alarm"
    Severity = "medium"
  })
}

# =============================================================================
# Composite Alarm — Endpoint Health
# =============================================================================
# Fires when ANY critical alarm is in ALARM state, providing a single
# "endpoint unhealthy" signal for incident management / PagerDuty.
# =============================================================================

resource "aws_cloudwatch_composite_alarm" "endpoint_health" {
  count = local.create_alarms ? 1 : 0

  alarm_name        = "${local.name_prefix}-endpoint-unhealthy"
  alarm_description = "Composite: SageMaker endpoint is unhealthy — one or more critical alarms are firing"

  alarm_rule = "ALARM(${aws_cloudwatch_metric_alarm.high_error_rate[0].alarm_name}) OR ALARM(${aws_cloudwatch_metric_alarm.high_latency[0].alarm_name}) OR ALARM(${aws_cloudwatch_metric_alarm.no_invocations[0].alarm_name}) OR ALARM(${aws_cloudwatch_metric_alarm.high_memory[0].alarm_name})"

  actions_enabled = true
  alarm_actions   = [aws_sns_topic.alerts.arn]
  ok_actions      = [aws_sns_topic.alerts.arn]

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-endpoint-unhealthy"
    Severity = "critical"
    Type     = "composite"
  })
}

# =============================================================================
# Anomaly Detection — Invocation Volume
# =============================================================================
# Uses CloudWatch anomaly detection (2 standard deviations) to identify
# unexpected traffic patterns — either drops (model failure, routing issue)
# or spikes (abuse, misconfiguration, load test leak).
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "invocation_anomaly" {
  count = local.create_alarms ? 1 : 0

  alarm_name          = "${local.name_prefix}-invocation-anomaly"
  comparison_operator = "LessThanLowerOrGreaterThanUpperThreshold"
  evaluation_periods  = 3
  threshold_metric_id = "ad1"
  alarm_description   = "SageMaker invocation volume is outside normal bounds (anomaly detection)"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "m1"
    return_data = true

    metric {
      metric_name = "Invocations"
      namespace   = "AWS/SageMaker"
      period      = 300
      stat        = "Sum"

      dimensions = {
        EndpointName = var.endpoint_name
        VariantName  = "AllTraffic"
      }
    }
  }

  metric_query {
    id          = "ad1"
    expression  = "ANOMALY_DETECTION_BAND(m1, 2)"
    label       = "Invocations (expected)"
    return_data = true
  }

  alarm_actions = [aws_sns_topic.alerts.arn]

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-invocation-anomaly-alarm"
    Severity = "medium"
    Type     = "anomaly-detection"
  })
}
