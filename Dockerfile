# Dockerfile for Customer Churn Prediction API
# 
# Multi-stage build for optimized production image
# Author: Vahant

# Stage 1: Builder
FROM python:3.9-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
# NOTE: We use requirements-docker.txt (not requirements.txt) to avoid
# pulling PyTorch + 4.7GB of NVIDIA CUDA libraries that the API doesn't need.
COPY requirements-docker.txt .
COPY requirements-api.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements-docker.txt
RUN pip install --no-cache-dir --user -r requirements-api.txt

# Stage 2: Production
FROM python:3.9-slim

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy installed packages from builder
# --chown ensures appuser owns the files (without it, they're owned by root
# and Python may fail to read .pth files or execute scripts)
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH
# PYTHONPATH directly tells Python where to find installed packages.
# PYTHONUSERBASE alone is NOT sufficient — it only tells pip where to install,
# but Python's site module may not add the directory to sys.path in Docker.
ENV PYTHONPATH=/home/appuser/.local/lib/python3.9/site-packages
ENV PYTHONUSERBASE=/home/appuser/.local

# Copy application code
COPY src/ ./src/
COPY model/ ./model/
COPY data/ ./data/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MODEL_PATH=/app/model/best_model_xgboost.joblib
ENV PREPROCESSOR_PATH=/app/model/preprocessor.joblib

# Change ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run the application
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
