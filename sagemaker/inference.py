#!/usr/bin/env python3
"""
SageMaker Inference Script for Customer Churn Prediction

This script handles model loading, input processing, prediction, and output formatting
for the deployed SageMaker endpoint.
"""

import joblib
import pandas as pd
import numpy as np
import json
import logging
from io import StringIO
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def model_fn(model_dir):
    """
    Load model from the model_dir.
    
    This function is called by SageMaker when the endpoint is created.
    
    Args:
        model_dir (str): Directory where the model artifacts are stored
        
    Returns:
        model: The loaded scikit-learn model
    """
    try:
        model_path = os.path.join(model_dir, 'model.joblib')
        logger.info(f"Loading model from {model_path}")
        
        model = joblib.load(model_path)
        logger.info("Model loaded successfully")
        
        return model
        
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        raise


def input_fn(request_body, request_content_type):
    """
    Parse input data for prediction.
    
    This function processes the incoming request and converts it to a format
    that can be used by the predict_fn function.
    
    Args:
        request_body: The body of the request sent to the endpoint
        request_content_type: The content type of the request
        
    Returns:
        pandas.DataFrame: Processed input data ready for prediction
    """
    try:
        logger.info(f"Processing input with content type: {request_content_type}")
        
        if request_content_type == 'application/json':
            # Handle JSON input
            input_data = json.loads(request_body)
            
            # Handle both single instance and batch predictions
            if isinstance(input_data, dict):
                # Single instance
                df = pd.DataFrame([input_data])
            elif isinstance(input_data, list):
                # Batch of instances
                df = pd.DataFrame(input_data)
            else:
                raise ValueError("JSON input must be a dictionary or list of dictionaries")
                
            logger.info(f"Processed JSON input. Shape: {df.shape}")
            return df
            
        elif request_content_type == 'text/csv':
            # Handle CSV input
            df = pd.read_csv(StringIO(request_body), header=None)
            logger.info(f"Processed CSV input. Shape: {df.shape}")
            return df
            
        else:
            raise ValueError(f'Unsupported content type: {request_content_type}')
            
    except Exception as e:
        logger.error(f"Error processing input: {e}")
        raise


def predict_fn(input_data, model):
    """
    Make prediction using the loaded model.
    
    Args:
        input_data (pandas.DataFrame): Input data for prediction
        model: The loaded scikit-learn model
        
    Returns:
        dict: Dictionary containing predictions and probabilities
    """
    try:
        logger.info(f"Making predictions for {len(input_data)} instances")
        
        predictions = model.predict(input_data)
        
        probabilities = model.predict_proba(input_data)
        
        feature_names = getattr(model, 'feature_names_in_', None)
        
        result = {
            'predictions': predictions.tolist(),
            'probabilities': probabilities.tolist(),
            'num_instances': len(input_data)
        }
        
        if hasattr(model, 'classes_'):
            result['class_labels'] = model.classes_.tolist()
        
        confidence_scores = np.max(probabilities, axis=1)
        result['confidence_scores'] = confidence_scores.tolist()
        
        logger.info(f"Predictions completed successfully for {len(input_data)} instances")
        
        return result
        
    except Exception as e:
        logger.error(f"Error during prediction: {e}")
        raise


def output_fn(prediction, content_type):
    """
    Format prediction output.
    
    Args:
        prediction: The prediction result from predict_fn
        content_type: The desired output content type
        
    Returns:
        str: Formatted prediction output
    """
    try:
        logger.info(f"Formatting output with content type: {content_type}")
        
        if content_type == 'application/json':
            return json.dumps(prediction, indent=2)
        else:
            raise ValueError(f'Unsupported output content type: {content_type}')
            
    except Exception as e:
        logger.error(f"Error formatting output: {e}")
        raise


# Optional: Handler for batch transform jobs
def transform_fn(model, request_body, request_content_type, response_content_type):
    """
    Alternative handler that combines input_fn, predict_fn, and output_fn.
    
    This is useful for batch transform jobs or when you need more control
    over the entire inference pipeline.
    """
    try:
        input_data = input_fn(request_body, request_content_type)
        
        prediction = predict_fn(input_data, model)
        
        output = output_fn(prediction, response_content_type)
        
        return output
        
    except Exception as e:
        logger.error(f"Error in transform_fn: {e}")
        raise


def ping():
    """
    Health check function for the endpoint.
    
    Returns:
        tuple: (status_code, message)
    """
    try:
        return 200, "OK"
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return 500, f"Health check failed: {e}"
