"""
FastAPI REST API for Customer Churn Prediction

Production-ready API with:
- Health checks
- Batch predictions
- Model explainability endpoint
- Request validation
- Rate limiting ready

Author: Vahant
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
import joblib
import logging
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Customer Churn Prediction API",
    description="ML-powered customer churn prediction with explainability",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model (Pipeline: preprocessor + model, loaded on startup)
model = None


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
    """Load trained Pipeline model on startup"""
    global model

    model_path = os.environ.get(
        'MODEL_PATH',
        'model/model.joblib')

    try:
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            logger.info(f"Model loaded from {model_path}")
        else:
            logger.warning(f"Model not found at {model_path}")
    except Exception as e:
        logger.error(f"Error loading model: {e}")


# Helper functions
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add engineered features matching train_model.py exactly."""
    df = df.copy()
    df["spend_per_tenure"]    = df["Total Spend"] / (df["Tenure"] + 1)
    df["support_per_tenure"]  = df["Support Calls"] / (df["Tenure"] + 1)
    df["usage_per_tenure"]    = df["Usage Frequency"] / (df["Tenure"] + 1)
    df["delay_per_tenure"]    = df["Payment Delay"] / (df["Tenure"] + 1)
    df["cost_per_usage"]      = df["Total Spend"] / (df["Usage Frequency"] + 1)
    df["recency_score"]       = 1.0 / (df["Last Interaction"] + 1)
    df["risk_score"]          = (df["Support Calls"] * df["Payment Delay"]) / (df["Total Spend"] + 1)
    df["frustration_index"]   = df["Support Calls"] * df["Payment Delay"] * (1.0 / (df["Usage Frequency"] + 1))
    df["is_high_support"]     = (df["Support Calls"] >= 5).astype(int)
    df["is_payment_late"]     = (df["Payment Delay"] >= 15).astype(int)
    df["is_low_usage"]        = (df["Usage Frequency"] <= 5).astype(int)
    df["is_new_customer"]     = (df["Tenure"] <= 6).astype(int)
    df["is_long_tenure"]      = (df["Tenure"] >= 36).astype(int)
    df["tenure_bucket"]       = pd.cut(df["Tenure"], bins=[0, 6, 12, 24, 48, 200], labels=[0, 1, 2, 3, 4]).astype(int)
    df["age_group"]           = pd.cut(df["Age"], bins=[0, 25, 35, 45, 55, 100], labels=[0, 1, 2, 3, 4]).astype(int)
    return df


def preprocess_input(customer: CustomerFeatures) -> pd.DataFrame:
    """Convert customer features to model input DataFrame with engineered features."""
    data = {
        'Age': customer.Age,
        'Tenure': customer.Tenure,
        'Usage Frequency': customer.Usage_Frequency,
        'Support Calls': customer.Support_Calls,
        'Payment Delay': customer.Payment_Delay,
        'Total Spend': customer.Total_Spend,
        'Last Interaction': customer.Last_Interaction,
        'Gender': customer.Gender,
        'Subscription Type': customer.Subscription_Type,
        'Contract Length': customer.Contract_Length
    }
    df = pd.DataFrame([data])
    df = engineer_features(df)
    return df


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
        "version": "2.0.0",
        "documentation": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy" if model is not None else "degraded",
        model_loaded=model is not None,
        version="2.0.0",
        timestamp=datetime.now().isoformat()
    )


@app.post("/predict", response_model=PredictionResponse)
async def predict_single(customer: CustomerFeatures):
    """
    Predict churn for a single customer.

    Returns prediction, probability, and risk level.
    """
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service unavailable."
        )

    try:
        # Preprocess
        X = preprocess_input(customer)

        # Predict
        prediction = model.predict(X)[0]
        probabilities = model.predict_proba(X)[0]

        churn_prob = float(probabilities[1])
        retention_prob = float(probabilities[0])

        return PredictionResponse(
            churn_prediction=int(prediction),
            churn_probability=round(churn_prob, 4),
            retention_probability=round(retention_prob, 4),
            risk_level=get_risk_level(churn_prob),
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(request: BatchPredictionRequest):
    """
    Predict churn for multiple customers.

    More efficient than multiple single predictions.
    """
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service unavailable."
        )

    start_time = datetime.now()

    try:
        predictions = []

        for i, customer in enumerate(request.customers):
            X = preprocess_input(customer)
            pred = model.predict(X)[0]
            probs = model.predict_proba(X)[0]

            churn_prob = float(probs[1])

            predictions.append(PredictionResponse(
                customer_id=f"customer_{i}",
                churn_prediction=int(pred),
                churn_probability=round(churn_prob, 4),
                retention_probability=round(float(probs[0]), 4),
                risk_level=get_risk_level(churn_prob),
                timestamp=datetime.now().isoformat()
            ))

        # Calculate summary
        churn_count = sum(1 for p in predictions if p.churn_prediction == 1)
        high_risk_count = sum(1 for p in predictions if p.risk_level == "HIGH")

        processing_time = (datetime.now() - start_time).total_seconds() * 1000

        return BatchPredictionResponse(
            predictions=predictions,
            summary={
                "total_customers": len(predictions),
                "predicted_churners": churn_count,
                "churn_rate": round(churn_count / len(predictions), 4),
                "high_risk_count": high_risk_count,
                "medium_risk_count": sum(1 for p in predictions if p.risk_level == "MEDIUM"),
                "low_risk_count": sum(1 for p in predictions if p.risk_level == "LOW")
            },
            processing_time_ms=round(processing_time, 2)
        )

    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/explain", response_model=ExplainabilityResponse)
async def explain_prediction(customer: CustomerFeatures):
    """
    Get explainable prediction with feature contributions.

    Uses SHAP-style explanation (simplified version).
    """
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded. Service unavailable."
        )

    try:
        X = preprocess_input(customer)

        prediction = model.predict(X)[0]
        probabilities = model.predict_proba(X)[0]
        churn_prob = float(probabilities[1])

        # Get feature importance (for tree-based models)
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
        else:
            # Fallback: use coefficients for linear models
            importances = np.abs(
                model.coef_[0]) if hasattr(
                model,
                'coef_') else np.zeros(
                X.shape[1])

        # Create feature contribution approximation
        feature_contrib = X.flatten() * importances[:len(X.flatten())]

        # Map to feature names (simplified)
        feature_names_local = [
            'Age', 'Tenure', 'Usage Frequency', 'Support Calls',
            'Payment Delay', 'Total Spend', 'Last Interaction',
            'Gender_Male', 'Subscription_Standard', 'Subscription_Premium',
            'Contract_Quarterly', 'Contract_Annual'
        ]

        # Create contribution dict
        contributions = []
        for i, (name, contrib) in enumerate(
                zip(feature_names_local[:len(feature_contrib)], feature_contrib)):
            contributions.append({
                'feature': name,
                'value': float(X.flatten()[i]),
                'contribution': float(contrib)
            })

        # Sort by absolute contribution
        contributions.sort(key=lambda x: abs(x['contribution']), reverse=True)

        # Split into positive and negative
        churn_factors = [c for c in contributions if c['contribution'] > 0][:5]
        retention_factors = [
            c for c in contributions if c['contribution'] <= 0][:5]

        # Generate explanation text
        if prediction == 1:
            text = f"This customer has a {churn_prob:.1%} probability of churning. "
            text += "Main risk factors: "
            text += ", ".join([f"{c['feature']}" for c in churn_factors[:3]])
        else:
            text = f"This customer is likely to stay (retention probability: {1-churn_prob:.1%}). "
            text += "Positive factors: "
            text += ", ".join([f"{c['feature']}" for c in retention_factors[:3]])

        return ExplainabilityResponse(
            prediction=int(prediction),
            probability=round(churn_prob, 4),
            top_churn_factors=churn_factors,
            top_retention_factors=retention_factors,
            explanation_text=text
        )

    except Exception as e:
        logger.error(f"Explanation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/model/info")
async def model_info():
    """Get information about the loaded model"""
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Model not loaded"
        )

    info = {
        "model_type": type(model).__name__,
        "n_features": model.n_features_in_ if hasattr(model, 'n_features_in_') else "unknown",
        "classes": model.classes_.tolist() if hasattr(model, 'classes_') else [0, 1]
    }

    if hasattr(model, 'n_estimators'):
        info["n_estimators"] = model.n_estimators

    if hasattr(model, 'max_depth'):
        info["max_depth"] = model.max_depth

    return info


# Run with: uvicorn api:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
