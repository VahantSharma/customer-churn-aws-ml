# =============================================================================
# Staging Environment — Main Configuration
# =============================================================================
# Production-like settings with moderate resources:
#
# - KMS encryption on all resources (parity with prod)
# - CloudTrail enabled for audit compliance testing
# - VPC Endpoints enabled, VPC Flow Logs on
# - Single NAT Gateway (cost compromise)
# - IMMUTABLE image tags, auto-scaling enabled
# - Data capture for model monitoring
# - Alarms ON (validates alert configs before prod)
# - 30-day log retention
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
      Environment = "staging"
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

# =============================================================================
# Module: KMS — Customer-Managed Encryption Keys
# =============================================================================

module "kms" {
  source = "../../modules/kms"

  project_name            = var.project_name
  environment             = "staging"
  aws_account_id          = data.aws_caller_identity.current.account_id
  deletion_window_in_days = 14    # Moderate window for staging
  enable_key_rotation     = true
}

# =============================================================================
# Module: Security — CloudTrail & Audit
# =============================================================================

module "security" {
  source = "../../modules/security"

  project_name                = var.project_name
  environment                 = "staging"
  aws_account_id              = data.aws_caller_identity.current.account_id
  enable_cloudtrail           = true
  cloudtrail_s3_kms_key_arn   = module.kms.s3_key_arn
  cloudwatch_kms_key_arn      = module.kms.cloudwatch_key_arn
  cloudtrail_log_retention_days = 30
  enable_data_events          = false   # Enable in prod only (adds cost)
  monitored_s3_bucket_arns    = [
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
  environment            = "staging"
  vpc_cidr               = "10.1.0.0/16"    # Different CIDR from dev
  availability_zones     = var.availability_zones
  enable_vpc_endpoints   = true              # Enable all VPC endpoints
  single_nat_gateway     = true              # Still single NAT for staging
  enable_flow_logs       = true
  flow_logs_retention_days = 14
  cloudwatch_kms_key_arn = module.kms.cloudwatch_key_arn
}

# =============================================================================
# Module: IAM
# =============================================================================

module "iam" {
  source = "../../modules/iam"

  project_name               = var.project_name
  environment                = "staging"
  data_bucket_arn            = module.s3.data_bucket_arn
  model_bucket_arn           = module.s3.model_bucket_arn
  ecr_repository_arn         = module.ecr.repository_arn
  github_repo                = var.github_repo
  terraform_state_bucket_arn = var.terraform_state_bucket_arn
  terraform_lock_table_arn   = var.terraform_lock_table_arn
  kms_s3_key_arn             = module.kms.s3_key_arn
  kms_sagemaker_key_arn      = module.kms.sagemaker_key_arn
  enable_kms_policies        = true
}

# =============================================================================
# Module: S3
# =============================================================================

module "s3" {
  source = "../../modules/s3"

  project_name       = var.project_name
  environment        = "staging"
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
  environment          = "staging"
  image_tag_mutability = "IMMUTABLE"    # No overwriting tags in staging
  scan_on_push         = true
  kms_key_arn          = module.kms.s3_key_arn
}

# =============================================================================
# Module: SageMaker
# =============================================================================

module "sagemaker" {
  source = "../../modules/sagemaker"

  project_name                = var.project_name
  environment                 = "staging"
  sagemaker_execution_role_arn = module.iam.sagemaker_execution_role_arn
  model_artifact_s3_uri       = var.model_artifact_s3_uri
  inference_image_uri         = var.inference_image_uri != "" ? var.inference_image_uri : "${module.ecr.repository_url}:latest"
  vpc_id                      = module.networking.vpc_id
  private_subnet_ids          = module.networking.private_subnet_ids
  security_group_ids          = [module.networking.sagemaker_security_group_id]
  model_bucket_name           = module.s3.model_bucket_name
  kms_key_arn                 = module.kms.sagemaker_key_arn

  create_notebook        = false          # No notebook in staging
  deploy_endpoint        = var.deploy_endpoint
  instance_type          = "ml.m5.large"  # Production-grade
  min_instance_count     = 1
  max_instance_count     = 2
  enable_auto_scaling    = true
  enable_data_capture    = true           # Monitor model inputs/outputs
  enable_direct_internet = false
}

# =============================================================================
# Module: Monitoring
# =============================================================================

module "monitoring" {
  source = "../../modules/monitoring"

  project_name           = var.project_name
  environment            = "staging"
  endpoint_name          = module.sagemaker.endpoint_name
  alert_email            = var.alert_email
  enable_alarms          = true              # Alarms ON in staging
  log_retention_days     = 30
  sns_kms_key_arn        = module.kms.sns_key_arn
  cloudwatch_kms_key_arn = module.kms.cloudwatch_key_arn

  # Slightly relaxed thresholds vs prod
  error_rate_threshold     = 3
  latency_threshold_us     = 3000000   # 3 seconds
  cpu_threshold_percent    = 85
  memory_threshold_percent = 90
  disk_threshold_percent   = 85
}
