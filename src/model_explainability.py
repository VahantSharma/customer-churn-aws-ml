"""
Model Explainability Module using SHAP

This module provides model interpretability features essential for:
- Regulatory compliance (GDPR, CCPA right to explanation)
- Business stakeholder communication
- Model debugging and validation
- Feature importance analysis

Author: Vahant
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from typing import Dict, List, Optional, Union
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import SHAP (optional dependency)
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not installed. Install with: pip install shap")


class ModelExplainer:
    """
    Comprehensive model explainability using SHAP values.

    Provides:
    - Global feature importance
    - Local (individual prediction) explanations
    - Feature interaction analysis
    - Visualization tools
    """

    def __init__(
            self, model, feature_names: List[str], model_type: str = "tree"):
        """
        Initialize the explainer.

        Args:
            model: Trained sklearn-compatible model
            feature_names: List of feature names
            model_type: Type of model ('tree', 'linear', 'kernel')
        """
        self.model = model
        self.feature_names = feature_names
        self.model_type = model_type
        self.explainer = None
        self.shap_values = None
        self.expected_value = None

        if not SHAP_AVAILABLE:
            raise ImportError(
                "SHAP is required for model explainability. Install with: pip install shap")

    def fit(self, X: Union[np.ndarray, pd.DataFrame],
            sample_size: int = 100) -> 'ModelExplainer':
        """
        Fit the SHAP explainer on background data.

        Args:
            X: Training data for background distribution
            sample_size: Number of samples for background (for efficiency)

        Returns:
            self
        """
        logger.info(
            f"Fitting SHAP explainer with {sample_size} background samples")

        # Convert to DataFrame if needed
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X, columns=self.feature_names)

        # Sample for efficiency
        if len(X) > sample_size:
            X_sample = X.sample(n=sample_size, random_state=42)
        else:
            X_sample = X

        # Create appropriate explainer based on model type
        if self.model_type == "tree":
            self.explainer = shap.TreeExplainer(self.model)
        elif self.model_type == "linear":
            self.explainer = shap.LinearExplainer(self.model, X_sample)
        else:
            self.explainer = shap.KernelExplainer(
                self.model.predict_proba,
                X_sample
            )

        self.expected_value = self.explainer.expected_value
        logger.info("SHAP explainer fitted successfully")

        return self

    def explain_global(self, X: Union[np.ndarray, pd.DataFrame]) -> Dict:
        """
        Generate global feature importance explanations.

        Args:
            X: Data to explain (typically test set)

        Returns:
            Dictionary with global importance metrics
        """
        logger.info(f"Computing global SHAP values for {len(X)} samples")

        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X, columns=self.feature_names)

        # Compute SHAP values
        self.shap_values = self.explainer.shap_values(X)

        # Handle multi-output (binary classification returns list)
        if isinstance(self.shap_values, list):
            # Use positive class SHAP values
            shap_values_positive = self.shap_values[1]
        else:
            shap_values_positive = self.shap_values

        # Calculate mean absolute SHAP values (global importance)
        mean_abs_shap = np.abs(shap_values_positive).mean(axis=0)

        # Create importance DataFrame
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'mean_abs_shap': mean_abs_shap,
            'mean_shap': shap_values_positive.mean(axis=0),
            'std_shap': shap_values_positive.std(axis=0)
        }).sort_values('mean_abs_shap', ascending=False)

        logger.info("Global explanations computed")

        return {
            'importance_ranking': importance_df.to_dict('records'),
            'top_features': importance_df.head(10)['feature'].tolist(),
            'shap_values': shap_values_positive
        }

    def explain_instance(self, instance: Union[np.ndarray, pd.DataFrame, pd.Series],
                         include_plot: bool = True) -> Dict:
        """
        Explain a single prediction.

        Args:
            instance: Single data point to explain
            include_plot: Whether to generate waterfall plot

        Returns:
            Dictionary with instance-level explanation
        """
        # Ensure correct format
        if isinstance(instance, pd.Series):
            instance = instance.values.reshape(1, -1)
        elif isinstance(instance, pd.DataFrame):
            instance = instance.values

        if len(instance.shape) == 1:
            instance = instance.reshape(1, -1)

        # Get prediction
        prediction = self.model.predict(instance)[0]
        prediction_proba = self.model.predict_proba(instance)[0]

        # Get SHAP values for this instance
        instance_shap = self.explainer.shap_values(instance)

        if isinstance(instance_shap, list):
            instance_shap = instance_shap[1]  # Positive class

        instance_shap = instance_shap.flatten()

        # Create explanation
        feature_contributions = pd.DataFrame({
            'feature': self.feature_names,
            'value': instance.flatten(),
            'shap_value': instance_shap,
            'abs_shap': np.abs(instance_shap)
        }).sort_values('abs_shap', ascending=False)

        # Top contributing features
        top_positive = feature_contributions[feature_contributions['shap_value'] > 0].head(
            5)
        top_negative = feature_contributions[feature_contributions['shap_value'] < 0].head(
            5)

        return {
            'prediction': int(prediction),
            'probability': {
                'no_churn': float(prediction_proba[0]),
                'churn': float(prediction_proba[1])
            },
            'base_value': float(self.expected_value[1] if isinstance(self.expected_value, list)
                                else self.expected_value),
            'feature_contributions': feature_contributions.to_dict('records'),
            'top_churn_factors': top_positive[['feature', 'value', 'shap_value']].to_dict('records'),
            'top_retention_factors': top_negative[['feature', 'value', 'shap_value']].to_dict('records'),
            'explanation_text': self._generate_explanation_text(
                prediction, prediction_proba, top_positive, top_negative
            )
        }

    def _generate_explanation_text(self, prediction: int, proba: np.ndarray,
                                   top_positive: pd.DataFrame,
                                   top_negative: pd.DataFrame) -> str:
        """Generate human-readable explanation"""

        churn_status = "likely to churn" if prediction == 1 else "likely to stay"
        confidence = proba[prediction] * 100

        text = f"This customer is {churn_status} (confidence: {confidence:.1f}%).\n\n"

        if prediction == 1:
            text += "Key factors increasing churn risk:\n"
            for _, row in top_positive.head(3).iterrows():
                text += f"  • {row['feature']}: {row['value']:.2f} (impact: +{row['shap_value']:.3f})\n"

            text += "\nFactors helping retention:\n"
            for _, row in top_negative.head(3).iterrows():
                text += f"  • {row['feature']}: {row['value']:.2f} (impact: {row['shap_value']:.3f})\n"
        else:
            text += "Key factors supporting retention:\n"
            for _, row in top_negative.head(3).iterrows():
                text += f"  • {row['feature']}: {row['value']:.2f} (impact: {row['shap_value']:.3f})\n"

            text += "\nPotential churn risk factors to monitor:\n"
            for _, row in top_positive.head(3).iterrows():
                text += f"  • {row['feature']}: {row['value']:.2f} (impact: +{row['shap_value']:.3f})\n"

        return text

    def plot_global_importance(self, X: Union[np.ndarray, pd.DataFrame],
                               max_features: int = 15,
                               save_path: Optional[str] = None) -> plt.Figure:
        """
        Create global feature importance plot.

        Args:
            X: Data to explain
            max_features: Maximum features to show
            save_path: Optional path to save the plot

        Returns:
            matplotlib Figure
        """
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X, columns=self.feature_names)

        # Compute SHAP values if not already done
        if self.shap_values is None:
            self.explain_global(X)

        # Get positive class SHAP values
        shap_values = self.shap_values[1] if isinstance(
            self.shap_values, list) else self.shap_values

        # Create summary plot
        fig, axes = plt.subplots(1, 2, figsize=(16, 8))

        # Bar plot
        plt.sca(axes[0])
        shap.summary_plot(shap_values, X, plot_type="bar",
                          max_display=max_features, show=False)
        axes[0].set_title("Feature Importance (Mean |SHAP|)")

        # Beeswarm plot
        plt.sca(axes[1])
        shap.summary_plot(shap_values, X, max_display=max_features, show=False)
        axes[1].set_title("Feature Impact Distribution")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")

        return fig

    def plot_instance_explanation(self, instance: Union[np.ndarray, pd.DataFrame],
                                  save_path: Optional[str] = None) -> plt.Figure:
        """
        Create waterfall plot for single instance explanation.

        Args:
            instance: Single data point to explain
            save_path: Optional path to save the plot

        Returns:
            matplotlib Figure
        """
        if isinstance(instance, pd.Series):
            instance = instance.values.reshape(1, -1)
        elif isinstance(instance, pd.DataFrame):
            instance = instance.values

        if len(instance.shape) == 1:
            instance = instance.reshape(1, -1)

        instance_shap = self.explainer.shap_values(instance)

        if isinstance(instance_shap, list):
            instance_shap = instance_shap[1]

        # Create Explanation object for waterfall plot
        base_value = self.expected_value[1] if isinstance(
            self.expected_value, list) else self.expected_value

        exp = shap.Explanation(
            values=instance_shap.flatten(),
            base_values=base_value,
            data=instance.flatten(),
            feature_names=self.feature_names
        )

        fig = plt.figure(figsize=(12, 8))
        shap.waterfall_plot(exp, max_display=15, show=False)
        plt.title("Individual Prediction Explanation")

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")

        return fig

    def get_feature_interactions(self, X: Union[np.ndarray, pd.DataFrame],
                                 top_n: int = 5) -> Dict:
        """
        Analyze feature interactions.

        Args:
            X: Data to analyze
            top_n: Number of top interactions to return

        Returns:
            Dictionary with interaction analysis
        """
        if isinstance(X, np.ndarray):
            X = pd.DataFrame(X, columns=self.feature_names)

        # Compute SHAP interaction values (expensive!)
        logger.info(
            "Computing SHAP interaction values (this may take a while)...")

        if hasattr(self.explainer, 'shap_interaction_values'):
            interaction_values = self.explainer.shap_interaction_values(
                X.head(100))

            if isinstance(interaction_values, list):
                interaction_values = interaction_values[1]

            # Mean absolute interaction values
            mean_interactions = np.abs(interaction_values).mean(axis=0)

            # Get top interactions (excluding diagonal - main effects)
            np.fill_diagonal(mean_interactions, 0)

            # Find top interactions
            top_interactions = []
            for i in range(len(self.feature_names)):
                for j in range(i + 1, len(self.feature_names)):
                    top_interactions.append({
                        'feature_1': self.feature_names[i],
                        'feature_2': self.feature_names[j],
                        'interaction_strength': float(mean_interactions[i, j])
                    })

            top_interactions = sorted(top_interactions,
                                      key=lambda x: x['interaction_strength'],
                                      reverse=True)[:top_n]

            return {
                'top_interactions': top_interactions,
                'interaction_matrix': mean_interactions.tolist()
            }
        else:
            logger.warning(
                "Interaction values not available for this explainer type")
            return {'top_interactions': [], 'interaction_matrix': None}

    def save(self, path: str) -> None:
        """Save the explainer to disk"""
        joblib.dump({
            'model': self.model,
            'feature_names': self.feature_names,
            'model_type': self.model_type,
            'expected_value': self.expected_value
        }, path)
        logger.info(f"Explainer saved to {path}")

    @classmethod
    def load(cls, path: str,
             X_background: Optional[np.ndarray] = None) -> 'ModelExplainer':
        """Load a saved explainer"""
        data = joblib.load(path)
        explainer = cls(
            model=data['model'],
            feature_names=data['feature_names'],
            model_type=data['model_type']
        )
        explainer.expected_value = data['expected_value']

        if X_background is not None:
            explainer.fit(X_background)

        return explainer


def create_model_card(model, explainer: ModelExplainer,
                      metrics: Dict, output_path: str) -> str:
    """
    Generate a Model Card for documentation and compliance.

    Model Cards are standardized documentation for ML models,
    essential for responsible AI practices.
    """

    global_explanation = explainer.explain_global(
        explainer.shap_values) if explainer.shap_values is not None else {}

    model_card = f"""
# Model Card: Customer Churn Prediction

## Model Details
- **Model Type**: {type(model).__name__}
- **Version**: 2.0
- **Training Date**: {pd.Timestamp.now().strftime('%Y-%m-%d')}
- **Framework**: scikit-learn

## Intended Use
- **Primary Use**: Predict customer churn probability
- **Users**: Customer Success teams, Marketing
- **Out-of-scope**: Credit decisions, automated service termination

## Training Data
- **Source**: Customer behavior and demographic data
- **Size**: Specified at training time
- **Features**: {len(explainer.feature_names)} features after preprocessing

## Performance Metrics
- **Accuracy**: {metrics.get('accuracy', 'N/A')}
- **ROC-AUC**: {metrics.get('roc_auc', 'N/A')}
- **Precision**: {metrics.get('precision', 'N/A')}
- **Recall**: {metrics.get('recall', 'N/A')}
- **F1-Score**: {metrics.get('f1', 'N/A')}

## Feature Importance (Top 5)
{_format_feature_importance(global_explanation.get('importance_ranking', [])[:5])}

## Ethical Considerations
- Model does not use protected attributes (race, religion, etc.)
- Gender is used as a feature - monitor for disparate impact
- Regular fairness audits recommended

## Limitations
- Performance may degrade with distribution shift
- Requires retraining with new customer segments
- Not suitable for real-time high-frequency predictions

## Monitoring Recommendations
- Track prediction distribution weekly
- Alert on >10% drift in feature distributions
- Quarterly model performance review

---
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    with open(output_path, 'w') as f:
        f.write(model_card)

    logger.info(f"Model card saved to {output_path}")
    return model_card


def _format_feature_importance(importance_list: List[Dict]) -> str:
    """Format feature importance for model card"""
    if not importance_list:
        return "Not available"

    lines = []
    for i, item in enumerate(importance_list, 1):
        lines.append(
            f"{i}. **{item['feature']}**: {item['mean_abs_shap']:.4f}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Example usage
    print("Model Explainability Module")
    print("=" * 40)
    print("This module provides SHAP-based model explainability.")
    print("\nUsage:")
    print("  from model_explainability import ModelExplainer")
    print("  explainer = ModelExplainer(model, feature_names)")
    print("  explainer.fit(X_train)")
    print("  explanation = explainer.explain_instance(X_test[0])")
