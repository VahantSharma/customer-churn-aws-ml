# Terraform Infrastructure — Customer Churn ML Pipeline

Production-grade Infrastructure as Code for the Customer Churn ML prediction platform on AWS.

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        AWS Account                               │
│                                                                  │
│  ┌─────────┐   Encrypts    ┌───────────────────────────────────┐ │
│  │   KMS   │──────────────▶│  All resources (S3, CW, SNS, SM) │ │
│  └─────────┘               └───────────────────────────────────┘ │
│                                                                  │
│  ┌──────────┐  Audit logs  ┌────────────────────┐               │
│  │ Security │─────────────▶│ S3 + CloudWatch    │               │
│  │(CloudTr) │              │ (encrypted)        │               │
│  └──────────┘              └────────────────────┘               │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐           │
│  │                   VPC (Networking)                │           │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │           │
│  │  │ Public   │  │ Private  │  │ VPC Endpoints  │ │           │
│  │  │ Subnets  │  │ Subnets  │  │ (S3, SM, STS)  │ │           │
│  │  └──────────┘  └──────────┘  └────────────────┘ │           │
│  │  Flow Logs ──▶ CloudWatch (KMS encrypted)       │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                  │
│  ┌─────┐  ┌─────┐  ┌──────────┐  ┌─────────────┐              │
│  │ IAM │  │ S3  │  │   ECR    │  │  SageMaker  │              │
│  │     │  │     │  │          │  │ (Notebook +  │              │
│  │Perm │  │KMS  │  │KMS enc   │  │  Endpoint)  │              │
│  │Bndry│  │enc  │  │Scan+Push │  │  KMS volume │              │
│  └─────┘  └─────┘  └──────────┘  └─────────────┘              │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐           │
│  │              Monitoring                           │           │
│  │  SNS (KMS) → Alarms → Dashboard → Composite     │           │
│  │  Log Groups (KMS) → Anomaly Detection            │           │
│  └──────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

## Module Dependency Graph

```
KMS ──┬──▶ Networking (cloudwatch_kms_key_arn)
      ├──▶ IAM        (kms_s3_key_arn, kms_sagemaker_key_arn)
      ├──▶ S3         (kms_key_arn)
      ├──▶ ECR        (kms_key_arn)
      ├──▶ SageMaker  (kms_key_arn)
      ├──▶ Monitoring (sns_kms_key_arn, cloudwatch_kms_key_arn)
      └──▶ Security   (cloudtrail_s3_kms_key_arn, cloudwatch_kms_key_arn)

IAM ──────▶ S3         (sagemaker_role_arn)
            SageMaker  (sagemaker_execution_role_arn)

Networking ▶ SageMaker (vpc_id, private_subnet_ids, security_group_ids)

S3 ───────▶ IAM        (data_bucket_arn, model_bucket_arn)
            SageMaker  (model_bucket_name)
            Security   (monitored_s3_bucket_arns)

ECR ──────▶ IAM        (ecr_repository_arn)
            SageMaker  (inference_image_uri)

SageMaker ─▶ Monitoring (endpoint_name)
```

## Directory Structure

```
terraform/
├── .terraform-version          # Pins Terraform CLI version (1.6.0)
├── .tflint.hcl                 # TFLint configuration (AWS plugin)
├── README.md                   # This file
│
├── backend/                    # Remote state infrastructure
│   ├── main.tf                 # S3 bucket + DynamoDB (KMS encrypted)
│   ├── variables.tf            # Region, project, account ID
│   └── outputs.tf              # Bucket name, table name, KMS ARN
│
├── modules/
│   ├── kms/                    # Customer-managed encryption keys
│   │   ├── versions.tf         # Provider constraints
│   │   ├── variables.tf        # project, env, account, rotation
│   │   ├── main.tf             # 4 CMK keys (S3, CW, SNS, SM)
│   │   └── outputs.tf          # Key ARNs and IDs
│   │
│   ├── security/               # CloudTrail audit logging
│   │   ├── versions.tf
│   │   ├── variables.tf        # enable_cloudtrail, KMS ARNs, retention
│   │   ├── main.tf             # Trail, S3 bucket, CW delivery
│   │   └── outputs.tf          # Trail ARN, bucket name
│   │
│   ├── networking/             # VPC, subnets, NAT, VPC endpoints
│   │   ├── versions.tf
│   │   ├── locals.tf           # name_prefix, common_tags
│   │   ├── variables.tf        # CIDR, AZs, flow logs, endpoints
│   │   ├── main.tf             # VPC, subnets, routes, security groups
│   │   ├── flow_logs.tf        # VPC Flow Logs → CloudWatch (KMS)
│   │   └── outputs.tf          # VPC ID, subnet IDs, SG IDs, endpoints
│   │
│   ├── iam/                    # IAM roles with permission boundaries
│   │   ├── versions.tf
│   │   ├── locals.tf           # name_prefix, ARN prefixes
│   │   ├── variables.tf        # Bucket ARNs, GitHub repo, KMS ARNs
│   │   ├── main.tf             # 3 roles (SM, CICD, Monitor) + boundary
│   │   └── outputs.tf          # Role ARNs, boundary ARN
│   │
│   ├── s3/                     # Data + Model buckets with access logs
│   │   ├── versions.tf
│   │   ├── locals.tf           # KMS/AES256 conditional, name_prefix
│   │   ├── variables.tf        # Versioning, KMS, log retention
│   │   ├── main.tf             # 3 buckets (data, model, access-logs)
│   │   └── outputs.tf          # Bucket names, ARNs, encryption type
│   │
│   ├── ecr/                    # Container registry
│   │   ├── versions.tf
│   │   ├── variables.tf        # Mutability, scan, KMS
│   │   ├── main.tf             # Repository, lifecycle, scanning
│   │   └── outputs.tf          # Repository URL, ARN
│   │
│   ├── sagemaker/              # Notebook + Model + Endpoint
│   │   ├── versions.tf
│   │   ├── locals.tf           # name_prefix, common_tags
│   │   ├── variables.tf        # Instance types, scaling, data capture
│   │   ├── main.tf             # Notebook, model registry, endpoint
│   │   └── outputs.tf          # Endpoint name/ARN, notebook URL
│   │
│   └── monitoring/             # Dashboard, alarms, SNS, log groups
│       ├── versions.tf
│       ├── locals.tf           # name_prefix, create_alarms flag
│       ├── variables.tf        # Thresholds, retention, KMS ARNs
│       ├── main.tf             # SNS, CW dashboard, 6 alarms, composite
│       └── outputs.tf          # SNS ARN, alarm ARNs, dashboard
│
└── environments/
    ├── dev/
    │   ├── backend.tf          # S3 state: environments/dev/
    │   ├── main.tf             # Cheapest settings, notebook ON
    │   ├── variables.tf        # With validations
    │   ├── terraform.tfvars    # Default values
    │   └── outputs.tf          # All module outputs surfaced
    │
    ├── staging/
    │   ├── backend.tf          # S3 state: environments/staging/
    │   ├── main.tf             # Prod-like, single NAT, alarms ON
    │   ├── variables.tf
    │   ├── terraform.tfvars
    │   └── outputs.tf
    │
    └── prod/
        ├── backend.tf          # S3 state: environments/prod/
        ├── main.tf             # Full HA, dual NAT, all alarms
        ├── variables.tf
        ├── terraform.tfvars
        └── outputs.tf
```

## Modules Summary

| Module         | Resources                 | Key Features                                           |
| -------------- | ------------------------- | ------------------------------------------------------ |
| **kms**        | 4 CMK keys + aliases      | S3, CloudWatch, SNS, SageMaker keys with auto-rotation |
| **security**   | CloudTrail + S3 + CW      | API audit logging, optional S3 data events             |
| **networking** | VPC, subnets, NAT, SGs    | Flow Logs, VPC Endpoints (S3, SageMaker, STS)          |
| **iam**        | 3 roles + boundary        | Permission boundary, IAM paths, KMS policies           |
| **s3**         | 3 buckets                 | KMS/AES256 encryption, access logging, TLS-only        |
| **ecr**        | Repository                | KMS encryption, vulnerability scanning, lifecycle      |
| **sagemaker**  | Notebook, model, endpoint | KMS volume encryption, auto-scaling, data capture      |
| **monitoring** | SNS, dashboard, 7 alarms  | Composite alarm, anomaly detection, KMS encrypted      |

## Environment Comparison

| Feature        | Dev                 | Staging          | Prod                 |
| -------------- | ------------------- | ---------------- | -------------------- |
| KMS Encryption | ✅ (7-day deletion) | ✅ (14-day)      | ✅ (30-day)          |
| CloudTrail     | ❌                  | ✅ (mgmt events) | ✅ (+ data events)   |
| VPC Flow Logs  | ✅ (7-day)          | ✅ (14-day)      | ✅ (90-day)          |
| NAT Gateway    | Single              | Single           | Dual (HA)            |
| VPC Endpoints  | S3 only             | All              | All                  |
| Notebook       | ✅ ml.t3.medium     | ❌               | ❌                   |
| Endpoint       | Optional            | Optional         | Optional (2-5 HA)    |
| Auto-Scaling   | ❌                  | ✅ (1-2)         | ✅ (2-5 + scheduled) |
| Data Capture   | ❌                  | ✅               | ✅ (100%)            |
| Alarms         | ❌                  | ✅ (relaxed)     | ✅ (tight)           |
| Log Retention  | 7 days              | 30 days          | 90 days              |
| Image Tags     | Mutable             | Immutable        | Immutable            |
| S3 Versioning  | ❌                  | ✅               | ✅                   |

## Production Security Patterns

### 1. KMS CMK Everywhere

Every data-at-rest resource uses a dedicated Customer Managed Key (CMK) instead of default AES256:

- **Audit trail**: CloudTrail logs every key usage
- **Key rotation**: Automatic annual rotation
- **Access control**: Key policies + IAM policies (defense in depth)
- **Compliance**: SOC2, HIPAA, PCI-DSS require CMK

### 2. TLS-Only S3 Access

All S3 bucket policies enforce:

- `aws:SecureTransport = false` → Deny (no HTTP)
- `s3:TlsVersion < 1.2` → Deny (no old TLS)

### 3. Permission Boundaries

All IAM roles have a permission boundary that:

- Restricts to approved AWS services only
- Blocks `organizations:LeaveOrganization`
- Blocks billing/account modifications

### 4. VPC Flow Logs

Traffic metadata captured to CloudWatch Logs (KMS encrypted) for:

- Security investigation
- Network troubleshooting
- Compliance requirements

### 5. SNS Topic Policy

SNS topics restrict publishers to:

- CloudWatch Alarms (via service principal)
- Account owner (root)
- TLS-only access enforced

## Deployment

### Prerequisites

1. Terraform >= 1.6.0 (`tfenv install 1.6.0`)
2. AWS CLI configured with appropriate credentials
3. Remote state backend deployed (see below)

### Step 1: Deploy Remote State Backend

```bash
cd terraform/backend
terraform init
terraform apply -var="aws_region=us-east-1" \
                -var="project_name=customer-churn" \
                -var="aws_account_id=231284356634"
```

### Step 2: Deploy an Environment

```bash
cd terraform/environments/dev    # or staging / prod
terraform init
terraform plan -out=plan.tfplan
terraform apply plan.tfplan
```

### Deploy with Endpoint

```bash
terraform apply -var="deploy_endpoint=true" \
                -var="model_artifact_s3_uri=s3://bucket/model.tar.gz"
```

## Critical Design Decisions

### timestamp() Removed from SageMaker Endpoint Config

**Problem**: Original code used `timestamp()` in the endpoint config name, causing Terraform to show a forced replacement on every `plan` even when nothing changed.

**Fix**: Replaced with `name_prefix` + `create_before_destroy` lifecycle. AWS generates a unique suffix, and Terraform creates the new config before destroying the old one (zero-downtime deployments).

### S3 Encryption Policy Fixed

**Problem**: Original `DenyUnencryptedUploads` policy checked `s3:x-amz-server-side-encryption != AES256`, which:

1. Blocked valid uploads when bucket-default encryption handles it server-side
2. Blocked KMS-encrypted uploads entirely

**Fix**: Replaced with TLS-only enforcement (`aws:SecureTransport` + `s3:TlsVersion`), which is the actual security requirement. Bucket-default encryption handles the rest.

### Circular Dependency Avoidance (KMS ↔ IAM)

KMS key policies use root account admin access. IAM role policies grant `kms:Encrypt/Decrypt/GenerateDataKey` on specific key ARNs. This avoids a circular module dependency while maintaining defense-in-depth (both key policy AND IAM policy must allow access).

## Validation

```bash
# Format check
terraform fmt -recursive -check

# Validate configuration
cd terraform/environments/dev && terraform validate

# Lint with TFLint
tflint --init
tflint --recursive
```
