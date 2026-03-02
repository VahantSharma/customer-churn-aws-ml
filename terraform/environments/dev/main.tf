# =============================================================================
# Dev Environment — Main Configuration
# =============================================================================
# Development settings optimised for cost and fast iteration:
#
# - KMS encryption on all resources (compliance parity with prod)
# - CloudTrail disabled (optional in dev to save cost)
# - Cheapest instance types, no auto-scaling, no multi-AZ NAT
# - Notebook enabled, endpoint disabled by default
# - Monitoring log groups created but alarms disabled
# - VPC Flow Logs enabled (minimal overhead)
# - Short log retention (7 days)
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
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

# =============================================================================
# Data Sources
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# Module: KMS — Customer-Managed Encryption Keys
# =============================================================================
# Must be provisioned FIRST — all other modules consume key ARNs.
# =============================================================================

module "kms" {
  source = "../../modules/kms"

  project_name            = var.project_name
  environment             = "dev"
  aws_account_id          = data.aws_caller_identity.current.account_id
  deletion_window_in_days = 7     # Shorter window for dev (minimum allowed)
  enable_key_rotation     = true  # Always rotate, even in dev
}

# =============================================================================
# Module: Security — CloudTrail & Audit
# =============================================================================

module "security" {
  source = "../../modules/security"

  project_name              = var.project_name
  environment               = "dev"
  aws_account_id            = data.aws_caller_identity.current.account_id
  enable_cloudtrail         = false   # Save ~$2/month in dev
  cloudtrail_s3_kms_key_arn = module.kms.s3_key_arn
  cloudwatch_kms_key_arn    = module.kms.cloudwatch_key_arn
}

# =============================================================================
# Module: Networking
# =============================================================================

module "networking" {
  source = "../../modules/networking"

  project_name           = var.project_name
  environment            = "dev"
  vpc_cidr               = "10.0.0.0/16"
  availability_zones     = var.availability_zones
  enable_vpc_endpoints   = false    # Save costs — S3 Gateway (free) still created
  single_nat_gateway     = true     # Save ~$32/month — single NAT is fine for dev
  enable_flow_logs       = true     # Minimal cost, critical for debugging
  flow_logs_retention_days = 7
  cloudwatch_kms_key_arn = module.kms.cloudwatch_key_arn
}

# =============================================================================
# Module: IAM
# =============================================================================

module "iam" {
  source = "../../modules/iam"

  project_name               = var.project_name
  environment                = "dev"
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
  environment        = "dev"
  aws_account_id     = data.aws_caller_identity.current.account_id
  enable_versioning  = false    # Save costs in dev
  force_destroy      = true     # Allow terraform destroy to delete non-empty buckets in dev
  sagemaker_role_arn = module.iam.sagemaker_execution_role_arn
  kms_key_arn        = module.kms.s3_key_arn
}

# =============================================================================
# Module: ECR
# =============================================================================

module "ecr" {
  source = "../../modules/ecr"

  project_name         = var.project_name
  environment          = "dev"
  image_tag_mutability = "MUTABLE"     # Allow overwriting tags in dev
  scan_on_push         = true
  kms_key_arn          = module.kms.s3_key_arn   # Reuse S3 key for ECR
}

# =============================================================================
# Module: SageMaker
# =============================================================================

module "sagemaker" {
  source = "../../modules/sagemaker"

  project_name                = var.project_name
  environment                 = "dev"
  sagemaker_execution_role_arn = module.iam.sagemaker_execution_role_arn
  model_artifact_s3_uri       = var.model_artifact_s3_uri
  inference_image_uri         = var.inference_image_uri != "" ? var.inference_image_uri : "${module.ecr.repository_url}:latest"
  vpc_id                      = module.networking.vpc_id
  private_subnet_ids          = module.networking.private_subnet_ids
  security_group_ids          = [module.networking.sagemaker_security_group_id]
  model_bucket_name           = module.s3.model_bucket_name
  kms_key_arn                 = module.kms.sagemaker_key_arn

  # Notebook
  create_notebook        = true
  notebook_instance_type = "ml.t3.medium"    # Cheapest
  notebook_volume_size   = 10
  notebook_idle_timeout  = 3600              # Auto-stop after 1 hour
  enable_direct_internet = true              # Needed in dev for pip installs

  # Endpoint (disabled by default in dev — enable when ready to test)
  deploy_endpoint    = var.deploy_endpoint
  instance_type      = "ml.t2.medium"
  min_instance_count = 1
  max_instance_count = 1

  # No auto-scaling, no data capture in dev
  enable_auto_scaling = false
  enable_data_capture = false
}

# =============================================================================
# Module: Monitoring
# =============================================================================

module "monitoring" {
  source = "../../modules/monitoring"

  project_name           = var.project_name
  environment            = "dev"
  endpoint_name          = module.sagemaker.endpoint_name
  alert_email            = var.alert_email
  enable_alarms          = false     # No alarm noise in dev
  log_retention_days     = 7         # Short retention to save costs
  sns_kms_key_arn        = module.kms.sns_key_arn
  cloudwatch_kms_key_arn = module.kms.cloudwatch_key_arn
}
