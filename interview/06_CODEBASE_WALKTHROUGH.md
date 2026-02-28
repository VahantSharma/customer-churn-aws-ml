# Complete Codebase Walkthrough – What Was Built & How

## Original Repository vs My Contributions

### What Ashish Pal's Original Repo Had (8 commits, demo quality)

```
customer-churn-aws-ml/          ← ORIGINAL STRUCTURE
├── data/
│   ├── customer_churn.csv              # Raw dataset (23MB, ~100K rows)
│   └── customer_churn_processed.csv    # Pre-processed training data (71MB)
├── sagemaker/
│   ├── training.py                     # SageMaker training script (RandomForest only)
│   ├── inference.py                    # SageMaker inference handler (model_fn, input_fn, predict_fn, output_fn)
│   └── sagemaker_e2e.ipynb            # End-to-end SageMaker workflow notebook
├── ml_experiment.ipynb                 # Local experimentation (EDA, 3 algorithms, GridSearchCV)
├── ml_experiment_mlflow.ipynb          # Same pipeline + MLflow experiment tracking
├── requirements.txt                    # Python dependencies
├── setup.py                            # Package configuration
├── Makefile                            # Basic build commands
├── sagemaker-iam-policy.json           # IAM policy (S3 + SageMaker + MLflow)
├── .gitignore
└── README.md
```

**In plain English:** A Jupyter notebook-centric ML demo showing how to train a churn model locally, track experiments with MLflow, and deploy to SageMaker. NO production code, NO tests, NO Docker, NO CI/CD, NO data validation, NO API.

### What I Added (production engineering)

```
customer-churn-aws-ml/          ← NEW FILES MARKED WITH ★
├── src/                                ★ ENTIRE DIRECTORY (5 production modules)
│   ├── __init__.py
│   ├── api.py                          ★ FastAPI REST API (440 lines)
│   ├── data_validation.py              ★ Data quality pipeline (405 lines)
│   ├── model_explainability.py         ★ SHAP explainability engine (507 lines)
│   ├── cost_monitor.py                 ★ AWS cost tracking & optimization (365 lines)
│   └── hyperparameter_tuning.py        ★ SageMaker Bayesian HPO (385 lines)
│
├── tests/                              ★ ENTIRE DIRECTORY
│   └── test_pipeline.py                ★ 16 unit tests across 5 test classes (365 lines)
│
├── sagemaker/
│   ├── training_tunable.py             ★ Multi-algorithm training for HPO (231 lines)
│   └── train_deploy_vahant.ipynb       ★ My own e2e SageMaker notebook (tested on AWS)
│
├── .github/workflows/                  ★ ENTIRE DIRECTORY
│   └── ci-cd.yml                       ★ GitHub Actions CI/CD pipeline (120 lines)
│
├── interview/                          ★ ENTIRE DIRECTORY (interview prep docs)
│
├── Dockerfile                          ★ Multi-stage Docker build (64 lines)
├── DEPLOYMENT_GUIDE.md                 ★ Step-by-step AWS deployment guide
├── requirements-api.txt                ★ FastAPI-specific deps
└── requirements-minimal.txt            ★ Lightweight deps for CI
```

**Total new production code:** ~2,500+ lines across 8 Python files.

---

## Deep Dive: Each Module Explained

### 1. `src/api.py` — Production REST API

**What it does:** Serves the churn model over HTTP using FastAPI.

**Endpoints:**

| Endpoint | Method | What It Does |
|----------|--------|-------------|
| `/` | GET | Returns API version and links |
| `/health` | GET | Health check (model loaded status) |
| `/predict` | POST | Single customer churn prediction |
| `/predict/batch` | POST | Batch prediction for multiple customers |
| `/explain` | POST | Prediction + feature-level explanation |
| `/model/info` | GET | Model type, n_features, n_estimators |

**Key design decisions:**
- **Pydantic validation** on every request — enforces Age 18-100, valid Gender, valid Subscription Type, etc. Bad input is rejected with clear error messages before reaching the model
- **Risk level classification** — converts raw probability into business-readable "HIGH" (≥0.7), "MEDIUM" (≥0.4), "LOW"
- **Batch endpoint returns summary stats** — total churners, churn rate, risk distribution, processing time
- **Model loaded at startup** via `@app.on_event("startup")` with fallback graceful degradation (returns "degraded" health status if model missing)

**Why this matters for interviews:**
> "I didn't just train a model – I built a production API that other services can integrate with. The API validates inputs, returns structured responses with risk levels, and supports both single and batch predictions. It also has a health endpoint for load balancer integration."

---

### 2. `src/data_validation.py` — Data Quality Pipeline

**What it does:** Validates data before it reaches the model, preventing silent corruption.

**7 validation checks:**

| Check | PASS | WARNING | FAIL |
|-------|------|---------|------|
| Schema completeness | All 12 columns present | Extra columns | Missing columns |
| Missing values | 0% missing | <5% missing | >5% missing |
| Duplicate CustomerIDs | No duplicates | Duplicates found | — |
| Categorical values | All valid | — | Invalid values (e.g., "Enterprise" subscription) |
| Numerical bounds | All within range | <1% out of bounds | >1% out of bounds |
| Outlier detection (IQR) | No outliers | Outliers found | — |
| Target class balance | 10-90% churn rate | 5-10% or 90-95% | <5% or >95% |

**Key design decisions:**
- **Three-tier status (PASS/WARN/FAIL)** instead of binary — allows soft alerts without blocking
- **`strict_mode` flag** — when True, warnings become failures (for production vs development)
- **Can run as standalone CLI** — `python src/data_validation.py data/customer_churn.csv`

---

### 3. `src/model_explainability.py` — SHAP-Based Interpretability

**What it does:** Makes the "black box" model transparent using SHAP values.

**Capabilities:**
- **Global importance** — which features matter most across all predictions
- **Instance-level explanation** — why THIS specific customer was flagged
- **Feature interactions** — which pairs of features work together
- **Visualization** — bar plots, beeswarm plots, waterfall plots
- **Human-readable text generation** — "This customer is likely to churn (confidence: 73%). Key factors: contract type (+0.34), short tenure (+0.15)..."
- **Model Card generation** — regulatory compliance document (GDPR/CCPA)

**Key design decisions:**
- **Auto-selects explainer type** — TreeExplainer for tree models, LinearExplainer for linear, KernelExplainer for everything else
- **Background sampling** — uses 100 random samples for efficiency (SHAP can be slow on large datasets)
- **Saves/loads** explainer state for production use

---

### 4. `src/cost_monitor.py` — AWS Cost Tracking

**What it does:** Monitors real-time AWS spending and prevents budget blowouts.

**Features:**
- Lists all active SageMaker endpoints with hourly cost
- Tracks training job costs based on instance type × duration
- Generates monthly cost projections
- Provides optimization recommendations (e.g., "This endpoint has been running 72 hours, costing $8.28 — consider deleting")
- **Automated idle endpoint cleanup** with dry-run safety mode

**Key design decisions:**
- **Built-in pricing table** for common instance types (ml.m5.large: $0.115/hr, ml.t2.medium: $0.056/hr, etc.)
- **Dry-run by default** — `cleanup_idle_endpoints(dry_run=True)` only reports, doesn't delete

---

### 5. `src/hyperparameter_tuning.py` — Automated Model Optimization

**What it does:** Wraps SageMaker's HyperparameterTuner for automated Bayesian optimization.

**Supports 3 algorithms with pre-defined ranges:**

| Algorithm | Tunable Params |
|-----------|---------------|
| Random Forest | n_estimators, max_depth, min_samples_split/leaf, max_features |
| XGBoost | n_estimators, max_depth, learning_rate, subsample, colsample, gamma, reg_alpha/lambda |
| Gradient Boosting | n_estimators, max_depth, learning_rate, subsample, min_samples_split/leaf |

**Key design decisions:**
- **Bayesian strategy** (not Random) — converges faster with fewer jobs
- **Early stopping** — kills underperforming jobs automatically
- **Cost estimation before running** — `estimate_tuning_cost(max_jobs=10)` returns `{max_cost: $0.96, typical_cost: $0.67}`
- **`training_tunable.py`** in sagemaker/ is the counterpart training script that accepts algorithm selection via hyperparameters

---

### 6. `tests/test_pipeline.py` — Automated Test Suite

**16 tests across 5 classes:**

| Class | Tests | What They Verify |
|-------|-------|-----------------|
| `TestDataValidator` | 8 | Valid data passes, missing cols fail, invalid categories fail, out-of-bounds detection, strict mode, report generation, empty df handling |
| `TestPreprocessing` | 2 | Output shape (7 numerical + 5 one-hot = 12 features), standard scaling (mean≈0, std≈1) |
| `TestModelPrediction` | 3 | Prediction shape, binary values (0/1), probability range [0,1] summing to 1 |
| `TestInferencePipeline` | 3 | JSON parsing (single + batch), CSV parsing |
| `TestEndToEnd` | 1 | Full pipeline: generate data → split → scale → train RandomForest → predict → accuracy >60% |

---

### 7. `Dockerfile` — Production Container

**Multi-stage build:**
1. **Builder stage**: Python 3.9-slim + gcc + requirements install
2. **Production stage**: Python 3.9-slim + app code + non-root user

**Security features:**
- Non-root user (`appuser`)
- No build tools in final image
- Health check built into container spec

---

### 8. `.github/workflows/ci-cd.yml` — CI/CD Pipeline

**4 jobs:**

| Job | Trigger | What It Does |
|-----|---------|-------------|
| `test` | Every push/PR | flake8 lint → black format check → pytest + coverage → codecov upload |
| `build` | After test passes | Docker Buildx → build image → smoke test (`import sklearn`) |
| `deploy` | Main branch push only | AWS creds → S3 data upload → **⚠️ deploy step is placeholder** |
| `notify` | Always | Pipeline results summary in GitHub step summary |

---

## Configuration & Infrastructure Files

### `sagemaker-iam-policy.json`
Grants permissions for:
- S3 ListBucket, GetObject, PutObject, DeleteObject (scoped to `arn:aws:s3:::SageMaker`)
- SageMaker model package operations
- **MLflow tracking server operations** (create, list, update, delete, access UI)

**⚠️ Issue:** MLflow actions use `"Resource": "*"` — should be scoped to specific tracking server ARN.

### `Makefile`
Targets: `install`, `install-dev`, `clean`, `test`, `format`, `lint`, `notebook`, `setup-aws`, `deploy-model`, `delete-endpoint`, `build`, `docs`, `env-create`, `check-structure`

### `setup.py`
Version 2.0.0, extras for `[dev]` (pytest, black, flake8, mypy) and `[notebook]` (jupyter, matplotlib, seaborn).

---

## What This Project Demonstrates (Summary)

| Skill Area | Evidence |
|-----------|---------|
| **ML Engineering** | XGBoost training, hyperparameter tuning, SHAP explainability |
| **Software Engineering** | Clean code, Pydantic validation, error handling, logging |
| **Cloud/AWS** | SageMaker training + deployment, S3, IAM, cost management |
| **API Development** | FastAPI with batch support, documentation, health checks |
| **Testing** | 16 unit tests, CI coverage reporting |
| **DevOps** | Docker multi-stage, GitHub Actions CI/CD |
| **Data Engineering** | Data validation pipeline with 7 quality checks |
| **Production Readiness** | Non-root Docker, graceful degradation, structured logging |
