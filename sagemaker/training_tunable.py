#!/usr/bin/env python3
"""
Tunable SageMaker Training Script

Supports multiple algorithms for hyperparameter tuning:
- Random Forest
- XGBoost
- Gradient Boosting

Author: Vahant
"""

import argparse
import joblib
import pandas as pd
import numpy as np
import os
import sys
import json
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
from sklearn.model_selection import train_test_split
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import XGBoost
try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not available, using sklearn alternatives")


def parse_args():
    """Parse command line arguments for hyperparameter tuning"""
    parser = argparse.ArgumentParser()
    
    # Algorithm selection
    parser.add_argument('--algorithm', type=str, default='random_forest',
                       choices=['random_forest', 'xgboost', 'gradient_boosting'])
    
    # Common hyperparameters
    parser.add_argument('--n-estimators', type=int, default=100)
    parser.add_argument('--max-depth', type=int, default=10)
    parser.add_argument('--random-state', type=int, default=42)
    
    # Random Forest specific
    parser.add_argument('--min-samples-split', type=int, default=2)
    parser.add_argument('--min-samples-leaf', type=int, default=1)
    parser.add_argument('--max-features', type=str, default='sqrt')
    
    # XGBoost/GradientBoosting specific
    parser.add_argument('--learning-rate', type=float, default=0.1)
    parser.add_argument('--subsample', type=float, default=0.8)
    parser.add_argument('--colsample-bytree', type=float, default=0.8)
    parser.add_argument('--gamma', type=float, default=0)
    parser.add_argument('--reg-alpha', type=float, default=0)
    parser.add_argument('--reg-lambda', type=float, default=1)
    
    # SageMaker paths
    parser.add_argument('--model-dir', type=str, 
                       default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'))
    parser.add_argument('--train', type=str, 
                       default=os.environ.get('SM_CHANNEL_TRAIN', '/opt/ml/input/data/train'))
    parser.add_argument('--output-data-dir', type=str,
                       default=os.environ.get('SM_OUTPUT_DATA_DIR', '/opt/ml/output/data'))
    
    return parser.parse_args()


def load_data(data_dir):
    """Load training data from directory"""
    logger.info(f"Loading data from {data_dir}")
    
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    
    if not csv_files:
        raise FileNotFoundError(f"No CSV files in {data_dir}")
    
    data_file = next((f for f in csv_files if 'processed' in f.lower()), csv_files[0])
    data_path = os.path.join(data_dir, data_file)
    
    data = pd.read_csv(data_path)
    logger.info(f"Loaded {len(data)} samples with {data.shape[1]} columns")
    
    return data


def prepare_data(data):
    """Prepare features and target"""
    if 'Churn' not in data.columns:
        raise ValueError("Target column 'Churn' not found")
    
    X = data.drop('Churn', axis=1)
    y = data['Churn']
    
    logger.info(f"Features: {X.shape[1]}, Target distribution: {y.value_counts().to_dict()}")
    
    return X, y


def create_model(args):
    """Create model based on algorithm selection"""
    algorithm = args.algorithm
    
    if algorithm == 'random_forest':
        model = RandomForestClassifier(
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            min_samples_split=args.min_samples_split,
            min_samples_leaf=args.min_samples_leaf,
            max_features=args.max_features,
            random_state=args.random_state,
            n_jobs=-1
        )
    
    elif algorithm == 'xgboost':
        if not XGBOOST_AVAILABLE:
            logger.warning("XGBoost not available, falling back to GradientBoosting")
            algorithm = 'gradient_boosting'
        else:
            model = XGBClassifier(
                n_estimators=args.n_estimators,
                max_depth=args.max_depth,
                learning_rate=args.learning_rate,
                subsample=args.subsample,
                colsample_bytree=args.colsample_bytree,
                gamma=args.gamma,
                reg_alpha=args.reg_alpha,
                reg_lambda=args.reg_lambda,
                random_state=args.random_state,
                eval_metric='logloss',
                use_label_encoder=False
            )
    
    if algorithm == 'gradient_boosting':
        model = GradientBoostingClassifier(
            n_estimators=args.n_estimators,
            max_depth=args.max_depth,
            learning_rate=args.learning_rate,
            subsample=args.subsample,
            min_samples_split=args.min_samples_split,
            min_samples_leaf=args.min_samples_leaf,
            random_state=args.random_state
        )
    
    logger.info(f"Created {type(model).__name__} model")
    return model


def train_and_evaluate(model, X, y, args):
    """Train model and compute metrics for HPO"""
    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=args.random_state, stratify=y
    )
    
    logger.info(f"Training on {len(X_train)} samples, validating on {len(X_val)}")
    
    # Train
    model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = model.predict(X_val)
    y_pred_proba = model.predict_proba(X_val)[:, 1]
    
    accuracy = accuracy_score(y_val, y_pred)
    auc = roc_auc_score(y_val, y_pred_proba)
    
    # Log metrics for SageMaker HPO
    # These must follow the format: key=value;
    print(f"validation:accuracy={accuracy};")
    print(f"validation:auc={auc};")
    
    logger.info(f"Validation Accuracy: {accuracy:.4f}")
    logger.info(f"Validation AUC: {auc:.4f}")
    logger.info(f"\n{classification_report(y_val, y_pred)}")
    
    return {'accuracy': accuracy, 'auc': auc}


def save_model(model, model_dir, metrics):
    """Save model and metadata"""
    os.makedirs(model_dir, exist_ok=True)
    
    # Save model
    model_path = os.path.join(model_dir, 'model.joblib')
    joblib.dump(model, model_path)
    logger.info(f"Model saved to {model_path}")
    
    # Save metrics
    metrics_path = os.path.join(model_dir, 'metrics.json')
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    logger.info(f"Metrics saved to {metrics_path}")


def main():
    """Main training function"""
    try:
        args = parse_args()
        
        logger.info("=" * 50)
        logger.info("Starting Training Job")
        logger.info(f"Algorithm: {args.algorithm}")
        logger.info("=" * 50)
        
        # Load and prepare data
        data = load_data(args.train)
        X, y = prepare_data(data)
        
        # Create and train model
        model = create_model(args)
        metrics = train_and_evaluate(model, X, y, args)
        
        # Save
        save_model(model, args.model_dir, metrics)
        
        logger.info("Training completed successfully!")
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
