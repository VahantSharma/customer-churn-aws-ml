# Quick Reference Card - Interview Day Cheat Sheet

## Print this and review 30 minutes before interview

---

## 1. KEY NUMBERS (Memorize)

| Metric | Value | What It Means |
|--------|-------|---------------|
| **AUC** | 0.89 | 89% chance model ranks churner higher than non-churner |
| **Features** | 19 | Input columns after preprocessing |
| **Test Coverage** | 16 tests | Unit tests for validation, prediction, API |
| **Training Time** | ~15 min | On ml.m5.large instance |
| **Training Cost** | ~$0.03 | $0.115/hr × 0.25hr |
| **Endpoint Cost** | ~$36/month | If left running 24/7 |

---

## 2. TECH STACK (Know Each One)

```
ML:         XGBoost 1.5-1 (AWS built-in container)
Framework:  scikit-learn, pandas, numpy
API:        FastAPI with Pydantic validation
Explain:    SHAP (SHapley Additive exPlanations)
Testing:    pytest (16 unit tests)
CI/CD:      GitHub Actions
Container:  Docker (multi-stage build)
Cloud:      AWS SageMaker, S3, IAM, CloudWatch
```

---

## 3. HYPERPARAMETERS (Explain Why)

```python
objective = "binary:logistic"  # Binary classification
num_round = 100                # Iterations (enough to converge)
max_depth = 5                  # Prevent overfitting
eta = 0.2                      # Learning rate (0.1-0.3 typical)
subsample = 0.8                # Reduces overfitting
eval_metric = "auc"            # Best for imbalanced data
```

---

## 4. API ENDPOINTS (6 Total)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check for load balancer |
| `/predict` | POST | Single customer prediction |
| `/predict/batch` | POST | Multiple customers |
| `/explain` | POST | SHAP explanation |
| `/model/info` | GET | Model metadata |
| `/metrics` | GET | Prometheus metrics |

---

## 5. FILE QUICK REFERENCE

**Your contributions:**
- `src/pipeline.py` - Data validation, preprocessing
- `src/api.py` - FastAPI REST endpoints
- `src/explainability.py` - SHAP wrapper
- `tests/` - 16 unit tests
- `.github/workflows/` - CI/CD pipeline
- `Dockerfile`, `docker-compose.yml`
- `sagemaker/train_deploy_vahant.ipynb` - Full training notebook

**Original work (Ashish):**
- `ml_experiment.ipynb` - Research notebook
- `data/` - Raw and processed CSVs
- `sagemaker/training.py`, `inference.py` - SageMaker scripts

---

## 6. QUICK ANSWERS TO COMMON QUESTIONS

**"What is SHAP?"**
> SHAP values show each feature's contribution to a specific prediction. If tenure has SHAP = -0.3, that feature is pushing toward "no churn."

**"Why XGBoost?"**
> Best performance on tabular data, handles missing values, native SageMaker support, fast training.

**"How did you handle class imbalance?"**
> Used AUC metric (threshold-independent), can add scale_pos_weight if needed.

**"What's the difference between training and inference?"**
> Training: Learn patterns from historical data. Inference: Apply learned patterns to new data to make predictions.

**"What does AUC = 0.89 mean?"**
> If I randomly pick one churner and one non-churner, there's an 89% chance the model ranks the churner as higher risk.

---

## 7. AWS RESOURCES (Your Specific Setup)

```
Account ID:     231284356634
Region:         us-east-1
IAM User:       sagemaker-developer
S3 Bucket:      customer-churn-vahant-2026
Endpoint Name:  churn-prediction-endpoint
Role ARN:       arn:aws:iam::231284356634:role/service-role/
                AmazonSageMaker-ExecutionRole-20260212T230810
```

---

## 8. THINGS TO SAY (Not Do)

**Opening:**
> "I built an end-to-end ML system for customer churn prediction - from data validation to cloud deployment."

**When asked about challenges:**
> "The trickiest part was SageMaker's data format requirements. I debugged using CloudWatch logs and systematic elimination."

**When asked what you'd improve:**
> "I'd add automated retraining triggers and A/B testing for model updates."

**When you don't know something:**
> "I haven't implemented that specifically, but my approach would be... [explain logical thinking]"

---

## 9. RED FLAGS TO AVOID

❌ Don't say "I just followed a tutorial"
❌ Don't claim to have done things you didn't
❌ Don't panic if asked about something you don't know
❌ Don't speak in pure technical jargon - explain simply first

✅ Do say "I designed this because..."
✅ Do explain your decision-making process
✅ Do admit knowledge gaps and explain how you'd learn
✅ Do connect technical choices to business outcomes

---

## 10. FINAL CONFIDENCE BOOSTERS

**You built:**
- A working ML model (0.89 AUC)
- A production-ready API (6 endpoints)
- Cloud deployment (SageMaker)
- Automated testing (16 tests)
- Model explainability (SHAP)
- Cost monitoring

**You understand:**
- Why XGBoost works well
- How to prevent overfitting
- AWS infrastructure basics
- CI/CD principles
- Production vs research code differences

**You can discuss:**
- Feature engineering strategies
- Model monitoring approaches
- Scaling considerations
- Cost optimization

---

**YOU GOT THIS! 💪**

The code works. The model is deployed. You understand it end-to-end.
