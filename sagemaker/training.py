#!/usr/bin/env python3
"""
SageMaker Training Script for Customer Churn Prediction

This script is designed to run on SageMaker training instances.
It loads data, trains a Random Forest model, and saves the trained model.
"""

import argparse
import joblib
import pandas as pd
import numpy as np
import os
import sys
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Train Customer Churn Prediction Model')
    
    # Hyperparameters
    parser.add_argument('--n-estimators', type=int, default=100,
                       help='Number of trees in the random forest')
    parser.add_argument('--max-depth', type=int, default=10,
                       help='Maximum depth of the trees')
    parser.add_argument('--min-samples-split', type=int, default=2,
                       help='Minimum number of samples required to split an internal node')
    parser.add_argument('--min-samples-leaf', type=int, default=1,
                       help='Minimum number of samples required to be at a leaf node')
    parser.add_argument('--random-state', type=int, default=42,
                       help='Random state for reproducibility')
    
    # SageMaker specific arguments
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'),
                       help='Directory to save the trained model')
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAIN', '/opt/ml/input/data/train'),
                       help='Directory containing training data')
    
    return parser.parse_args()


def load_data(train_dir):
    """Load training data from the specified directory."""
    logger.info(f"Loading data from {train_dir}")
    
    csv_files = [f for f in os.listdir(train_dir) if f.endswith('.csv')]
    
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {train_dir}")
    
    data_file = None
    for file in csv_files:
        if 'churn' in file.lower() or 'processed' in file.lower():
            data_file = file
            break
    
    if not data_file:
        data_file = csv_files[0]  
    
    data_path = os.path.join(train_dir, data_file)
    logger.info(f"Loading data from {data_path}")
    
    try:
        data = pd.read_csv(data_path)
        logger.info(f"Data loaded successfully. Shape: {data.shape}")
        return data
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise


def prepare_features(data):
    """Prepare features and target variable."""
    logger.info("Preparing features and target variable")
    
    # Check if 'Churn' column exists
    if 'Churn' not in data.columns:
        logger.error("Target column 'Churn' not found in data")
        logger.info(f"Available columns: {list(data.columns)}")
        raise ValueError("Target column 'Churn' not found")
    
    X = data.drop('Churn', axis=1)
    y = data['Churn']
    
    logger.info(f"Features shape: {X.shape}")
    logger.info(f"Target shape: {y.shape}")
    logger.info(f"Target distribution:\n{y.value_counts()}")
    
    return X, y


def train_model(X, y, args):
    """Train the Random Forest model."""
    logger.info("Training Random Forest model")
    
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, random_state=args.random_state, stratify=y
    )
    
    model = RandomForestClassifier(
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        min_samples_split=args.min_samples_split,
        min_samples_leaf=args.min_samples_leaf,
        random_state=args.random_state,
        n_jobs=-1  
    )
    
    logger.info(f"Training with parameters: n_estimators={args.n_estimators}, "
               f"max_depth={args.max_depth}, min_samples_split={args.min_samples_split}")
    
    model.fit(X_train, y_train)
    
    y_pred = model.predict(X_val)
    accuracy = accuracy_score(y_val, y_pred)
    
    logger.info(f"Validation accuracy: {accuracy:.4f}")
    logger.info(f"Classification Report:\n{classification_report(y_val, y_pred)}")
    
    feature_importance = pd.DataFrame({
        'feature': X.columns,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    logger.info(f"Top 10 Feature Importances:\n{feature_importance.head(10)}")
    
    return model


def save_model(model, model_dir):
    """Save the trained model."""
    logger.info(f"Saving model to {model_dir}")
    
    # Ensure model directory exists
    os.makedirs(model_dir, exist_ok=True)
    
    # Save model
    model_path = os.path.join(model_dir, 'model.joblib')
    joblib.dump(model, model_path)
    
    logger.info(f"Model saved successfully to {model_path}")


def main():
    """Main training function."""
    try:
        args = parse_args()
        
        logger.info("Starting training job")
        logger.info(f"Arguments: {vars(args)}")
        
        data = load_data(args.train)
        
        X, y = prepare_features(data)
        
        model = train_model(X, y, args)
        
        save_model(model, args.model_dir)
        
        logger.info("Training completed successfully!")
        
    except Exception as e:
        logger.error(f"Training failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
