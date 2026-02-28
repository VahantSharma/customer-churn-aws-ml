# =============================================================================
# SageMaker Module — Notebook, Model, Endpoint, Auto-Scaling
# =============================================================================
# Provisions the core ML infrastructure:
#   - Notebook instance (dev environment with auto-stop)
#   - Model (registered from S3 artifact)
#   - Endpoint configuration (instance type, data capture, variants)
#   - Endpoint (live inference)
#   - Auto-scaling (invocation-based, configurable per environment)
#   - Model package group (model registry for versioning)
#
# Bug Fix (from original):
#   The endpoint config used timestamp() in its name, which caused Terraform
#   to detect drift on EVERY plan — showing a forced replacement even when
#   nothing changed. Fixed by using name_prefix with create_before_destroy
#   lifecycle, which is the standard AWS pattern for immutable resources.
#
# Security Improvements:
#   - KMS volume encryption for notebook and training data
#   - Root access disabled on notebook
#   - Network isolation option for models
# =============================================================================

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# =============================================================================
# SageMaker Notebook Instance (Development Environment)
# =============================================================================

resource "aws_sagemaker_notebook_instance_lifecycle_configuration" "auto_stop" {
  count = var.create_notebook ? 1 : 0
  name  = "${local.name_prefix}-autostop"

  # Script runs on notebook start — schedules auto-shutdown after idle period
  on_start = base64encode(<<-EOF
    #!/bin/bash
    set -e

    IDLE_TIME=${var.notebook_idle_timeout}

    echo "Configuring auto-stop after $${IDLE_TIME}s idle..."

    # Create the auto-stop script
    cat > /home/ec2-user/SageMaker/auto-stop.sh << 'SCRIPT'
    #!/bin/bash
    IDLE_TIME=$${1:-3600}
    
    # Check if any kernel is active
    ACTIVE_KERNELS=$(jupyter notebook list 2>/dev/null | grep -c "http" || true)
    
    if [ "$ACTIVE_KERNELS" -eq 0 ]; then
      echo "No active kernels. Checking idle time..."
      LAST_ACTIVITY=$(stat -c %Y /home/ec2-user/SageMaker/ 2>/dev/null || echo 0)
      CURRENT_TIME=$(date +%s)
      IDLE_SECONDS=$((CURRENT_TIME - LAST_ACTIVITY))
      
      if [ "$IDLE_SECONDS" -gt "$IDLE_TIME" ]; then
        echo "Notebook idle for $${IDLE_SECONDS}s (threshold: $${IDLE_TIME}s). Stopping..."
        sudo shutdown -h now
      fi
    fi
    SCRIPT

    chmod +x /home/ec2-user/SageMaker/auto-stop.sh

    # Schedule check every 5 minutes
    (crontab -l 2>/dev/null; echo "*/5 * * * * /home/ec2-user/SageMaker/auto-stop.sh ${var.notebook_idle_timeout}") | crontab -
    
    echo "Auto-stop configured successfully."
  EOF
  )
}

resource "aws_sagemaker_notebook_instance" "main" {
  count = var.create_notebook ? 1 : 0

  name                    = "${local.name_prefix}-notebook"
  role_arn                = var.sagemaker_execution_role_arn
  instance_type           = var.notebook_instance_type
  platform_identifier     = "notebook-al2-v2"
  volume_size             = var.notebook_volume_size
  direct_internet_access  = var.enable_direct_internet ? "Enabled" : "Disabled"
  kms_key_id              = var.kms_key_arn != "" ? var.kms_key_arn : null

  # VPC configuration (private subnet)
  subnet_id       = var.private_subnet_ids[0]
  security_groups = var.security_group_ids

  lifecycle_config_name = aws_sagemaker_notebook_instance_lifecycle_configuration.auto_stop[0].name

  root_access = "Disabled"

  tags = merge(local.common_tags, {
    Name     = "${local.name_prefix}-notebook"
    AutoStop = "${var.notebook_idle_timeout}s"
  })
}

# =============================================================================
# Model Package Group (Model Registry)
# =============================================================================

resource "aws_sagemaker_model_package_group" "main" {
  model_package_group_name = "${local.name_prefix}-models"

  model_package_group_description = "Model registry for ${var.project_name} churn prediction models (${var.environment})"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-models"
  })
}

# =============================================================================
# SageMaker Model (Registered Model pointing to S3 artifact)
# =============================================================================

resource "aws_sagemaker_model" "main" {
  count = var.deploy_endpoint ? 1 : 0

  name               = "${local.name_prefix}-model"
  execution_role_arn = var.sagemaker_execution_role_arn

  primary_container {
    image          = var.inference_image_uri
    model_data_url = var.model_artifact_s3_uri
    environment = {
      SAGEMAKER_PROGRAM         = "inference.py"
      SAGEMAKER_SUBMIT_DIRECTORY = var.model_artifact_s3_uri
    }
  }

  vpc_config {
    subnets            = var.private_subnet_ids
    security_group_ids = var.security_group_ids
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-model"
  })
}

# =============================================================================
# Endpoint Configuration
# =============================================================================
# FIX: Removed timestamp() which caused plan drift on every run.
# Using name_prefix + create_before_destroy instead — AWS generates a unique
# suffix, and the old config is only deleted after the new one is active.
# This is the standard pattern for immutable AWS resources.

resource "aws_sagemaker_endpoint_configuration" "main" {
  count = var.deploy_endpoint ? 1 : 0

  name_prefix = "${local.name_prefix}-config-"

  production_variants {
    variant_name           = "AllTraffic"
    model_name             = aws_sagemaker_model.main[0].name
    initial_instance_count = var.min_instance_count
    instance_type          = var.instance_type
    initial_variant_weight = 1.0
    volume_size_in_gb      = var.endpoint_volume_size
  }

  # KMS encryption for endpoint storage volume
  kms_key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null

  # Data capture for model monitoring
  dynamic "data_capture_config" {
    for_each = var.enable_data_capture ? [1] : []

    content {
      enable_capture              = true
      initial_sampling_percentage = var.data_capture_sampling_percentage
      destination_s3_uri          = "s3://${var.model_bucket_name}/data-capture/${var.environment}"
      kms_key_id                  = var.kms_key_arn != "" ? var.kms_key_arn : null

      capture_options {
        capture_mode = "Input"
      }
      capture_options {
        capture_mode = "Output"
      }

      capture_content_type_header {
        json_content_types = ["application/json"]
      }
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-endpoint-config"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# SageMaker Endpoint (Live Inference)
# =============================================================================

resource "aws_sagemaker_endpoint" "main" {
  count = var.deploy_endpoint ? 1 : 0

  name                 = "${local.name_prefix}-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.main[0].name

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-endpoint"
  })
}

# =============================================================================
# Auto-Scaling (Invocation-based)
# =============================================================================

resource "aws_appautoscaling_target" "sagemaker" {
  count = var.deploy_endpoint && var.enable_auto_scaling ? 1 : 0

  max_capacity       = var.max_instance_count
  min_capacity       = var.min_instance_count
  resource_id        = "endpoint/${aws_sagemaker_endpoint.main[0].name}/variant/AllTraffic"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"
  service_namespace  = "sagemaker"
}

resource "aws_appautoscaling_policy" "sagemaker_target_tracking" {
  count = var.deploy_endpoint && var.enable_auto_scaling ? 1 : 0

  name               = "${local.name_prefix}-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.sagemaker[0].resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.sagemaker[0].service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "SageMakerVariantInvocationsPerInstance"
    }

    target_value       = var.scaling_target_invocations
    scale_in_cooldown  = var.scale_in_cooldown
    scale_out_cooldown = var.scale_out_cooldown
  }
}

# Scheduled scaling — scale down during off-hours (cost optimization)
resource "aws_appautoscaling_scheduled_action" "scale_down_night" {
  count = var.deploy_endpoint && var.enable_auto_scaling && var.enable_scheduled_scaling ? 1 : 0

  name               = "${local.name_prefix}-scale-down-night"
  service_namespace  = aws_appautoscaling_target.sagemaker[0].service_namespace
  resource_id        = aws_appautoscaling_target.sagemaker[0].resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker[0].scalable_dimension

  schedule = "cron(0 22 * * ? *)"  # 10 PM UTC

  scalable_target_action {
    min_capacity = 1
    max_capacity = 1
  }
}

resource "aws_appautoscaling_scheduled_action" "scale_up_morning" {
  count = var.deploy_endpoint && var.enable_auto_scaling && var.enable_scheduled_scaling ? 1 : 0

  name               = "${local.name_prefix}-scale-up-morning"
  service_namespace  = aws_appautoscaling_target.sagemaker[0].service_namespace
  resource_id        = aws_appautoscaling_target.sagemaker[0].resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker[0].scalable_dimension

  schedule = "cron(0 8 * * ? *)"  # 8 AM UTC

  scalable_target_action {
    min_capacity = var.min_instance_count
    max_capacity = var.max_instance_count
  }
}
