# =============================================================================
# Prod Environment — Main Configuration
# =============================================================================
# Full production-grade settings:
#
# - KMS CMK encryption on ALL resources (S3, CloudWatch, SNS, SageMaker)
# - CloudTrail with S3 data events for complete audit trail
# - HA networking: dual NAT (one per AZ), all VPC endpoints
# - VPC Flow Logs with 90-day retention
# - IMMUTABLE image tags, no force_delete on ECR
# - Full auto-scaling (2-5 instances), scheduled scaling at night
# - 100% data capture for model monitoring
# - All alarms + composite alarm + anomaly detection
# - 90-day log retention
# - 30-day KMS key deletion window
# =============================================================================

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "prod"
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

# =============================================================================
# Module: KMS — Customer-Managed Encryption Keys
# =============================================================================
# Provisioned FIRST — all downstream modules consume these key ARNs.
# 30-day deletion window in prod to prevent accidental key loss.
# =============================================================================

module "kms" {
  source = "../../modules/kms"

  project_name            = var.project_name
  environment             = "prod"
  aws_account_id          = data.aws_caller_identity.current.account_id
  deletion_window_in_days = 30    # Maximum protection for prod
  enable_key_rotation     = true
}

# =============================================================================
# Module: Security — CloudTrail & Audit
# =============================================================================
# Full audit trail with S3 data events for object-level tracking.
# CloudTrail logs encrypted with KMS and delivered to both S3 and CloudWatch.
# =============================================================================

module "security" {
  source = "../../modules/security"

  project_name                  = var.project_name
  environment                   = "prod"
  aws_account_id                = data.aws_caller_identity.current.account_id
  enable_cloudtrail             = true
  cloudtrail_s3_kms_key_arn     = module.kms.s3_key_arn
  cloudwatch_kms_key_arn        = module.kms.cloudwatch_key_arn
  cloudtrail_log_retention_days = 365    # 1 year retention for compliance
  trail_s3_bucket_expiration_days = 730  # 2 years before S3 expiry
  enable_data_events            = true   # Object-level S3 audit
  monitored_s3_bucket_arns      = [
    module.s3.data_bucket_arn,
    module.s3.model_bucket_arn
  ]
}

# =============================================================================
# Module: Networking
# =============================================================================

module "networking" {
  source = "../../modules/networking"

  project_name           = var.project_name
  environment            = "prod"
  vpc_cidr               = "10.2.0.0/16"    # Different CIDR from dev & staging
  availability_zones     = var.availability_zones
  enable_vpc_endpoints   = true              # All VPC endpoints
  single_nat_gateway     = false             # HA — one NAT per AZ
  enable_flow_logs       = true
  flow_logs_retention_days = 90              # Match log retention
  cloudwatch_kms_key_arn = module.kms.cloudwatch_key_arn
}

# =============================================================================
# Module: IAM
# =============================================================================

module "iam" {
  source = "../../modules/iam"

  project_name               = var.project_name
  environment                = "prod"
  data_bucket_arn            = module.s3.data_bucket_arn
  model_bucket_arn           = module.s3.model_bucket_arn
  ecr_repository_arn         = module.ecr.repository_arn
  github_repo                = var.github_repo
  terraform_state_bucket_arn = var.terraform_state_bucket_arn
  terraform_lock_table_arn   = var.terraform_lock_table_arn
  kms_s3_key_arn             = module.kms.s3_key_arn
  kms_sagemaker_key_arn      = module.kms.sagemaker_key_arn
}

# =============================================================================
# Module: S3
# =============================================================================

module "s3" {
  source = "../../modules/s3"

  project_name       = var.project_name
  environment        = "prod"
  aws_account_id     = data.aws_caller_identity.current.account_id
  enable_versioning  = true
  sagemaker_role_arn = module.iam.sagemaker_execution_role_arn
  kms_key_arn        = module.kms.s3_key_arn
}

# =============================================================================
# Module: ECR
# =============================================================================

module "ecr" {
  source = "../../modules/ecr"

  project_name         = var.project_name
  environment          = "prod"
  image_tag_mutability = "IMMUTABLE"
  scan_on_push         = true
  kms_key_arn          = module.kms.s3_key_arn
}

# =============================================================================
# Module: SageMaker
# =============================================================================

module "sagemaker" {
  source = "../../modules/sagemaker"

  project_name                = var.project_name
  environment                 = "prod"
  sagemaker_execution_role_arn = module.iam.sagemaker_execution_role_arn
  model_artifact_s3_uri       = var.model_artifact_s3_uri
  inference_image_uri         = var.inference_image_uri != "" ? var.inference_image_uri : "${module.ecr.repository_url}:latest"
  vpc_id                      = module.networking.vpc_id
  private_subnet_ids          = module.networking.private_subnet_ids
  security_group_ids          = [module.networking.sagemaker_security_group_id]
  model_bucket_name           = module.s3.model_bucket_name
  kms_key_arn                 = module.kms.sagemaker_key_arn

  # No notebook in prod
  create_notebook = false

  # Full production endpoint
  deploy_endpoint              = var.deploy_endpoint
  instance_type                = "ml.m5.xlarge"  # Production instance
  endpoint_volume_size         = 30              # 30GB for model artifacts
  min_instance_count           = 2               # Always 2 for HA
  max_instance_count           = 5               # Scale up to 5
  enable_auto_scaling          = true
  scaling_target_invocations   = 70
  scale_in_cooldown            = 300
  scale_out_cooldown           = 60

  # Full data capture for model monitoring
  enable_data_capture              = true
  data_capture_sampling_percentage = 100

  # Scale down at night, up in morning (cost optimization)
  enable_scheduled_scaling = true
  enable_direct_internet   = false
}

# =============================================================================
# Module: Monitoring
# =============================================================================

module "monitoring" {
  source = "../../modules/monitoring"

  project_name           = var.project_name
  environment            = "prod"
  endpoint_name          = module.sagemaker.endpoint_name
  alert_email            = var.alert_email
  enable_alarms          = true
  log_retention_days     = 90
  sns_kms_key_arn        = module.kms.sns_key_arn
  cloudwatch_kms_key_arn = module.kms.cloudwatch_key_arn

  # Tight production thresholds
  error_rate_threshold     = 1         # Any 5XX error triggers alarm
  latency_threshold_us     = 2000000   # 2 seconds P99
  cpu_threshold_percent    = 80
  memory_threshold_percent = 85
  disk_threshold_percent   = 80
}
