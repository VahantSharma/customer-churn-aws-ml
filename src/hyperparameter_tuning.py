"""
SageMaker Hyperparameter Tuning for Customer Churn Prediction

This module implements automated hyperparameter optimization using:
- SageMaker Hyperparameter Tuning Jobs
- Bayesian optimization strategy
- Cost-aware tuning with early stopping

Author: Vahant
"""

import boto3
import sagemaker
from sagemaker.sklearn import SKLearn
from sagemaker.tuner import (
    HyperparameterTuner,
    ContinuousParameter,
    IntegerParameter,
    CategoricalParameter
)
from sagemaker.inputs import TrainingInput
from datetime import datetime
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ChurnModelTuner:
    """
    Automated hyperparameter tuning for customer churn models.

    Features:
    - Multiple algorithm support (RandomForest, XGBoost, GradientBoosting)
    - Cost-efficient tuning strategies
    - Automatic best model selection
    - Detailed tuning analytics
    """

    # Hyperparameter ranges for different algorithms
    HYPERPARAMETER_RANGES = {
        'random_forest': {
            'n-estimators': IntegerParameter(50, 300),
            'max-depth': IntegerParameter(3, 20),
            'min-samples-split': IntegerParameter(2, 20),
            'min-samples-leaf': IntegerParameter(1, 10),
            'max-features': CategoricalParameter(['sqrt', 'log2', 'auto'])
        },
        'xgboost': {
            'n-estimators': IntegerParameter(50, 300),
            'max-depth': IntegerParameter(3, 12),
            'learning-rate': ContinuousParameter(0.01, 0.3, scaling_type='Logarithmic'),
            'subsample': ContinuousParameter(0.6, 1.0),
            'colsample-bytree': ContinuousParameter(0.6, 1.0),
            'gamma': ContinuousParameter(0, 5),
            'reg-alpha': ContinuousParameter(0, 1),
            'reg-lambda': ContinuousParameter(0, 1)
        },
        'gradient_boosting': {
            'n-estimators': IntegerParameter(50, 300),
            'max-depth': IntegerParameter(3, 15),
            'learning-rate': ContinuousParameter(0.01, 0.3, scaling_type='Logarithmic'),
            'min-samples-split': IntegerParameter(2, 20),
            'min-samples-leaf': IntegerParameter(1, 10),
            'subsample': ContinuousParameter(0.6, 1.0)
        }
    }

    def __init__(self,
                 role: Optional[str] = None,
                 session: Optional[sagemaker.Session] = None):
        """
        Initialize the tuner.

        Args:
            role: SageMaker execution role ARN
            session: SageMaker session
        """
        self.session = session or sagemaker.Session()
        self.role = role or sagemaker.get_execution_role()
        self.bucket = self.session.default_bucket()

        self.tuner = None
        self.best_training_job = None
        self.tuning_results = None

        logger.info("ChurnModelTuner initialized")
        logger.info(f"  Role: {self.role[:50]}...")
        logger.info(f"  Bucket: {self.bucket}")

    def create_tuning_job(self,
                          training_data_s3: str,
                          algorithm: str = 'random_forest',
                          objective_metric: str = 'validation:auc',
                          max_jobs: int = 10,
                          max_parallel_jobs: int = 2,
                          instance_type: str = 'ml.m5.large',
                          base_job_name: str = 'churn-tuning') -> HyperparameterTuner:
        """
        Create and configure a hyperparameter tuning job.

        Args:
            training_data_s3: S3 URI for training data
            algorithm: Algorithm to tune ('random_forest', 'xgboost', 'gradient_boosting')
            objective_metric: Metric to optimize
            max_jobs: Maximum number of training jobs
            max_parallel_jobs: Maximum parallel jobs (cost control)
            instance_type: Training instance type
            base_job_name: Base name for tuning job

        Returns:
            Configured HyperparameterTuner
        """
        logger.info(f"Creating tuning job for {algorithm}")
        logger.info(
            f"  Max jobs: {max_jobs}, Max parallel: {max_parallel_jobs}")
        logger.info(f"  Instance type: {instance_type}")

        # Validate algorithm
        if algorithm not in self.HYPERPARAMETER_RANGES:
            raise ValueError(f"Unknown algorithm: {algorithm}. "
                             f"Choose from: {list(self.HYPERPARAMETER_RANGES.keys())}")

        # Create estimator
        estimator = SKLearn(
            entry_point='training_tunable.py',
            source_dir='sagemaker',
            role=self.role,
            instance_type=instance_type,
            framework_version='1.0-1',
            py_version='py3',
            hyperparameters={
                'algorithm': algorithm,
                'random-state': 42
            },
            sagemaker_session=self.session
        )

        # Get hyperparameter ranges for algorithm
        hyperparameter_ranges = self.HYPERPARAMETER_RANGES[algorithm]

        # Create tuner
        self.tuner = HyperparameterTuner(
            estimator=estimator,
            objective_metric_name=objective_metric,
            hyperparameter_ranges=hyperparameter_ranges,
            objective_type='Maximize',
            max_jobs=max_jobs,
            max_parallel_jobs=max_parallel_jobs,
            strategy='Bayesian',  # More efficient than Random
            base_tuning_job_name=base_job_name,
            early_stopping_type='Auto'  # Stop poor performing jobs early
        )

        logger.info("Tuning job configured successfully")
        return self.tuner

    def run_tuning(self,
                   training_data_s3: str,
                   wait: bool = True,
                   logs: bool = False) -> Dict:
        """
        Execute the hyperparameter tuning job.

        Args:
            training_data_s3: S3 URI for training data
            wait: Whether to wait for completion
            logs: Whether to show logs (can be verbose)

        Returns:
            Dictionary with tuning results
        """
        if self.tuner is None:
            raise ValueError(
                "Tuner not configured. Call create_tuning_job first.")

        logger.info("Starting hyperparameter tuning job...")
        start_time = datetime.now()

        # Create training input
        train_input = TrainingInput(training_data_s3, content_type='text/csv')

        # Start tuning
        self.tuner.fit({'train': train_input}, wait=wait, logs=logs)

        if wait:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds() / 60

            logger.info(f"Tuning completed in {duration:.2f} minutes")

            # Get results
            self.tuning_results = self._get_tuning_results()
            return self.tuning_results
        else:
            return {"status": "running",
                    "tuning_job_name": self.tuner.latest_tuning_job.name}

    def _get_tuning_results(self) -> Dict:
        """Extract and format tuning results"""

        # Get best training job
        self.best_training_job = self.tuner.best_training_job()

        # Get analytics
        analytics = self.tuner.analytics()

        # Training job summaries
        training_job_summaries = analytics.training_job_summaries()

        results = {
            'best_job': {
                'name': self.best_training_job,
                'hyperparameters': self._get_best_hyperparameters(),
                'objective_value': self._get_best_objective_value()
            },
            'total_jobs': len(training_job_summaries),
            'completed_jobs': len([j for j in training_job_summaries
                                  if j.get('TrainingJobStatus') == 'Completed']),
            'all_jobs': training_job_summaries
        }

        logger.info(f"Best job: {results['best_job']['name']}")
        logger.info(
            f"Best objective value: {results['best_job']['objective_value']}")

        return results

    def _get_best_hyperparameters(self) -> Dict:
        """Get hyperparameters from best training job"""
        sm_client = boto3.client('sagemaker')

        response = sm_client.describe_training_job(
            TrainingJobName=self.best_training_job
        )

        return response.get('HyperParameters', {})

    def _get_best_objective_value(self) -> float:
        """Get objective metric value from best training job"""
        sm_client = boto3.client('sagemaker')

        response = sm_client.describe_training_job(
            TrainingJobName=self.best_training_job
        )

        final_metric = response.get('FinalMetricDataList', [])
        if final_metric:
            return final_metric[0].get('Value', None)
        return None

    def get_best_model_uri(self) -> str:
        """Get S3 URI of the best model artifact"""
        if self.best_training_job is None:
            raise ValueError("No tuning results available. Run tuning first.")

        sm_client = boto3.client('sagemaker')

        response = sm_client.describe_training_job(
            TrainingJobName=self.best_training_job
        )

        return response['ModelArtifacts']['S3ModelArtifacts']

    def deploy_best_model(self,
                          endpoint_name: str,
                          instance_type: str = 'ml.t2.medium',
                          instance_count: int = 1) -> sagemaker.Predictor:
        """
        Deploy the best model from tuning to an endpoint.

        Args:
            endpoint_name: Name for the endpoint
            instance_type: Instance type for inference
            instance_count: Number of instances

        Returns:
            SageMaker Predictor for the deployed model
        """
        logger.info(f"Deploying best model to endpoint: {endpoint_name}")

        predictor = self.tuner.deploy(
            initial_instance_count=instance_count,
            instance_type=instance_type,
            endpoint_name=endpoint_name,
            entry_point='inference.py',
            source_dir='sagemaker'
        )

        logger.info(f"Model deployed successfully to {endpoint_name}")
        return predictor

    def estimate_tuning_cost(self,
                             max_jobs: int,
                             instance_type: str = 'ml.m5.large',
                             avg_job_duration_minutes: int = 5) -> Dict:
        """
        Estimate the cost of a tuning job.

        Args:
            max_jobs: Maximum number of training jobs
            instance_type: Instance type
            avg_job_duration_minutes: Estimated average job duration

        Returns:
            Cost estimate dictionary
        """
        # Instance pricing (approximate, varies by region)
        instance_pricing = {
            'ml.m5.large': 0.115,
            'ml.m5.xlarge': 0.23,
            'ml.m5.2xlarge': 0.461,
            'ml.m5.4xlarge': 0.922,
            'ml.t2.medium': 0.056,
            'ml.t3.medium': 0.050
        }

        hourly_rate = instance_pricing.get(instance_type, 0.115)
        hours_per_job = avg_job_duration_minutes / 60

        # Worst case: all jobs run
        max_cost = max_jobs * hourly_rate * hours_per_job

        # Typical case: ~70% of jobs complete (due to early stopping)
        typical_cost = max_cost * 0.7

        return {
            'instance_type': instance_type,
            'hourly_rate': hourly_rate,
            'max_jobs': max_jobs,
            'avg_job_duration_minutes': avg_job_duration_minutes,
            'max_cost_usd': round(max_cost, 2),
            'typical_cost_usd': round(typical_cost, 2),
            'recommendation': 'Use early stopping and limit parallel jobs to optimize cost'
        }


def quick_tune(training_data_s3: str,
               algorithm: str = 'random_forest',
               max_jobs: int = 5,
               role: Optional[str] = None) -> Dict:
    """
    Quick function to run hyperparameter tuning.

    Args:
        training_data_s3: S3 URI for training data
        algorithm: Algorithm to tune
        max_jobs: Maximum training jobs
        role: SageMaker execution role

    Returns:
        Tuning results dictionary
    """
    tuner = ChurnModelTuner(role=role)
    tuner.create_tuning_job(
        training_data_s3=training_data_s3,
        algorithm=algorithm,
        max_jobs=max_jobs,
        max_parallel_jobs=2,
        instance_type='ml.m5.large'
    )

    return tuner.run_tuning(training_data_s3, wait=True)


if __name__ == "__main__":
    # Example usage
    print("SageMaker Hyperparameter Tuning Module")
    print("=" * 50)

    # Cost estimation example
    tuner = ChurnModelTuner.__new__(ChurnModelTuner)
    cost = tuner.estimate_tuning_cost(
        max_jobs=10,
        instance_type='ml.m5.large',
        avg_job_duration_minutes=5
    )

    print("\nCost Estimate for 10-job tuning run:")
    print(f"  Instance: {cost['instance_type']}")
    print(f"  Max Cost: ${cost['max_cost_usd']}")
    print(f"  Typical Cost: ${cost['typical_cost_usd']}")
    print(f"\nRecommendation: {cost['recommendation']}")
