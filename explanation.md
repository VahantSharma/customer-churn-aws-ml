# The Complete Story of This Project — Explained Simply

> If you can't explain it simply, you don't understand it well enough. — Richard Feynman

This document explains **everything** in this project — what it was, what it became, why every piece exists, and how everything connects. By the time you finish reading, you'll be able to explain this project to anyone and answer any question about it.

---

## Table of Contents

1. [What Is This Project About?](#1-what-is-this-project-about)
2. [The Big Picture — How Everything Connects](#2-the-big-picture--how-everything-connects)
3. [What Existed Before (The Starting Point)](#3-what-existed-before-the-starting-point)
4. [What Was Built On Top (The Transformation)](#4-what-was-built-on-top-the-transformation)
5. [The Data — Where It All Starts](#5-the-data--where-it-all-starts)
6. [The ML Notebooks — Experimentation Phase](#6-the-ml-notebooks--experimentation-phase)
7. [The Source Code (`src/`) — Production Python](#7-the-source-code-src--production-python)
8. [The API (`src/api.py`) — Serving Predictions](#8-the-api-srcapipy--serving-predictions)
9. [SageMaker Scripts — Cloud ML Training](#9-sagemaker-scripts--cloud-ml-training)
10. [The Tests — Quality Assurance](#10-the-tests--quality-assurance)
11. [Docker — Containerization](#11-docker--containerization)
12. [CI/CD — Automated Pipeline](#12-cicd--automated-pipeline)
13. [Terraform — The Infrastructure (The Big One)](#13-terraform--the-infrastructure-the-big-one)
14. [Terraform Module-by-Module Deep Dive](#14-terraform-module-by-module-deep-dive)
15. [Terraform Environments — Dev, Staging, Prod](#15-terraform-environments--dev-staging-prod)
16. [How Everything Flows End-to-End](#16-how-everything-flows-end-to-end)
17. [Key Design Decisions and Why](#17-key-design-decisions-and-why)
18. [What Makes This "Production-Grade"](#18-what-makes-this-production-grade)
19. [File-by-File Reference](#19-file-by-file-reference)

---

## 1. What Is This Project About?

Imagine you're a telecom company. You have thousands of customers, and some of them are about to leave (churn). If you could predict WHO is going to leave BEFORE they leave, you could offer them a discount, upgrade their plan, or reach out — and keep them. That's worth millions.

This project does exactly that:

1. **Takes customer data** (age, tenure, support calls, spending, etc.)
2. **Trains a machine learning model** (XGBoost/Random Forest) to learn the pattern of "customers who left vs. customers who stayed"
3. **Deploys that model as a web API** so anyone can send customer data and get back: "this customer has a 78% chance of leaving"
4. **Explains WHY** the model thinks so (using SHAP values — "support calls are high, spending dropped")
5. **Runs on AWS** with proper infrastructure (SageMaker for training, ECR for Docker images, S3 for data)
6. **Has complete infrastructure-as-code** (Terraform) — the entire AWS setup can be created/destroyed with one command

**In one sentence:** It's an end-to-end ML system that predicts customer churn, serves predictions via an API, and has production-grade cloud infrastructure managed by code.

---

## 2. The Big Picture — How Everything Connects

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DEVELOPER'S LAPTOP                          │
│                                                                     │
│   data/customer_churn.csv ──→ ml_experiment.ipynb ──→ model/*.joblib│
│         (raw data)             (train model)          (saved model) │
│                                                                     │
│   src/api.py ──→ Dockerfile ──→ Docker Image                       │
│   (FastAPI app)    (package it)   (ready to ship)                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │ git push
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        GITHUB                                       │
│                                                                     │
│   .github/workflows/ci-cd.yml                                      │
│   1. Run tests (pytest)                                             │
│   2. Lint code (flake8)                                             │
│   3. Build Docker image                                             │
│   4. Deploy to AWS (on main branch)                                │
└────────────────────────┬────────────────────────────────────────────┘
                         │ deploy
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS CLOUD                                    │
│                                                                     │
│   ┌─────────┐  ┌──────────┐  ┌───────────────┐  ┌──────────────┐ │
│   │   S3    │  │   ECR    │  │  SageMaker    │  │  CloudWatch  │ │
│   │ (data,  │  │ (Docker  │  │  (Notebook,   │  │  (Monitoring │ │
│   │ models) │  │  images) │  │   Endpoint)   │  │   Alarms)    │ │
│   └─────────┘  └──────────┘  └───────────────┘  └──────────────┘ │
│                                                                     │
│   All inside a VPC, encrypted with KMS, logged by CloudTrail       │
│   Managed by Terraform (8 modules, 3 environments)                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. What Existed Before (The Starting Point)

This project was originally forked from [ashishpal2702/customer-churn-aws-ml](https://github.com/ashishpal2702/customer-churn-aws-ml). The original was a basic ML experiment:

**What the original had:**

- A Jupyter notebook that loaded CSV data, trained a model, and showed metrics
- A basic SageMaker training script
- A requirements.txt

**What the original did NOT have:**

- No API (couldn't serve predictions)
- No Docker (couldn't containerize)
- No CI/CD (no automated testing/deployment)
- No tests (no quality assurance)
- No data validation (garbage in = garbage out)
- No model explainability (black box predictions)
- No infrastructure-as-code (manual AWS console clicking)
- No cost monitoring

---

## 4. What Was Built On Top (The Transformation)

The project was transformed in roughly 3 phases:

### Phase 1: Production Python Application

- **FastAPI REST API** with health checks, batch predictions, model explainability
- **Data validation module** with schema checks, outlier detection, range validation
- **Model explainability** using SHAP (explains WHY the model makes each prediction)
- **Hyperparameter tuning** module for SageMaker HPO
- **AWS cost monitoring** module to track spending
- **Unit tests** (pytest) covering the pipeline
- **Docker** multi-stage build for the API
- **CI/CD** with GitHub Actions

### Phase 2: Interview Prep Documentation

- 8 interview prep documents covering:
  - Project overview, technical deep-dive, interview questions
  - Codebase walkthrough, DevOps roadmap
  - Terraform implementation plan

### Phase 3: Production-Grade Terraform Infrastructure

This was the major engineering effort. The entire AWS infrastructure was written as code:

- **8 Terraform modules** (KMS, Security, Networking, IAM, S3, ECR, SageMaker, Monitoring)
- **3 environments** (dev, staging, prod) — each with different security/cost profiles
- **53 total `.tf` files** — all cross-validated for correctness
- Every resource encrypted with KMS CMK (Customer Managed Keys)
- VPC flow logs, CloudTrail audit, permission boundaries, composite alarms

---

## 5. The Data — Where It All Starts

### `data/customer_churn.csv` (23 MB, ~440,000 rows)

This is the raw dataset. Each row is one customer. The columns are:

| Column            | Type   | What It Means                            | Example    |
| ----------------- | ------ | ---------------------------------------- | ---------- |
| CustomerID        | int    | Unique customer identifier               | 2, 3, 4... |
| Age               | int    | Customer's age                           | 30         |
| Gender            | string | Male or Female                           | "Female"   |
| Tenure            | int    | Months they've been a customer           | 39         |
| Usage Frequency   | int    | How often they use the service per month | 14         |
| Support Calls     | int    | Number of support calls made             | 5          |
| Payment Delay     | int    | Days of payment delay                    | 18         |
| Subscription Type | string | What plan they're on                     | "Standard" |
| Contract Length   | string | Contract duration                        | "Annual"   |
| Total Spend       | float  | Total dollars spent                      | 932.0      |
| Last Interaction  | int    | Days since last interaction              | 17         |
| **Churn**         | int    | **Did they leave?** 1=yes, 0=no          | 1          |

The `Churn` column is the **target variable** — it's what we're trying to predict.

### `data/customer_churn_processed.csv` (71 MB)

This is the same data after one-hot encoding (converting categorical columns like "Gender" and "Subscription Type" into numbers). This is what SageMaker actually trains on.

### Intuitive Understanding of the Features

Think of it like a doctor diagnosing a patient:

- **High support calls** = customer is frustrated → more likely to churn
- **High payment delay** = customer doesn't care anymore → churn signal
- **Long tenure** = customer has been loyal for years → less likely to churn
- **High usage frequency** = customer actively uses the product → less likely to churn
- **Monthly contract** = easy to cancel → higher churn risk than Annual

The ML model learns these patterns from 440K historical examples.

---

## 6. The ML Notebooks — Experimentation Phase

### `ml_experiment.ipynb`

This is the main experimentation notebook. It:

1. Loads `customer_churn.csv`
2. Does exploratory data analysis (EDA) — histograms, correlations, churn distribution
3. Preprocesses: handles missing values, encodes categorical features, scales numericals
4. Trains multiple models: Logistic Regression, Random Forest, XGBoost, Gradient Boosting
5. Compares them using ROC-AUC, accuracy, precision, recall, F1
6. Picks the best one (typically XGBoost with ROC-AUC ~0.887)
7. Saves the trained model as `model/best_model_xgboost.joblib`
8. Shows feature importance and SHAP plots

### `ml_experiment_mlflow.ipynb`

Same as above but uses **MLflow** for experiment tracking. MLflow logs:

- Every hyperparameter tried
- Every metric achieved
- Model artifacts
- Lets you compare runs in a dashboard

### `sagemaker/sagemaker_e2e.ipynb`

End-to-end SageMaker notebook that:

1. Creates a SageMaker session
2. Uploads data to S3
3. Configures and runs a training job on an `ml.m5.large` instance
4. Deploys the model to an endpoint
5. Tests predictions against the endpoint
6. Cleans up (deletes endpoint to stop charges)

---

## 7. The Source Code (`src/`) — Production Python

### `src/__init__.py`

Just declares the package version (2.0.0) and author. Nothing else.

### `src/data_validation.py` — Data Quality Gatekeeper

**Why it exists:** In production, you can't just trust that data is clean. What if someone sends you a CSV with a missing column? Or ages of 500? Or a new gender value like "Other" that the model wasn't trained on?

**What it does:**

- **Schema validation:** Checks every expected column exists with correct types
- **Missing value detection:** Fails if >5% missing, warns if any
- **Duplicate detection:** Finds duplicate CustomerIDs
- **Categorical validation:** Ensures Gender is only "Male"/"Female", Subscription is only "Basic"/"Standard"/"Premium"
- **Numerical bounds:** Age must be 18-100, Tenure 0-100, etc.
- **Outlier detection:** Uses IQR method to find statistical outliers
- **Target balance:** Checks if churn rate is too extreme (e.g., 99% churn = useless model)

**How it works:**

```python
validator = DataValidator()
passed, results = validator.validate(df)
report = validator.generate_report()  # Human-readable report
```

Has two modes:

- **Normal mode:** Failures = fail, warnings = still pass
- **Strict mode:** Anything abnormal = fail

### `src/model_explainability.py` — The "Why" Behind Predictions

**Why it exists:** A model that says "this customer will churn" is useful. A model that says "this customer will churn BECAUSE their support calls are 3x higher than average and their spending dropped 40%" is 10x more useful. Also required for GDPR "right to explanation."

**What it does (using SHAP):**

SHAP (SHapley Additive exPlanations) comes from game theory. Imagine you have 10 features. SHAP asks: "For this specific prediction, how much did each feature push the prediction up or down?"

- **Global explanation:** Across all customers, which features matter most? (Total Spend, Support Calls, Usage Frequency are typically top 3)
- **Local explanation:** For THIS specific customer, why did the model predict churn?
- **Feature interactions:** Do some features interact? (e.g., high support calls + low tenure = very high churn)

It also generates:

- Bar plots (feature importance)
- Beeswarm plots (shows direction — high value = more churn?)
- Waterfall plots (individual prediction breakdown)
- Model cards (documentation for compliance)

### `src/hyperparameter_tuning.py` — Automated Model Optimization

**Why it exists:** Choosing `n_estimators=100, max_depth=10` by hand is guessing. Hyperparameter tuning systematically tries hundreds of combinations to find the best one.

**What it does:**

- Creates SageMaker Hyperparameter Tuning jobs
- Uses **Bayesian optimization** (smarter than random search — learns from previous jobs)
- Supports Random Forest, XGBoost, and Gradient Boosting
- Includes cost estimation before running
- Deploys the best model automatically

**Key design choice:** Uses `early_stopping_type='Auto'` — if a training job is clearly not going to beat the current best, SageMaker kills it early. This saves money.

### `src/cost_monitor.py` — Money Tracker

**Why it exists:** SageMaker endpoints cost money every second they're running. An `ml.t2.medium` is $0.056/hour = $40/month. An `ml.m5.xlarge` is $0.23/hour = $166/month. Forget to delete an endpoint? That's your AWS bill.

**What it does:**

- Lists all active SageMaker endpoints with their running costs
- Shows recent training job costs
- Projects monthly costs
- Generates optimization recommendations ("hey, this endpoint has been running 72 hours")
- Can auto-delete idle endpoints (with dry-run mode for safety)

---

## 8. The API (`src/api.py`) — Serving Predictions

This is a **FastAPI** web application. Think of it as a waiter at a restaurant — customers (other services) come in, place orders (send customer data), and get back predictions.

### Endpoints:

| Method                | Path                                                                   | What It Does |
| --------------------- | ---------------------------------------------------------------------- | ------------ |
| `GET /`               | Root — returns API info and version                                    |
| `GET /health`         | Health check — is the model loaded?                                    |
| `POST /predict`       | Single prediction — send one customer, get one prediction              |
| `POST /predict/batch` | Batch prediction — send many customers, get all predictions at once    |
| `POST /explain`       | Explainable prediction — prediction + SHAP-style feature contributions |
| `GET /model/info`     | What model is loaded? How many features? How many trees?               |

### Request Validation

The API uses **Pydantic models** to validate input. If you send `Age: 150`, it rejects it immediately with a clear error. If you send `Gender: "Unknown"`, rejected. This prevents garbage from reaching the model.

```python
class CustomerFeatures(BaseModel):
    Age: int = Field(..., ge=18, le=100)
    Gender: str  # validated to be "Male" or "Female"
    Subscription_Type: str  # validated to be "Basic"/"Standard"/"Premium"
    # ... etc
```

### Startup

When the API starts, it loads the model and preprocessor from disk:

```
MODEL_PATH=/app/model/best_model_xgboost.joblib
PREPROCESSOR_PATH=/app/model/preprocessor.joblib
```

These paths are set via environment variables (Docker-friendly).

### Risk Levels

The API doesn't just return probability — it maps it to business-friendly risk levels:

- `>= 0.7` → **HIGH** (contact customer immediately)
- `>= 0.4` → **MEDIUM** (monitor closely)
- `< 0.4` → **LOW** (customer is likely stable)

---

## 9. SageMaker Scripts — Cloud ML Training

### `sagemaker/training.py`

This script runs **inside a SageMaker training instance**. SageMaker spins up an EC2 machine, puts your data in `/opt/ml/input/data/train/`, runs this script, and expects the trained model to be saved in `/opt/ml/model/`.

**What it does:**

1. Parses hyperparameters from command line args (SageMaker passes them as `--n-estimators 100`)
2. Loads CSV from the training channel directory
3. Splits into train/validation (80/20)
4. Trains a RandomForestClassifier
5. Logs metrics (accuracy, classification report, feature importance)
6. Saves model as `model.joblib`

### `sagemaker/inference.py`

This script runs **inside a SageMaker endpoint** (the deployed model). It implements 4 SageMaker handler functions:

| Function                               | When Called      | What It Does                                       |
| -------------------------------------- | ---------------- | -------------------------------------------------- |
| `model_fn(model_dir)`                  | Endpoint startup | Loads `model.joblib` from disk                     |
| `input_fn(request_body, content_type)` | Every request    | Parses JSON or CSV input into a DataFrame          |
| `predict_fn(input_data, model)`        | Every request    | Runs `model.predict()` and `model.predict_proba()` |
| `output_fn(prediction, content_type)`  | Every response   | Formats output as JSON                             |

There's also `transform_fn` which combines all three for batch transform jobs.

---

## 10. The Tests — Quality Assurance

### `tests/test_pipeline.py`

Contains 5 test classes with ~12 test methods:

**TestDataValidator:**

- `test_valid_data_passes` — generate clean synthetic data, assert validator passes
- `test_missing_columns_detected` — drop columns, assert failure
- `test_invalid_categories_detected` — inject "Unknown" gender, assert failure
- `test_out_of_bounds_detected` — set Age=150, assert warning/failure
- `test_strict_mode` — verify strict mode is more restrictive
- `test_report_generation` — validate report format
- `test_empty_dataframe` — edge case, should fail gracefully

**TestPreprocessing:**

- Tests StandardScaler + OneHotEncoder produce correct output shape (7 numerical + 5 one-hot = 12 features)
- Tests scaling produces mean≈0, std≈1

**TestModelPrediction:**

- Tests prediction shape (n_samples,)
- Tests probability shape (n_samples, 2)
- Tests predictions are valid (only 0 or 1)
- Tests probabilities are in [0, 1] and sum to 1

**TestInferencePipeline:**

- Tests JSON parsing (single and batch)
- Tests CSV parsing

**TestEndToEnd:**

- Full pipeline: synthetic data → split → scale → train → predict → check accuracy > 0.6

---

## 11. Docker — Containerization

### `Dockerfile` — Multi-Stage Build

**Why multi-stage?** The build stage installs compilers (gcc) to build C extensions. The production stage doesn't need compilers — smaller image, smaller attack surface.

```
Stage 1 (builder):
  python:3.9-slim + gcc → install all Python packages → heavy image

Stage 2 (production):
  python:3.9-slim (no gcc) → copy only the installed packages → lean image
```

**Security features:**

- Runs as `appuser` (non-root) — even if the container is compromised, attacker can't modify the system
- `HEALTHCHECK` instruction — Docker knows when the container is unhealthy
- `PYTHONUNBUFFERED=1` — logs appear in real-time (important for CloudWatch)

**What's in the image:**

```
/app/
  src/api.py          ← the FastAPI app
  model/*.joblib      ← trained model files (if present)
  data/               ← data files
```

**Startup command:** `uvicorn src.api:app --host 0.0.0.0 --port 8000`

### `requirements.txt` vs `requirements-api.txt` vs `requirements-minimal.txt`

| File                       | Purpose               | What's In It                                                             |
| -------------------------- | --------------------- | ------------------------------------------------------------------------ |
| `requirements.txt`         | Full ML environment   | pandas, numpy, sklearn, xgboost, shap, sagemaker, boto3, mlflow, jupyter |
| `requirements-api.txt`     | API-only dependencies | fastapi, uvicorn, pydantic, httpx                                        |
| `requirements-minimal.txt` | CI/testing only       | pandas, numpy, sklearn, joblib, pytest, flake8                           |

---

## 12. CI/CD — Automated Pipeline

### `.github/workflows/ci-cd.yml`

This runs automatically on every `git push`. It has 4 jobs:

```
Push to GitHub
     │
     ▼
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌────────┐
│  TEST   │────→│  BUILD  │────→│  DEPLOY  │     │ NOTIFY │
│         │     │         │     │          │     │        │
│ pytest  │     │ Docker  │     │ SageMaker│     │Summary │
│ flake8  │     │ build   │     │ (main    │     │ table  │
│ black   │     │         │     │  only)   │     │        │
│ coverage│     │         │     │          │     │        │
└─────────┘     └─────────┘     └──────────┘     └────────┘
```

**Test job:**

- Installs Python 3.9 with pip cache
- Runs flake8 lint (critical errors first, then style)
- Runs black format check
- Runs pytest with coverage
- Uploads coverage to Codecov

**Build job (only if tests pass):**

- Uses Docker Buildx (faster builds with caching)
- Builds the image but doesn't push (validation only)
- Runs a smoke test: `docker run ... python -c "import sklearn; print('OK')"`

**Deploy job (only on main branch push):**

- Configures AWS credentials from GitHub Secrets
- Uploads data to S3
- Placeholder for actual SageMaker deployment script

**Notify job (always runs):**

- Writes a summary table to GitHub Actions Summary

---

## 13. Terraform — The Infrastructure (The Big One)

### What Is Terraform?

Imagine you need to set up AWS: create a VPC, subnets, security groups, IAM roles, S3 buckets, ECR repos, SageMaker notebook, CloudWatch alarms, KMS keys, CloudTrail... That's hundreds of clicks in the AWS Console. If you need to do it again for staging? Another hundred clicks. For prod? Again.

**Terraform** lets you write all of this as code:

```hcl
resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
}
```

Then run `terraform apply` and it creates everything. Run `terraform destroy` and it tears it all down. Change one parameter and run `apply` again — it updates only what changed.

### Why This Terraform Is Special

Most Terraform tutorials create a VPC and an EC2 instance. This project has **production-grade** infrastructure with:

- **8 modules** — each does one thing well and can be reused
- **3 environments** — dev (cheap, relaxed), staging (medium), prod (expensive, locked down)
- **KMS encryption everywhere** — Customer Managed Keys, not default AWS keys
- **VPC Flow Logs** — captures all network traffic (compliance requirement)
- **CloudTrail** — logs every API call to AWS (audit requirement)
- **Permission boundaries** — even if an IAM role has `*` permissions, the boundary restricts it
- **S3 bucket policies** — deny unencrypted access, require TLS
- **Composite CloudWatch alarms** — one alarm that aggregates 6 individual signals
- **Anomaly detection** — automatically detects unusual patterns

### Directory Structure

```
terraform/
├── .terraform-version          ← pins Terraform to 1.6.0
├── .tflint.hcl                 ← linting rules (naming conventions)
├── terraform.tfvars.example    ← template for user-specific values
├── README.md                   ← architecture docs
│
├── backend/                    ← S3 + DynamoDB for state storage
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
│
├── modules/
│   ├── kms/                    ← KMS encryption keys (4 CMK keys)
│   ├── security/               ← CloudTrail audit logging
│   ├── networking/             ← VPC, subnets, NAT, security groups
│   ├── iam/                    ← IAM roles with permission boundaries
│   ├── s3/                     ← S3 buckets (data, models, access logs)
│   ├── ecr/                    ← ECR Docker registry
│   ├── sagemaker/              ← SageMaker notebook + endpoint
│   └── monitoring/             ← CloudWatch dashboard + alarms
│
└── environments/
    ├── dev/                    ← cheap, fast iteration
    ├── staging/                ← production-like but cheaper
    └── prod/                   ← full security + reliability
```

### The Module Pattern

Each module follows this structure:

```
module_name/
├── versions.tf    ← provider version constraints
├── locals.tf      ← naming convention + tags (computed once, used everywhere)
├── variables.tf   ← inputs (what the caller provides)
├── main.tf        ← the actual resources
└── outputs.tf     ← what the module exposes to callers
```

**Why `locals.tf`?**
Instead of writing `"${var.project_name}-${var.environment}-thing"` in 15 places, you write it once:

```hcl
locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
```

Then use `local.name_prefix` everywhere. Change the naming pattern? One place.

**Why `versions.tf`?**
Terraform providers get updated. Version 5.0 of the AWS provider might have breaking changes. Pinning `~> 5.0` means "5.x only, not 6.0". This prevents surprise breakage.

---

## 14. Terraform Module-by-Module Deep Dive

### Module 1: KMS (Encryption Foundation)

**Think of it like:** A locksmith who makes 4 special keys. Every other module comes to this locksmith to get their key for locking their data.

**What it creates:**
| Key | Who Uses It | What It Encrypts |
|-----|-------------|-----------------|
| S3 Key | S3 module | Data buckets, model buckets, state bucket |
| CloudWatch Key | Networking, Monitoring | Log groups (flow logs, application logs) |
| SNS Key | Monitoring | Alert notification messages |
| SageMaker Key | SageMaker | Notebook volumes, model artifacts |

**Why CMK instead of default AWS keys?**

- You control the key policy (who can use it)
- You get CloudTrail logs of every encrypt/decrypt operation
- You can rotate keys automatically
- Required for SOC2/HIPAA compliance

**Smart feature:** `deletion_window_in_days` is configurable per environment:

- Dev: 7 days (quick cleanup)
- Staging: 14 days (some safety)
- Prod: 30 days (maximum protection against accidental deletion)

---

### Module 2: Security (Audit & Compliance)

**Think of it like:** A security camera system for your AWS account. Records every single thing anyone does.

**What it creates:**

- **CloudTrail trail** — logs every AWS API call (who created what, who deleted what, who accessed what)
- **Dedicated S3 bucket** for trail logs (encrypted with KMS, lifecycle policies)
- **CloudWatch Log Group** for trail delivery (quick queries with CloudWatch Insights)

**Key configuration options:**

- `enable_cloudtrail` — off in dev (saves money), on in staging/prod
- `enable_s3_data_events` — logs every S3 read/write. Off by default (very verbose). On in prod.
- `trail_retention_days` — 90 in staging, 365 in prod (compliance requires 1 year)

**Why separate from other modules?** CloudTrail is a cross-cutting concern — it audits everything. If it were inside the S3 module or IAM module, you'd have circular dependencies.

---

### Module 3: Networking (VPC)

**Think of it like:** Building a private office building with controlled entrances.

**What it creates:**

```
     Internet
        │
   ┌────▼────┐
   │  IGW    │  ← Internet Gateway (front door)
   └────┬────┘
        │
 ┌──────▼──────┐
 │ Public      │  ← Subnet with public IP (if needed)
 │ Subnet(s)   │
 └──────┬──────┘
        │
   ┌────▼────┐
   │  NAT    │  ← Network Address Translation (private → internet, one way)
   │  GW     │
   └────┬────┘
        │
 ┌──────▼──────┐
 │ Private     │  ← Where SageMaker notebooks and endpoints live
 │ Subnet(s)   │    No direct internet access (security)
 └─────────────┘
```

**Security groups (firewall rules):**

- SageMaker SG: allows HTTPS outbound only (needs to reach S3, ECR)
- No inbound rules from the internet

**VPC Endpoints (private AWS access):**

- S3 Gateway endpoint → SageMaker talks to S3 without going through the internet
- SageMaker API endpoint → internal VPC access
- STS endpoint → for IAM role assumption

**VPC Flow Logs:**

- Captures metadata about ALL network traffic (source IP, dest IP, port, accept/reject)
- Stored in CloudWatch Log Group (encrypted with KMS)
- Required for SOC2/HIPAA/PCI-DSS

**Environment differences:**

- Dev: 2 AZs, 1 NAT Gateway (cheaper — $32/month per NAT)
- Prod: 2 AZs, 2 NAT Gateways (high availability — if one AZ goes down, the other still works)

---

### Module 4: IAM (Identity & Access Management)

**Think of it like:** An HR department that issues ID badges with specific permissions.

**What it creates:**

| Role                     | Who Uses It       | What It Can Do                                                      |
| ------------------------ | ----------------- | ------------------------------------------------------------------- |
| SageMaker Execution Role | SageMaker service | Read/write S3, pull ECR images, write CloudWatch logs, use KMS keys |
| CI/CD Role (OIDC)        | GitHub Actions    | Push to ECR, deploy SageMaker, read S3                              |
| Monitoring Role          | CloudWatch        | Write logs, publish SNS                                             |

**OIDC Federation (the cool part):**
Instead of putting AWS access keys in GitHub Secrets (risky — if leaked, attacker has access), we use OIDC:

1. GitHub Actions says: "I am a workflow from repo VahantSharma/customer-churn-aws-ml"
2. AWS says: "I trust GitHub's identity provider. Here's temporary credentials for 1 hour."
3. No static keys anywhere. No rotation needed. No leak risk.

**Permission Boundaries:**
Even if someone attaches `AdministratorAccess` to the SageMaker role (by mistake), the permission boundary limits it to only S3, SageMaker, ECR, CloudWatch, and KMS. Defense-in-depth.

---

### Module 5: S3 (Storage)

**Think of it like:** A filing cabinet system with 3 drawers, each locked with its own key.

**What it creates:**

| Bucket             | Purpose                          | Lifecycle                                                                 |
| ------------------ | -------------------------------- | ------------------------------------------------------------------------- |
| Data bucket        | Training data (CSVs)             | → IA after 90 days → Glacier after 365                                    |
| Model bucket       | Trained model artifacts          | → IA after 180 days (models rarely accessed after newer ones are trained) |
| Access logs bucket | Audit trail of who accessed what | AES256 encrypted (logging bucket can't use CMK — chicken-and-egg)         |

**Security policies:**

- **TLS-only:** Every bucket has a policy that denies any request not using HTTPS
- **Versioning:** Enabled on data and model buckets (accidental deletion recovery)
- **KMS encryption:** Server-side encryption with CMK keys from the KMS module
- **Public access blocked:** `aws_s3_bucket_public_access_block` set to block everything

**Why 3 separate buckets instead of 1?**

- Different lifecycle policies (data gets cold faster than models)
- Different access patterns (CI/CD writes models, SageMaker reads data)
- Blast radius — if one bucket is compromised, the others are isolated

---

### Module 6: ECR (Container Registry)

**Think of it like:** A private Docker Hub inside your AWS account.

**What it creates:**

- One ECR repository for the Docker image
- Image scanning on push (checks for vulnerabilities like CVE-2024-XXXX)
- Lifecycle policy: keep only the last N images
- KMS encryption on stored images

**Why ECR instead of Docker Hub?**

- Private (no one outside your AWS account can pull images)
- Integrated with IAM (fine-grained access control)
- Vulnerability scanning built-in
- No external network dependency for SageMaker to pull images

---

### Module 7: SageMaker (The ML Engine)

**Think of it like:** A fully-equipped lab for training and deploying ML models.

**What it creates:**

**Notebook Instance:**

- A Jupyter notebook in the cloud, inside your VPC
- Git repo pre-configured
- KMS-encrypted volume
- `ml.t3.medium` in dev, `ml.m5.xlarge` in prod
- Lifecycle config for auto-idle shutdown (cost savings)

**Model Package Group:**

- A "registry" for model versions
- Each trained model gets a version number
- You can approve/reject model versions before deployment
- Think of it like a staging area for models

**Endpoint (optional — only if `deploy_endpoint = true`):**

- A running inference server that responds to API calls
- Uses `create_before_destroy` lifecycle — new endpoint is healthy before old one dies (zero-downtime deployments)
- `name_prefix` instead of `name` — because endpoints have unique names, and Terraform needs to create a new one before destroying the old one

**The `timestamp()` Bug Fix:**
The original code used `timestamp()` in endpoint names. Problem: `timestamp()` changes every second, so every `terraform plan` showed "will destroy and recreate endpoint." Fixed by using `name_prefix` + `create_before_destroy`.

---

### Module 8: Monitoring (Observability)

**Think of it like:** A control room with dashboards and alarm bells.

**What it creates:**

**SNS Topic (Alert Channel):**

- Where alarms send notifications
- Email subscription for the team
- Encrypted with KMS
- Topic policy: only CloudWatch can publish, only over TLS

**CloudWatch Dashboard:**

- Visual display of all key metrics
- Header widget showing project name and environment
- Alarm status widget (green/red overview)
- Charts: invocations, latency, errors, CPU, memory, disk

**6 Individual Alarms:**

| Alarm              | Threshold (Prod) | What It Catches        |
| ------------------ | ---------------- | ---------------------- |
| 5XX Error Rate     | ≥ 1 per period   | Model is crashing      |
| Model Latency      | ≥ 2 seconds      | Model is too slow      |
| No Invocations     | = 0 for period   | Endpoint might be dead |
| CPU Utilization    | ≥ 80%            | Need to scale up       |
| Memory Utilization | ≥ 85%            | About to OOM           |
| Disk Utilization   | ≥ 80%            | Disk is filling up     |

**Composite Alarm:**

- Combines 5XX errors, latency, and no-invocations into ONE alarm
- Triggers when ANY of them fire
- This is what you page for — "endpoint health is degraded"

**Anomaly Detection:**

- ML-based monitoring on invocation volume
- CloudWatch learns the normal pattern (e.g., 100 requests/hour during business hours, 10 at night)
- Alerts when something deviates (sudden spike = possible DDoS, sudden drop = possible outage)

**3 Log Groups:**

- `/aws/sagemaker/endpoints/{name}` — model inference logs
- `/aws/sagemaker/training/{name}` — training job logs
- `/custom/{name}/application` — application-level logs

---

## 15. Terraform Environments — Dev, Staging, Prod

Each environment is a root module that composes all 8 child modules with environment-specific settings.

### How Environments Are Structured

```
environments/dev/main.tf:
  module "kms"        { source = "../../modules/kms"        ... }
  module "security"   { source = "../../modules/security"   ... }
  module "networking" { source = "../../modules/networking" ... }
  module "iam"        { source = "../../modules/iam"        ... }
  module "s3"         { source = "../../modules/s3"         ... }
  module "ecr"        { source = "../../modules/ecr"        ... }
  module "sagemaker"  { source = "../../modules/sagemaker"  ... }
  module "monitoring" { source = "../../modules/monitoring" ... }
```

### Environment Comparison Table

| Setting                     | Dev               | Staging     | Prod                     |
| --------------------------- | ----------------- | ----------- | ------------------------ |
| **KMS deletion window**     | 7 days            | 14 days     | 30 days                  |
| **CloudTrail**              | Disabled          | Enabled     | Enabled + S3 data events |
| **Trail retention**         | —                 | 90 days     | 365 days                 |
| **NAT Gateways**            | 1 (cheap)         | 1           | 2 (HA)                   |
| **VPC Flow Logs**           | 14 days retention | 30 days     | 90 days                  |
| **Notebook instance**       | ml.t3.medium      | ml.t3.large | ml.m5.xlarge             |
| **Endpoint deployed**       | No (manual)       | No          | Yes                      |
| **S3 expiration**           | 365 days          | 365 days    | 730 days (2 years)       |
| **Error alarm threshold**   | 5 errors          | 3 errors    | 1 error                  |
| **Latency alarm threshold** | 5 seconds         | 3 seconds   | 2 seconds                |
| **CPU alarm threshold**     | 90%               | 85%         | 80%                      |
| **ECR force_delete**        | true              | true        | false                    |

### Why These Choices?

**Dev is cheap and disposable:**

- No CloudTrail (saves ~$2/month in storage)
- Single NAT Gateway ($32/month instead of $64)
- No endpoint deployed by default (biggest cost saver)
- KMS keys can be deleted in 7 days (iterate fast)
- Relaxed alarm thresholds (don't spam during development)

**Staging is production-like but cost-conscious:**

- CloudTrail ON (test audit logging actually works)
- Still single NAT (cost saving)
- Relaxed alarm thresholds (3 errors before alerting)

**Prod is locked down:**

- CloudTrail + S3 data events (full audit trail)
- Dual NAT Gateways (AZ failure resilient)
- Endpoint deployed by default
- 30-day KMS deletion window (maximum accidental deletion protection)
- Tight alarm thresholds (1 error = page the engineer)
- 2-year S3 retention for compliance
- ECR force_delete = false (can't accidentally wipe prod images)

---

## 16. How Everything Flows End-to-End

### Flow 1: Local Development

```
1. Developer clones repo
2. Creates venv, installs requirements
3. Runs ml_experiment.ipynb → trains model → saves to model/
4. Runs uvicorn src.api:app → starts API on localhost:8000
5. Sends curl requests to /predict → gets predictions
6. Runs pytest → all tests pass
7. Commits and pushes to GitHub
```

### Flow 2: CI/CD Pipeline

```
1. Push triggers GitHub Actions
2. Tests run (pytest + flake8)
3. Docker image builds and passes smoke test
4. (On main branch) AWS credentials are configured
5. Data uploaded to S3
6. Deployment to SageMaker triggered
```

### Flow 3: Training on SageMaker

```
1. Data is in S3 (uploaded by CI/CD or manually)
2. SageMaker training job spins up ml.m5.large instance
3. training.py runs:
   - Loads CSV from /opt/ml/input/data/train/
   - Trains RandomForest
   - Saves model.joblib to /opt/ml/model/
4. SageMaker packages model as model.tar.gz
5. Uploads to S3 (model bucket)
6. Training instance is terminated (stop paying)
```

### Flow 4: Serving Predictions

```
1. SageMaker endpoint is created (ml.t2.medium)
2. inference.py loads model from model.tar.gz
3. Request comes in (JSON or CSV)
4. input_fn() parses it → DataFrame
5. predict_fn() runs model.predict() → prediction + probabilities
6. output_fn() formats as JSON
7. Response sent back to caller
```

### Flow 5: Infrastructure Provisioning

```
1. cd terraform/environments/dev
2. terraform init (downloads providers, configures backend)
3. terraform plan (shows what will be created)
4. terraform apply (creates everything in AWS)
   → KMS keys
   → VPC + subnets + NAT + security groups + flow logs
   → IAM roles with permission boundaries
   → S3 buckets (data, model, access logs) with KMS
   → ECR repository
   → SageMaker notebook + model registry
   → CloudWatch dashboard + alarms + SNS topic
5. terraform output (shows important ARNs and URLs)
```

---

## 17. Key Design Decisions and Why

### Decision 1: FastAPI over Flask

FastAPI is faster (async), has automatic OpenAPI docs, and Pydantic gives you request validation for free. Flask would require writing all of that manually.

### Decision 2: XGBoost as the Primary Model

XGBoost handles tabular data better than neural networks. It's fast to train, works well with SHAP for explainability, and is the industry standard for classification on structured data.

### Decision 3: SHAP over LIME

SHAP has theoretical guarantees (Shapley values from game theory). LIME is an approximation that can give inconsistent results. For compliance (GDPR right to explanation), SHAP's mathematical foundation is stronger.

### Decision 4: Terraform Modules over Flat Files

With modules, you can:

- Reuse the same networking module across dev/staging/prod
- Test modules independently
- Have clear interfaces (inputs and outputs)
- Without modules, you'd have one massive 1000-line file that's impossible to maintain

### Decision 5: KMS CMK over Default Encryption

Default S3 encryption uses AWS-managed keys — you can't see who used them. CMK gives you CloudTrail audit logs of every encrypt/decrypt operation. Required for serious compliance.

### Decision 6: `name_prefix` over `name` for SageMaker Endpoints

Terraform needs to create the new resource before destroying the old one (zero downtime). But AWS requires unique names. `name_prefix` tells Terraform: "generate a unique name starting with this prefix."

### Decision 7: 3 S3 Buckets instead of 1

Different lifecycle policies, different access patterns, smaller blast radius. In production, "one bucket for everything" is a code smell.

### Decision 8: Composite Alarms

Six individual alarms = six notification emails. A composite alarm says "endpoint health is bad" — one actionable signal instead of noise.

---

## 18. What Makes This "Production-Grade"

Here's what separates this from a tutorial project:

| Aspect          | Tutorial                     | This Project                                               |
| --------------- | ---------------------------- | ---------------------------------------------------------- |
| Encryption      | Default AES256 (or none)     | KMS CMK on every resource                                  |
| IAM             | `AmazonSageMakerFullAccess`  | Least-privilege with permission boundaries                 |
| Networking      | Public subnet or default VPC | Private subnets, NAT, VPC endpoints, flow logs             |
| Logging         | print() statements           | CloudTrail + CloudWatch + structured logging               |
| State           | Local terraform.tfstate      | S3 + DynamoDB with KMS encryption and locking              |
| Variables       | Hardcoded strings            | Validated variables with type constraints                  |
| Naming          | Random names                 | `locals.tf` with consistent `{project}-{env}` prefix       |
| Monitoring      | None                         | Dashboard + 6 alarms + composite alarm + anomaly detection |
| Environments    | One folder                   | Dev/staging/prod with different security profiles          |
| Secrets         | In code                      | OIDC federation, no static credentials                     |
| Data validation | None                         | Schema, bounds, outliers, categories, target balance       |
| Testing         | None                         | pytest with coverage, pre-commit linting                   |
| API validation  | None                         | Pydantic models with field validators                      |
| Docker          | Single FROM                  | Multi-stage build, non-root user, health check             |

---

## 19. File-by-File Reference

### Root Level

| File                        | Purpose                                           |
| --------------------------- | ------------------------------------------------- |
| `Dockerfile`                | Multi-stage Docker build for the FastAPI app      |
| `Makefile`                  | Convenience commands (install, test, lint, clean) |
| `requirements.txt`          | Full Python dependencies (ML + AWS + Jupyter)     |
| `requirements-api.txt`      | API-only deps (FastAPI, Uvicorn, Pydantic)        |
| `requirements-minimal.txt`  | Minimal deps for CI testing                       |
| `setup.py`                  | Python package configuration                      |
| `.gitignore`                | Files to exclude from git                         |
| `README.md`                 | Project overview and quick start                  |
| `DEPLOYMENT_GUIDE.md`       | Step-by-step AWS deployment instructions          |
| `LICENSE`                   | MIT License                                       |
| `sagemaker-iam-policy.json` | IAM policy for SageMaker/MLflow permissions       |

### `src/` — Application Code

| File                       | Purpose                                            |
| -------------------------- | -------------------------------------------------- |
| `__init__.py`              | Package declaration (v2.0.0)                       |
| `api.py`                   | FastAPI REST API (health, predict, batch, explain) |
| `data_validation.py`       | Data quality checks (schema, bounds, outliers)     |
| `model_explainability.py`  | SHAP-based prediction explanations                 |
| `hyperparameter_tuning.py` | SageMaker HPO with Bayesian optimization           |
| `cost_monitor.py`          | AWS cost tracking and optimization                 |

### `sagemaker/` — SageMaker Scripts

| File                  | Purpose                                               |
| --------------------- | ----------------------------------------------------- |
| `training.py`         | Training script for SageMaker instances               |
| `inference.py`        | Inference handler for SageMaker endpoints             |
| `sagemaker_e2e.ipynb` | End-to-end notebook (train → deploy → test → cleanup) |

### `tests/` — Quality Assurance

| File               | Purpose                                                       |
| ------------------ | ------------------------------------------------------------- |
| `__init__.py`      | Package declaration                                           |
| `test_pipeline.py` | 12+ tests covering validation, preprocessing, prediction, e2e |

### `data/` — Datasets

| File                           | Purpose                                      |
| ------------------------------ | -------------------------------------------- |
| `customer_churn.csv`           | Raw customer data (440K rows, 12 columns)    |
| `customer_churn_processed.csv` | One-hot encoded version (71MB) for SageMaker |

### `terraform/` — Infrastructure as Code (53 files)

| Directory               | Files | Purpose                                      |
| ----------------------- | ----- | -------------------------------------------- |
| `backend/`              | 3     | S3 + DynamoDB state backend with KMS         |
| `modules/kms/`          | 4     | 4 CMK encryption keys                        |
| `modules/security/`     | 4     | CloudTrail audit logging                     |
| `modules/networking/`   | 6     | VPC, subnets, NAT, SGs, endpoints, flow logs |
| `modules/iam/`          | 5     | 3 roles with permission boundaries + OIDC    |
| `modules/s3/`           | 5     | 3 buckets with KMS, TLS policies, lifecycle  |
| `modules/ecr/`          | 4     | Docker registry with scanning and KMS        |
| `modules/sagemaker/`    | 5     | Notebook + model registry + endpoint         |
| `modules/monitoring/`   | 5     | Dashboard + 6 alarms + composite + anomaly   |
| `environments/dev/`     | 5     | Dev environment configuration                |
| `environments/staging/` | 5     | Staging environment configuration            |
| `environments/prod/`    | 5     | Production environment configuration         |

### `interview/` — Documentation

| File                                  | Purpose                         |
| ------------------------------------- | ------------------------------- |
| `01_PROJECT_OVERVIEW.md`              | High-level project description  |
| `02_TECHNICAL_DEEP_DIVE.md`           | Detailed technical architecture |
| `03_INTERVIEW_QUESTIONS.md`           | Common interview Q&A            |
| `04_PROJECT_ENHANCEMENTS.md`          | Feature enhancements made       |
| `05_QUICK_REFERENCE.md`               | Quick reference card            |
| `06_CODEBASE_WALKTHROUGH.md`          | Code walkthrough                |
| `07_DEVOPS_FUTURE_ROADMAP.md`         | Future DevOps plans             |
| `08_TERRAFORM_IMPLEMENTATION_PLAN.md` | Terraform design document       |

---

## Summary

This project is a **complete ML system** that goes from raw CSV data to production predictions on AWS, with every layer properly engineered:

1. **Data layer:** 440K customer records with validation pipeline
2. **ML layer:** XGBoost model with SHAP explainability, hyperparameter tuning
3. **API layer:** FastAPI with Pydantic validation, batch support, health checks
4. **Container layer:** Multi-stage Docker with non-root user
5. **CI/CD layer:** GitHub Actions with test → build → deploy pipeline
6. **Infrastructure layer:** 8 Terraform modules across 3 environments
7. **Security layer:** KMS everywhere, permission boundaries, CloudTrail, OIDC
8. **Monitoring layer:** Dashboard, 6 alarms, composite alarm, anomaly detection

Every piece exists for a reason. Nothing is "just for show." And if you understand this document, you understand the project better than most people who coded it.
