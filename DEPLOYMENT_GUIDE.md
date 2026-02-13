# AWS SageMaker Deployment Guide

Complete guide for deploying the Customer Churn Prediction model to AWS SageMaker.

## Prerequisites

- AWS Account with credits
- AWS CLI installed and configured
- Python 3.9+
- IAM permissions for SageMaker, S3, and IAM

## Step 1: AWS CLI Configuration

### Install AWS CLI

Download from: https://aws.amazon.com/cli/

### Configure Credentials

```bash
aws configure
```

Enter your credentials:
- **AWS Access Key ID**: From AWS Console → IAM → Users → Security credentials
- **AWS Secret Access Key**: From AWS Console
- **Default region**: `us-east-1` (recommended)
- **Default output format**: `json`

### Verify Configuration

```bash
aws sts get-caller-identity
```

## Step 2: Create S3 Bucket

### Create Bucket

```bash
aws s3 mb s3://churn-prediction-YOUR-USERNAME --region us-east-1
```

### Upload Training Data

```bash
aws s3 cp data/customer_churn_processed.csv s3://churn-prediction-YOUR-USERNAME/data/processed/
```

### Verify Upload

```bash
aws s3 ls s3://churn-prediction-YOUR-USERNAME/data/processed/
```

## Step 3: Create SageMaker Execution Role

### Option A: AWS Console

1. Navigate to **IAM → Roles → Create Role**
2. Select **SageMaker** as trusted service
3. Attach policy: **AmazonSageMakerFullAccess**
4. Name the role: `SageMakerExecutionRole`
5. Copy the Role ARN

### Option B: AWS CLI

```bash
aws iam create-role \
    --role-name SageMakerExecutionRole \
    --assume-role-policy-document file://sagemaker-iam-policy.json

aws iam attach-role-policy \
    --role-name SageMakerExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
```

## Step 4: Train Model on SageMaker

### Python Script

```python
import sagemaker
from sagemaker.sklearn import SKLearn

# Initialize session
session = sagemaker.Session()
role = "arn:aws:iam::YOUR_ACCOUNT_ID:role/SageMakerExecutionRole"
bucket = "churn-prediction-YOUR-USERNAME"

# Create estimator
estimator = SKLearn(
    entry_point='training.py',
    source_dir='sagemaker',
    role=role,
    instance_type='ml.m5.large',
    framework_version='1.0-1',
    hyperparameters={
        'n-estimators': 100,
        'max-depth': 10
    }
)

# Start training (~5 minutes, ~$0.10)
estimator.fit({'train': f's3://{bucket}/data/processed/'})

print(f"Model artifact: {estimator.model_data}")
```

**Training Cost:** ~$0.10 for a 5-minute job

## Step 5: Deploy Endpoint

> **Warning:** Endpoints incur hourly charges. Delete when not in use.

### Deploy

```python
predictor = estimator.deploy(
    instance_type='ml.t2.medium',  # $0.056/hour
    initial_instance_count=1,
    endpoint_name='churn-prediction-endpoint'
)

print(f"Endpoint: {predictor.endpoint_name}")
```

### Test Endpoint

```python
import json

test_data = {
    "Age": 35,
    "Tenure": 24,
    "Usage Frequency": 15,
    "Support Calls": 2,
    "Payment Delay": 5,
    "Total Spend": 1500.50,
    "Last Interaction": 14,
    "Gender_Male": 1,
    "Subscription_Standard": 1,
    "Subscription_Premium": 0,
    "Contract_Quarterly": 0,
    "Contract_Annual": 1
}

result = predictor.predict(test_data)
print(f"Prediction: {result}")
```

## Step 6: Delete Endpoint

**Execute immediately after testing to stop charges.**

### Python

```python
import boto3

client = boto3.client('sagemaker')
client.delete_endpoint(EndpointName='churn-prediction-endpoint')
client.delete_endpoint_config(EndpointConfigName='churn-prediction-endpoint')
print("Endpoint deleted")
```

### AWS CLI

```bash
aws sagemaker delete-endpoint --endpoint-name churn-prediction-endpoint
```

## Cost Monitoring

### List Active Endpoints

```bash
aws sagemaker list-endpoints
```

### Delete All Endpoints (Emergency)

```bash
aws sagemaker list-endpoints --query 'Endpoints[*].EndpointName' --output text | \
    xargs -I {} aws sagemaker delete-endpoint --endpoint-name {}
```

### Check S3 Storage

```bash
aws s3 ls s3://YOUR-BUCKET --recursive --summarize
```

## Batch Transform (Cost-Effective Alternative)

For bulk predictions without maintaining an endpoint:

```python
from sagemaker.sklearn import SKLearnModel

model = SKLearnModel(
    model_data='s3://YOUR-BUCKET/model/model.tar.gz',
    role=role,
    entry_point='inference.py',
    source_dir='sagemaker'
)

transformer = model.transformer(
    instance_count=1,
    instance_type='ml.m5.large',
    strategy='MultiRecord'
)

transformer.transform(
    data='s3://YOUR-BUCKET/data/batch_input/',
    content_type='text/csv',
    split_type='Line'
)

transformer.wait()
```

**Advantage:** Pay only for processing time, no ongoing charges.

## Local Testing (Free)

Always test locally before deploying:

### Start API

```bash
uvicorn src.api:app --reload --port 8000
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Prediction
curl -X POST http://localhost:8000/predict \
    -H "Content-Type: application/json" \
    -d '{"Age":35,"Tenure":24,"Usage Frequency":15,"Support Calls":2,"Payment Delay":5,"Total Spend":1500.50,"Last Interaction":14,"Gender":"Male","Subscription Type":"Standard","Contract Length":"Annual"}'
```

## Cost Summary

| Action | Estimated Cost |
|--------|----------------|
| Training job (5 min) | $0.10 |
| Endpoint (1 hour) | $0.056 |
| Endpoint (24 hours) | $1.34 |
| Endpoint (1 month) | $40.32 |
| S3 storage (1 GB/month) | $0.023 |

## Troubleshooting

### Permission Denied
- Verify IAM role has `AmazonSageMakerFullAccess`
- Check S3 bucket permissions

### Endpoint Creation Failed
- Check CloudWatch logs: SageMaker → Training Jobs → Logs
- Verify training script has no errors

### Model Not Found
- Ensure S3 path to model artifact is correct
- Verify model.tar.gz contains model.joblib

## Next Steps

1. Set up CloudWatch alarms for endpoint monitoring
2. Implement A/B testing with multiple model variants
3. Configure auto-scaling for production workloads
4. Set up model registry for versioning
