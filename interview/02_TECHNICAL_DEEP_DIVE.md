# Technical Deep Dive - Interview Preparation

## Part 1: The Machine Learning

### Why XGBoost?

**What to say in interview:**
> "I chose XGBoost for several reasons. First, it consistently outperforms other algorithms on structured/tabular data like customer records. Second, it handles missing values natively and doesn't require extensive preprocessing. Third, it trains quickly and has built-in support in AWS SageMaker, which reduces deployment complexity. Finally, it provides feature importance scores, which are crucial for business stakeholders who want to understand why customers churn."

**Technical reasons:**
1. **Gradient Boosting:** Builds trees sequentially, each correcting errors of previous
2. **Regularization:** L1 and L2 regularization prevent overfitting
3. **Parallel Processing:** Column-based splits enable parallelization
4. **Handling Imbalanced Data:** `scale_pos_weight` parameter for class imbalance

### Hyperparameters I Used

```python
objective='binary:logistic'  # Binary classification
num_round=100               # 100 boosting iterations
max_depth=5                 # Shallow trees prevent overfitting
eta=0.2                     # Learning rate (not too fast, not too slow)
subsample=0.8               # Use 80% of data per tree (reduces overfitting)
colsample_bytree=0.8        # Use 80% of features per tree
eval_metric='auc'           # Area Under Curve (good for imbalanced classes)
```

**Why these values?**
- `max_depth=5`: Deeper trees = more complex patterns = overfitting risk
- `eta=0.2`: Lower learning rate = more stable but needs more rounds
- `subsample=0.8`: Random sampling adds regularization
- `eval_metric='auc'`: Better than accuracy for imbalanced datasets (churn is minority class)

### Model Evaluation

**Metrics I track:**
| Metric | What It Measures | Why Important |
|--------|------------------|---------------|
| AUC-ROC | Discrimination ability | How well model separates churners from non-churners |
| Precision | True positives / All predicted positives | Avoid wasting resources on false alarms |
| Recall | True positives / All actual positives | Catch as many churners as possible |
| F1 Score | Harmonic mean of precision/recall | Balance between precision and recall |

**Interview talking point:**
> "I focused on AUC because churn prediction is typically an imbalanced problem - maybe 15-20% churn rate. Accuracy would be misleading because a model that always predicts 'no churn' would be 80% accurate but completely useless. AUC measures how well the model ranks customers by churn probability, regardless of the threshold we choose."

---

## Part 2: The Data Pipeline

### Data Validation (`src/data_validation.py`)

**What it does:**
```python
class DataValidator:
    def validate(self, df: pd.DataFrame) -> ValidationReport:
        # Check for required columns
        # Validate data types
        # Check value ranges
        # Detect anomalies
        # Return detailed report
```

**Why I built this:**
> "In production, data quality issues are the #1 cause of ML failures. Bad data silently corrupts predictions. My validator catches issues like missing columns, invalid values, and out-of-range numbers BEFORE they reach the model. This prevents silent failures and makes debugging much easier."

**Key validations:**
1. **Schema validation:** Required columns exist
2. **Type checking:** Numeric columns are actually numbers
3. **Range validation:** Age between 0-120, charges > 0
4. **Categorical validation:** Only known category values
5. **Null detection:** Missing value thresholds

### Feature Engineering

**What I did to the raw data:**

| Original | Transformation | Reason |
|----------|----------------|--------|
| `gender: Male/Female` | `gender: 0/1` | XGBoost needs numeric |
| `contract: Month-to-month` | `contract: 0` | Factorize categories |
| `TotalCharges: string` | `TotalCharges: float` | Fix data type |
| `Churn: Yes/No` | `Churn: 1/0` | Binary target |

**Interview talking point:**
> "XGBoost can't process text directly, so I converted all categorical variables to numeric codes using factorization. I preserved a mapping dictionary so we can interpret predictions later. I also moved the target column to the first position because that's what SageMaker's built-in XGBoost expects."

---

## Part 3: The AWS Architecture

### Why SageMaker?

**What to say:**
> "I used SageMaker because it provides managed infrastructure for ML. Instead of setting up EC2 instances, installing dependencies, and managing scaling myself, SageMaker handles all that. It also provides built-in algorithm containers, automatic model artifact management, and one-click deployment to endpoints. This lets me focus on the ML problem rather than DevOps."

### Components Used

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS INFRASTRUCTURE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │    IAM      │    │     S3      │    │  SageMaker  │             │
│  │   Role      │    │   Bucket    │    │   Studio    │             │
│  │             │    │             │    │             │             │
│  │ Permissions │    │ Data Store  │    │ Notebook    │             │
│  └─────────────┘    └─────────────┘    │ Environment │             │
│         │                  │           └─────────────┘             │
│         │                  │                  │                     │
│         ▼                  ▼                  ▼                     │
│  ┌─────────────────────────────────────────────────┐               │
│  │              SageMaker Training                  │               │
│  │  ┌─────────────────────────────────────────┐   │               │
│  │  │  ml.m5.large instance                    │   │               │
│  │  │  - Downloads XGBoost container          │   │               │
│  │  │  - Downloads data from S3               │   │               │
│  │  │  - Trains model (100 rounds)            │   │               │
│  │  │  - Uploads model.tar.gz to S3           │   │               │
│  │  └─────────────────────────────────────────┘   │               │
│  └─────────────────────────────────────────────────┘               │
│                           │                                         │
│                           ▼                                         │
│  ┌─────────────────────────────────────────────────┐               │
│  │              SageMaker Endpoint                  │               │
│  │  ┌─────────────────────────────────────────┐   │               │
│  │  │  ml.t2.medium instance                   │   │               │
│  │  │  - Loads model into memory              │   │               │
│  │  │  - Listens for HTTP requests            │   │               │
│  │  │  - Returns predictions                  │   │               │
│  │  └─────────────────────────────────────────┘   │               │
│  └─────────────────────────────────────────────────┘               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Cost Management

**What I implemented:**
```python
class AWSCostMonitor:
    def get_endpoint_costs(self):
        # Calculate hourly/daily/monthly costs
        # Track training job costs
        # Alert when approaching budget
        # Recommend cost optimizations
```

**Interview talking point:**
> "Cloud cost management is often overlooked but critical. I built a cost monitor that tracks real-time spending across SageMaker endpoints and training jobs. It provides budget alerts and optimization recommendations like suggesting smaller instances or identifying idle endpoints. For this project with a $100 budget, staying cost-conscious was essential."

---

## Part 4: The API Layer

### Why FastAPI?

**What to say:**
> "I chose FastAPI for the REST API because it's modern, fast, and provides automatic documentation. It uses Python type hints for request validation, generates OpenAPI specs automatically, and is async-capable for high throughput. It's also easier to test than Flask and has become the industry standard for ML APIs."

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check for load balancers |
| `/predict` | POST | Single customer prediction |
| `/predict/batch` | POST | Multiple customers at once |
| `/explain` | POST | SHAP explanation for prediction |
| `/model/info` | GET | Model metadata and version |
| `/metrics` | GET | Prometheus-compatible metrics |

### Example Request/Response

```bash
# Request
POST /predict
{
  "tenure": 24,
  "monthly_charges": 65.50,
  "total_charges": 1572.00,
  "contract": "Month-to-month",
  "internet_service": "Fiber optic"
}

# Response
{
  "customer_id": "generated-uuid",
  "churn_probability": 0.73,
  "churn_prediction": true,
  "risk_level": "HIGH",
  "confidence": 0.89,
  "top_factors": [
    {"feature": "contract", "impact": 0.34},
    {"feature": "tenure", "impact": -0.21}
  ]
}
```

---

## Part 5: Testing & CI/CD

### Test Categories

```python
# tests/test_pipeline.py

class TestDataValidator:      # 7 tests
    # Valid data passes
    # Missing columns detected
    # Invalid categories detected
    # Out of bounds detected
    # Strict mode behavior
    # Report generation
    # Empty dataframe handling

class TestPreprocessing:      # 2 tests
    # Shape preserved
    # Scaling correct

class TestModelPrediction:    # 3 tests
    # Output shape correct
    # Values in valid range
    # Probabilities sum to 1

class TestInferencePipeline:  # 3 tests
    # JSON parsing
    # Batch processing
    # CSV parsing

class TestEndToEnd:           # 1 test
    # Full pipeline integration
```

### CI/CD Pipeline

```yaml
# .github/workflows/ci-cd.yml

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
      - name: Install dependencies
        run: pip install -r requirements-minimal.txt
      - name: Run linting
        run: flake8 src/ tests/
      - name: Run tests
        run: pytest tests/ -v
```

**Interview talking point:**
> "I implemented CI/CD using GitHub Actions. Every push triggers automated linting with flake8 and runs all 16 unit tests. This catches bugs before they reach production. The pipeline takes about 2 minutes and provides immediate feedback on code quality."

---

## Part 6: Model Explainability

### Why SHAP?

**What to say:**
> "Model explainability is crucial for trust and compliance. I implemented SHAP (SHapley Additive exPlanations) which provides game-theory-based feature attributions. For each prediction, SHAP tells us exactly which features pushed the probability up or down and by how much. This is essential for regulated industries and helps business users trust the model's decisions."

### How It Works

```python
# For a prediction of 73% churn probability:
{
  "base_value": 0.20,  # Average churn rate
  "contributions": {
    "contract_Month-to-month": +0.34,  # Increases churn risk
    "tenure_2": +0.15,                  # Short tenure = risky
    "tech_support_No": +0.08,           # No support = risky
    "monthly_charges_89": -0.04         # Moderate charges = good
  },
  "final_prediction": 0.73
}
```

**Business value:**
- Customer Service: "This customer is at risk because they're on month-to-month with no tech support"
- Marketing: "Offer contract upgrade to reduce churn risk"
- Product: "Tech support is a key retention driver"

---

## Part 7: Docker Containerization

### Dockerfile Explanation

```dockerfile
# Multi-stage build for smaller image
FROM python:3.9-slim as builder
# Install build dependencies
# Copy and install requirements

FROM python:3.9-slim as runtime
# Copy only what's needed
# Set up non-root user (security)
# Expose port 8000
# Health check endpoint
# Run with uvicorn
```

**Why multi-stage:**
> "I used a multi-stage Docker build to minimize the final image size. The builder stage installs all dependencies including compilers, but the runtime stage only copies the compiled packages. This reduces the image from ~1.2GB to ~500MB, which means faster deployments and lower storage costs."

### Running Locally

```bash
# Build
docker build -t churn-predictor .

# Run
docker run -p 8000:8000 -e MODEL_PATH=/app/model churn-predictor

# Test
curl http://localhost:8000/health
```
