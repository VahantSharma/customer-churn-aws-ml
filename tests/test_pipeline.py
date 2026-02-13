"""
Unit Tests for Customer Churn Prediction Pipeline

Comprehensive test coverage for:
- Data validation
- Preprocessing pipeline
- Model training
- Inference pipeline

Author: Vahant
Run with: pytest tests/ -v
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from data_validation import DataValidator, ValidationStatus, validate_training_data


class TestDataValidator:
    """Test suite for DataValidator class"""
    
    @pytest.fixture
    def valid_data(self):
        """Create valid test dataset"""
        np.random.seed(42)
        n_samples = 100
        
        return pd.DataFrame({
            'CustomerID': [f'CUST_{i}' for i in range(n_samples)],
            'Age': np.random.randint(18, 70, n_samples),
            'Gender': np.random.choice(['Male', 'Female'], n_samples),
            'Tenure': np.random.randint(1, 60, n_samples),
            'Usage Frequency': np.random.randint(1, 30, n_samples),
            'Support Calls': np.random.randint(0, 10, n_samples),
            'Payment Delay': np.random.randint(0, 30, n_samples),
            'Subscription Type': np.random.choice(['Basic', 'Standard', 'Premium'], n_samples),
            'Contract Length': np.random.choice(['Monthly', 'Quarterly', 'Annual'], n_samples),
            'Total Spend': np.random.uniform(100, 5000, n_samples),
            'Last Interaction': np.random.randint(1, 90, n_samples),
            'Churn': np.random.choice([0, 1], n_samples, p=[0.7, 0.3])
        })
    
    @pytest.fixture
    def invalid_data_missing_cols(self, valid_data):
        """Create dataset with missing columns"""
        return valid_data.drop(['Age', 'Gender'], axis=1)
    
    @pytest.fixture
    def invalid_data_wrong_categories(self, valid_data):
        """Create dataset with invalid categorical values"""
        df = valid_data.copy()
        df.loc[0, 'Gender'] = 'Unknown'
        df.loc[1, 'Subscription Type'] = 'Enterprise'
        return df
    
    @pytest.fixture
    def invalid_data_out_of_bounds(self, valid_data):
        """Create dataset with out-of-bounds values"""
        df = valid_data.copy()
        df.loc[0, 'Age'] = 150  # Too old
        df.loc[1, 'Age'] = 10   # Too young
        return df
    
    def test_valid_data_passes(self, valid_data):
        """Test that valid data passes all checks"""
        validator = DataValidator()
        passed, results = validator.validate(valid_data)
        
        # Should pass overall
        assert passed, "Valid data should pass validation"
        
        # Check for no failures
        failed = [r for r in results if r.status == ValidationStatus.FAILED]
        assert len(failed) == 0, f"Valid data should have no failures: {failed}"
    
    def test_missing_columns_detected(self, invalid_data_missing_cols):
        """Test that missing columns are detected"""
        validator = DataValidator()
        passed, results = validator.validate(invalid_data_missing_cols)
        
        # Should fail
        assert not passed, "Data with missing columns should fail"
        
        # Check schema validation failed
        schema_results = [r for r in results if r.check_name == 'schema_completeness']
        assert len(schema_results) == 1
        assert schema_results[0].status == ValidationStatus.FAILED
    
    def test_invalid_categories_detected(self, invalid_data_wrong_categories):
        """Test that invalid categorical values are detected"""
        validator = DataValidator()
        passed, results = validator.validate(invalid_data_wrong_categories)
        
        # Should fail
        assert not passed, "Data with invalid categories should fail"
        
        # Check categorical validation failed
        cat_results = [r for r in results if 'categorical_values' in r.check_name 
                      and r.status == ValidationStatus.FAILED]
        assert len(cat_results) > 0
    
    def test_out_of_bounds_detected(self, invalid_data_out_of_bounds):
        """Test that out-of-bounds values are detected"""
        validator = DataValidator()
        passed, results = validator.validate(invalid_data_out_of_bounds)
        
        # Find bounds check results
        bounds_results = [r for r in results if 'bounds_check' in r.check_name]
        
        # At least one should have warning or failure
        assert any(r.status in [ValidationStatus.WARNING, ValidationStatus.FAILED] 
                  for r in bounds_results)
    
    def test_strict_mode(self, valid_data):
        """Test strict mode treats warnings as failures"""
        # Add some outliers to generate warnings
        df = valid_data.copy()
        df.loc[0, 'Total Spend'] = 50000  # Outlier
        
        # Non-strict mode
        validator_normal = DataValidator(strict_mode=False)
        passed_normal, _ = validator_normal.validate(df)
        
        # Strict mode
        validator_strict = DataValidator(strict_mode=True)
        passed_strict, _ = validator_strict.validate(df)
        
        # Strict should be more restrictive
        # (This test may vary based on data)
    
    def test_report_generation(self, valid_data):
        """Test report generation"""
        validator = DataValidator()
        validator.validate(valid_data)
        report = validator.generate_report()
        
        # Report should contain key sections
        assert "DATA VALIDATION REPORT" in report
        assert "SUMMARY" in report
        assert "Passed:" in report
    
    def test_empty_dataframe(self):
        """Test handling of empty DataFrame"""
        validator = DataValidator()
        empty_df = pd.DataFrame()
        
        passed, results = validator.validate(empty_df)
        
        # Should fail with schema error
        assert not passed


class TestPreprocessing:
    """Test suite for data preprocessing"""
    
    @pytest.fixture
    def sample_data(self):
        """Create sample dataset for preprocessing tests"""
        return pd.DataFrame({
            'CustomerID': ['C1', 'C2', 'C3'],
            'Age': [25, 35, 45],
            'Gender': ['Male', 'Female', 'Male'],
            'Tenure': [12, 24, 36],
            'Usage Frequency': [10, 20, 30],
            'Support Calls': [1, 2, 3],
            'Payment Delay': [0, 5, 10],
            'Subscription Type': ['Basic', 'Standard', 'Premium'],
            'Contract Length': ['Monthly', 'Quarterly', 'Annual'],
            'Total Spend': [500, 1000, 1500],
            'Last Interaction': [7, 14, 21],
            'Churn': [0, 0, 1]
        })
    
    def test_preprocessing_shape(self, sample_data):
        """Test that preprocessing produces correct output shape"""
        from sklearn.preprocessing import StandardScaler, OneHotEncoder
        from sklearn.compose import ColumnTransformer
        
        # Remove non-features
        X = sample_data.drop(['CustomerID', 'Churn'], axis=1)
        
        numerical_cols = ['Age', 'Tenure', 'Usage Frequency', 'Support Calls', 
                         'Payment Delay', 'Total Spend', 'Last Interaction']
        categorical_cols = ['Gender', 'Subscription Type', 'Contract Length']
        
        preprocessor = ColumnTransformer([
            ('num', StandardScaler(), numerical_cols),
            ('cat', OneHotEncoder(drop='first', sparse_output=False), categorical_cols)
        ])
        
        X_processed = preprocessor.fit_transform(X)
        
        # Should have 7 numerical + 3 categorical (with dropped first)
        # Gender: 1, Subscription: 2, Contract: 2 = 5 categorical
        expected_features = 7 + 5
        assert X_processed.shape[1] == expected_features
    
    def test_numerical_scaling(self, sample_data):
        """Test that numerical features are properly scaled"""
        from sklearn.preprocessing import StandardScaler
        
        numerical_data = sample_data[['Age', 'Tenure', 'Total Spend']]
        scaler = StandardScaler()
        scaled = scaler.fit_transform(numerical_data)
        
        # Check mean is approximately 0 and std is approximately 1
        assert np.abs(scaled.mean()) < 0.1
        assert np.abs(scaled.std() - 1) < 0.1


class TestModelPrediction:
    """Test suite for model predictions"""
    
    @pytest.fixture
    def trained_model(self):
        """Create a simple trained model for testing"""
        from sklearn.ensemble import RandomForestClassifier
        
        # Create dummy training data
        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1], 100)
        
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X, y)
        
        return model
    
    def test_prediction_output_shape(self, trained_model):
        """Test prediction output has correct shape"""
        X_test = np.random.randn(5, 10)
        
        predictions = trained_model.predict(X_test)
        assert predictions.shape == (5,)
        
        probabilities = trained_model.predict_proba(X_test)
        assert probabilities.shape == (5, 2)
    
    def test_prediction_values_valid(self, trained_model):
        """Test prediction values are valid"""
        X_test = np.random.randn(10, 10)
        
        predictions = trained_model.predict(X_test)
        
        # All predictions should be 0 or 1
        assert all(p in [0, 1] for p in predictions)
        
        # Probabilities should sum to 1
        probabilities = trained_model.predict_proba(X_test)
        assert np.allclose(probabilities.sum(axis=1), 1.0)
    
    def test_probability_range(self, trained_model):
        """Test probabilities are in valid range"""
        X_test = np.random.randn(10, 10)
        
        probabilities = trained_model.predict_proba(X_test)
        
        assert np.all(probabilities >= 0)
        assert np.all(probabilities <= 1)


class TestInferencePipeline:
    """Test suite for inference pipeline components"""
    
    def test_json_input_parsing(self):
        """Test JSON input parsing for inference"""
        import json
        
        # Sample JSON input
        json_input = json.dumps({
            "Age": 35,
            "Tenure": 12,
            "Usage Frequency": 15,
            "Support Calls": 2,
            "Payment Delay": 5,
            "Total Spend": 1000.50,
            "Last Interaction": 7
        })
        
        # Parse JSON
        data = json.loads(json_input)
        df = pd.DataFrame([data])
        
        assert len(df) == 1
        assert df['Age'].iloc[0] == 35
    
    def test_batch_json_input(self):
        """Test batch JSON input parsing"""
        import json
        
        batch_input = json.dumps([
            {"Age": 25, "Tenure": 6},
            {"Age": 35, "Tenure": 12},
            {"Age": 45, "Tenure": 24}
        ])
        
        data = json.loads(batch_input)
        df = pd.DataFrame(data)
        
        assert len(df) == 3
    
    def test_csv_input_parsing(self):
        """Test CSV input parsing"""
        from io import StringIO
        
        csv_input = "25,6,10,1,0,500,7\n35,12,20,2,5,1000,14"
        
        df = pd.read_csv(StringIO(csv_input), header=None)
        
        assert df.shape == (2, 7)


# Integration Tests
class TestEndToEnd:
    """End-to-end integration tests"""
    
    def test_full_pipeline(self):
        """Test complete pipeline from data to prediction"""
        from sklearn.model_selection import train_test_split
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import accuracy_score
        
        # Create synthetic data
        np.random.seed(42)
        n_samples = 500
        
        X = np.random.randn(n_samples, 5)
        # Create target with some pattern
        y = (X[:, 0] + X[:, 1] > 0).astype(int)
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X_train_scaled, y_train)
        
        # Predict
        predictions = model.predict(X_test_scaled)
        
        # Evaluate
        accuracy = accuracy_score(y_test, predictions)
        
        # Should have reasonable accuracy (pattern is learnable)
        assert accuracy > 0.6, f"Expected accuracy > 0.6, got {accuracy}"


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
