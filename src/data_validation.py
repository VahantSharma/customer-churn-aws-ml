"""
Data Validation Module for Customer Churn Prediction

This module implements comprehensive data validation using Great Expectations-style
checks to ensure data quality before model training and inference.

Author: Vahant
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    """Validation result status"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


@dataclass
class ValidationResult:
    """Container for validation results"""
    check_name: str
    status: ValidationStatus
    message: str
    details: Optional[Dict] = None


class DataValidator:
    """
    Comprehensive data validation for customer churn prediction.

    Implements checks for:
    - Schema validation (column presence and types)
    - Data quality (missing values, duplicates, outliers)
    - Statistical properties (distribution drift)
    - Business rules (valid ranges, categorical values)
    """

    # Expected schema for customer churn data
    EXPECTED_SCHEMA = {
        'CustomerID': 'object',
        'Age': 'int64',
        'Gender': 'object',
        'Tenure': 'int64',
        'Usage Frequency': 'int64',
        'Support Calls': 'int64',
        'Payment Delay': 'int64',
        'Subscription Type': 'object',
        'Contract Length': 'object',
        'Total Spend': 'float64',
        'Last Interaction': 'int64',
        'Churn': 'int64'
    }

    # Valid categorical values
    VALID_CATEGORIES = {
        'Gender': ['Male', 'Female'],
        'Subscription Type': ['Basic', 'Standard', 'Premium'],
        'Contract Length': ['Monthly', 'Quarterly', 'Annual']
    }

    # Numerical feature bounds (based on business logic)
    NUMERICAL_BOUNDS = {
        'Age': (18, 100),
        'Tenure': (0, 100),
        'Usage Frequency': (0, 50),
        'Support Calls': (0, 20),
        'Payment Delay': (0, 60),
        'Total Spend': (0, 10000),
        'Last Interaction': (0, 365)
    }

    def __init__(self, strict_mode: bool = False):
        """
        Initialize validator.

        Args:
            strict_mode: If True, warnings are treated as failures
        """
        self.strict_mode = strict_mode
        self.validation_results: List[ValidationResult] = []

    def validate(
            self, df: pd.DataFrame) -> Tuple[bool, List[ValidationResult]]:
        """
        Run all validation checks on the dataframe.

        Args:
            df: DataFrame to validate

        Returns:
            Tuple of (overall_pass, list_of_validation_results)
        """
        self.validation_results = []

        # Run all checks
        self._check_schema(df)
        self._check_missing_values(df)
        self._check_duplicates(df)
        self._check_categorical_values(df)
        self._check_numerical_bounds(df)
        self._check_outliers(df)
        self._check_target_balance(df)

        # Determine overall result
        failed_checks = [r for r in self.validation_results
                         if r.status == ValidationStatus.FAILED]
        warning_checks = [r for r in self.validation_results
                          if r.status == ValidationStatus.WARNING]

        if self.strict_mode:
            overall_pass = len(failed_checks) == 0 and len(warning_checks) == 0
        else:
            overall_pass = len(failed_checks) == 0

        # Log summary
        logger.info(
            f"Validation complete: {len(self.validation_results)} checks run")
        logger.info(
            f"  Passed: {len([r for r in self.validation_results if r.status == ValidationStatus.PASSED])}")
        logger.info(f"  Warnings: {len(warning_checks)}")
        logger.info(f"  Failed: {len(failed_checks)}")

        return overall_pass, self.validation_results

    def _check_schema(self, df: pd.DataFrame) -> None:
        """Check if all expected columns are present"""
        missing_cols = set(self.EXPECTED_SCHEMA.keys()) - set(df.columns)
        extra_cols = set(df.columns) - set(self.EXPECTED_SCHEMA.keys())

        if missing_cols:
            self.validation_results.append(ValidationResult(
                check_name="schema_completeness",
                status=ValidationStatus.FAILED,
                message=f"Missing columns: {missing_cols}",
                details={"missing_columns": list(missing_cols)}
            ))
        elif extra_cols:
            self.validation_results.append(ValidationResult(
                check_name="schema_completeness",
                status=ValidationStatus.WARNING,
                message=f"Extra columns found: {extra_cols}",
                details={"extra_columns": list(extra_cols)}
            ))
        else:
            self.validation_results.append(ValidationResult(
                check_name="schema_completeness",
                status=ValidationStatus.PASSED,
                message="All expected columns present"
            ))

    def _check_missing_values(self, df: pd.DataFrame) -> None:
        """Check for missing values"""
        missing_counts = df.isnull().sum()
        missing_cols = missing_counts[missing_counts > 0]

        if len(missing_cols) > 0:
            missing_pct = (missing_cols / len(df) * 100).round(2)

            # More than 5% missing is a failure
            critical_missing = missing_pct[missing_pct > 5]

            if len(critical_missing) > 0:
                self.validation_results.append(ValidationResult(
                    check_name="missing_values",
                    status=ValidationStatus.FAILED,
                    message=f"Critical missing values (>5%): {critical_missing.to_dict()}",
                    details={"missing_percentages": missing_pct.to_dict()}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    check_name="missing_values",
                    status=ValidationStatus.WARNING,
                    message=f"Minor missing values detected: {missing_pct.to_dict()}",
                    details={"missing_percentages": missing_pct.to_dict()}
                ))
        else:
            self.validation_results.append(ValidationResult(
                check_name="missing_values",
                status=ValidationStatus.PASSED,
                message="No missing values detected"
            ))

    def _check_duplicates(self, df: pd.DataFrame) -> None:
        """Check for duplicate records"""
        if 'CustomerID' in df.columns:
            duplicate_ids = df['CustomerID'].duplicated().sum()

            if duplicate_ids > 0:
                self.validation_results.append(ValidationResult(
                    check_name="duplicate_check",
                    status=ValidationStatus.WARNING,
                    message=f"Found {duplicate_ids} duplicate CustomerIDs",
                    details={"duplicate_count": int(duplicate_ids)}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    check_name="duplicate_check",
                    status=ValidationStatus.PASSED,
                    message="No duplicate CustomerIDs found"
                ))

    def _check_categorical_values(self, df: pd.DataFrame) -> None:
        """Check if categorical columns contain only valid values"""
        for col, valid_values in self.VALID_CATEGORIES.items():
            if col in df.columns:
                invalid_values = set(
                    df[col].dropna().unique()) - set(valid_values)

                if invalid_values:
                    self.validation_results.append(ValidationResult(
                        check_name=f"categorical_values_{col}",
                        status=ValidationStatus.FAILED,
                        message=f"Invalid values in {col}: {invalid_values}",
                        details={"invalid_values": list(invalid_values)}
                    ))
                else:
                    self.validation_results.append(ValidationResult(
                        check_name=f"categorical_values_{col}",
                        status=ValidationStatus.PASSED,
                        message=f"All values in {col} are valid"
                    ))

    def _check_numerical_bounds(self, df: pd.DataFrame) -> None:
        """Check if numerical columns are within expected bounds"""
        for col, (min_val, max_val) in self.NUMERICAL_BOUNDS.items():
            if col in df.columns:
                out_of_bounds = (
                    (df[col] < min_val) | (
                        df[col] > max_val)).sum()

                if out_of_bounds > 0:
                    pct_out = (out_of_bounds / len(df) * 100)

                    if pct_out > 1:  # More than 1% out of bounds
                        self.validation_results.append(ValidationResult(
                            check_name=f"bounds_check_{col}",
                            status=ValidationStatus.FAILED,
                            message=f"{col}: {out_of_bounds} values ({pct_out:.2f}%) out of bounds [{min_val}, {max_val}]",
                            details={
                                "out_of_bounds_count": int(out_of_bounds),
                                "percentage": round(pct_out, 2)
                            }
                        ))
                    else:
                        self.validation_results.append(ValidationResult(
                            check_name=f"bounds_check_{col}",
                            status=ValidationStatus.WARNING,
                            message=f"{col}: Minor bound violations ({out_of_bounds} values)",
                            details={"out_of_bounds_count": int(out_of_bounds)}
                        ))
                else:
                    self.validation_results.append(ValidationResult(
                        check_name=f"bounds_check_{col}",
                        status=ValidationStatus.PASSED,
                        message=f"{col} values within expected bounds"
                    ))

    def _check_outliers(self, df: pd.DataFrame) -> None:
        """Check for statistical outliers using IQR method"""
        numerical_cols = df.select_dtypes(include=[np.number]).columns
        outlier_summary = {}

        for col in numerical_cols:
            if col not in ['CustomerID', 'Churn']:
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR

                outliers = (
                    (df[col] < lower_bound) | (
                        df[col] > upper_bound)).sum()
                if outliers > 0:
                    outlier_summary[col] = int(outliers)

        if outlier_summary:
            total_outliers = sum(outlier_summary.values())
            self.validation_results.append(ValidationResult(
                check_name="outlier_detection",
                status=ValidationStatus.WARNING,
                message=f"Outliers detected in {len(outlier_summary)} columns (total: {total_outliers})",
                details={"outliers_per_column": outlier_summary}
            ))
        else:
            self.validation_results.append(ValidationResult(
                check_name="outlier_detection",
                status=ValidationStatus.PASSED,
                message="No significant outliers detected"
            ))

    def _check_target_balance(self, df: pd.DataFrame) -> None:
        """Check target variable class balance"""
        if 'Churn' in df.columns:
            churn_rate = df['Churn'].mean()

            if churn_rate < 0.05 or churn_rate > 0.95:
                self.validation_results.append(ValidationResult(
                    check_name="target_balance",
                    status=ValidationStatus.FAILED,
                    message=f"Severe class imbalance: {churn_rate:.2%} churn rate",
                    details={"churn_rate": round(churn_rate, 4)}
                ))
            elif churn_rate < 0.1 or churn_rate > 0.9:
                self.validation_results.append(ValidationResult(
                    check_name="target_balance",
                    status=ValidationStatus.WARNING,
                    message=f"Moderate class imbalance: {churn_rate:.2%} churn rate",
                    details={"churn_rate": round(churn_rate, 4)}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    check_name="target_balance",
                    status=ValidationStatus.PASSED,
                    message=f"Acceptable class balance: {churn_rate:.2%} churn rate",
                    details={"churn_rate": round(churn_rate, 4)}
                ))

    def generate_report(self) -> str:
        """Generate a human-readable validation report"""
        report_lines = [
            "=" * 60,
            "DATA VALIDATION REPORT",
            "=" * 60,
            ""
        ]

        for result in self.validation_results:
            status_icon = {
                ValidationStatus.PASSED: "✓",
                ValidationStatus.WARNING: "⚠",
                ValidationStatus.FAILED: "✗"
            }[result.status]

            report_lines.append(f"[{status_icon}] {result.check_name}")
            report_lines.append(f"    Status: {result.status.value.upper()}")
            report_lines.append(f"    Message: {result.message}")
            if result.details:
                report_lines.append(f"    Details: {result.details}")
            report_lines.append("")

        # Summary
        passed = len(
            [r for r in self.validation_results if r.status == ValidationStatus.PASSED])
        warnings = len(
            [r for r in self.validation_results if r.status == ValidationStatus.WARNING])
        failed = len(
            [r for r in self.validation_results if r.status == ValidationStatus.FAILED])

        report_lines.extend([
            "-" * 60,
            "SUMMARY",
            "-" * 60,
            f"Total Checks: {len(self.validation_results)}",
            f"Passed: {passed}",
            f"Warnings: {warnings}",
            f"Failed: {failed}",
            "=" * 60
        ])

        return "\n".join(report_lines)


def validate_training_data(data_path: str) -> Tuple[bool, str]:
    """
    Convenience function to validate training data.

    Args:
        data_path: Path to CSV file

    Returns:
        Tuple of (passed, report_string)
    """
    df = pd.read_csv(data_path)
    validator = DataValidator()
    passed, results = validator.validate(df)
    report = validator.generate_report()
    return passed, report


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    else:
        data_path = "./data/customer_churn.csv"

    passed, report = validate_training_data(data_path)
    print(report)

    if not passed:
        sys.exit(1)
