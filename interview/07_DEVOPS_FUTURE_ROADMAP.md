# DevOps Future Roadmap – Making This a Complete DevOps Showcase

## Current State: What's Already DevOps

| What Exists | Maturity |
|------------|----------|
| GitHub Actions CI/CD | Partial — test + lint works, deploy step is placeholder |
| Docker containerization | Good — multi-stage build, non-root user, health check |
| Unit tests (pytest) | Good — 16 tests, coverage reporting |
| Code formatting/linting | Good — black + flake8 in CI |
| Makefile automation | Basic — install, test, lint, deploy targets |
| AWS cost monitoring | Good — but runs manually, not automated |

**What's completely missing:** Infrastructure-as-Code, container registry, automated deployment, monitoring/alerting, secrets management, environment separation, security scanning, ML pipeline orchestration, auto-scaling.

---

## Phase 1: Terraform Infrastructure-as-Code (THE MUST-HAVE)

This is the **#1 thing** that transforms this project from "ML project with some DevOps" to "DevOps-driven ML project."

### Why Terraform?
- **Reproducibility** — anyone can spin up the exact same infrastructure
- **Version control** — infrastructure changes go through PR review
- **Multi-environment** — one template, three environments (dev/staging/prod)
- **Drift detection** — know when someone changes something manually
- **Destroy in one command** — crucial for budget management

### What to Build

#### 1.1. Terraform Module: S3 Buckets
```
terraform/modules/s3/
```

**Resources:**
- **Training data bucket** — stores `customer_churn.csv` and processed data
  - Versioning enabled (rollback if data is corrupted)
  - Lifecycle rule: transition to Glacier after 90 days
  - Server-side encryption (SSE-S3)
  - Block all public access
- **Model artifacts bucket** — stores `model.tar.gz` from training
  - Versioning enabled (keep every model version)
  - Lifecycle rule: keep last 10 versions, expire older
  - Cross-region replication optional (disaster recovery)
- **Terraform state bucket** — stores `terraform.tfstate`
  - Versioning enabled (state history)
  - DynamoDB table for state locking

**Why this matters:**
> "I provisioned all S3 infrastructure through Terraform with encryption, versioning, and lifecycle policies. This means model artifacts are versioned so we can always roll back, old data automatically moves to cheaper storage, and everything is reproducible across environments."

#### 1.2. Terraform Module: IAM Roles & Policies
```
terraform/modules/iam/
```

**Resources:**
- **SageMaker execution role** — used by training jobs and endpoints
  - Permissions: S3 read/write (scoped to our buckets), SageMaker training/endpoint, CloudWatch logs, ECR pull
  - NO wildcard resources (replace current `"Resource": "*"`)
- **CI/CD deployment role** — used by GitHub Actions via OIDC
  - Permissions: S3 upload, SageMaker deploy, ECR push, IAM PassRole
  - Trust policy: only GitHub Actions from our repo
- **Cost monitoring role** — read-only for cost tracking
  - Permissions: Cost Explorer read, CloudWatch read, SageMaker describe

**Why this matters:**
> "My IAM setup follows least-privilege principle. Each role has only the permissions it needs, scoped to specific resource ARNs. I also use OIDC federation for CI/CD instead of static access keys, which is more secure."

#### 1.3. Terraform Module: ECR (Container Registry)
```
terraform/modules/ecr/
```

**Resources:**
- **ECR repository** for the FastAPI Docker image
  - Image scanning enabled (detect CVEs on push)
  - Lifecycle policy: keep last 5 tagged images, delete untagged after 7 days
  - Encryption with AWS-managed key

**Why this matters:**
> "Docker images are pushed to ECR with automatic vulnerability scanning. The lifecycle policy keeps storage costs minimal by pruning old images."

#### 1.4. Terraform Module: SageMaker
```
terraform/modules/sagemaker/
```

**Resources:**
- **SageMaker notebook instance** (for development)
  - Instance type: `ml.t3.medium` (cheapest)
  - Lifecycle config: auto-stop after 1 hour idle
  - Attached to our VPC
- **SageMaker model** (registered model from S3)
- **SageMaker endpoint configuration** (instance type, scaling)
- **SageMaker endpoint** (serves predictions)
- **SageMaker model package group** (model registry for versioning)
- **Auto-scaling policy** — scale from 1 to 3 instances based on invocation count

**Why this matters:**
> "SageMaker infrastructure is code-defined. The notebook auto-stops to save costs, the endpoint has auto-scaling configured, and models are registered in a model registry for version tracking."

#### 1.5. Terraform Module: Networking (VPC)
```
terraform/modules/networking/
```

**Resources:**
- **VPC** with CIDR `10.0.0.0/16`
- **Public subnet** (NAT Gateway, bastion host if needed)
- **Private subnet** (SageMaker endpoint, training jobs)
- **Security groups** — restrict endpoint access to API Gateway or specific IPs
- **VPC endpoints for S3 and SageMaker** — traffic never leaves AWS network (faster, cheaper, more secure)

**Why this matters:**
> "SageMaker resources run inside a private subnet. Data never traverses the public internet because I configured VPC endpoints for S3 and SageMaker API calls. This is both a security and cost optimization."

#### 1.6. Terraform Module: Monitoring & Alerting
```
terraform/modules/monitoring/
```

**Resources:**
- **CloudWatch dashboard** with widgets for:
  - Endpoint invocation count (per minute)
  - Endpoint latency (p50, p95, p99)
  - Endpoint 4XX/5XX error rate
  - Training job duration trends
  - Model data capture volume
- **CloudWatch alarms:**
  - 5XX rate > 1% for 5 minutes → SNS alert
  - P99 latency > 2 seconds → SNS alert
  - Model invocations drop to 0 for 1 hour → SNS alert (endpoint might be down)
  - Monthly cost > $80 → SNS alert
- **SNS topic** for alarm notifications (email / Slack webhook)
- **CloudWatch log groups** for training and inference logs (retention: 30 days)

**Why this matters:**
> "I built observability into the infrastructure. The CloudWatch dashboard gives real-time visibility into model performance, and alarms proactively notify us before issues impact users. For example, if latency spikes above 2 seconds or error rate exceeds 1%, we get an alert."

#### 1.7. Terraform Environments
```
terraform/environments/
├── dev/            # Developer sandbox
├── staging/        # Pre-production testing
└── prod/           # Production
```

Each environment uses the **same modules** but different variables:

| Variable | Dev | Staging | Prod |
|----------|-----|---------|------|
| Instance type | ml.t2.medium | ml.m5.large | ml.m5.xlarge |
| Min instances | 1 | 1 | 2 |
| Max instances | 1 | 2 | 5 |
| Auto-scaling | Off | On | On |
| Monitoring alarms | Off | Email only | Email + Slack |
| S3 versioning | Off | On | On |
| VPC endpoints | No | Yes | Yes |

#### 1.8. Terraform Backend
Remote state with S3 + DynamoDB:
- State stored in dedicated S3 bucket with versioning
- DynamoDB table for state locking (prevent concurrent modifications)
- State is encrypted at rest (SSE-S3)

---

## Phase 2: Complete the CI/CD Pipeline

### What Needs Fixing
The current deploy job is literally `echo "Add deployment script here"`. We need to replace this with an actual automated deployment.

### Enhanced Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CI/CD PIPELINE (GitHub Actions)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────┐   ┌────────────┐   ┌──────────┐   ┌────────────┐        │
│  │  Lint &   │──►│  Security  │──►│  Build & │──►│ Terraform  │        │
│  │  Test     │   │  Scan      │   │  Push    │   │  Plan      │        │
│  │          │   │            │   │  to ECR  │   │            │        │
│  │ flake8   │   │ Trivy scan │   │          │   │ Show diff  │        │
│  │ pytest   │   │ pip audit  │   │          │   │ on PR      │        │
│  │ coverage │   │ Snyk/Bandit│   │          │   │            │        │
│  └──────────┘   └────────────┘   └──────────┘   └────────────┘        │
│       │               │               │               │                │
│       ▼               ▼               ▼               ▼                │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │                    PR Merge to main                          │        │
│  └────────────────────────────────────────────────────────────┘        │
│                              │                                          │
│       ┌──────────────────────┼──────────────────────┐                  │
│       ▼                      ▼                      ▼                  │
│  ┌──────────┐   ┌────────────────┐   ┌──────────────────┐             │
│  │ Deploy   │──►│  Integration   │──►│  Deploy Staging  │             │
│  │ to Dev   │   │  Tests on Dev  │   │  (Manual gate)   │             │
│  │ (auto)   │   │                │   │                  │             │
│  └──────────┘   └────────────────┘   └──────────────────┘             │
│                                              │                          │
│                                              ▼                          │
│                                   ┌──────────────────┐                  │
│                                   │  Deploy Prod     │                  │
│                                   │  (Manual gate)   │                  │
│                                   │  + Smoke tests   │                  │
│                                   │  + Rollback check│                  │
│                                   └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### New CI/CD Jobs to Add

#### 2.1. Security Scanning Job
```yaml
security-scan:
  steps:
    - pip-audit (Python vulnerability scanner)
    - Trivy container scan (CVE detection)
    - Bandit (Python security linter)
    - checkov (Terraform security scanner)
```

**Why:**
> "Every build is automatically scanned for known vulnerabilities in dependencies, container base images, Python security anti-patterns, and Terraform misconfigurations."

#### 2.2. ECR Push Job
```yaml
build-and-push:
  steps:
    - Login to ECR
    - Build Docker image
    - Tag with git SHA + 'latest'
    - Push to ECR
    - Scan image in ECR
```

#### 2.3. Terraform Plan/Apply
```yaml
terraform-plan:   # On PRs — show infra diff as PR comment
terraform-apply:  # On main merge — apply changes
```

#### 2.4. Deploy with Model Validation
```yaml
deploy-dev:
  steps:
    - Terraform apply (dev)
    - Deploy new model to SageMaker endpoint
    - Run prediction tests against endpoint
    - Validate response latency < 500ms
    - Validate prediction accuracy on test set > 85% AUC

deploy-staging:
  needs: [deploy-dev]
  environment: staging  # Manual approval required
  steps:
    - Terraform apply (staging)
    - Deploy model
    - Run full integration test suite

deploy-prod:
  needs: [deploy-staging]
  environment: production  # Manual approval required
  steps:
    - Terraform apply (prod)
    - Deploy model (canary — 10% traffic first)
    - Monitor error rate for 10 minutes
    - If OK → shift to 100%
    - If NOT → rollback to previous model
```

#### 2.5. GitHub OIDC Authentication (Replace Static Keys)
```yaml
permissions:
  id-token: write   # Required for OIDC

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::ACCOUNT:role/github-actions-role
      aws-region: us-east-1
      # NO access keys — uses OIDC federation
```

**Why this matters:**
> "I replaced static AWS access keys with OIDC federation. GitHub generates a short-lived token for each workflow run, and AWS verifies it against our IAM trust policy. This means no secrets to rotate and no risk of leaked credentials."

---

## Phase 3: Advanced Monitoring & Observability

### 3.1. SageMaker Model Monitor
Set up automated monitoring for:

| Monitor Type | What It Detects | Action |
|-------------|----------------|--------|
| Data Quality | Input feature distribution drift | Alert + trigger retraining |
| Model Quality | Accuracy/AUC degradation | Alert + flag for review |
| Bias | Prediction disparities across groups | Alert + compliance report |
| Feature Attribution | SHAP value distribution change | Alert + investigation |

**Implementation:**
- Enable Data Capture on endpoint (captures 100% of input/output)
- Schedule daily monitoring job (compare against baseline)
- Store results in S3, alarm on violations

### 3.2. Custom CloudWatch Metrics
Push custom metrics from the FastAPI app:
- `churn_predictions_total` (Counter)
- `churn_high_risk_percentage` (Gauge)
- `prediction_latency_seconds` (Histogram)
- `model_version` (Info)

### 3.3. Centralized Logging
- All application logs → CloudWatch Logs
- Structured JSON logging (parseable by CloudWatch Insights)
- Log queries: "Show me all predictions with churn_probability > 0.9 in the last hour"

### 3.4. Distributed Tracing (Optional Advanced)
- X-Ray integration for API → SageMaker → S3 traces
- Identify bottlenecks in the prediction pipeline

---

## Phase 4: Security Hardening

### 4.1. Secrets Management
```
AWS Secrets Manager:
├── /churn-api/prod/api-keys       # API authentication keys
├── /churn-api/prod/db-credentials  # If adding a database
└── /churn-api/prod/slack-webhook   # Alert notifications
```

### 4.2. Encryption
- **S3:** SSE-S3 or SSE-KMS for all buckets
- **SageMaker volumes:** KMS-encrypted EBS
- **ECR images:** KMS encryption
- **In-transit:** TLS everywhere (SageMaker endpoints already use HTTPS)

### 4.3. Network Security
- SageMaker endpoints in private subnet (no public IP)
- API Gateway as the only public-facing component
- VPC endpoints for AWS service access (S3, SageMaker API, ECR)
- Security groups: endpoint only accepts from API Gateway SG

### 4.4. Container Security
- Base image: `python:3.9-slim` (already small attack surface)
- No root access (already implemented ✅)
- Read-only filesystem where possible
- Pin all dependency versions (currently using `>=` — switch to `==`)
- Trivy scan in CI + ECR scan on push

### 4.5. IAM Hardening
- **Service control policies** at org level
- **Permission boundaries** on all roles
- **Condition keys** — restrict actions by source IP, MFA, etc.
- **Access Analyzer** — detect unused permissions

---

## Phase 5: ML Pipeline Orchestration (AWS Step Functions / SageMaker Pipelines)

### Automated Training Pipeline

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Trigger │───►│ Validate │───►│  Train   │───►│ Evaluate │
│ (Schedule│    │   Data   │    │  Model   │    │  Model   │
│  or Drift│    │          │    │          │    │          │
│  Alert)  │    │ data_    │    │ training │    │ AUC>0.85?│
│          │    │ validation│    │ .py      │    │          │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
                    │                                │
                    ▼                           ┌────┴─────┐
               ┌──────────┐                 YES │          │ NO
               │  FAIL:   │                     ▼          ▼
               │  Alert   │               ┌──────────┐ ┌──────────┐
               │  Team    │               │ Register │ │  Alert   │
               └──────────┘               │  Model   │ │  Team    │
                                          │  in      │ │  Needs   │
                                          │  Registry│ │  Review  │
                                          └──────────┘ └──────────┘
                                               │
                                               ▼
                                          ┌──────────┐
                                          │  Deploy  │
                                          │  Canary  │
                                          │  (10%)   │
                                          └──────────┘
                                               │
                                          ┌────┴─────┐
                                     OK   │          │ Errors
                                          ▼          ▼
                                     ┌──────────┐ ┌──────────┐
                                     │  Full    │ │ Rollback │
                                     │  Deploy  │ │ Previous │
                                     │  (100%)  │ │  Model   │
                                     └──────────┘ └──────────┘
```

### Retraining Triggers
1. **Scheduled**: Weekly cron (`0 6 * * MON`)
2. **Drift-based**: Model Monitor detects distribution shift
3. **Performance-based**: AUC drops below threshold on labeled data
4. **Manual**: Data team uploads new training data to S3

### A/B Testing with Endpoint Variants
```python
# SageMaker supports traffic splitting natively
endpoint_config = {
    "ProductionVariants": [
        {"ModelName": "model-v2", "InitialVariantWeight": 0.1},  # New model
        {"ModelName": "model-v1", "InitialVariantWeight": 0.9},  # Existing model
    ]
}
# Monitor for 24 hours, then promote or rollback
```

---

## Phase 6: Advanced DevOps Additions

### 6.1. API Gateway + Lambda (Serverless Option)
Instead of running a SageMaker endpoint 24/7 ($40/month), consider:
- **API Gateway** → **Lambda** → **SageMaker Serverless Endpoint**
- Cost: ~$0 when idle, pay only per invocation
- Perfect for low-traffic development/staging environments

### 6.2. Docker Compose for Local Development
```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports: ["8000:8000"]
    volumes: ["./model:/app/model"]

  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    ports: ["5000:5000"]

  localstack:
    image: localstack/localstack
    ports: ["4566:4566"]
    environment:
      SERVICES: s3,sagemaker
```

**Why:** Developers can run the entire stack locally without AWS credentials.

### 6.3. Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    hooks: [{ id: black }]
  - repo: https://github.com/PyCQA/isort
    hooks: [{ id: isort }]
  - repo: https://github.com/PyCQA/flake8
    hooks: [{ id: flake8 }]
  - repo: https://github.com/antonbabenko/pre-commit-terraform
    hooks: [{ id: terraform_fmt }, { id: terraform_validate }, { id: tflint }]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks: [{ id: check-yaml }, { id: detect-private-key }, { id: no-commit-to-branch }]
```

### 6.4. GitOps with ArgoCD (If Using EKS)
If the project grows to Kubernetes:
- ArgoCD watches Git for changes to k8s manifests
- Auto-syncs cluster state to match Git
- Provides drift detection and self-healing

### 6.5. Dependency Management
Replace `>=` version pinning with exact versions:
```
# Use pip-tools
pip-compile requirements.in → requirements.txt (locked)
pip-compile requirements-api.in → requirements-api.txt (locked)
```

Or switch to `uv` for faster dependency resolution.

### 6.6. Feature Store (SageMaker Feature Store)
- Centralize feature computation
- Ensure training and inference use the same feature engineering
- Historical feature storage for time-travel queries

### 6.7. API Tests (Missing from Current Codebase)
```python
# tests/test_api.py
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_predict_valid():
    response = client.post("/predict", json={...})
    assert response.status_code == 200
    assert "churn_probability" in response.json()

def test_predict_invalid():
    response = client.post("/predict", json={"Age": -5})
    assert response.status_code == 422  # Validation error
```

### 6.8. Integration Tests Against AWS
```python
# tests/integration/test_sagemaker_endpoint.py
# Run only in deploy pipeline, not on every PR

def test_endpoint_responds():
    runtime = boto3.client('sagemaker-runtime')
    response = runtime.invoke_endpoint(
        EndpointName='churn-prediction-dev',
        ContentType='application/json',
        Body=json.dumps(test_payload)
    )
    result = json.loads(response['Body'].read())
    assert 'prediction' in result
```

---

## Phase 7: Documentation & Compliance

### 7.1. Architecture Decision Records (ADRs)
```
docs/adr/
├── 001-choose-xgboost.md
├── 002-choose-sagemaker-over-ec2.md
├── 003-terraform-over-cloudformation.md
├── 004-fastapi-over-flask.md
└── 005-github-oidc-over-static-keys.md
```

### 7.2. Runbook
```
docs/runbook/
├── how-to-deploy.md
├── how-to-rollback.md
├── how-to-retrain.md
├── how-to-troubleshoot.md
└── incident-response.md
```

### 7.3. Cost Report Automation
Weekly automated cost report sent via SNS:
```
Weekly AWS Cost Report
─────────────────────
SageMaker Endpoints:  $4.20
SageMaker Training:   $0.30
S3 Storage:           $0.05
CloudWatch:           $0.15
Total:                $4.70
Budget Remaining:     $95.30
```

---

## Implementation Priority (What to Do First)

```
         HIGH IMPACT
              │
   ┌──────────┼──────────┐
   │ P0       │ P1       │
   │          │          │
   │ Terraform│ CloudWatch│
   │ Modules  │ Monitoring│
   │          │          │
   │ Fix CI/CD│ GitHub   │
   │ Deploy   │ OIDC     │
   │          │          │
   │ ECR Push │ Security │
   │          │ Scanning │
LOW│──────────┼──────────│HIGH
EFFORT        │          EFFORT
   │ P2       │ P3       │
   │          │          │
   │ Pre-     │ SageMaker│
   │ commit   │ Pipelines│
   │          │          │
   │ API Tests│ API      │
   │          │ Gateway  │
   │          │          │
   │ Dep.     │ A/B      │
   │ Locking  │ Testing  │
   └──────────┼──────────┘
              │
         LOW IMPACT
```

### Suggested Order of Execution:

1. **Week 1:** Terraform modules (S3 + IAM + ECR) + remote backend
2. **Week 2:** Terraform modules (SageMaker + Networking) + complete CI/CD deploy step + ECR push
3. **Week 3:** Terraform environments (dev/staging/prod) + GitHub OIDC + environment promotion gates
4. **Week 4:** CloudWatch monitoring + alerting + container scanning
5. **Week 5:** SageMaker Model Monitor + API tests + integration tests
6. **Week 6:** ML pipeline (Step Functions) + A/B testing + API Gateway

---

## How to Talk About This in Interviews

### When asked "What DevOps tools have you used?"
> "I've implemented a complete DevOps pipeline for an ML project: Terraform for infrastructure-as-code provisioning all AWS resources (S3, IAM, SageMaker, ECR, VPC, CloudWatch), GitHub Actions CI/CD with automated testing, security scanning, Docker image builds pushed to ECR, Terraform plan/apply, and multi-environment deployment with manual approval gates. The infrastructure includes private VPC networking, CloudWatch monitoring with alerting, and OIDC-based authentication."

### When asked "How do you handle deployments?"
> "I use a blue-green deployment approach. Code merges trigger automated builds, which push Docker images to ECR and run Terraform to update infrastructure. Deployment goes through dev → staging → production with manual approval gates at each stage. The production deploy uses canary releases — 10% traffic to the new model, monitor for errors, then shift to 100%. If anything fails, automatic rollback to the previous model."

### When asked "How do you handle infrastructure?"
> "Everything is Terraform — modularized into S3, IAM, SageMaker, ECR, networking, and monitoring modules. Each environment (dev/staging/prod) reuses the same modules with different variable values. State is stored in S3 with DynamoDB locking, and all changes go through PR review with `terraform plan` output posted as a PR comment."

### When asked "What about monitoring?"
> "I have CloudWatch dashboards tracking endpoint latency (p50/p95/p99), invocation count, and error rate. Alarms trigger SNS notifications if error rate exceeds 1% or latency exceeds 2 seconds. Additionally, SageMaker Model Monitor runs daily to detect data drift and model quality degradation, triggering automated retraining when necessary."
