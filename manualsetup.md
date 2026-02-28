# Manual Setup Guide — Everything You Need to Do by Hand

> This document covers every single manual step required to make this project actually work. The code is written — but code alone doesn't deploy itself. These are the things YOU need to do.

---

## Table of Contents

1. [Prerequisites — Install These First](#1-prerequisites--install-these-first)
2. [AWS Account Setup](#2-aws-account-setup)
3. [AWS CLI Configuration](#3-aws-cli-configuration)
4. [Terraform State Backend Bootstrap](#4-terraform-state-backend-bootstrap)
5. [GitHub Secrets Configuration](#5-github-secrets-configuration)
6. [Terraform — First Deployment](#6-terraform--first-deployment)
7. [Training a Model (Getting model/.joblib Files)](#7-training-a-model-getting-modeljoblib-files)
8. [Running the API Locally](#8-running-the-api-locally)
9. [Docker Build and Run](#9-docker-build-and-run)
10. [Uploading Data to S3](#10-uploading-data-to-s3)
11. [SageMaker Training Job](#11-sagemaker-training-job)
12. [SageMaker Endpoint Deployment](#12-sagemaker-endpoint-deployment)
13. [ECR — Push Docker Image](#13-ecr--push-docker-image)
14. [CloudWatch Monitoring Setup](#14-cloudwatch-monitoring-setup)
15. [Cleanup — Avoid Surprise Bills](#15-cleanup--avoid-surprise-bills)
16. [Troubleshooting Common Issues](#16-troubleshooting-common-issues)
17. [Cost Awareness — What Costs Money](#17-cost-awareness--what-costs-money)

---

## Progress Summary (as of March 2026)

| #   | Section                     | Status              | How It Was Done                                                                                                                                        |
| --- | --------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Prerequisites               | ✅ DONE             | Installed manually on local machine                                                                                                                    |
| 2   | AWS Account Setup           | ✅ DONE             | Manual via AWS Console (IAM user uses inline admin policy instead of listed managed policies — see note)                                               |
| 3   | AWS CLI Configuration       | ✅ DONE             | `aws configure` run manually                                                                                                                           |
| 4   | Terraform Backend Bootstrap | ✅ DONE             | `terraform apply` in `terraform/backend/` — 9 resources created                                                                                        |
| 5   | GitHub Secrets              | ✅ DONE             | Configured manually in GitHub repo settings (static credentials, not OIDC)                                                                             |
| 6   | Terraform First Deployment  | ❌ NOT DONE         | `terraform apply` in `environments/dev/` has not been run yet                                                                                          |
| 7   | Training a Model            | ❌ NOT DONE         | `model/` only contains `.gitkeep` — no trained model files                                                                                             |
| 8   | Running API Locally         | ❌ NOT DONE         | Blocked by Step 7 (no model files)                                                                                                                     |
| 9   | Docker Build & Run          | ✅ DONE (via CI/CD) | Docker image builds & passes all tests in GitHub Actions. Not run locally with model.                                                                  |
| 10  | Uploading Data to S3        | ⚠️ PARTIAL          | CI/CD uploads `customer_churn_processed.csv` to `s3://customer-churn-vahant-2026/data/processed/`. Terraform-managed buckets don't exist yet (Step 6). |
| 11  | SageMaker Training Job      | ❌ NOT DONE         | Requires Steps 6 + 10                                                                                                                                  |
| 12  | SageMaker Endpoint          | ❌ NOT DONE         | Optional, costs ~$40/mo                                                                                                                                |
| 13  | ECR Push                    | ❌ NOT DONE         | ECR repo doesn't exist yet (needs Step 6)                                                                                                              |
| 14  | CloudWatch Monitoring       | ❌ NOT DONE         | Resources created by Terraform (needs Step 6)                                                                                                          |
| 15  | Cleanup                     | ⏳ N/A              | Nothing to clean up yet                                                                                                                                |
| 16  | Troubleshooting             | 📖 Reference        | No action needed                                                                                                                                       |
| 17  | Cost Awareness              | 📖 Reference        | No action needed                                                                                                                                       |

---

## 1. Prerequisites — Install These First

> ✅ **STATUS: DONE** — All tools installed and verified on local machine (Python 3.9, pip, Git, AWS CLI v2, Terraform 1.6+, Docker). Python virtual environment created and dependencies installed.

### On Your Local Machine

| Tool                 | Version | Install Command / URL                                                         | Why You Need It                     |
| -------------------- | ------- | ----------------------------------------------------------------------------- | ----------------------------------- |
| **Python**           | 3.9+    | https://www.python.org/downloads/                                             | Runs the ML code and API            |
| **pip**              | Latest  | `python -m pip install --upgrade pip`                                         | Installs Python packages            |
| **Git**              | Latest  | https://git-scm.com/downloads                                                 | Version control                     |
| **AWS CLI v2**       | Latest  | https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html | Talks to AWS from your terminal     |
| **Terraform**        | 1.6.0+  | https://developer.hashicorp.com/terraform/install                             | Deploys infrastructure              |
| **Docker**           | Latest  | https://www.docker.com/products/docker-desktop/                               | Builds container images             |
| **tfenv** (optional) | Latest  | https://github.com/tfutils/tfenv                                              | Manages multiple Terraform versions |

### Verify Installations

Run each of these and confirm they work:

```bash
python --version        # Should show 3.9+
pip --version           # Should show 20+
git --version           # Should show 2.x
aws --version           # Should show aws-cli/2.x
terraform --version     # Should show v1.6.0+
docker --version        # Should show 20+
```

### Install Python Dependencies

```bash
# Create and activate a virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
pip install -r requirements-api.txt
```

---

## 2. AWS Account Setup

> ✅ **STATUS: DONE** — AWS Account `231284356634` active, IAM user `sagemaker-developer` created with access keys.
>
> ⚠️ **NOTE:** Section 2.2 lists 10 managed IAM policies to attach. Instead, an **inline administrator policy** (`"Effect": "Allow", "Action": "*", "Resource": "*"`) was attached directly to the `sagemaker-developer` user. This was done because AWS returned a quota error when trying to attach multiple managed policies. The inline admin policy covers all the same permissions (and more). For production, this should be scoped down to least-privilege.

### 2.1 Create an AWS Account (if you don't have one)

1. Go to https://aws.amazon.com/
2. Click "Create an AWS Account"
3. Enter email, password, account name
4. Add payment method (credit card required — you get a free tier)
5. Verify phone number
6. Select "Basic Support" (free)

### 2.2 Create an IAM User (DON'T use the root account)

> **CRITICAL:** Never use the root account for day-to-day work. Create an IAM user.

1. Go to **AWS Console → IAM → Users → Create user**
2. Username: `sagemaker-developer` (or your preferred name)
3. Check "Provide user access to the AWS Management Console" (optional)
4. Click **Next**
5. Select "Attach policies directly"
6. Attach these policies:
   - `AmazonSageMakerFullAccess`
   - `AmazonS3FullAccess`
   - `AmazonEC2ContainerRegistryFullAccess`
   - `CloudWatchFullAccess`
   - `IAMFullAccess` (needed for Terraform to create roles)
   - `AWSKeyManagementServicePowerUser`
   - `CloudTrailFullAccess` (needed for security module)
   - `AmazonVPCFullAccess`
   - `AmazonSNSFullAccess`
   - `AmazonDynamoDBFullAccess` (for Terraform state locking)

   > **For production**, use a more restrictive custom policy. These are broad permissions for development. The Terraform IAM module creates properly scoped roles.

7. Click **Create user**

### 2.3 Create Access Keys

1. Go to **IAM → Users → your-user → Security credentials**
2. Scroll to "Access keys"
3. Click **Create access key**
4. Select "Command Line Interface (CLI)"
5. Check the confirmation box
6. Click **Next → Create access key**
7. **SAVE BOTH VALUES** — Secret Key is shown only once:
   - `Access key ID`: AKIA...
   - `Secret access key`: ...

> **IMPORTANT:** Never commit these to git. Never share them. If compromised, immediately deactivate from the IAM console.

---

## 3. AWS CLI Configuration

> ✅ **STATUS: DONE** — AWS CLI configured with `sagemaker-developer` credentials, region `us-east-1`, output `json`. Verified with `aws sts get-caller-identity`.

### 3.1 Configure Default Profile

```bash
aws configure
```

Enter:

```
AWS Access Key ID [None]: AKIA....YOUR_ACCESS_KEY
AWS Secret Access Key [None]: ....YOUR_SECRET_KEY
Default region name [None]: us-east-1
Default output format [None]: json
```

### 3.2 Verify It Works

```bash
aws sts get-caller-identity
```

Expected output:

```json
{
  "UserId": "AIDAXXXXXXXXXXXXXXXXX",
  "Account": "231284356634",
  "Arn": "arn:aws:iam::231284356634:user/sagemaker-developer"
}
```

If you see an error, your credentials are wrong. Re-run `aws configure`.

### 3.3 Test S3 Access

```bash
aws s3 ls
```

This should list your S3 buckets (or empty list if you're new).

---

## 4. Terraform State Backend Bootstrap

> ✅ **STATUS: DONE** — Backend bootstrapped successfully. 9 resources created:
>
> - S3 bucket: `customer-churn-terraform-state-231284356634`
> - DynamoDB table: `customer-churn-terraform-locks`
> - KMS CMK for state encryption
> - Bucket versioning, lifecycle rules, public access blocks, server-side encryption
>
> Local state file exists at `terraform/backend/terraform.tfstate`.

> **Why this step?** Terraform needs to store its state somewhere. We store it in S3 (encrypted, locked with DynamoDB). But we need to create that S3 bucket first — manually, since Terraform can't store its state in a bucket that doesn't exist yet.

### 4.1 Navigate to Backend Directory

```bash
cd terraform/backend
```

### 4.2 Initialize Terraform (local state for bootstrap only)

```bash
terraform init
```

### 4.3 Review What Will Be Created

```bash
terraform plan
```

This will show:

- S3 bucket: `customer-churn-terraform-state-{account_id}`
- DynamoDB table: `customer-churn-terraform-locks`
- KMS key for state encryption

### 4.4 Apply (Create the Backend)

```bash
terraform apply
```

Type `yes` when prompted.

### 4.5 Note the Output Values

After apply, note these output values — you'll need them:

```
state_bucket_arn = "arn:aws:s3:::customer-churn-terraform-state-231284356634"
lock_table_arn = "arn:aws:dynamodb:us-east-1:231284356634:table/customer-churn-terraform-locks"
```

> **IMPORTANT:** The backend itself uses LOCAL state (stored in `terraform.tfstate` in the backend/ directory). This is intentional — the backend bootstrap is a one-time operation. Protect this file.

---

## 5. GitHub Secrets Configuration

> ✅ **STATUS: DONE (Sections 5.1 & 5.2)** — All 4 secrets configured in GitHub repo `VahantSharma/customer-churn-aws-ml`:
>
> - `AWS_ACCESS_KEY_ID` ✅
> - `AWS_SECRET_ACCESS_KEY` ✅
> - `S3_BUCKET` = `customer-churn-vahant-2026` ✅
> - `SAGEMAKER_ROLE` = SageMaker execution role ARN ✅
>
> ❌ **Section 5.3 (OIDC Federation): NOT DONE** — Currently using static access keys. OIDC setup requires Terraform deployment (Step 6) to create the CI/CD IAM role first. Can be done later as a security improvement.

> **Why?** The CI/CD pipeline (GitHub Actions) needs AWS credentials to deploy. These are stored as GitHub Secrets — encrypted, not visible in logs.

### 5.1 Go to Repository Settings

1. Go to https://github.com/VahantSharma/customer-churn-aws-ml
2. Click **Settings** (top menu)
3. Click **Secrets and variables → Actions** (left sidebar)

### 5.2 Add These Secrets

Click **New repository secret** for each:

| Secret Name             | Value                                | Where to Get It                      |
| ----------------------- | ------------------------------------ | ------------------------------------ |
| `AWS_ACCESS_KEY_ID`     | `AKIA....`                           | From IAM user access keys (Step 2.3) |
| `AWS_SECRET_ACCESS_KEY` | The secret key                       | From IAM user access keys (Step 2.3) |
| `S3_BUCKET`             | `customer-churn-vahant-2026`         | Your S3 bucket name                  |
| `SAGEMAKER_ROLE`        | `arn:aws:iam::231284356634:role/...` | From IAM console or Terraform output |

### 5.3 (Better Alternative) Set Up OIDC Federation

Instead of static credentials, use OIDC federation — the Terraform IAM module creates this role. After Terraform apply:

1. Get the CI/CD role ARN from Terraform outputs: `module.iam.cicd_role_arn`
2. Update `.github/workflows/ci-cd.yml` to use OIDC:

```yaml
- name: Configure AWS
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::231284356634:role/customer-churn-dev-cicd
    aws-region: us-east-1
```

This eliminates the need for `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` secrets entirely.

---

## 6. Terraform — First Deployment

> ❌ **STATUS: NOT YET DONE** — Only the backend (Step 4) has been bootstrapped. The actual infrastructure deployment (`terraform init` + `terraform apply` in `terraform/environments/dev/`) has not been run. This step creates ~30-40 resources including VPC, S3 data/model buckets, ECR repo, IAM roles, SageMaker notebook, CloudWatch dashboard, SNS topic, etc. Estimated cost: ~$37-73/month when idle.

### 6.1 Create Your terraform.tfvars

```bash
cd terraform/environments/dev
```

The `terraform.tfvars` file should already exist. If not, create one based on the example:

```bash
cp ../../terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region      = "us-east-1"
project_name    = "customer-churn"
github_repo     = "VahantSharma/customer-churn-aws-ml"
deploy_endpoint = false
alert_email     = "your-real-email@gmail.com"
```

### 6.2 Initialize Terraform

```bash
terraform init
```

This downloads providers and configures the S3 backend. You should see:

```
Terraform has been successfully initialized!
```

> **If you get a backend error:** Make sure Step 4 (Bootstrap) was completed successfully. The S3 bucket and DynamoDB table must exist.

### 6.3 Plan

```bash
terraform plan -out=plan.tfplan
```

Review the plan carefully. For a fresh deployment, expect ~30-40 resources.

### 6.4 Apply

```bash
terraform apply plan.tfplan
```

This will take 5-15 minutes. The slowest resources are:

- NAT Gateway (~2 min)
- VPC Endpoints (~3 min)
- SageMaker Notebook Instance (~5 min)

### 6.5 After Apply — Subscribe to SNS Alerts

When Terraform creates the SNS topic and email subscription, AWS sends a confirmation email. **You MUST confirm it:**

1. Check your inbox for email from `no-reply@sns.amazonaws.com`
2. Subject: "AWS Notification - Subscription Confirmation"
3. Click the **Confirm subscription** link

If you don't confirm, you'll never receive alarm notifications.

### 6.6 View Outputs

```bash
terraform output
```

Save these — you'll need them:

```
vpc_id = "vpc-0abc123..."
sagemaker_notebook_url = "https://customer-churn-dev-notebook.notebook.us-east-1.sagemaker.aws"
ecr_repository_url = "231284356634.dkr.ecr.us-east-1.amazonaws.com/customer-churn-dev"
data_bucket_name = "customer-churn-data-dev-231284356634"
model_bucket_name = "customer-churn-models-dev-231284356634"
sagemaker_execution_role_arn = "arn:aws:iam::231284356634:role/customer-churn-dev-sagemaker-execution"
```

---

## 7. Training a Model (Getting model/.joblib Files)

> ❌ **STATUS: NOT YET DONE** — The `model/` directory currently only contains `.gitkeep`. No trained model files (`best_model_xgboost.joblib`, `preprocessor.joblib`) exist yet. Training can be done via Option A (local script, free and quickest) without needing Terraform deployment.

The API needs trained model files to serve predictions. There are 3 ways to get them:

### Option A: Train Locally (Quickest, Free)

```bash
# Make sure venv is activated
cd /path/to/project

# Run the notebook or use this script:
python -c "
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib

# Load data
df = pd.read_csv('data/customer_churn.csv')

# Prepare
X = df.drop(['CustomerID', 'Churn'], axis=1)
y = df['Churn']

num_cols = ['Age', 'Tenure', 'Usage Frequency', 'Support Calls', 'Payment Delay', 'Total Spend', 'Last Interaction']
cat_cols = ['Gender', 'Subscription Type', 'Contract Length']

preprocessor = ColumnTransformer([
    ('num', StandardScaler(), num_cols),
    ('cat', OneHotEncoder(drop='first', sparse_output=False), cat_cols)
])

X_processed = preprocessor.fit_transform(X)
X_train, X_test, y_train, y_test = train_test_split(X_processed, y, test_size=0.2, random_state=42)

# Train
model = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
model.fit(X_train, y_train)

# Save
joblib.dump(model, 'model/best_model_xgboost.joblib')
joblib.dump(preprocessor, 'model/preprocessor.joblib')
print(f'Accuracy: {model.score(X_test, y_test):.4f}')
print('Model saved to model/')
"
```

### Option B: Use the Jupyter Notebook

```bash
jupyter notebook ml_experiment.ipynb
```

Run all cells. The notebook saves the model at the end.

### Option C: Train on SageMaker (Cloud)

See [Step 11: SageMaker Training Job](#11-sagemaker-training-job).

---

## 8. Running the API Locally

> ❌ **STATUS: NOT YET DONE** — Blocked by Step 7 (no model files exist). Once model files are trained and saved to `model/`, this can be tested with `uvicorn src.api:app --reload`.

### 8.1 Make Sure Model Files Exist

```bash
ls model/
# Should show: best_model_xgboost.joblib  preprocessor.joblib
```

If not, complete Step 7 first.

### 8.2 Start the API

```bash
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started reloader process
INFO:     Model loaded from model/best_model_xgboost.joblib
```

### 8.3 Test It

**Health check:**

```bash
curl http://localhost:8000/health
```

**Single prediction:**

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "Age": 35,
    "Tenure": 24,
    "Usage Frequency": 15,
    "Support Calls": 2,
    "Payment Delay": 5,
    "Total Spend": 1500.50,
    "Last Interaction": 14,
    "Gender": "Male",
    "Subscription Type": "Standard",
    "Contract Length": "Annual"
  }'
```

**API documentation:**
Open http://localhost:8000/docs in your browser — interactive Swagger UI.

---

## 9. Docker Build and Run

> ✅ **STATUS: DONE (via GitHub Actions CI/CD — not manually)**
>
> The Docker image was **not built and run manually** as described below. Instead, it was built and tested automatically by the GitHub Actions CI/CD pipeline (`.github/workflows/ci-cd.yml`, **Build Docker** job).
>
> **What CI/CD does:**
>
> - Builds multi-stage Docker image using BuildKit with GitHub Actions cache
> - Runs 3 verification tests inside the container:
>   1. `python -c "import sys; print(sys.path)"` — verifies Python path setup
>   2. `python -c "from sklearn.ensemble import RandomForestClassifier; print('sklearn OK')"` — verifies ML dependencies
>   3. `python -c "from src.api import app; print('API OK')"` — verifies FastAPI app imports
>
> **Fixes applied during development:**
>
> - Added `ENV PYTHONPATH=/home/appuser/.local/lib/python3.9/site-packages` to fix `ModuleNotFoundError: No module named 'sklearn'`
> - Created `requirements-docker.txt` (5 slim packages) instead of using `requirements.txt` which pulled PyTorch + 4.7GB NVIDIA CUDA via `sagemaker>=2.100.0`
> - Created `.dockerignore` to exclude `.git/`, `terraform/`, notebooks, etc. from build context
> - Added `--chown=appuser:appuser` to COPY to fix root-owned files for non-root user
> - Added `load: true` to BuildKit step and removed duplicate `docker build` command in CI/CD
>
> ⚠️ **Not yet tested locally** with actual model files mounted via `-v $(pwd)/model:/app/model`.

### 9.1 Build the Image

```bash
docker build -t churn-prediction:latest .
```

This takes 2-5 minutes on first build (downloads Python packages).

### 9.2 Run the Container

```bash
docker run -p 8000:8000 churn-prediction:latest
```

### 9.3 Test

```bash
curl http://localhost:8000/health
```

> **Note:** The Docker image expects model files in `/app/model/`. If you haven't trained a model yet, the health endpoint will report `"status": "degraded"`. The API still starts — it just can't make predictions until model files are present.

### 9.4 Run with Model Files (if they're local)

```bash
docker run -p 8000:8000 \
  -v $(pwd)/model:/app/model \
  churn-prediction:latest
```

---

## 10. Uploading Data to S3

> ⚠️ **STATUS: PARTIALLY DONE (via GitHub Actions CI/CD — not as described below)**
>
> The CI/CD pipeline's **Deploy to SageMaker** job automatically uploads `data/customer_churn_processed.csv` to:
>
> ```
> s3://customer-churn-vahant-2026/data/processed/customer_churn_processed.csv
> ```
>
> This is the manually-created S3 bucket (GitHub secret `S3_BUCKET`), **not** the Terraform-managed data bucket described below.
>
> The steps below reference Terraform-managed buckets (e.g., `customer-churn-data-dev-231284356634`) which **don't exist yet** — they will be created when Step 6 (Terraform First Deployment) is completed.

### 10.1 Upload to Your Data Bucket

After Terraform creates the S3 buckets:

```bash
# Get bucket name from Terraform output
BUCKET=$(cd terraform/environments/dev && terraform output -raw data_bucket_name)

# Upload raw data
aws s3 cp data/customer_churn.csv s3://$BUCKET/raw/customer_churn.csv

# Upload processed data (for SageMaker training)
aws s3 cp data/customer_churn_processed.csv s3://$BUCKET/processed/customer_churn_processed.csv
```

### 10.2 Verify Upload

```bash
aws s3 ls s3://$BUCKET/ --recursive
```

---

## 11. SageMaker Training Job

> ❌ **STATUS: NOT YET DONE** — Requires Step 6 (Terraform deployment to create SageMaker resources, IAM roles, and data buckets) and Step 10 (data uploaded to Terraform-managed S3 bucket). This is an alternative to Step 7 Option A (local training). Training on SageMaker costs ~$0.01 per run.

### 11.1 Via the SageMaker Notebook (Recommended)

1. Open the SageMaker notebook URL from Terraform output
2. Upload `sagemaker/sagemaker_e2e.ipynb` to the notebook
3. Update the notebook variables:
   ```python
   role = "arn:aws:iam::231284356634:role/customer-churn-dev-sagemaker-execution"  # From Terraform output
   bucket = "customer-churn-data-dev-231284356634"  # From Terraform output
   ```
4. Run all cells

### 11.2 Via Python Script

```python
import sagemaker
from sagemaker.sklearn import SKLearn

session = sagemaker.Session()
role = "arn:aws:iam::231284356634:role/customer-churn-dev-sagemaker-execution"

estimator = SKLearn(
    entry_point='training.py',
    source_dir='sagemaker',
    role=role,
    instance_type='ml.m5.large',
    framework_version='1.0-1',
    hyperparameters={
        'n-estimators': 100,
        'max-depth': 10
    }
)

# Point to data in S3
estimator.fit({
    'train': 's3://customer-churn-data-dev-231284356634/processed/'
})

print(f"Model artifact: {estimator.model_data}")
```

### 11.3 Cost

| Instance     | Hourly Rate | Typical Training Time | Cost   |
| ------------ | ----------- | --------------------- | ------ |
| ml.m5.large  | $0.115/hr   | 5 minutes             | ~$0.01 |
| ml.m5.xlarge | $0.23/hr    | 3 minutes             | ~$0.01 |

Training is cheap — you pay only for the minutes the instance runs.

---

## 12. SageMaker Endpoint Deployment

> ❌ **STATUS: NOT YET DONE** — Optional and expensive (~$40/month). Requires a trained model (Step 7 or 11). Deploy only for testing, then delete immediately.

> **WARNING:** Endpoints cost money EVERY SECOND they're running. Always delete when done testing.

### 12.1 Deploy from Training Job

```python
predictor = estimator.deploy(
    instance_type='ml.t2.medium',
    initial_instance_count=1,
    endpoint_name='customer-churn-endpoint'
)
```

### 12.2 Test the Endpoint

```python
import json

response = predictor.predict(
    json.dumps({"Age": 35, "Tenure": 24}),
    initial_args={"ContentType": "application/json"}
)
print(response)
```

### 12.3 DELETE THE ENDPOINT When Done

```python
predictor.delete_endpoint()
predictor.delete_model()
```

Or via CLI:

```bash
aws sagemaker delete-endpoint --endpoint-name customer-churn-endpoint
aws sagemaker delete-endpoint-config --endpoint-name customer-churn-endpoint
```

### 12.4 Cost

| Instance     | Per Hour | Per Day | Per Month |
| ------------ | -------- | ------- | --------- |
| ml.t2.medium | $0.056   | $1.34   | $40.32    |
| ml.t3.medium | $0.050   | $1.20   | $36.00    |
| ml.m5.large  | $0.115   | $2.76   | $82.80    |

---

## 13. ECR — Push Docker Image

> ❌ **STATUS: NOT YET DONE** — ECR repository does not exist yet. It will be created by Terraform in Step 6. Once created, the Docker image (which already builds successfully in CI/CD) can be tagged and pushed.

### 13.1 Authenticate Docker to ECR

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 231284356634.dkr.ecr.us-east-1.amazonaws.com
```

### 13.2 Build and Tag

```bash
# Get repository URL from Terraform output
ECR_URL=$(cd terraform/environments/dev && terraform output -raw ecr_repository_url)

docker build -t churn-prediction:latest .
docker tag churn-prediction:latest $ECR_URL:latest
docker tag churn-prediction:latest $ECR_URL:$(git rev-parse --short HEAD)
```

### 13.3 Push

```bash
docker push $ECR_URL:latest
docker push $ECR_URL:$(git rev-parse --short HEAD)
```

### 13.4 Verify

```bash
aws ecr describe-images --repository-name customer-churn-dev --region us-east-1
```

---

## 14. CloudWatch Monitoring Setup

> ❌ **STATUS: NOT YET DONE** — CloudWatch dashboard, alarms, and SNS topic are all created by Terraform (Step 6). Once Terraform is deployed, only manual action needed is confirming the SNS email subscription.

Most of this is automated by Terraform, but some things need manual setup:

### 14.1 Confirm SNS Email Subscription

After `terraform apply`, check your email and click the confirmation link. Without this, you'll never receive alarm notifications.

### 14.2 Access the Dashboard

1. Go to **AWS Console → CloudWatch → Dashboards**
2. Find the dashboard named `customer-churn-{env}-dashboard`
3. Widgets are pre-configured by Terraform

### 14.3 Test Alarms

To verify alarms work:

```bash
# Set an alarm to ALARM state (for testing)
aws cloudwatch set-alarm-state \
  --alarm-name "customer-churn-dev-endpoint-5xx-errors" \
  --state-value ALARM \
  --state-reason "Testing alarm notification"
```

You should receive an email. Then reset:

```bash
aws cloudwatch set-alarm-state \
  --alarm-name "customer-churn-dev-endpoint-5xx-errors" \
  --state-value OK \
  --state-reason "Test complete"
```

---

## 15. Cleanup — Avoid Surprise Bills

> ⏳ **STATUS: NOT APPLICABLE YET** — No billable infrastructure has been deployed (Terraform Step 6 not run, no endpoints, no notebook instances). The only active resources are the Terraform backend (S3 bucket + DynamoDB table + KMS key ≈ ~$1/month) and the manually-created S3 bucket `customer-churn-vahant-2026`.

### 15.1 Delete SageMaker Endpoints (MOST IMPORTANT)

```bash
# List all endpoints
aws sagemaker list-endpoints

# Delete each one
aws sagemaker list-endpoints --query 'Endpoints[*].EndpointName' --output text | \
  xargs -I {} aws sagemaker delete-endpoint --endpoint-name {}
```

### 15.2 Stop SageMaker Notebook

```bash
aws sagemaker stop-notebook-instance --notebook-instance-name customer-churn-dev-notebook
```

### 15.3 Terraform Destroy (Nuclear Option)

This destroys ALL infrastructure in an environment:

```bash
cd terraform/environments/dev
terraform destroy
```

Type `yes` when prompted. This will:

- Delete VPC and all networking
- Delete S3 buckets (if force_delete is enabled or buckets are empty)
- Delete ECR repository
- Delete SageMaker resources
- Delete CloudWatch alarms and dashboard
- Delete IAM roles
- Delete KMS keys (scheduled for deletion)

### 15.4 Things to Check Manually

After `terraform destroy`, verify these are gone:

```bash
# Check for running endpoints
aws sagemaker list-endpoints

# Check for running notebook instances
aws sagemaker list-notebook-instances --status-equals InService

# Check for NAT Gateways (cost $32/month each)
aws ec2 describe-nat-gateways --filter Name=state,Values=available

# Check for EIPs (cost $3.6/month if not attached)
aws ec2 describe-addresses
```

---

## 16. Troubleshooting Common Issues

> 📖 **STATUS: REFERENCE SECTION** — No action required. Consult when encountering issues.

### "terraform init" fails with backend error

**Cause:** The S3 state bucket doesn't exist yet.  
**Fix:** Complete Step 4 (Backend Bootstrap) first.

### "terraform apply" fails with permission error

**Cause:** Your IAM user doesn't have the required permissions.  
**Fix:** Attach the policies listed in Step 2.2. Check which permission is missing by reading the error: `AccessDenied: User: arn:aws:iam::...:user/... is not authorized to perform: ec2:CreateVpc`.

### "aws configure" — Invalid credentials

**Cause:** Wrong Access Key ID or Secret Access Key.  
**Fix:** Go to IAM → Users → Security credentials → Create new access key. Delete the old one.

### Docker build fails with "gcc not found"

**Cause:** Build stage can't install C extensions.  
**Fix:** The Dockerfile already includes `gcc` in the builder stage. If you modified it, restore the `apt-get install gcc python3-dev` line.

### API returns "Model not loaded. Service unavailable."

**Cause:** Model files don't exist in the expected path.  
**Fix:** Train a model first (Step 7). Check the paths:

```bash
ls model/best_model_xgboost.joblib
ls model/preprocessor.joblib
```

### SageMaker training job fails

**Cause:** Usually data format issues.  
**Fix:** Check CloudWatch logs:

1. Go to **AWS Console → SageMaker → Training Jobs**
2. Click on the failed job
3. Click "View logs" to see the error

Common issues:

- CSV has wrong columns
- S3 path doesn't exist
- IAM role doesn't have S3 access

### "ResourceInUseException" when deploying SageMaker endpoint

**Cause:** An endpoint with that name already exists.  
**Fix:** Delete the existing endpoint first:

```bash
aws sagemaker delete-endpoint --endpoint-name your-endpoint-name
```

### SNS notifications not arriving

**Cause:** You didn't confirm the email subscription.  
**Fix:** Check your email for the confirmation link (also check spam). If you can't find it:

```bash
# Resend by unsubscribing and re-applying Terraform
aws sns list-subscriptions-by-topic --topic-arn YOUR_TOPIC_ARN
```

### Terraform shows "Plan: X to add, Y to change, Z to destroy" unexpectedly

**Cause:** Someone changed infrastructure manually (Console click-ops).  
**Fix:** Either:

1. Run `terraform apply` to bring state back in sync
2. Or import the manually-created resource: `terraform import aws_xxx.name resource-id`

---

## 17. Cost Awareness — What Costs Money

> 📖 **STATUS: REFERENCE SECTION** — No action required. Review before deploying Terraform (Step 6) to understand cost implications. Current monthly spend: ~$1 (backend S3 + DynamoDB + KMS only).

### Things That Cost Money Per Hour (MOST DANGEROUS)

| Resource                          | Per Hour | Per Month | Action                                                |
| --------------------------------- | -------- | --------- | ----------------------------------------------------- |
| NAT Gateway                       | $0.045   | $32.40    | Terraform-managed, destroyed with `terraform destroy` |
| SageMaker Endpoint (ml.t2.medium) | $0.056   | $40.32    | **DELETE IMMEDIATELY AFTER TESTING**                  |
| SageMaker Notebook (ml.t3.medium) | $0.050   | $36.00    | **STOP when not using**                               |
| ELastic IP (unattached)           | $0.005   | $3.60     | Check after destroy                                   |

### Things That Cost Money Per GB (Low Risk)

| Resource        | Per GB/Month      | Typical Cost          |
| --------------- | ----------------- | --------------------- |
| S3 Standard     | $0.023            | < $1 for this project |
| CloudWatch Logs | $0.50/GB ingested | < $1                  |
| ECR Storage     | $0.10             | < $1                  |

### Things That Are Free

| Resource                        | Notes                                |
| ------------------------------- | ------------------------------------ |
| IAM Roles                       | Free                                 |
| Security Groups                 | Free                                 |
| KMS Keys                        | $1/month per key (4 keys = $4/month) |
| CloudWatch Dashboard            | Free (up to 3)                       |
| CloudWatch Alarms               | Free (up to 10)                      |
| DynamoDB (on-demand, low usage) | Free tier covers state locks         |
| CloudTrail (1 trail)            | Free (additional trails cost)        |

### Monthly Cost Estimate by Environment

| Environment | Minimum (idle)     | Typical (development)     | Maximum (everything running) |
| ----------- | ------------------ | ------------------------- | ---------------------------- |
| Dev         | ~$37 (NAT + KMS)   | ~$73 (+ notebook running) | ~$113 (+ endpoint)           |
| Staging     | ~$37               | ~$73                      | ~$113                        |
| Prod        | ~$69 (2 NAT + KMS) | ~$105 (+ notebook)        | ~$186 (+ endpoint)           |

### The #1 Cost Saving Tip

**Stop/delete SageMaker endpoints** when you're not actively testing. An idle endpoint costs $40/month doing absolutely nothing. Use batch transform for one-off predictions instead.

```bash
# Check if any endpoints are running
aws sagemaker list-endpoints --status-equals InService

# Delete them
aws sagemaker delete-endpoint --endpoint-name ENDPOINT_NAME
```

---

## Quick Reference: The Complete Step Order

For a brand-new setup, do these in order:

```
 ✅  1. Install prerequisites (Python, AWS CLI, Terraform, Docker)           ← DONE
 ✅  2. Create AWS account & IAM user                                        ← DONE (inline admin policy)
 ✅  3. Run `aws configure`                                                  ← DONE
 ✅  4. Bootstrap Terraform backend (`cd terraform/backend && terraform apply`) ← DONE (9 resources)
 ❌  5. Create terraform.tfvars in environments/dev/                          ← NOT DONE
 ❌  6. Run `terraform init` then `terraform apply` in environments/dev/      ← NOT DONE
 ❌  7. Confirm SNS email subscription                                       ← NOT DONE (needs Step 6)
 ❌  8. Train model locally (or via SageMaker)                                ← NOT DONE
 ⚠️  9. Upload data to S3                                                    ← PARTIAL (CI/CD uploads to manual bucket)
 ❌ 10. Run API locally to verify                                             ← NOT DONE (needs Step 8)
 ❌ 11. Build and push Docker image to ECR                                    ← NOT DONE (needs Step 6)
 ❌ 12. (Optional) Deploy SageMaker endpoint                                  ← NOT DONE
 ✅ 13. Set up GitHub Secrets for CI/CD                                       ← DONE
 ✅ 14. Push code → CI/CD runs automatically                                  ← DONE (all 4 jobs GREEN)
```

After you're done for the day:

```
1. Delete SageMaker endpoints
2. Stop SageMaker notebook
3. (If done with environment) terraform destroy
```
