# Customer Churn Prediction - Complete Project Overview

## Executive Summary

**What I Built:** An end-to-end machine learning system that predicts which customers are likely to cancel their service (churn), deployed on AWS SageMaker with a production-ready API.

**Business Impact:** Enables proactive customer retention by identifying at-risk customers before they leave, potentially saving $X per customer in acquisition costs.

**Tech Stack:** Python, XGBoost, AWS SageMaker, S3, FastAPI, Docker, GitHub Actions

---

## Project Timeline & My Contributions

### Phase 1: Foundation (Original Repository)
**Source:** Open-source starter code
**What existed:**
- Basic Jupyter notebooks for local experimentation
- Raw dataset (customer_churn.csv)
- Simple sklearn models (Random Forest, Logistic Regression)
- Template SageMaker files (unconfigured)

### Phase 2: Production Engineering (My Work)
**What I added:**

| Component | Purpose | Files Created |
|-----------|---------|---------------|
| Data Validation | Prevent bad data from crashing model | `src/data_validation.py` |
| REST API | Enable integration with other systems | `src/api.py` |
| Model Explainability | SHAP-based explanations for predictions | `src/model_explainability.py` |
| Cost Monitoring | Track AWS spending in real-time | `src/cost_monitor.py` |
| Hyperparameter Tuning | Automated model optimization | `src/hyperparameter_tuning.py` |
| Unit Tests | 16 automated tests for reliability | `tests/test_pipeline.py` |
| CI/CD Pipeline | Automated testing on every commit | `.github/workflows/ci-cd.yml` |
| Docker Container | Portable deployment anywhere | `Dockerfile` |
| SageMaker Training | Cloud-based model training | `sagemaker/train_deploy_vahant.ipynb` |

### Phase 3: Cloud Deployment (My Work)
- Configured AWS IAM roles and permissions
- Set up S3 bucket for data storage
- Trained XGBoost model on SageMaker
- Deployed real-time inference endpoint
- Tested predictions with live data

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CUSTOMER CHURN ML SYSTEM                          │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Raw Data  │────►│  Validation │────►│  Training   │────►│   Model     │
│   (CSV)     │     │  Pipeline   │     │  (XGBoost)  │     │  Artifact   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │                    │                    │
                          ▼                    ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │   S3        │     │  SageMaker  │     │  S3         │
                    │   Bucket    │     │  Training   │     │  model.tar  │
                    └─────────────┘     │  Instance   │     └─────────────┘
                                        └─────────────┘            │
                                                                   │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐            │
│   Client    │────►│  FastAPI    │────►│  SageMaker  │◄───────────┘
│   Request   │     │  API        │     │  Endpoint   │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                   │                    │
       │                   ▼                    ▼
       │            ┌─────────────┐     ┌─────────────┐
       └────────────│  Response   │◄────│  Prediction │
                    │  + SHAP     │     │  + Probability│
                    └─────────────┘     └─────────────┘
```

---

## Key Metrics

| Metric | Value | Significance |
|--------|-------|--------------|
| Model AUC | ~0.89 | Excellent discrimination ability |
| Training Time | ~15 min | Fast iteration cycle |
| Inference Latency | <100ms | Real-time predictions |
| Test Coverage | 16 tests | Production-ready quality |
| Deployment Cost | ~$0.05/hr | Cost-effective for demos |

---

## Files Structure

```
customer-churn-aws-ml/
├── data/
│   ├── customer_churn.csv              # Raw dataset (1M rows)
│   └── customer_churn_processed.csv    # Cleaned dataset
│
├── src/                                # Production code (MY WORK)
│   ├── __init__.py
│   ├── api.py                          # FastAPI REST endpoints
│   ├── data_validation.py              # Input validation
│   ├── model_explainability.py         # SHAP explanations
│   ├── cost_monitor.py                 # AWS cost tracking
│   └── hyperparameter_tuning.py        # Model optimization
│
├── sagemaker/                          # AWS deployment
│   ├── training.py                     # Training script (original)
│   ├── inference.py                    # Inference script (original)
│   ├── sagemaker_e2e.ipynb            # Original template
│   └── train_deploy_vahant.ipynb       # My configured notebook
│
├── tests/                              # Automated tests (MY WORK)
│   └── test_pipeline.py                # 16 test cases
│
├── model/                              # Local model storage
│   └── .gitkeep
│
├── .github/workflows/                  # CI/CD (MY WORK)
│   └── ci-cd.yml                       # GitHub Actions
│
├── interview/                          # Interview prep (MY WORK)
│   └── [documentation files]
│
├── Dockerfile                          # Container (MY WORK)
├── requirements.txt                    # Dependencies
├── requirements-minimal.txt            # Lightweight deps (MY WORK)
├── README.md                           # Project documentation
├── DEPLOYMENT_GUIDE.md                 # AWS deployment guide (MY WORK)
├── Makefile                            # Build automation
└── setup.py                            # Package configuration
```

---

## What This Project Demonstrates

### Technical Skills
- **Machine Learning:** XGBoost, feature engineering, model evaluation
- **Cloud Computing:** AWS SageMaker, S3, IAM, cost management
- **Software Engineering:** Clean code, testing, CI/CD, Docker
- **API Development:** FastAPI, REST design, error handling

### Soft Skills
- **Problem Solving:** Transformed research code into production system
- **Documentation:** Comprehensive guides and explanations
- **Cost Awareness:** Budget-conscious cloud deployment
- **Best Practices:** Following industry standards

---

## Quick Stats for Interview

- **Lines of Production Code:** ~2,500+
- **Test Cases:** 16 passing
- **AWS Services Used:** 5 (SageMaker, S3, IAM, CloudWatch, EC2)
- **API Endpoints:** 6 (health, predict, batch, explain, metrics, model-info)
- **Docker Image Size:** ~500MB (multi-stage build)
- **Model Accuracy (AUC):** ~0.89
