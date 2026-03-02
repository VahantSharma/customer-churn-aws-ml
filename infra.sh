#!/usr/bin/env bash
# =============================================================================
# infra.sh — Destroy / Recreate AWS Infrastructure with Data Backup
# =============================================================================
# Usage:
#   ./infra.sh up        Restore data from local backup → terraform apply
#   ./infra.sh down      Backup S3 data locally → terraform destroy
#   ./infra.sh status    Show what's running and estimated cost
#
# The Terraform BACKEND (state bucket + DynamoDB lock) is NEVER destroyed.
# Only the dev environment resources are cycled.
#
# Data is backed up to ./backups/ before destroy and restored after apply.
# =============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
TF_DIR="$PROJECT_ROOT/terraform/environments/dev"
BACKUP_DIR="$PROJECT_ROOT/backups"
AWS_ACCOUNT="231284356634"
REGION="us-east-1"

# S3 buckets managed by Terraform
DATA_BUCKET="customer-churn-data-dev-${AWS_ACCOUNT}"
MODELS_BUCKET="customer-churn-models-dev-${AWS_ACCOUNT}"
ECR_REPO="customer-churn-dev"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# =============================================================================
# STATUS — Show what's running
# =============================================================================
cmd_status() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  AWS Resource Status${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""

    # Check SageMaker notebook
    log "SageMaker Notebooks:"
    aws sagemaker list-notebook-instances \
        --query "NotebookInstances[?contains(NotebookInstanceName,'churn')].[NotebookInstanceName,NotebookInstanceStatus,InstanceType]" \
        --output table 2>/dev/null || echo "  (none found)"
    echo ""

    # Check SageMaker endpoints
    log "SageMaker Endpoints:"
    local endpoints
    endpoints=$(aws sagemaker list-endpoints \
        --query "Endpoints[?contains(EndpointName,'churn')].[EndpointName,EndpointStatus]" \
        --output text 2>/dev/null)
    if [ -z "$endpoints" ]; then
        echo "  (none running — good, no cost)"
    else
        echo "$endpoints"
    fi
    echo ""

    # Check NAT Gateways
    log "NAT Gateways (cost: ~\$32/month each):"
    aws ec2 describe-nat-gateways \
        --query "NatGateways[?State=='available'].[NatGatewayId,State,SubnetId]" \
        --output table 2>/dev/null || echo "  (none)"
    echo ""

    # Check S3 buckets
    log "S3 Buckets:"
    aws s3 ls 2>/dev/null | grep "churn" || echo "  (none)"
    echo ""

    # Check ECR
    log "ECR Images:"
    aws ecr list-images --repository-name "$ECR_REPO" \
        --query "imageIds[*].imageTag" --output text 2>/dev/null || echo "  (none)"
    echo ""

    # Check KMS keys
    log "KMS Keys:"
    aws kms list-aliases \
        --query "Aliases[?contains(AliasName,'churn')].[AliasName]" \
        --output text 2>/dev/null || echo "  (none)"
    echo ""

    # Estimated monthly cost
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  Estimated Monthly Cost (if all up)${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo "  NAT Gateway:         ~\$32/month"
    echo "  SageMaker Notebook:  ~\$3.50/day (when InService)"
    echo "  KMS Keys (4):        ~\$4/month"
    echo "  S3 Storage:          <\$1/month"
    echo "  ECR Storage:         <\$1/month"
    echo "  CloudWatch Logs:     <\$1/month"
    echo "  ─────────────────────────────────"
    echo "  TOTAL (notebook on): ~\$40-50/month"
    echo "  TOTAL (all down):    \$0/month"
    echo ""
}

# =============================================================================
# DOWN — Backup data + Destroy infrastructure
# =============================================================================
cmd_down() {
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}  INFRASTRUCTURE TEARDOWN${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""
    echo "This will:"
    echo "  1. Backup S3 data and model artifacts to ./backups/"
    echo "  2. Destroy ALL dev environment resources"
    echo "  3. Keep the Terraform backend (state bucket + lock table)"
    echo ""
    read -p "Continue? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        warn "Aborted."
        exit 0
    fi

    # ---- Step 1: Backup S3 data locally ----
    log "Backing up S3 data to $BACKUP_DIR ..."
    mkdir -p "$BACKUP_DIR/data" "$BACKUP_DIR/models"

    if aws s3 ls "s3://$DATA_BUCKET/" &>/dev/null; then
        log "  Syncing s3://$DATA_BUCKET/ → backups/data/"
        if ! aws s3 sync "s3://$DATA_BUCKET/" "$BACKUP_DIR/data/"; then
            error "  FAILED to backup data bucket! Aborting to prevent data loss."
            error "  Fix the issue above and re-run: ./infra.sh down"
            exit 1
        fi
        local data_size
        data_size=$(du -sh "$BACKUP_DIR/data" 2>/dev/null | cut -f1)
        if [ -z "$(ls -A "$BACKUP_DIR/data" 2>/dev/null)" ]; then
            warn "  Data backup folder is EMPTY despite bucket existing."
            read -p "  Continue anyway? (yes/no): " cont
            [ "$cont" != "yes" ] && exit 1
        else
            log "  Data backup complete ($data_size)"
        fi
    else
        warn "  Data bucket not found or empty — skipping"
    fi

    if aws s3 ls "s3://$MODELS_BUCKET/" &>/dev/null; then
        log "  Syncing s3://$MODELS_BUCKET/ → backups/models/"
        if ! aws s3 sync "s3://$MODELS_BUCKET/" "$BACKUP_DIR/models/"; then
            error "  FAILED to backup models bucket! Aborting to prevent data loss."
            error "  Fix the issue above and re-run: ./infra.sh down"
            exit 1
        fi
        local models_size
        models_size=$(du -sh "$BACKUP_DIR/models" 2>/dev/null | cut -f1)
        if [ -z "$(ls -A "$BACKUP_DIR/models" 2>/dev/null)" ]; then
            warn "  Models backup folder is EMPTY despite bucket existing."
            read -p "  Continue anyway? (yes/no): " cont
            [ "$cont" != "yes" ] && exit 1
        else
            log "  Models backup complete ($models_size)"
        fi
    else
        warn "  Models bucket not found or empty — skipping"
    fi

    # ---- Step 2: Stop SageMaker notebook (if running) ----
    local nb_status
    nb_status=$(aws sagemaker describe-notebook-instance \
        --notebook-instance-name "customer-churn-dev-notebook" \
        --query "NotebookInstanceStatus" --output text 2>/dev/null || echo "NotFound")

    if [ "$nb_status" = "InService" ]; then
        log "Stopping SageMaker notebook before destroy..."
        aws sagemaker stop-notebook-instance \
            --notebook-instance-name "customer-churn-dev-notebook"
        log "  Waiting for notebook to stop (this takes ~1-2 min)..."
        aws sagemaker wait notebook-instance-stopped \
            --notebook-instance-name "customer-churn-dev-notebook" 2>/dev/null || true
        log "  Notebook stopped."
    fi

    # ---- Step 3: Terraform destroy ----
    log "Running terraform destroy on dev environment..."
    cd "$TF_DIR"
    terraform init -input=false
    terraform destroy -auto-approve

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  TEARDOWN COMPLETE${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "  All dev resources destroyed."
    echo "  Data backed up to: $BACKUP_DIR/"
    echo "  Terraform state preserved in S3."
    echo ""
    echo "  To bring everything back:"
    echo "    ./infra.sh up"
    echo ""
    echo "  Monthly cost is now: \$0"
    echo ""
}

# =============================================================================
# UP — Create infrastructure + Restore data
# =============================================================================
cmd_up() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  INFRASTRUCTURE SETUP${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    # ---- Step 1: Terraform apply ----
    log "Running terraform apply on dev environment..."
    cd "$TF_DIR"
    terraform init -input=false
    terraform apply -auto-approve

    echo ""
    log "Infrastructure created. Restoring data..."

    # ---- Step 2: Restore S3 data from backup ----
    if [ -d "$BACKUP_DIR/data" ] && [ "$(ls -A "$BACKUP_DIR/data" 2>/dev/null)" ]; then
        log "  Restoring data → s3://$DATA_BUCKET/"
        aws s3 sync "$BACKUP_DIR/data/" "s3://$DATA_BUCKET/" --quiet
        log "  Data restored."
    else
        warn "  No data backup found — uploading from local data/ folder..."
        if [ -f "$PROJECT_ROOT/data/customer_churn.csv" ]; then
            aws s3 cp "$PROJECT_ROOT/data/customer_churn.csv" "s3://$DATA_BUCKET/"
            aws s3 cp "$PROJECT_ROOT/data/customer_churn_processed.csv" "s3://$DATA_BUCKET/" 2>/dev/null || true
        fi
    fi

    if [ -d "$BACKUP_DIR/models" ] && [ "$(ls -A "$BACKUP_DIR/models" 2>/dev/null)" ]; then
        log "  Restoring models → s3://$MODELS_BUCKET/"
        aws s3 sync "$BACKUP_DIR/models/" "s3://$MODELS_BUCKET/" --quiet
        log "  Models restored."
    else
        warn "  No models backup found — uploading from local model/ folder..."
        if [ -d "$PROJECT_ROOT/model" ]; then
            aws s3 sync "$PROJECT_ROOT/model/" "s3://$MODELS_BUCKET/v2/" --quiet
        fi
    fi

    # ---- Step 3: Push Docker image to ECR ----
    log "Checking if Docker image needs to be pushed to ECR..."
    local ecr_images
    ecr_images=$(aws ecr list-images --repository-name "$ECR_REPO" \
        --query "imageIds[*].imageTag" --output text 2>/dev/null || echo "")

    if [ -z "$ecr_images" ]; then
        log "  ECR is empty. Building and pushing Docker image..."
        cd "$PROJECT_ROOT"

        # Build
        docker build -t churn-prediction:latest .

        # Auth + tag + push
        aws ecr get-login-password --region "$REGION" | \
            docker login --username AWS --password-stdin \
            "${AWS_ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

        docker tag churn-prediction:latest \
            "${AWS_ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest"
        docker push \
            "${AWS_ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest"

        log "  Docker image pushed to ECR."
    else
        log "  ECR already has images: $ecr_images — skipping push."
    fi

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  INFRASTRUCTURE READY${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "  All dev resources are up."
    echo "  S3 data and model artifacts restored."
    echo "  ECR images available."
    echo ""
    echo "  To start the API locally:"
    echo "    uvicorn src.api:app --reload --port 8000"
    echo ""
    echo "  To verify AWS resources:"
    echo "    ./infra.sh status"
    echo ""
    echo "  To tear down and save money:"
    echo "    ./infra.sh down"
    echo ""
}

# =============================================================================
# MAIN
# =============================================================================
case "${1:-help}" in
    up)     cmd_up ;;
    down)   cmd_down ;;
    status) cmd_status ;;
    *)
        echo ""
        echo "Usage: ./infra.sh <command>"
        echo ""
        echo "Commands:"
        echo "  up       Create all AWS resources + restore data from backup"
        echo "  down     Backup data + destroy all AWS resources (cost → \$0)"
        echo "  status   Show running resources and estimated costs"
        echo ""
        ;;
esac
