@echo off
REM =============================================================================
REM infra.bat — Windows wrapper for infra.sh
REM =============================================================================
REM Usage:
REM   infra up        Create all AWS resources + restore data from backup
REM   infra down      Backup data + destroy all AWS resources (cost = $0)
REM   infra status    Show running resources and estimated costs
REM =============================================================================

setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0"
set "TF_DIR=%PROJECT_ROOT%terraform\environments\dev"
set "BACKUP_DIR=%PROJECT_ROOT%backups"
set "AWS_ACCOUNT=231284356634"
set "REGION=us-east-1"
set "DATA_BUCKET=customer-churn-data-dev-%AWS_ACCOUNT%"
set "MODELS_BUCKET=customer-churn-models-dev-%AWS_ACCOUNT%"
set "ECR_REPO=customer-churn-dev"

if "%~1"=="" goto :usage
if "%~1"=="up" goto :up
if "%~1"=="down" goto :down
if "%~1"=="status" goto :status
goto :usage

REM =============================================================================
REM STATUS
REM =============================================================================
:status
echo.
echo ========================================
echo   AWS Resource Status
echo ========================================
echo.

echo [INFO] SageMaker Notebooks:
aws sagemaker list-notebook-instances --query "NotebookInstances[?contains(NotebookInstanceName,'churn')].[NotebookInstanceName,NotebookInstanceStatus,InstanceType]" --output table 2>nul
echo.

echo [INFO] SageMaker Endpoints:
aws sagemaker list-endpoints --query "Endpoints[?contains(EndpointName,'churn')].[EndpointName,EndpointStatus]" --output table 2>nul || echo   (none running)
echo.

echo [INFO] NAT Gateways (~$32/month each):
aws ec2 describe-nat-gateways --query "NatGateways[?State=='available'].[NatGatewayId,State]" --output table 2>nul
echo.

echo [INFO] S3 Buckets:
aws s3 ls 2>nul | findstr "churn"
echo.

echo [INFO] ECR Images:
aws ecr list-images --repository-name %ECR_REPO% --query "imageIds[*].imageTag" --output text 2>nul || echo   (none)
echo.

echo [INFO] KMS Keys:
aws kms list-aliases --query "Aliases[?contains(AliasName,'churn')].[AliasName]" --output text 2>nul
echo.

echo ========================================
echo   Estimated Monthly Cost
echo ========================================
echo   NAT Gateway:         ~$32/month
echo   SageMaker Notebook:  ~$3.50/day (when InService)
echo   KMS Keys (4):        ~$4/month
echo   S3 + ECR + Logs:     ~$1/month
echo   ---------------------------------
echo   TOTAL (notebook on): ~$40-50/month
echo   TOTAL (all down):    $0/month
echo.
goto :eof

REM =============================================================================
REM DOWN — Backup + Destroy
REM =============================================================================
:down
echo.
echo ========================================
echo   INFRASTRUCTURE TEARDOWN
echo ========================================
echo.
echo This will:
echo   1. Backup S3 data and model artifacts to .\backups\
echo   2. Destroy ALL dev environment resources
echo   3. Keep the Terraform backend (state bucket + lock table)
echo.
set /p CONFIRM="Continue? (yes/no): "
if not "%CONFIRM%"=="yes" (
    echo [WARN] Aborted.
    goto :eof
)

REM Backup S3 data
echo [INFO] Backing up S3 data...
if not exist "%BACKUP_DIR%\data" mkdir "%BACKUP_DIR%\data"
if not exist "%BACKUP_DIR%\models" mkdir "%BACKUP_DIR%\models"

echo [INFO]   Syncing s3://%DATA_BUCKET%/ to backups\data\
aws s3 sync "s3://%DATA_BUCKET%/" "%BACKUP_DIR%\data\" --quiet 2>nul
echo [INFO]   Syncing s3://%MODELS_BUCKET%/ to backups\models\
aws s3 sync "s3://%MODELS_BUCKET%/" "%BACKUP_DIR%\models\" --quiet 2>nul
echo [INFO]   Backup complete.

REM Stop SageMaker notebook if running
echo [INFO] Checking SageMaker notebook...
for /f "tokens=*" %%i in ('aws sagemaker describe-notebook-instance --notebook-instance-name customer-churn-dev-notebook --query NotebookInstanceStatus --output text 2^>nul') do set NB_STATUS=%%i
if "%NB_STATUS%"=="InService" (
    echo [INFO]   Stopping notebook...
    aws sagemaker stop-notebook-instance --notebook-instance-name customer-churn-dev-notebook
    echo [INFO]   Waiting for notebook to stop (~1-2 min^)...
    aws sagemaker wait notebook-instance-stopped --notebook-instance-name customer-churn-dev-notebook 2>nul
    echo [INFO]   Notebook stopped.
)

REM Terraform destroy
echo [INFO] Running terraform destroy...
pushd "%TF_DIR%"
terraform init -input=false
terraform destroy -auto-approve
popd

echo.
echo ========================================
echo   TEARDOWN COMPLETE
echo ========================================
echo.
echo   All dev resources destroyed.
echo   Data backed up to: %BACKUP_DIR%\
echo   Terraform state preserved in S3.
echo.
echo   To bring everything back:
echo     infra up
echo.
echo   Monthly cost is now: $0
echo.
goto :eof

REM =============================================================================
REM UP — Create + Restore
REM =============================================================================
:up
echo.
echo ========================================
echo   INFRASTRUCTURE SETUP
echo ========================================
echo.

REM Terraform apply
echo [INFO] Running terraform apply...
pushd "%TF_DIR%"
terraform init -input=false
terraform apply -auto-approve
popd

echo.
echo [INFO] Infrastructure created. Restoring data...

REM Restore S3 data
if exist "%BACKUP_DIR%\data\customer_churn.csv" (
    echo [INFO]   Restoring data to s3://%DATA_BUCKET%/
    aws s3 sync "%BACKUP_DIR%\data\" "s3://%DATA_BUCKET%/" --quiet
    echo [INFO]   Data restored.
) else (
    echo [WARN]   No backup found. Uploading from local data\ folder...
    if exist "%PROJECT_ROOT%data\customer_churn.csv" (
        aws s3 cp "%PROJECT_ROOT%data\customer_churn.csv" "s3://%DATA_BUCKET%/"
        aws s3 cp "%PROJECT_ROOT%data\customer_churn_processed.csv" "s3://%DATA_BUCKET%/" 2>nul
    )
)

if exist "%BACKUP_DIR%\models\" (
    echo [INFO]   Restoring models to s3://%MODELS_BUCKET%/
    aws s3 sync "%BACKUP_DIR%\models\" "s3://%MODELS_BUCKET%/" --quiet
    echo [INFO]   Models restored.
) else (
    echo [WARN]   No models backup found. Uploading from local model\ folder...
    if exist "%PROJECT_ROOT%model\" (
        aws s3 sync "%PROJECT_ROOT%model\" "s3://%MODELS_BUCKET%/v2/" --quiet
    )
)

REM Check ECR
echo [INFO] Checking ECR...
for /f "tokens=*" %%i in ('aws ecr list-images --repository-name %ECR_REPO% --query "imageIds[*].imageTag" --output text 2^>nul') do set ECR_IMAGES=%%i
if "%ECR_IMAGES%"=="" (
    echo [INFO]   ECR is empty. Build and push Docker image with:
    echo            docker build -t churn-prediction:latest .
    echo            aws ecr get-login-password --region %REGION% ^| docker login --username AWS --password-stdin %AWS_ACCOUNT%.dkr.ecr.%REGION%.amazonaws.com
    echo            docker tag churn-prediction:latest %AWS_ACCOUNT%.dkr.ecr.%REGION%.amazonaws.com/%ECR_REPO%:latest
    echo            docker push %AWS_ACCOUNT%.dkr.ecr.%REGION%.amazonaws.com/%ECR_REPO%:latest
) else (
    echo [INFO]   ECR has images: %ECR_IMAGES%
)

echo.
echo ========================================
echo   INFRASTRUCTURE READY
echo ========================================
echo.
echo   All dev resources are up.
echo   S3 data and model artifacts restored.
echo.
echo   To verify:  infra status
echo   To tear down:  infra down
echo.
goto :eof

REM =============================================================================
REM USAGE
REM =============================================================================
:usage
echo.
echo Usage: infra ^<command^>
echo.
echo Commands:
echo   up       Create all AWS resources + restore data from backup
echo   down     Backup data + destroy all AWS resources (cost = $0)
echo   status   Show running resources and estimated costs
echo.
goto :eof
