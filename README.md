# Customer Churn Prediction

Production-grade ML system for customer churn prediction with AWS SageMaker deployment, model explainability, and MLOps practices.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![AWS](https://img.shields.io/badge/AWS-SageMaker-FF9900.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)
![License](https://img.shields.io/badge/License-MIT-blue.svg)

## Overview

End-to-end ML engineering project demonstrating:

| Component | Technology |
|-----------|------------|
| Data Validation | Custom pipeline with schema & quality checks |
| Model Explainability | SHAP-based interpretability |
| Production API | FastAPI with batch prediction support |
| Cloud Deployment | AWS SageMaker training & inference |
| CI/CD | GitHub Actions |
| Containerization | Docker multi-stage builds |

## Project Structure

```
├── src/
│   ├── api.py                 # FastAPI application
│   ├── data_validation.py     # Data quality checks
│   ├── model_explainability.py # SHAP explanations
│   ├── hyperparameter_tuning.py # SageMaker HPO
│   └── cost_monitor.py        # AWS cost tracking
├── sagemaker/
│   ├── training.py            # Training script
│   ├── inference.py           # Inference handler
│   └── training_tunable.py    # HPO-ready training
├── tests/
│   └── test_pipeline.py       # Unit tests
├── .github/workflows/
│   └── ci-cd.yml              # CI/CD pipeline
├── data/
│   └── customer_churn.csv     # Dataset
├── Dockerfile
├── requirements.txt
└── DEPLOYMENT_GUIDE.md
```

## Quick Start

### Installation

```bash
git clone https://github.com/yourusername/customer-churn-prediction.git
cd customer-churn-prediction

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
pip install -r requirements-api.txt
```

### Local Development

```bash
# Run tests
pytest tests/ -v

# Start API server
uvicorn src.api:app --reload --port 8000

# Validate data
python src/data_validation.py data/customer_churn.csv
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/predict` | Single prediction |
| POST | `/predict/batch` | Batch predictions |
| POST | `/explain` | Prediction with explanation |

### Example Request

```bash
curl -X POST "http://localhost:8000/predict" \
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

## AWS Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed instructions.

### Cost Estimate ($100 Budget)

| Resource | Rate | Recommended Usage |
|----------|------|-------------------|
| SageMaker Training (ml.m5.large) | $0.115/hr | ~$0.10 per run |
| SageMaker Endpoint (ml.t2.medium) | $0.056/hr | Delete when idle |
| S3 Storage | $0.023/GB/mo | Minimal |

**Important:** Always delete endpoints when not in use.

```python
import boto3
client = boto3.client('sagemaker')
client.delete_endpoint(EndpointName='your-endpoint')
```

## Model Performance

| Metric | Score |
|--------|-------|
| ROC-AUC | 0.887 |
| Accuracy | 83.4% |
| Precision | 80.1% |
| Recall | 74.3% |
| F1-Score | 77.1% |

### Top Features
1. Total Spend
2. Usage Frequency
3. Support Calls
4. Tenure
5. Payment Delay

## Testing

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=html
```

## Docker

```bash
docker build -t churn-prediction:latest .
docker run -p 8000:8000 churn-prediction:latest
```

## Model Explainability

```python
from src.model_explainability import ModelExplainer

explainer = ModelExplainer(model, feature_names)
explainer.fit(X_train)
explanation = explainer.explain_instance(customer_data)
print(explanation['explanation_text'])
```

## Credits

- Original Implementation: [ashishpal2702](https://github.com/ashishpal2702/customer-churn-aws-ml)
- Extended by: Vahant
  - Production API (FastAPI)
  - SHAP-based explainability
  - Data validation pipeline
  - Unit test suite
  - CI/CD pipeline
  - Docker containerization
  - AWS cost monitoring
  - Hyperparameter tuning module

## License

MIT License - See [LICENSE](LICENSE)
