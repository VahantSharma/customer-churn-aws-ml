# =============================================================================
# Dev Environment — Terraform Variable Values
# =============================================================================
# Dev-specific defaults. Override at runtime:
#   terraform apply -var="deploy_endpoint=true"
# =============================================================================

aws_region   = "us-east-1"
project_name = "customer-churn"
github_repo  = "VahantSharma/customer-churn-aws-ml"

# Endpoint is disabled by default in dev — enable when ready to test
deploy_endpoint = false
alert_email     = ""
