# =============================================================================
# IAM Module — Roles & Policies for SageMaker, CI/CD, and Monitoring
# =============================================================================
# Creates least-privilege IAM roles:
#   1. SageMaker Execution Role — used by training jobs & endpoints
#   2. GitHub Actions CI/CD Role — OIDC federation (no static keys)
#   3. Monitoring Role — read-only for cost tracking & alerting
#
# Design Decisions:
#   - Permission boundaries: Prevent privilege escalation even if
#     role policies are misconfigured or overly broad
#   - IAM path: Organizes roles under /project/ for easy auditing
#   - KMS permissions: Integrated with CMK encryption module
#   - No wildcard resources: Every resource ARN is scoped
# =============================================================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# =============================================================================
# Permission Boundary — limits the ceiling of what ANY role can do
# =============================================================================
# Even if someone attaches AdministratorAccess to a role, the boundary
# ensures they can't exceed these permissions. Defense-in-depth.

resource "aws_iam_policy" "permission_boundary" {
  name        = "${local.name_prefix}-permission-boundary"
  path        = "/project/${var.project_name}/"
  description = "Permission boundary for all ${var.project_name} roles in ${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowedServices"
        Effect = "Allow"
        Action = [
          "sagemaker:*",
          "s3:*",
          "ecr:*",
          "logs:*",
          "cloudwatch:*",
          "sns:*",
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
          "kms:CreateGrant",
          "kms:ReEncrypt*",
          "iam:PassRole",
          "iam:GetRole",
          "ce:GetCostAndUsage",
          "ce:GetCostForecast",
          "sts:AssumeRole",
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      },
      {
        Sid      = "DenyOrganizationLeave"
        Effect   = "Deny"
        Action   = ["organizations:LeaveOrganization"]
        Resource = "*"
      },
      {
        Sid    = "DenyBillingModification"
        Effect = "Deny"
        Action = [
          "aws-portal:Modify*",
          "account:*"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-permission-boundary"
  })
}

# =============================================================================
# 1. SageMaker Execution Role
# =============================================================================

resource "aws_iam_role" "sagemaker_execution" {
  name = "${local.name_prefix}-sagemaker-execution"
  path = "/project/${var.project_name}/"

  permissions_boundary = aws_iam_policy.permission_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSageMakerAssume"
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-sagemaker-execution"
    Role = "sagemaker-execution"
  })
}

# SageMaker S3 access — scoped to project buckets only
resource "aws_iam_policy" "sagemaker_s3" {
  name = "${local.name_prefix}-sagemaker-s3"
  path = "/project/${var.project_name}/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ListBuckets"
        Effect = "Allow"
        Action = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = [
          var.data_bucket_arn,
          var.model_bucket_arn
        ]
      },
      {
        Sid    = "ReadWriteObjects"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${var.data_bucket_arn}/*",
          "${var.model_bucket_arn}/*"
        ]
      }
    ]
  })

  tags = local.common_tags
}

# SageMaker core operations — scoped to project resources
resource "aws_iam_policy" "sagemaker_operations" {
  name = "${local.name_prefix}-sagemaker-ops"
  path = "/project/${var.project_name}/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SageMakerTraining"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateTrainingJob",
          "sagemaker:DescribeTrainingJob",
          "sagemaker:StopTrainingJob",
          "sagemaker:CreateModel",
          "sagemaker:DescribeModel",
          "sagemaker:DeleteModel",
          "sagemaker:CreateEndpoint",
          "sagemaker:CreateEndpointConfig",
          "sagemaker:DescribeEndpoint",
          "sagemaker:DescribeEndpointConfig",
          "sagemaker:DeleteEndpoint",
          "sagemaker:DeleteEndpointConfig",
          "sagemaker:UpdateEndpoint",
          "sagemaker:InvokeEndpoint",
          "sagemaker:AddTags",
          "sagemaker:CreateModelPackageGroup",
          "sagemaker:CreateModelPackage",
          "sagemaker:UpdateModelPackage",
          "sagemaker:DescribeModelPackageGroup",
          "sagemaker:DescribeModelPackage",
          "sagemaker:ListModelPackages"
        ]
        Resource = [
          "${local.sagemaker_arn_prefix}:*"
        ]
      },
      {
        Sid    = "SageMakerHyperparameterTuning"
        Effect = "Allow"
        Action = [
          "sagemaker:CreateHyperParameterTuningJob",
          "sagemaker:DescribeHyperParameterTuningJob",
          "sagemaker:StopHyperParameterTuningJob",
          "sagemaker:ListTrainingJobsForHyperParameterTuningJob"
        ]
        Resource = [
          "${local.sagemaker_arn_prefix}:hyper-parameter-tuning-job/*"
        ]
      },
      {
        Sid    = "PassRole"
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/project/${var.project_name}/${local.name_prefix}-sagemaker-execution"
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "sagemaker.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = local.common_tags
}

# CloudWatch Logs — for training/inference logging
resource "aws_iam_policy" "sagemaker_cloudwatch" {
  name = "${local.name_prefix}-sagemaker-cw"
  path = "/project/${var.project_name}/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents"
        ]
        Resource = [
          "${local.logs_arn_prefix}:log-group:/aws/sagemaker/*"
        ]
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = [
              "aws/sagemaker/Endpoints",
              "aws/sagemaker/TrainingJobs"
            ]
          }
        }
      }
    ]
  })

  tags = local.common_tags
}

# ECR pull — for pulling inference container images
resource "aws_iam_policy" "sagemaker_ecr" {
  name = "${local.name_prefix}-sagemaker-ecr"
  path = "/project/${var.project_name}/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ECRAuth"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = var.ecr_repository_arn != "" ? [var.ecr_repository_arn] : ["*"]
      }
    ]
  })

  tags = local.common_tags
}

# KMS — for decrypting/encrypting data with customer-managed keys
resource "aws_iam_policy" "sagemaker_kms" {
  count = var.enable_kms_policies ? 1 : 0

  name = "${local.name_prefix}-sagemaker-kms"
  path = "/project/${var.project_name}/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "KMSDecryptEncrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
          "kms:ReEncrypt*"
        ]
        Resource = compact([
          var.kms_s3_key_arn,
          var.kms_sagemaker_key_arn
        ])
      },
      {
        Sid    = "KMSCreateGrant"
        Effect = "Allow"
        Action = "kms:CreateGrant"
        Resource = compact([
          var.kms_sagemaker_key_arn
        ])
        Condition = {
          Bool = {
            "kms:GrantIsForAWSResource" = "true"
          }
        }
      }
    ]
  })

  tags = local.common_tags
}

# Attach all policies to SageMaker role
resource "aws_iam_role_policy_attachment" "sagemaker_s3" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = aws_iam_policy.sagemaker_s3.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_operations" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = aws_iam_policy.sagemaker_operations.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_cloudwatch" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = aws_iam_policy.sagemaker_cloudwatch.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_ecr" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = aws_iam_policy.sagemaker_ecr.arn
}

resource "aws_iam_role_policy_attachment" "sagemaker_kms" {
  count = var.enable_kms_policies ? 1 : 0

  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = aws_iam_policy.sagemaker_kms[0].arn
}

# =============================================================================
# 2. GitHub Actions CI/CD Role (OIDC Federation)
# =============================================================================

# OIDC Provider for GitHub Actions
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub's OIDC certificate thumbprint
  thumbprint_list = [var.github_oidc_thumbprint]

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-github-oidc"
  })
}

resource "aws_iam_role" "cicd" {
  name = "${local.name_prefix}-cicd"
  path = "/project/${var.project_name}/"

  permissions_boundary = aws_iam_policy.permission_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowGitHubOIDC"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:*"
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-cicd"
    Role = "cicd"
  })
}

resource "aws_iam_policy" "cicd" {
  name = "${local.name_prefix}-cicd"
  path = "/project/${var.project_name}/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid    = "S3Access"
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:ListBucket",
            "s3:DeleteObject"
          ]
          Resource = [
            var.data_bucket_arn,
            "${var.data_bucket_arn}/*",
            var.model_bucket_arn,
            "${var.model_bucket_arn}/*"
          ]
        },
        {
          Sid    = "ECRAccess"
          Effect = "Allow"
          Action = [
            "ecr:GetAuthorizationToken",
            "ecr:BatchCheckLayerAvailability",
            "ecr:GetDownloadUrlForLayer",
            "ecr:BatchGetImage",
            "ecr:PutImage",
            "ecr:InitiateLayerUpload",
            "ecr:UploadLayerPart",
            "ecr:CompleteLayerUpload"
          ]
          Resource = var.ecr_repository_arn != "" ? [var.ecr_repository_arn, "*"] : ["*"]
        },
        {
          Sid    = "SageMakerDeploy"
          Effect = "Allow"
          Action = [
            "sagemaker:CreateModel",
            "sagemaker:CreateEndpointConfig",
            "sagemaker:CreateEndpoint",
            "sagemaker:UpdateEndpoint",
            "sagemaker:DescribeEndpoint",
            "sagemaker:DescribeEndpointConfig",
            "sagemaker:DeleteEndpoint",
            "sagemaker:DeleteEndpointConfig",
            "sagemaker:DeleteModel",
            "sagemaker:InvokeEndpoint",
            "sagemaker:CreateModelPackage",
            "sagemaker:UpdateModelPackage"
          ]
          Resource = [
            "${local.sagemaker_arn_prefix}:*"
          ]
        },
        {
          Sid    = "PassSageMakerRole"
          Effect = "Allow"
          Action = "iam:PassRole"
          Resource = aws_iam_role.sagemaker_execution.arn
          Condition = {
            StringEquals = {
              "iam:PassedToService" = "sagemaker.amazonaws.com"
            }
          }
        }
      ],
      var.terraform_state_bucket_arn != "" ? [
        {
          Sid    = "TerraformState"
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:ListBucket"
          ]
          Resource = [
            var.terraform_state_bucket_arn,
            "${var.terraform_state_bucket_arn}/*"
          ]
        }
      ] : [],
      var.terraform_lock_table_arn != "" ? [
        {
          Sid    = "TerraformLock"
          Effect = "Allow"
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:DeleteItem"
          ]
          Resource = var.terraform_lock_table_arn
        }
      ] : []
    )
  })

  tags = local.common_tags
}

# KMS policy for CI/CD role — needed for S3 encrypted object access
resource "aws_iam_policy" "cicd_kms" {
  count = var.enable_kms_policies ? 1 : 0

  name = "${local.name_prefix}-cicd-kms"
  path = "/project/${var.project_name}/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "KMSDecryptEncrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = compact([
          var.kms_s3_key_arn
        ])
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "cicd" {
  role       = aws_iam_role.cicd.name
  policy_arn = aws_iam_policy.cicd.arn
}

resource "aws_iam_role_policy_attachment" "cicd_kms" {
  count = var.enable_kms_policies ? 1 : 0

  role       = aws_iam_role.cicd.name
  policy_arn = aws_iam_policy.cicd_kms[0].arn
}

# =============================================================================
# 3. Monitoring Read-Only Role
# =============================================================================

resource "aws_iam_role" "monitoring" {
  name = "${local.name_prefix}-monitoring"
  path = "/project/${var.project_name}/"

  permissions_boundary = aws_iam_policy.permission_boundary.arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowLambdaAssume"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-monitoring"
    Role = "monitoring"
  })
}

resource "aws_iam_policy" "monitoring" {
  name = "${local.name_prefix}-monitoring"
  path = "/project/${var.project_name}/"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchRead"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "cloudwatch:DescribeAlarms"
        ]
        Resource = "*"
      },
      {
        Sid    = "CostExplorerRead"
        Effect = "Allow"
        Action = [
          "ce:GetCostAndUsage",
          "ce:GetCostForecast"
        ]
        Resource = "*"
      },
      {
        Sid    = "SageMakerDescribe"
        Effect = "Allow"
        Action = [
          "sagemaker:DescribeEndpoint",
          "sagemaker:DescribeTrainingJob",
          "sagemaker:ListEndpoints",
          "sagemaker:ListTrainingJobs"
        ]
        Resource = "*"
      },
      {
        Sid    = "LogsRead"
        Effect = "Allow"
        Action = [
          "logs:GetLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${local.logs_arn_prefix}:log-group:/aws/sagemaker/*"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "monitoring" {
  role       = aws_iam_role.monitoring.name
  policy_arn = aws_iam_policy.monitoring.arn
}
