"""
FastAPI REST API for Customer Churn Prediction (v2 — Hybrid)

Production-ready API with:
- Hybrid prediction: Rules Engine + ML Model
- Health checks
- Batch predictions
- Model explainability endpoint
- Request validation

The v2 pipeline addresses the synthetic data issue:
  - 49.6% of rows follow deterministic rules (100% churn) → handled by Rules Engine
  - 50.4% of rows are ambiguous (14.2% churn) → handled by ML Model
  - Combined: Hybrid predictor gives honest, transparent predictions

Author: Vahant
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional
import pandas as pd
import joblib
import json
import logging
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Customer Churn Prediction API",
    description=(
        "ML-powered customer churn prediction with hybrid approach: "
        "Rules Engine for deterministic cases + ML Model for ambiguous cases"
    ),
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
ml_pipeline = None       # sklearn Pipeline for ambiguous cases
metrics_info = None       # Loaded metrics.json
SPEND_THRESHOLD = 405.0   # Q20 of Total Spend (from training)


# Pydantic models for request/response validation
class CustomerFeatures(BaseModel):
    """Input features for a single customer"""
    Age: int = Field(..., ge=18, le=100, description="Customer age (18-100)")
    Tenure: int = Field(..., ge=0, le=100, description="Months as customer")
    Usage_Frequency: int = Field(..., ge=0, le=50, alias="Usage Frequency")
    Support_Calls: int = Field(..., ge=0, le=20, alias="Support Calls")
    Payment_Delay: int = Field(..., ge=0, le=60, alias="Payment Delay")
    Total_Spend: float = Field(..., ge=0, le=10000, alias="Total Spend")
    Last_Interaction: int = Field(..., ge=0, le=365, alias="Last Interaction")
    Gender: str = Field(..., description="Male or Female")
    Subscription_Type: str = Field(..., alias="Subscription Type")
    Contract_Length: str = Field(..., alias="Contract Length")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
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
            }
        }

    @validator('Gender')
    def validate_gender(cls, v):
        if v not in ['Male', 'Female']:
            raise ValueError('Gender must be Male or Female')
        return v

    @validator('Subscription_Type')
    def validate_subscription(cls, v):
        if v not in ['Basic', 'Standard', 'Premium']:
            raise ValueError(
                'Subscription Type must be Basic, Standard, or Premium')
        return v

    @validator('Contract_Length')
    def validate_contract(cls, v):
        if v not in ['Monthly', 'Quarterly', 'Annual']:
            raise ValueError(
                'Contract Length must be Monthly, Quarterly, or Annual')
        return v


class PredictionResponse(BaseModel):
    """Response for single prediction"""
    customer_id: Optional[str] = None
    churn_prediction: int
    churn_probability: float
    retention_probability: float
    risk_level: str
    prediction_source: str = "ml"  # "rules" or "ml"
    timestamp: str


class BatchPredictionRequest(BaseModel):
    """Request for batch predictions"""
    customers: List[CustomerFeatures]


class BatchPredictionResponse(BaseModel):
    """Response for batch predictions"""
    predictions: List[PredictionResponse]
    summary: Dict
    processing_time_ms: float


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    model_loaded: bool
    approach: str
    version: str
    timestamp: str


class ExplainabilityResponse(BaseModel):
    """Model explainability response"""
    prediction: int
    probability: float
    top_churn_factors: List[Dict]
    top_retention_factors: List[Dict]
    explanation_text: str


# Startup event - load model
@app.on_event("startup")
async def load_model():
    """Load trained ML Pipeline and metrics on startup."""
    global ml_pipeline, metrics_info

    model_path = os.environ.get("MODEL_PATH", "model/model.joblib")
    metrics_path = os.environ.get("METRICS_PATH", "model/metrics.json")

    try:
        if os.path.exists(model_path):
            ml_pipeline = joblib.load(model_path)
            logger.info(f"ML Pipeline loaded from {model_path}")
        else:
            logger.warning(f"Model not found at {model_path}")

        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                metrics_info = json.load(f)
            logger.info(f"Metrics loaded from {metrics_path}")
    except Exception as e:
        logger.error(f"Error loading model: {e}")


# ---------- Rules Engine (inline — matches train_model_v2.py) ----------
def check_deterministic_churn(row: dict) -> bool:
    """Check if a customer matches any deterministic churn rule.

    Rules (from synthetic data analysis):
      1. Support Calls >= 6
      2. Contract Length == Monthly
      3. Payment Delay > 20
      4. Total Spend <= SPEND_THRESHOLD (Q20 ≈ 405)
    """
    if row.get("Support Calls", 0) >= 6:
        return True
    if row.get("Contract Length", "") == "Monthly":
        return True
    if row.get("Payment Delay", 0) > 20:
        return True
    if row.get("Total Spend", 9999) <= SPEND_THRESHOLD:
        return True
    return False


# ---------- Feature engineering (matches train_model_v2.py) ----------
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features matching train_model_v2.py (conservative).

    Removed from v1: risk_score, frustration_index, recency_score,
    support_per_tenure, delay_per_tenure, is_high_support, is_payment_late,
    is_low_usage.
    """
    df = df.copy()
    df["spend_per_tenure"] = df["Total Spend"] / (df["Tenure"] + 1)
    df["usage_per_tenure"] = df["Usage Frequency"] / (df["Tenure"] + 1)
    df["cost_per_usage"]   = df["Total Spend"] / (df["Usage Frequency"] + 1)
    df["age_tenure_ratio"] = df["Age"] / (df["Tenure"] + 1)
    df["is_new_customer"]  = (df["Tenure"] <= 6).astype(int)
    df["is_long_tenure"]   = (df["Tenure"] >= 40).astype(int)
    df["is_senior"]        = (df["Age"] >= 50).astype(int)
    df["tenure_bucket"] = pd.cut(
        df["Tenure"], bins=[0, 6, 12, 24, 36, 61],
        labels=[0, 1, 2, 3, 4], include_lowest=True,
    ).astype(float)
    df["age_group"] = pd.cut(
        df["Age"], bins=[0, 25, 35, 45, 55, 100],
        labels=[0, 1, 2, 3, 4], include_lowest=True,
    ).astype(float)
    return df


def preprocess_input(customer: CustomerFeatures) -> dict:
    """Convert customer features to a raw dict and engineered DataFrame."""
    raw = {
        "Age": customer.Age,
        "Tenure": customer.Tenure,
        "Usage Frequency": customer.Usage_Frequency,
        "Support Calls": customer.Support_Calls,
        "Payment Delay": customer.Payment_Delay,
        "Total Spend": customer.Total_Spend,
        "Last Interaction": customer.Last_Interaction,
        "Gender": customer.Gender,
        "Subscription Type": customer.Subscription_Type,
        "Contract Length": customer.Contract_Length,
    }
    return raw


def predict_single_customer(raw: dict) -> tuple:
    """Hybrid prediction: rules first, then ML.

    Returns (prediction, churn_probability, source).
    """
    # Phase 1: Check deterministic rules
    if check_deterministic_churn(raw):
        return 1, 1.0, "rules"

    # Phase 2: ML model for ambiguous cases
    if ml_pipeline is None:
        raise RuntimeError("ML model not loaded")

    df = pd.DataFrame([raw])
    df = engineer_features(df)
    prediction = int(ml_pipeline.predict(df)[0])
    churn_prob = float(ml_pipeline.predict_proba(df)[0, 1])
    return prediction, churn_prob, "ml"


def get_risk_level(probability: float) -> str:
    """Convert probability to risk level"""
    if probability >= 0.7:
        return "HIGH"
    elif probability >= 0.4:
        return "MEDIUM"
    else:
        return "LOW"


# API Endpoints
@app.get("/", response_model=Dict)
async def root():
    """Root endpoint with API info"""
    return {
        "name": "Customer Churn Prediction API",
        "version": "3.0.0",
        "approach": "Hybrid (Rules Engine + ML Model)",
        "documentation": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if ml_pipeline is not None else "degraded",
        model_loaded=ml_pipeline is not None,
        approach="hybrid",
        version="3.0.0",
        timestamp=datetime.now().isoformat(),
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict_single(customer: CustomerFeatures):
    """
    Predict churn for a single customer.

    Uses hybrid approach:
    - Rules Engine checks deterministic patterns first (100% churn)
    - ML Model handles ambiguous cases
    """
    if ml_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service unavailable.",
        )

    try:
        raw = preprocess_input(customer)
        prediction, churn_prob, source = predict_single_customer(raw)
        retention_prob = 1.0 - churn_prob

        return PredictionResponse(
            churn_prediction=prediction,
            churn_probability=round(churn_prob, 4),
            retention_probability=round(retention_prob, 4),
            risk_level=get_risk_level(churn_prob),
            prediction_source=source,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(request: BatchPredictionRequest):
    """
    Predict churn for multiple customers using hybrid approach.
    """
    if ml_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service unavailable.",
        )

    start_time = datetime.now()

    try:
        predictions = []

        for i, customer in enumerate(request.customers):
            raw = preprocess_input(customer)
            pred, churn_prob, source = predict_single_customer(raw)

            predictions.append(PredictionResponse(
                customer_id=f"customer_{i}",
                churn_prediction=pred,
                churn_probability=round(churn_prob, 4),
                retention_probability=round(1.0 - churn_prob, 4),
                risk_level=get_risk_level(churn_prob),
                prediction_source=source,
                timestamp=datetime.now().isoformat(),
            ))

        churn_count = sum(1 for p in predictions if p.churn_prediction == 1)
        rules_count = sum(1 for p in predictions if p.prediction_source == "rules")
        high_risk = sum(1 for p in predictions if p.risk_level == "HIGH")

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return BatchPredictionResponse(
            predictions=predictions,
            summary={
                "total_customers": len(predictions),
                "predicted_churners": churn_count,
                "churn_rate": round(churn_count / max(len(predictions), 1), 4),
                "rules_engine_matches": rules_count,
                "ml_model_predictions": len(predictions) - rules_count,
                "high_risk_count": high_risk,
                "medium_risk_count": sum(1 for p in predictions if p.risk_level == "MEDIUM"),
                "low_risk_count": sum(1 for p in predictions if p.risk_level == "LOW"),
            },
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/explain", response_model=ExplainabilityResponse)
async def explain_prediction(customer: CustomerFeatures):
    """
    Get explainable prediction with feature contributions.

    For rules-engine matches, explains which deterministic rule fired.
    For ML predictions, shows approximate feature contributions.
    """
    if ml_pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service unavailable.",
        )

    try:
        raw = preprocess_input(customer)
        prediction, churn_prob, source = predict_single_customer(raw)

        # If a deterministic rule fired, explain which one
        if source == "rules":
            fired_rules = []
            if raw["Support Calls"] >= 6:
                fired_rules.append({
                    "feature": "Support Calls",
                    "value": raw["Support Calls"],
                    "contribution": 1.0,
                    "rule": "Support Calls >= 6 → 100% churn in training data",
                })
            if raw["Contract Length"] == "Monthly":
                fired_rules.append({
                    "feature": "Contract Length",
                    "value": raw["Contract Length"],
                    "contribution": 1.0,
                    "rule": "Monthly contract → 100% churn in training data",
                })
            if raw["Payment Delay"] > 20:
                fired_rules.append({
                    "feature": "Payment Delay",
                    "value": raw["Payment Delay"],
                    "contribution": 1.0,
                    "rule": "Payment Delay > 20 → 100% churn in training data",
                })
            if raw["Total Spend"] <= SPEND_THRESHOLD:
                fired_rules.append({
                    "feature": "Total Spend",
                    "value": raw["Total Spend"],
                    "contribution": 1.0,
                    "rule": f"Total Spend <= {SPEND_THRESHOLD} → 100% churn in training data",
                })

            text = (
                f"DETERMINISTIC CHURN (probability=100%). "
                f"This customer matches {len(fired_rules)} rule(s): "
                + ", ".join(r["rule"] for r in fired_rules)
            )

            return ExplainabilityResponse(
                prediction=1,
                probability=1.0,
                top_churn_factors=fired_rules,
                top_retention_factors=[],
                explanation_text=text,
            )

        # ML prediction — use feature importance from CSV if available
        feature_imp_path = os.environ.get(
            "FEATURE_IMPORTANCE_PATH", "model/feature_importance.csv"
        )
        importance_map = {}
        if os.path.exists(feature_imp_path):
            imp_df = pd.read_csv(feature_imp_path)
            importance_map = dict(zip(imp_df["feature"], imp_df["importance"]))

        # Build contribution approximation
        df = pd.DataFrame([raw])
        df = engineer_features(df)
        feature_names = list(df.columns)

        contributions = []
        for name in feature_names:
            val = float(df[name].iloc[0]) if pd.api.types.is_numeric_dtype(df[name]) else 0
            imp = importance_map.get(name, 0.01)
            raw_val = df[name].iloc[0]
            # Convert numpy types to native Python types for JSON serialization
            if pd.api.types.is_numeric_dtype(df[name]):
                serializable_val = float(raw_val) if isinstance(raw_val, float) else int(raw_val)
            else:
                serializable_val = str(raw_val)
            contributions.append({
                "feature": name,
                "value": serializable_val,
                "contribution": float(val * imp),
            })

        contributions.sort(key=lambda x: abs(x["contribution"]), reverse=True)
        churn_factors = [c for c in contributions if c["contribution"] > 0][:5]
        retention_factors = [c for c in contributions if c["contribution"] <= 0][:5]

        if prediction == 1:
            text = (
                f"This customer has a {churn_prob:.1%} probability of churning "
                f"(ML model prediction). Main risk factors: "
                + ", ".join(c["feature"] for c in churn_factors[:3])
            )
        else:
            text = (
                f"This customer is likely to stay (retention: {1-churn_prob:.1%}). "
                f"Positive factors: "
                + ", ".join(c["feature"] for c in retention_factors[:3])
            )

        return ExplainabilityResponse(
            prediction=int(prediction),
            probability=round(churn_prob, 4),
            top_churn_factors=churn_factors,
            top_retention_factors=retention_factors,
            explanation_text=text,
        )

    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/model/info")
async def model_info():
    """Get information about the loaded model and hybrid approach."""
    info = {
        "approach": "hybrid",
        "description": "Rules Engine for deterministic cases + ML Model for ambiguous cases",
        "rules_engine": {
            "rules": [
                "Support Calls >= 6 → churn",
                "Contract Length == Monthly → churn",
                "Payment Delay > 20 → churn",
                f"Total Spend <= {SPEND_THRESHOLD} → churn",
            ],
            "coverage": "49.6% of training data",
            "precision": "100% (by definition — deterministic patterns)",
        },
        "ml_model": {
            "loaded": ml_pipeline is not None,
            "type": type(ml_pipeline).__name__ if ml_pipeline is not None else None,
            "trained_on": "222,391 ambiguous rows (14.2% churn rate)",
        },
        "version": "3.0.0",
    }

    if metrics_info:
        info["training_metrics"] = {
            "ml_model_on_ambiguous": metrics_info.get("ml_model_metrics_on_ambiguous", {}),
            "hybrid_on_full_data": metrics_info.get("hybrid_metrics_on_full_data", {}),
        }

    return info


# Run with: uvicorn api:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
