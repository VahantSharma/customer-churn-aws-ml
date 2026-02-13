"""
Setup script for AWS SageMaker Customer Churn Prediction project.
"""

from setuptools import setup, find_packages

# Read the README file
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements from requirements.txt
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="customer-churn-prediction",
    version="2.0.0",
    author="Vahant",
    author_email="vahant@example.com",
    description="Production-grade customer churn prediction with AWS SageMaker and model explainability",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Vahant/customer-churn-prediction",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Data Scientists",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "black>=21.0.0",
            "flake8>=3.9.0",
            "isort>=5.0.0",
            "mypy>=0.800",
        ],
        "notebook": [
            "jupyter>=1.0.0",
            "ipykernel>=6.0.0",
            "matplotlib>=3.4.0",
            "seaborn>=0.11.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "train-churn-model=training:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yaml", "*.yml"],
    },
    project_urls={
        "Bug Reports": "https://github.com/yourusername/aws-sagemaker-churn-prediction/issues",
        "Source": "https://github.com/yourusername/aws-sagemaker-churn-prediction",
        "Documentation": "https://github.com/yourusername/aws-sagemaker-churn-prediction/blob/main/README.md",
    },
)
