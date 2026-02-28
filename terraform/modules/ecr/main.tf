# =============================================================================
# ECR Module — Container Registry for Docker Images
# =============================================================================
# Stores FastAPI Docker images built by CI/CD.
# Scan-on-push detects CVEs. Lifecycle policy prunes old images.
# KMS encryption for image layers at rest.
# =============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  use_kms     = var.kms_key_arn != ""

  common_tags = {
    Module      = "ecr"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_ecr_repository" "main" {
  name                 = "${local.name_prefix}"
  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  encryption_configuration {
    encryption_type = local.use_kms ? "KMS" : "AES256"
    kms_key         = local.use_kms ? var.kms_key_arn : null
  }

  force_delete = var.environment != "prod"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}"
  })
}

# ============================================================================
# Lifecycle Policy — Auto-prune old images to control costs
# ============================================================================

resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 release images (tagged v*)"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v"]
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 3 dev images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["dev-"]
          countType     = "imageCountMoreThan"
          countNumber   = 3
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 3
        description  = "Delete untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 4
        description  = "Delete ANY image older than 90 days"
        selection = {
          tagStatus   = "any"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 90
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ============================================================================
# Repository Policy — Who can push/pull
# ============================================================================

resource "aws_ecr_repository_policy" "main" {
  count      = var.allowed_account_ids != null ? 1 : 0
  repository = aws_ecr_repository.main.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowPull"
        Effect = "Allow"
        Principal = {
          AWS = [for id in var.allowed_account_ids : "arn:aws:iam::${id}:root"]
        }
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
      }
    ]
  })
}
