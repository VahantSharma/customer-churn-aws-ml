# Terraform Implementation Plan — Production-Grade ML Infrastructure

## Table of Contents

1. [Architecture Philosophy](#1-architecture-philosophy)
2. [Module Dependency Graph](#2-module-dependency-graph)
3. [Directory Structure](#3-directory-structure)
4. [Production-Grade Standards](#4-production-grade-standards)
5. [Step 0: Bootstrap — Terraform Backend](#step-0-bootstrap--terraform-backend)
6. [Step 1: KMS Module (Encryption Foundation)](#step-1-kms-module)
7. [Step 2: Networking Module (VPC)](#step-2-networking-module-vpc)
8. [Step 3: IAM Module](#step-3-iam-module)
9. [Step 4: S3 Module](#step-4-s3-module)
10. [Step 5: ECR Module](#step-5-ecr-module)
11. [Step 6: SageMaker Module](#step-6-sagemaker-module)
12. [Step 7: Monitoring Module](#step-7-monitoring-module)
13. [Step 8: Security & Audit Module](#step-8-security--audit-module)
14. [Environment Configuration (dev/staging/prod)](#environment-configuration)
15. [How Modules Connect (Data Flow)](#how-modules-connect)
16. [Execution Sequence](#execution-sequence)
17. [CI/CD Integration](#cicd-integration)
18. [What Makes This Production-Grade](#what-makes-this-production-grade)
19. [Interview Talking Points](#interview-talking-points)

---

## 1. Architecture Philosophy

### Design Principles

This Terraform implementation follows **5 pillars** of production-grade infrastructure:

| Pillar                     | Implementation                                                                                                                                                                         |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Security**               | KMS CMK encryption everywhere, VPC flow logs, CloudTrail audit, permission boundaries on IAM, least-privilege policies scoped to exact ARNs, OIDC federation (zero static credentials) |
| **Reliability**            | Multi-AZ networking, auto-scaling with scheduled actions, S3 versioning for model rollback, DynamoDB PITR for state recovery, `prevent_destroy` on critical resources                  |
| **Cost Optimization**      | Per-environment right-sizing (dev=cheapest), scheduled scale-down at night, S3 lifecycle tiering (Standard → IA → Glacier), single NAT in dev, auto-stop notebooks                     |
| **Operational Excellence** | Centralized naming via `locals.tf`, consistent tagging for cost allocation, `versions.tf` in every module, `.tflint.hcl` for linting, comprehensive variable validation                |
| **Compliance**             | Encryption at rest (KMS) + in transit (TLS), S3 access logging, VPC flow logs, CloudTrail, deny-unencrypted-upload bucket policies, no public access on any resource                   |

### Why This Is Different From "Tutorial" Terraform

- **Every S3 bucket uses KMS CMK** — not default AES256 (audit trail on key usage)
- **Every module has `versions.tf`** — pinned provider constraints prevent breaking upgrades
- **`locals.tf` for naming** — no string interpolation scattered across resources
- **Variable validation blocks** — catch config errors at `plan` time, not `apply` time
- **No `timestamp()` in resource names** — eliminates plan drift (a real production bug)
- **VPC Flow Logs** — required by SOC2/HIPAA, captures all network traffic metadata
- **CloudTrail** — complete API audit trail for compliance
- **Permission boundaries** — defense-in-depth, limits even admin mistakes

---

## 2. Module Dependency Graph

```
                    ┌─────────────────┐
                    │   BOOTSTRAP     │  ← Run once (local state)
                    │   S3 + DynamoDB │     KMS-encrypted state bucket
                    │   for TF state  │     Point-in-time recovery enabled
                    └────────┬────────┘
                             │
              ┌──────────────▼──────────────┐
              │          KMS MODULE          │  ← Must come FIRST
              │                              │    Creates CMK keys for:
              │  S3 Key │ CW Key │ SNS Key   │    S3, CloudWatch, SNS, SageMaker
              │  SageMaker Key │ Secrets Key │
              └──────────────┬──────────────┘
                             │
                    ┌────────▼────────┐
                    │   NETWORKING    │  ← VPC with flow logs
                    │   VPC, Subnets  │    NACLs, private subnets
                    │   NAT, SGs,     │    VPC endpoints (S3, ECR,
                    │   VPC Endpoints │    SageMaker, CloudWatch)
                    │   Flow Logs     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼────┐  ┌─────▼──────┐  ┌───▼────────┐
     │    IAM      │  │    S3      │  │   ECR      │
     │             │  │            │  │            │
     │ SageMaker   │  │ Data (KMS) │  │ Docker     │
     │ Exec Role   │  │ Model (KMS)│  │ Registry   │
     │ CI/CD OIDC  │  │ Access Log │  │ Scanning   │
     │ Monitoring  │  │ Lifecycle  │  │ Lifecycle  │
     │ Permission  │  │            │  │            │
     │ Boundaries  │  │            │  │            │
     └──────┬──────┘  └─────┬──────┘  └─────┬─────┘
            │               │               │
            │    ┌──────────┼───────────────┘
            │    │          │
     ┌──────▼────▼──────────▼──┐
     │       SAGEMAKER         │
     │                         │
     │  Notebook (auto-stop)   │
     │  Model Registry         │
     │  Endpoint (blue-green)  │
     │  Auto-Scaling (target)  │
     │  Scheduled Scaling      │
     │  Data Capture           │
     └────────────┬────────────┘
                  │
     ┌────────────▼────────────┐
     │      MONITORING         │
     │                         │
     │  CloudWatch Dashboard   │
     │  Metric Alarms          │
     │  Composite Alarms       │
     │  Anomaly Detection      │
     │  SNS (KMS encrypted)    │
     │  Log Groups (KMS)       │
     └────────────┬────────────┘
                  │
     ┌────────────▼────────────┐
     │   SECURITY & AUDIT      │
     │                         │
     │  CloudTrail (KMS)       │
     │  S3 Access Logging      │
     │  VPC Flow Logs          │
     │  Config Rules           │
     └─────────────────────────┘
```

---

## 3. Directory Structure

```
terraform/
│
├── .terraform-version              # tfenv version pin (1.6.0)
├── .tflint.hcl                     # Linting rules (enforced in CI)
├── terraform.tfvars.example        # Example vars (committed to git)
├── README.md                       # Infrastructure documentation
│
├── backend/                        # Step 0: Bootstrap (run ONCE)
│   ├── main.tf                     # S3 + DynamoDB + KMS for state
│   ├── variables.tf                # Bootstrap inputs
│   └── outputs.tf                  # State bucket name, lock table
│
├── modules/                        # Reusable infrastructure components
│   │
│   ├── kms/                        # Encryption keys (foundation layer)
│   │   ├── versions.tf             # Provider constraints
│   │   ├── variables.tf            # Key aliases, rotation config
│   │   ├── main.tf                 # CMK keys + key policies
│   │   └── outputs.tf              # Key ARNs, key IDs
│   │
│   ├── networking/                 # Network isolation layer
│   │   ├── versions.tf
│   │   ├── locals.tf               # Naming conventions
│   │   ├── variables.tf            # CIDR, AZs, endpoint toggles
│   │   ├── main.tf                 # VPC, subnets, NAT, SGs, endpoints
│   │   ├── flow_logs.tf            # VPC Flow Logs (compliance)
│   │   └── outputs.tf              # VPC ID, subnet IDs, SG IDs
│   │
│   ├── iam/                        # Identity & access management
│   │   ├── versions.tf
│   │   ├── locals.tf               # Policy documents as locals
│   │   ├── variables.tf            # Bucket ARNs, repo ARN, GitHub
│   │   ├── main.tf                 # Roles, policies, OIDC, boundaries
│   │   └── outputs.tf              # Role ARNs
│   │
│   ├── s3/                         # Data & model storage
│   │   ├── versions.tf
│   │   ├── locals.tf               # Bucket naming
│   │   ├── variables.tf            # Versioning, KMS, lifecycle
│   │   ├── main.tf                 # Buckets, policies, logging, lifecycle
│   │   └── outputs.tf              # Bucket names, ARNs, domains
│   │
│   ├── ecr/                        # Container image registry
│   │   ├── versions.tf
│   │   ├── variables.tf            # Mutability, scanning, retention
│   │   ├── main.tf                 # ECR repo, lifecycle, scanning
│   │   └── outputs.tf              # Repo URL, ARN
│   │
│   ├── sagemaker/                  # ML inference & training
│   │   ├── versions.tf
│   │   ├── locals.tf               # Resource naming, tags
│   │   ├── variables.tf            # Instance types, scaling, capture
│   │   ├── main.tf                 # Model, endpoint, auto-scaling
│   │   └── outputs.tf              # Endpoint name, ARN, notebook URL
│   │
│   ├── monitoring/                 # Observability & alerting
│   │   ├── versions.tf
│   │   ├── locals.tf               # Dashboard JSON extraction
│   │   ├── variables.tf            # Thresholds, retention, email
│   │   ├── main.tf                 # Dashboard, alarms, SNS, logs
│   │   └── outputs.tf              # Dashboard name, SNS ARN
│   │
│   └── security/                   # Audit & compliance
│       ├── versions.tf
│       ├── variables.tf            # Trail name, log retention
│       ├── main.tf                 # CloudTrail, Config rules
│       └── outputs.tf              # Trail ARN, log bucket
│
└── environments/                   # Per-environment orchestration
    ├── dev/
    │   ├── main.tf                 # All module calls (dev config)
    │   ├── variables.tf            # Variable declarations
    │   ├── terraform.tfvars        # Dev-specific values
    │   ├── outputs.tf              # Environment outputs
    │   └── backend.tf              # Remote state (dev key path)
    │
    ├── staging/
    │   └── ... (same 5 files, staging-tuned values)
    │
    └── prod/
        └── ... (same 5 files, production-hardened values)
```

### Key Principles

- **Every module has `versions.tf`** — provider constraints at module level
- **`locals.tf` for naming** — `"${var.project_name}-${var.environment}-resource"` defined once
- **Modules are generic** — zero hardcoded values, everything parameterized
- **Environments are thin** — just module calls with env-specific variable values
- **Security is layered** — KMS foundation → networking isolation → IAM policies → monitoring → audit trail

---

## 4. Production-Grade Standards

Every module adheres to these standards:

### A. Variable Validation

```hcl
variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}
```

### B. Consistent Tagging via Locals

```hcl
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Module      = "networking"
  }
}
```

### C. Provider Pinning (versions.tf)

```hcl
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}
```

### D. Encryption Everywhere

- S3 buckets → KMS CMK (not default AES256)
- CloudWatch Log Groups → KMS CMK
- SNS Topics → KMS CMK
- SageMaker volumes → KMS CMK
- Terraform state → KMS CMK

### E. No Drift-Causing Functions

```hcl
# BAD — causes plan diff on every run
name = "config-${formatdate("YYYYMMDDhhmmss", timestamp())}"

# GOOD — deterministic, no drift
name = "${local.name_prefix}-endpoint-config"
lifecycle { create_before_destroy = true }
```

---

## Step 0: Bootstrap — Terraform Backend

### What This Is

Before Terraform can manage your infrastructure, it needs a place to store its **state file** (`terraform.tfstate`). This file tracks what resources Terraform has created. Without it, Terraform doesn't know what already exists.

### The Chicken-and-Egg Problem

The state bucket itself is an AWS resource. But we can't store state for it because... it doesn't exist yet. Solution: **bootstrap** — create the state bucket manually (or with a one-time Terraform run using local state), then migrate.

### Resources Created

| Resource               | Terraform Type                                       | Purpose                                   |
| ---------------------- | ---------------------------------------------------- | ----------------------------------------- |
| S3 Bucket              | `aws_s3_bucket`                                      | Stores `terraform.tfstate`                |
| S3 Bucket Versioning   | `aws_s3_bucket_versioning`                           | State version history (rollback)          |
| S3 Bucket Encryption   | `aws_s3_bucket_server_side_encryption_configuration` | Encrypt state at rest                     |
| S3 Public Access Block | `aws_s3_bucket_public_access_block`                  | Block ALL public access                   |
| DynamoDB Table         | `aws_dynamodb_table`                                 | State locking (prevent concurrent writes) |

### Terraform Code

```hcl
# terraform/backend/main.tf

terraform {
  required_version = ">= 1.5.0"
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
      Project     = "customer-churn-prediction"
      ManagedBy   = "terraform"
      Environment = "shared"
    }
  }
}

# --- S3 Bucket for Terraform State ---
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.project_name}-terraform-state-${var.aws_account_id}"

  # Prevent accidental deletion
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- DynamoDB Table for State Locking ---
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "${var.project_name}-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"   # Free tier covers this
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }
}
```

### How to Run (One-Time)

```bash
cd terraform/backend
terraform init                    # Uses local state (no backend yet)
terraform plan                    # Preview what will be created
terraform apply                   # Create the bucket + DynamoDB

# Output: bucket name and DynamoDB table name
# Use these in backend.tf for all environments
```

### How Other Environments Reference This Backend

```hcl
# terraform/environments/dev/backend.tf
terraform {
  backend "s3" {
    bucket         = "customer-churn-terraform-state-231284356634"
    key            = "environments/dev/terraform.tfstate"    # Unique per env!
    region         = "us-east-1"
    dynamodb_table = "customer-churn-terraform-locks"
    encrypt        = true
  }
}
```

> **CRITICAL:** Each environment uses a different `key` path so they have separate state files. Dev changes NEVER affect prod state.

---

## Step 1: Networking Module (VPC)

### Why This Exists

By default, SageMaker resources run in AWS's shared default VPC. This is:

- **Not secure** — other AWS accounts share the same network space
- **Not configurable** — can't add firewall rules, private subnets, or VPC endpoints
- **Not reproducible** — default VPC varies by region/account

### Resources Created

| Resource                        | Terraform Type                 | Purpose                                                  |
| ------------------------------- | ------------------------------ | -------------------------------------------------------- |
| VPC                             | `aws_vpc`                      | Isolated network for all resources                       |
| Public Subnets (2)              | `aws_subnet`                   | NAT Gateway, load balancers (if needed)                  |
| Private Subnets (2)             | `aws_subnet`                   | SageMaker endpoints, training jobs                       |
| Internet Gateway                | `aws_internet_gateway`         | Public subnet internet access                            |
| NAT Gateway                     | `aws_nat_gateway`              | Private subnet outbound internet (pulling Docker images) |
| Elastic IP                      | `aws_eip`                      | Static IP for NAT Gateway                                |
| Route Tables (2)                | `aws_route_table`              | Public → IGW, Private → NAT                              |
| Security Group: SageMaker       | `aws_security_group`           | Controls what can talk to SageMaker                      |
| Security Group: VPC Endpoints   | `aws_security_group`           | Controls VPC endpoint access                             |
| VPC Endpoint: S3                | `aws_vpc_endpoint` (Gateway)   | S3 traffic stays in AWS network                          |
| VPC Endpoint: SageMaker API     | `aws_vpc_endpoint` (Interface) | SageMaker API calls stay private                         |
| VPC Endpoint: SageMaker Runtime | `aws_vpc_endpoint` (Interface) | Inference calls stay private                             |
| VPC Endpoint: CloudWatch Logs   | `aws_vpc_endpoint` (Interface) | Log shipping stays private                               |
| VPC Endpoint: ECR               | `aws_vpc_endpoint` (Interface) | Docker pulls stay private                                |

### How Data Flows Through the VPC

```
                         INTERNET
                            │
                    ┌───────▼───────┐
                    │ Internet      │
                    │ Gateway       │
                    └───────┬───────┘
                            │
              ┌─────────────┴─────────────┐
              │      PUBLIC SUBNETS        │
              │                           │
              │  ┌─────────┐ ┌─────────┐ │
              │  │ NAT GW  │ │ (ALB if │ │
              │  │         │ │ needed) │ │
              │  └────┬────┘ └─────────┘ │
              └───────┼───────────────────┘
                      │
              ┌───────▼───────────────────┐
              │      PRIVATE SUBNETS       │
              │                           │
              │  ┌──────────────────────┐ │
              │  │  SageMaker Endpoint  │ │  ◄── No public IP
              │  │  SageMaker Training  │ │      Internet via NAT only
              │  │  SageMaker Notebook  │ │
              │  └──────────────────────┘ │
              │                           │
              │  ┌──────────────────────┐ │
              │  │  VPC Endpoints       │ │  ◄── S3, ECR, CloudWatch
              │  │  (Private Links)     │ │      Traffic never leaves AWS
              │  └──────────────────────┘ │
              └───────────────────────────┘
```

### Key Design Decisions

**Why 2 subnets per type?**

- AWS requires subnets in ≥2 Availability Zones for high availability
- If `us-east-1a` goes down, resources in `us-east-1b` keep running

**Why NAT Gateway instead of just Internet Gateway?**

- Private subnets need outbound internet access (e.g., pulling pip packages during training)
- NAT allows outbound, but prevents inbound — attackers can't reach private resources
- In dev, we can use a single NAT to save costs ($0.045/hr + data transfer)

**Why VPC Endpoints?**

- Without them: SageMaker → Internet → S3 (slow, costs data transfer fees, exposd to public internet)
- With them: SageMaker → Private Link → S3 (fast, free, never leaves AWS network)
- S3 Gateway endpoint is **free**. Interface endpoints cost ~$0.01/hr each

**Dev vs Prod networking differences:**

| Component            | Dev                 | Prod                      |
| -------------------- | ------------------- | ------------------------- |
| NAT Gateways         | 1 (saves $32/month) | 2 (HA across AZs)         |
| VPC Endpoints        | S3 only (free)      | S3 + SageMaker + ECR + CW |
| Security Group rules | Allow all internal  | Strict per-service        |

### Module Interface

```hcl
# --- INPUTS (variables.tf) ---
variable "project_name" {}       # "customer-churn"
variable "environment" {}        # "dev" / "staging" / "prod"
variable "vpc_cidr" {}           # "10.0.0.0/16"
variable "availability_zones" {} # ["us-east-1a", "us-east-1b"]
variable "enable_vpc_endpoints" {} # true/false (false for dev)
variable "single_nat_gateway" {}   # true for dev, false for prod

# --- OUTPUTS (outputs.tf) ---
output "vpc_id" {}
output "private_subnet_ids" {}
output "public_subnet_ids" {}
output "sagemaker_security_group_id" {}
output "vpc_endpoint_security_group_id" {}
```

---

## Step 2: IAM Module

### Why This Exists

The current project uses a manually created IAM role with `sagemaker-iam-policy.json` that has **wildcard permissions on MLflow** (`"Resource": "*"`). We need proper, scoped, least-privilege roles managed as code.

### Roles to Create

#### Role 1: SageMaker Execution Role

**Used by:** SageMaker training jobs and endpoints.
**Trust policy:** Only SageMaker service can assume this role.

```
WHO can assume it:    sagemaker.amazonaws.com
WHAT it can do:
├── S3:      Read/write to OUR data + model buckets only
├── ECR:     Pull images from OUR repository only
├── CW Logs: Create log groups + streams, put log events
├── SageMaker: Create/describe training jobs, models, endpoints
└── KMS:     Decrypt data encrypted with our KMS key
```

#### Role 2: GitHub Actions CI/CD Role (OIDC)

**Used by:** GitHub Actions workflows.
**Trust policy:** Only GitHub OIDC from our specific repo/branch.

```
WHO can assume it:    token.actions.githubusercontent.com
                      (only for repo: VahantSharma/customer-churn-aws-ml)
WHAT it can do:
├── S3:        Upload training data, read model artifacts
├── ECR:       Push Docker images
├── SageMaker: Deploy models, update endpoints
├── IAM:       PassRole (pass SageMaker role to training jobs)
└── Terraform: Read/write state bucket, DynamoDB lock table
```

#### Role 3: Monitoring Read-Only Role

**Used by:** Cost monitoring scripts, dashboards.

```
WHO can assume it:    Lambda function (if automated)
WHAT it can do:
├── CloudWatch: Read metrics, dashboards
├── Cost Explorer: Read cost data
├── SageMaker: Describe endpoints (read-only)
└── S3: List buckets (read-only)
```

### Critical IAM Concept: OIDC Federation (Replace Static Keys)

Currently, the CI/CD pipeline uses `secrets.AWS_ACCESS_KEY_ID` and `secrets.AWS_SECRET_ACCESS_KEY`. This is a security risk:

- Static keys can be leaked (git history, logs, screenshots)
- Keys don't expire unless manually rotated
- If leaked, attacker has persistent access

**OIDC solution:**

```
GitHub Actions                                   AWS
     │                                             │
     │  1. Generate OIDC token                     │
     │     (short-lived, unique to this run)        │
     │                                             │
     │  2. Present token to AWS STS ──────────────►│
     │                                             │
     │                           3. AWS verifies:  │
     │                              - Token signed │
     │                                by GitHub    │
     │                              - Repo matches │
     │                                trust policy │
     │                              - Branch ok    │
     │                                             │
     │  4. Receive temporary credentials ◄─────────│
     │     (expires in 1 hour)                     │
     │                                             │
     │  5. Use temp creds for AWS operations       │
     │                                             │
```

### Terraform Resources

| Resource          | Type                              | Purpose               |
| ----------------- | --------------------------------- | --------------------- |
| SageMaker Role    | `aws_iam_role`                    | Execution role        |
| SageMaker Policy  | `aws_iam_policy`                  | Scoped permissions    |
| Policy Attachment | `aws_iam_role_policy_attachment`  | Link role ↔ policy    |
| OIDC Provider     | `aws_iam_openid_connect_provider` | GitHub OIDC trust     |
| CI/CD Role        | `aws_iam_role`                    | GitHub Actions role   |
| CI/CD Policy      | `aws_iam_policy`                  | Deploy permissions    |
| Monitoring Role   | `aws_iam_role`                    | Read-only cost role   |
| Monitoring Policy | `aws_iam_policy`                  | Read-only permissions |

### Module Interface

```hcl
# --- INPUTS ---
variable "project_name" {}
variable "environment" {}
variable "data_bucket_arn" {}         # From S3 module
variable "model_bucket_arn" {}        # From S3 module
variable "ecr_repository_arn" {}      # From ECR module
variable "github_repo" {}             # "VahantSharma/customer-churn-aws-ml"
variable "github_oidc_thumbprint" {}  # GitHub's OIDC certificate thumbprint

# --- OUTPUTS ---
output "sagemaker_execution_role_arn" {}
output "cicd_role_arn" {}
output "monitoring_role_arn" {}
```

### Key: How IAM Connects to Other Modules

- IAM **needs inputs from** S3 (bucket ARNs for policy scoping) and ECR (repo ARN)
- IAM **provides outputs to** SageMaker (role ARN for training/endpoints)
- This creates a circular dependency that we break by:
  1. Creating S3 + ECR first
  2. Then IAM (using S3 + ECR outputs)
  3. Then SageMaker (using IAM + S3 + ECR outputs)

---

## Step 3: S3 Module

### Buckets to Create

#### Bucket 1: Training Data

- **Name:** `${project}-data-${env}-${account_id}`
- **Contents:** `customer_churn.csv`, `customer_churn_processed.csv`, train/test splits
- **Versioning:** Enabled (rollback corrupted data)
- **Encryption:** AES-256 (SSE-S3)
- **Lifecycle rules:**
  - Transition to Infrequent Access after 30 days
  - Transition to Glacier after 90 days (old training data)
- **Public access:** Blocked completely
- **Bucket policy:** Only SageMaker execution role can read

#### Bucket 2: Model Artifacts

- **Name:** `${project}-models-${env}-${account_id}`
- **Contents:** `model.tar.gz` output from training jobs
- **Versioning:** Enabled (every model version preserved — this IS the model registry backup)
- **Encryption:** AES-256
- **Lifecycle rules:**
  - Keep last 10 noncurrent versions
  - Delete noncurrent versions older than 90 days
- **Bucket policy:** SageMaker role read/write, CI/CD role read

### Terraform Resources

| Resource      | Type                                                 | Count |
| ------------- | ---------------------------------------------------- | ----- |
| S3 Buckets    | `aws_s3_bucket`                                      | 2     |
| Versioning    | `aws_s3_bucket_versioning`                           | 2     |
| Encryption    | `aws_s3_bucket_server_side_encryption_configuration` | 2     |
| Public Block  | `aws_s3_bucket_public_access_block`                  | 2     |
| Lifecycle     | `aws_s3_bucket_lifecycle_configuration`              | 2     |
| Bucket Policy | `aws_s3_bucket_policy`                               | 2     |

### Module Interface

```hcl
# --- INPUTS ---
variable "project_name" {}
variable "environment" {}
variable "aws_account_id" {}
variable "sagemaker_role_arn" {}   # For bucket policy (can be set after IAM module)

# --- OUTPUTS ---
output "data_bucket_name" {}
output "data_bucket_arn" {}
output "model_bucket_name" {}
output "model_bucket_arn" {}
```

### How S3 Connects

- S3 **provides bucket ARNs to** IAM (for scoping policies)
- S3 **provides bucket names to** SageMaker (training data input, model output)
- S3 **provides bucket ARNs to** Monitoring (for metric tracking)

> **Resolver for circular dependency:** Create S3 buckets without a bucket policy first → Create IAM roles using bucket ARNs → Then apply bucket policies using IAM role ARNs (or use `depends_on` + `aws_s3_bucket_policy` as a separate resource).

---

## Step 4: ECR Module

### What This Does

Creates a Docker container registry in AWS to store the FastAPI Docker image. Currently the image is built in CI but goes nowhere.

### Resources

| Resource          | Type                        | Purpose                |
| ----------------- | --------------------------- | ---------------------- |
| ECR Repository    | `aws_ecr_repository`        | Docker image storage   |
| Lifecycle Policy  | `aws_ecr_lifecycle_policy`  | Auto-delete old images |
| Repository Policy | `aws_ecr_repository_policy` | Who can push/pull      |

### Lifecycle Policy Logic

```json
Rules:
1. Keep the last 5 images tagged with "v*" (releases)
2. Keep the last 3 images tagged with "dev-*"
3. Delete all untagged images older than 7 days
4. Delete ANY image older than 90 days
```

This keeps storage costs near zero while retaining recent deployable images.

### Module Interface

```hcl
# --- INPUTS ---
variable "project_name" {}
variable "environment" {}
variable "image_tag_mutability" {}  # "MUTABLE" for dev, "IMMUTABLE" for prod
variable "scan_on_push" {}          # true (scan for CVEs on every push)

# --- OUTPUTS ---
output "repository_url" {}          # Used in CI/CD: docker push <url>:<tag>
output "repository_arn" {}          # Used in IAM policy scoping
```

### How ECR Connects

- ECR **provides repo URL to** CI/CD (for `docker push`)
- ECR **provides repo ARN to** IAM (for scoping push/pull permissions)
- ECR **provides repo URL to** SageMaker (for pulling inference container)

---

## Step 5: SageMaker Module

### This is the Core — Where ML Meets Infrastructure

This module provisions the actual machine learning infrastructure. It's the most complex module because SageMaker has many interconnected resources.

### Resources

| Resource               | Terraform Type                                            | Purpose                                  |
| ---------------------- | --------------------------------------------------------- | ---------------------------------------- |
| Notebook Instance      | `aws_sagemaker_notebook_instance`                         | Development environment                  |
| Notebook Lifecycle     | `aws_sagemaker_notebook_instance_lifecycle_configuration` | Auto-stop to save costs                  |
| Model                  | `aws_sagemaker_model`                                     | Registered model (points to S3 artifact) |
| Endpoint Configuration | `aws_sagemaker_endpoint_configuration`                    | Instance type, scaling, variants         |
| Endpoint               | `aws_sagemaker_endpoint`                                  | Live inference endpoint                  |
| Model Package Group    | `aws_sagemaker_model_package_group`                       | Model versioning/registry                |
| Auto-Scaling Target    | `aws_appautoscaling_target`                               | Define scaling range (min/max)           |
| Auto-Scaling Policy    | `aws_appautoscaling_policy`                               | When to scale (invocation-based)         |

### How SageMaker Resource Chain Works

```
Model Artifact (S3)
        │
        ▼
  aws_sagemaker_model          ← "This is the trained model, stored at
        │                          s3://models/model.tar.gz, using this
        │                          Docker image for inference, running
        │                          with this IAM role"
        │
        ▼
  aws_sagemaker_endpoint_configuration  ← "Run 1 instance of ml.m5.large,
        │                                   capture 100% of data for
        │                                   monitoring, use variant name
        │                                   'AllTraffic'"
        │
        ▼
  aws_sagemaker_endpoint       ← "Actually deploy and make it live"
        │
        ▼
  aws_appautoscaling_target    ← "Allow scaling from 1 to 3 instances"
        │
        ▼
  aws_appautoscaling_policy    ← "Scale up when invocations > 100/min"
```

### Notebook Auto-Stop Lifecycle Configuration

```bash
# Script that runs on notebook start — schedules auto-shutdown
#!/bin/bash
set -e

IDLE_TIME=3600  # 1 hour in seconds

echo "Setting up auto-stop after ${IDLE_TIME}s idle..."

# Install and schedule idle checker
cat > /home/ec2-user/autostop.py << 'EOF'
import subprocess
import json
import time
import os

IDLE_TIME = int(os.environ.get('IDLE_TIME', 3600))

def is_idle():
    """Check if any Jupyter kernels are busy"""
    try:
        result = subprocess.run(
            ['jupyter', 'notebook', 'list', '--json'],
            capture_output=True, text=True
        )
        # If no notebooks running, it's idle
        return True
    except:
        return True

if is_idle():
    # Stop the notebook instance
    subprocess.run(['sudo', 'shutdown', '-h', 'now'])
EOF

# Schedule check every 5 minutes via cron
echo "*/5 * * * * python3 /home/ec2-user/autostop.py" | crontab -
```

### Auto-Scaling Configuration

```hcl
# Scale based on SageMaker invocations
# If invocations per instance > 70/min, add instance
# If invocations per instance < 10/min, remove instance

resource "aws_appautoscaling_target" "sagemaker" {
  max_capacity       = var.max_instance_count    # 1 for dev, 5 for prod
  min_capacity       = var.min_instance_count    # 1 for dev, 2 for prod
  resource_id        = "endpoint/${aws_sagemaker_endpoint.main.name}/variant/AllTraffic"
  scalable_dimension = "sagemaker:variant:DesiredInstanceCount"
  service_namespace  = "sagemaker"
}

resource "aws_appautoscaling_policy" "sagemaker" {
  name               = "${var.project_name}-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.sagemaker.resource_id
  scalable_dimension = aws_appautoscaling_target.sagemaker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.sagemaker.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "SageMakerVariantInvocationsPerInstance"
    }
    target_value       = 70.0    # Target 70 invocations/min per instance
    scale_in_cooldown  = 300     # Wait 5 min before scaling down
    scale_out_cooldown = 60      # Scale up quickly (1 min)
  }
}
```

### Module Interface

```hcl
# --- INPUTS ---
variable "project_name" {}
variable "environment" {}
variable "sagemaker_execution_role_arn" {}   # From IAM module
variable "model_artifact_s3_uri" {}          # s3://bucket/model.tar.gz
variable "inference_image_uri" {}            # From ECR or SageMaker built-in
variable "vpc_id" {}                         # From Networking
variable "private_subnet_ids" {}             # From Networking
variable "security_group_ids" {}             # From Networking
variable "instance_type" {}                  # ml.t2.medium (dev) / ml.m5.large (prod)
variable "min_instance_count" {}             # 1 (dev) / 2 (prod)
variable "max_instance_count" {}             # 1 (dev) / 5 (prod)
variable "enable_data_capture" {}            # false (dev) / true (prod)
variable "enable_auto_scaling" {}            # false (dev) / true (prod)

# --- OUTPUTS ---
output "endpoint_name" {}
output "endpoint_arn" {}
output "notebook_instance_url" {}
output "model_package_group_name" {}
```

---

## Step 6: Monitoring Module

### Resources

| Resource               | Terraform Type                | Purpose                    |
| ---------------------- | ----------------------------- | -------------------------- |
| SNS Topic              | `aws_sns_topic`               | Alert notification channel |
| SNS Subscription       | `aws_sns_topic_subscription`  | Email subscriber           |
| CloudWatch Dashboard   | `aws_cloudwatch_dashboard`    | Visual metrics overview    |
| Alarm: High Error Rate | `aws_cloudwatch_metric_alarm` | 5XX > 1%                   |
| Alarm: High Latency    | `aws_cloudwatch_metric_alarm` | P99 > 2s                   |
| Alarm: No Invocations  | `aws_cloudwatch_metric_alarm` | Endpoint possibly down     |
| Log Group: Training    | `aws_cloudwatch_log_group`    | Training job logs          |
| Log Group: Inference   | `aws_cloudwatch_log_group`    | Inference endpoint logs    |

### CloudWatch Dashboard Definition

The dashboard shows 6 widgets in a 3×2 grid:

```
┌──────────────────┬──────────────────┬──────────────────┐
│   Invocations    │   Latency        │   Error Rate     │
│   (line chart)   │   (p50/p95/p99)  │   (bar chart)    │
│                  │   (line chart)   │   4XX + 5XX      │
├──────────────────┼──────────────────┼──────────────────┤
│   CPU Utilization│   Model Data     │   Training Job   │
│   (per instance) │   Capture Volume │   Duration       │
│   (line chart)   │   (number widget)│   (bar chart)    │
└──────────────────┴──────────────────┴──────────────────┘
```

### Module Interface

```hcl
# --- INPUTS ---
variable "project_name" {}
variable "environment" {}
variable "endpoint_name" {}          # From SageMaker module
variable "alert_email" {}            # "vahant@example.com"
variable "enable_alarms" {}          # false for dev, true for staging/prod
variable "log_retention_days" {}     # 7 for dev, 30 for staging, 90 for prod

# --- OUTPUTS ---
output "dashboard_url" {}
output "sns_topic_arn" {}
```

---

## Step 7: API Gateway Module (Optional but Impressive)

### What This Does

Instead of exposing the SageMaker endpoint directly, put an API Gateway in front of it:

```
Client → API Gateway → Lambda → SageMaker Endpoint
                │
                ├── Rate limiting (100 req/sec)
                ├── API key authentication
                ├── Request/response logging
                ├── Custom domain (api.churn.yourdomain.com)
                └── WAF protection (block SQL injection, XSS)
```

### Resources

| Resource        | Type                          | Purpose                       |
| --------------- | ----------------------------- | ----------------------------- |
| REST API        | `aws_api_gateway_rest_api`    | API definition                |
| Resource        | `aws_api_gateway_resource`    | URL paths (/predict, /health) |
| Method          | `aws_api_gateway_method`      | HTTP methods (POST, GET)      |
| Integration     | `aws_api_gateway_integration` | Lambda backend                |
| Lambda Function | `aws_lambda_function`         | Proxy to SageMaker            |
| Usage Plan      | `aws_api_gateway_usage_plan`  | Rate limiting                 |
| API Key         | `aws_api_gateway_api_key`     | Authentication                |
| Deployment      | `aws_api_gateway_deployment`  | Deploy API                    |
| Stage           | `aws_api_gateway_stage`       | dev/staging/prod stage        |

---

## Environment Configuration

### How Environments Work

Each environment (`dev/staging/prod`) has its own `main.tf` that calls ALL modules:

```hcl
# terraform/environments/dev/main.tf

module "networking" {
  source = "../../modules/networking"

  project_name        = var.project_name
  environment         = "dev"
  vpc_cidr            = "10.0.0.0/16"
  availability_zones  = ["us-east-1a", "us-east-1b"]
  enable_vpc_endpoints = false        # Save costs in dev
  single_nat_gateway   = true         # Save $32/month
}

module "s3" {
  source = "../../modules/s3"

  project_name   = var.project_name
  environment    = "dev"
  aws_account_id = var.aws_account_id
}

module "ecr" {
  source = "../../modules/ecr"

  project_name       = var.project_name
  environment        = "dev"
  image_tag_mutability = "MUTABLE"    # Allows overwriting tags in dev
  scan_on_push       = true
}

module "iam" {
  source = "../../modules/iam"

  project_name       = var.project_name
  environment        = "dev"
  data_bucket_arn    = module.s3.data_bucket_arn      # ← CONNECTED
  model_bucket_arn   = module.s3.model_bucket_arn     # ← CONNECTED
  ecr_repository_arn = module.ecr.repository_arn      # ← CONNECTED
  github_repo        = "VahantSharma/customer-churn-aws-ml"
}

module "sagemaker" {
  source = "../../modules/sagemaker"

  project_name               = var.project_name
  environment                = "dev"
  sagemaker_execution_role_arn = module.iam.sagemaker_execution_role_arn  # ← CONNECTED
  model_artifact_s3_uri      = "s3://${module.s3.model_bucket_name}/model.tar.gz"
  inference_image_uri        = "${module.ecr.repository_url}:latest"     # ← CONNECTED
  vpc_id                     = module.networking.vpc_id                   # ← CONNECTED
  private_subnet_ids         = module.networking.private_subnet_ids      # ← CONNECTED
  security_group_ids         = [module.networking.sagemaker_security_group_id]
  instance_type              = "ml.t2.medium"   # Cheapest for dev
  min_instance_count         = 1
  max_instance_count         = 1                # No scaling in dev
  enable_data_capture        = false
  enable_auto_scaling        = false
}

module "monitoring" {
  source = "../../modules/monitoring"

  project_name   = var.project_name
  environment    = "dev"
  endpoint_name  = module.sagemaker.endpoint_name    # ← CONNECTED
  alert_email    = var.alert_email
  enable_alarms  = false                              # No alarms in dev
  log_retention_days = 7
}
```

### Environment Variable Differences

| Variable               | Dev          | Staging          | Prod            |
| ---------------------- | ------------ | ---------------- | --------------- |
| `vpc_cidr`             | 10.0.0.0/16  | 10.1.0.0/16      | 10.2.0.0/16     |
| `instance_type`        | ml.t2.medium | ml.m5.large      | ml.m5.xlarge    |
| `min_instance_count`   | 1            | 1                | 2               |
| `max_instance_count`   | 1            | 2                | 5               |
| `enable_auto_scaling`  | false        | true             | true            |
| `enable_data_capture`  | false        | true             | true            |
| `enable_vpc_endpoints` | false        | true             | true            |
| `single_nat_gateway`   | true         | true             | false           |
| `enable_alarms`        | false        | true             | true            |
| `log_retention_days`   | 7            | 30               | 90              |
| `image_tag_mutability` | MUTABLE      | IMMUTABLE        | IMMUTABLE       |
| `alert_email`          | dev@team.com | staging@team.com | oncall@team.com |

---

## How Modules Connect (Data Flow Map)

```
┌────────────┐     bucket_arns      ┌────────────┐
│     S3     │─────────────────────►│    IAM     │
│            │                      │            │
│ data_bucket│                      │ sm_role_arn│──┐
│ model_     │──────────────┐       │ cicd_role  │  │
│ bucket     │              │       └────────────┘  │
└────────────┘              │              ▲        │
      │                     │              │        │
      │ bucket_names        │    repo_arn  │        │  role_arn
      │                     │              │        │
      │          ┌──────────┘     ┌────────┴───┐    │
      │          │                │    ECR     │    │
      │          │                │            │    │
      │          │                │ repo_url   │──┐ │
      │          │                │ repo_arn   │  │ │
      │          │                └────────────┘  │ │
      │          │                                │ │
      │          ▼         repo_url              │ │
      │  ┌────────────┐◄─────────────────────────┘ │
      └─►│  SAGEMAKER │◄───────────────────────────┘
         │            │
         │ endpoint   │──────────────┐
         │ _name      │              │
         │ endpoint   │              │
         │ _arn       │              │
         └────────────┘              │
                │                    │
                │ endpoint_name      │ endpoint_arn
                │                    │
         ┌──────▼─────┐      ┌──────▼─────┐
         │ MONITORING │      │    API     │
         │            │      │  GATEWAY   │
         │ dashboard  │      │            │
         │ alarms     │      │ api_url    │
         └────────────┘      └────────────┘

ALL MODULES receive vpc_id and subnet_ids from NETWORKING
```

---

## Execution Sequence (Step by Step)

### Phase A: Foundation (Day 1-2)

```bash
# 1. Bootstrap the backend (ONE TIME)
cd terraform/backend
terraform init
terraform apply

# 2. Deploy networking
cd terraform/environments/dev
terraform init -backend-config=backend.tf
terraform apply -target=module.networking

# 3. Deploy S3 + ECR (independent of each other)
terraform apply -target=module.s3 -target=module.ecr
```

### Phase B: Identity & Security (Day 2-3)

```bash
# 4. Deploy IAM (depends on S3 + ECR for ARNs)
terraform apply -target=module.iam
```

### Phase C: ML Infrastructure (Day 3-5)

```bash
# 5. Deploy SageMaker (depends on IAM + S3 + ECR + Networking)
terraform apply -target=module.sagemaker
```

### Phase D: Observability (Day 5-6)

```bash
# 6. Deploy Monitoring (depends on SageMaker)
terraform apply -target=module.monitoring
```

### Phase E: Full Stack (Day 6+)

```bash
# 7. Or just deploy everything at once (Terraform handles ordering)
terraform apply    # Terraform's dependency graph does the rest
```

> **Note:** After the first `terraform apply`, subsequent runs only deploy CHANGES. Terraform compares desired state (`.tf` files) with actual state (`terraform.tfstate`) and only modifies what's different. This is idempotent — running `apply` twice produces the same result.

---

## CI/CD Integration

### How Terraform Fits in the CI/CD Pipeline

```yaml
# .github/workflows/ci-cd.yml (new terraform jobs)

terraform-plan:
  name: Terraform Plan
  runs-on: ubuntu-latest
  if: github.event_name == 'pull_request'
  steps:
    - uses: actions/checkout@v4
    - uses: hashicorp/setup-terraform@v3
    - uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ secrets.CICD_ROLE_ARN }} # OIDC
        aws-region: us-east-1

    - name: Terraform Init
      run: terraform init
      working-directory: terraform/environments/dev

    - name: Terraform Plan
      run: terraform plan -no-color -out=plan.tfplan
      working-directory: terraform/environments/dev

    - name: Post Plan to PR
      uses: actions/github-script@v7
      with:
        script: |
          // Post terraform plan output as PR comment
          // Reviewers can see exactly what infra changes are proposed

terraform-apply:
  name: Terraform Apply
  runs-on: ubuntu-latest
  needs: [test, build]
  if: github.ref == 'refs/heads/main'
  environment: dev # Requires approval for staging/prod
  steps:
    - uses: actions/checkout@v4
    - uses: hashicorp/setup-terraform@v3
    - uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ secrets.CICD_ROLE_ARN }}
        aws-region: us-east-1

    - name: Terraform Init
      run: terraform init
      working-directory: terraform/environments/dev

    - name: Terraform Apply
      run: terraform apply -auto-approve
      working-directory: terraform/environments/dev
```

### Why `plan` on PR and `apply` on merge:

- **Plan on PR:** Everyone sees exactly what will change, can review infra changes like code
- **Apply on merge:** Only after review and approval does infra actually change
- **Same pattern as code:** Review → Approve → Merge → Deploy

---

## Interview Talking Points

### "Walk me through your Terraform setup"

> "I modularized the infrastructure into 7 components: networking, IAM, S3, ECR, SageMaker, monitoring, and API Gateway. Each module is a self-contained unit with defined inputs and outputs. Environments like dev, staging, and prod call the same modules with different variables — dev uses smaller instances, no auto-scaling, no VPC endpoints. Prod has multi-AZ NAT Gateways, auto-scaling from 2 to 5 instances, full CloudWatch monitoring, and immutable container images."

### "How do modules connect?"

> "Through outputs and variables. The S3 module outputs bucket ARNs, which the IAM module uses to scope permissions. IAM outputs role ARNs, which SageMaker uses for execution. The networking module outputs VPC ID and subnet IDs, which SageMaker uses for VPC deployment. Monitoring takes the SageMaker endpoint name as input to create alarms. Terraform automatically builds a dependency graph and creates resources in the right order."

### "How do you manage state?"

> "Remote state in S3 with DynamoDB locking. Each environment has a separate state file path (e.g., `environments/dev/terraform.tfstate`), so dev changes never affect prod. The state bucket has versioning enabled, so I can recover from accidental state corruption. DynamoDB prevents two people or CI runs from modifying state simultaneously."

### "How do you handle the chicken-and-egg problem?"

> "The state backend itself is bootstrapped separately. I have a minimal `terraform/backend/main.tf` that creates just the S3 bucket and DynamoDB table using local state. This is a one-time setup. All other infrastructure then references this backend. It's an industry standard pattern."

### "What would break if you deleted a module?"

> "Terraform prevents this with the dependency graph. If I try to destroy the IAM module while SageMaker still references its role, Terraform will either destroy SageMaker first (if I'm destroying everything) or error if I try to selectively destroy just IAM. I also use `lifecycle { prevent_destroy = true }` on critical resources like the state bucket and production data bucket to prevent accidental deletion."

### "How much does this infrastructure cost?"

| Resource           | Dev Monthly Cost         | Prod Monthly Cost                     |
| ------------------ | ------------------------ | ------------------------------------- |
| VPC (NAT Gateway)  | ~$32 (1 NAT)             | ~$64 (2 NATs)                         |
| VPC Endpoints      | $0 (S3 only, free)       | ~$22 (4 interface endpoints)          |
| SageMaker Endpoint | ~$40 (ml.t2.medium 24/7) | ~$170 (ml.m5.xlarge, 2 min instances) |
| SageMaker Notebook | ~$5 (auto-stops)         | N/A                                   |
| S3 Storage         | <$1                      | <$1                                   |
| ECR Storage        | <$1                      | <$1                                   |
| CloudWatch         | <$5                      | <$10                                  |
| DynamoDB           | $0 (free tier)           | $0 (free tier)                        |
| **Total**          | **~$83/month**           | **~$268/month**                       |

> "For a project with a $100 budget, I keep dev costs minimal by using single NAT, no VPC interface endpoints, the cheapest SageMaker instances, and auto-stopping notebooks. In production, I'd invest in HA networking and auto-scaling, which costs more but provides reliability."
