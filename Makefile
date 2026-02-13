# Makefile for AWS SageMaker Customer Churn Prediction project

.PHONY: help install install-dev clean test format lint notebook setup-aws deploy-model delete-endpoint

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install project dependencies"
	@echo "  install-dev  - Install development dependencies"
	@echo "  clean        - Clean temporary files and cache"
	@echo "  test         - Run tests"
	@echo "  format       - Format code with black"
	@echo "  lint         - Run linting with flake8"
	@echo "  notebook     - Start Jupyter notebook"
	@echo "  setup-aws    - Configure AWS credentials"
	@echo "  deploy-model - Deploy model to SageMaker (requires trained model)"
	@echo "  delete-endpoint - Delete SageMaker endpoint"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -e ".[dev]"

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# Testing
test:
	python -m pytest tests/ -v

# Code formatting and linting
format:
	black . --line-length 88
	isort . --profile black

lint:
	flake8 . --max-line-length 88 --extend-ignore E203,W503
	mypy . --ignore-missing-imports

# Development
notebook:
	jupyter notebook

# AWS specific commands
setup-aws:
	@echo "Setting up AWS credentials..."
	@echo "Please run: aws configure"
	@echo "Or set the following environment variables:"
	@echo "  AWS_ACCESS_KEY_ID"
	@echo "  AWS_SECRET_ACCESS_KEY"
	@echo "  AWS_DEFAULT_REGION"

# SageMaker specific (these would need to be customized based on your setup)
deploy-model:
	@echo "To deploy the model, run the notebook: sagemaker_training_deployment.ipynb"
	@echo "Or use the SageMaker SDK programmatically"

delete-endpoint:
	@echo "To delete the endpoint, run the cleanup section in the notebook"
	@echo "Or use: aws sagemaker delete-endpoint --endpoint-name customer-churn-endpoint"

# Package building
build:
	python setup.py sdist bdist_wheel

# Documentation
docs:
	@echo "Documentation is available in README.md"
	@echo "For API documentation, see the docstrings in the code"

# Environment setup
env-create:
	python -m venv venv
	@echo "Virtual environment created. Activate with:"
	@echo "  source venv/bin/activate  (Linux/Mac)"
	@echo "  venv\\Scripts\\activate     (Windows)"

env-activate:
	@echo "To activate the virtual environment, run:"
	@echo "  source venv/bin/activate  (Linux/Mac)"
	@echo "  venv\\Scripts\\activate     (Windows)"

# Check project structure
check-structure:
	@echo "Project structure:"
	@find . -type f -name "*.py" -o -name "*.ipynb" -o -name "*.md" -o -name "*.txt" | head -20
