# ============================================================================
# Staging Environment — Backend Configuration
# ============================================================================

terraform {
  backend "s3" {
    bucket         = "customer-churn-terraform-state-231284356634"
    key            = "environments/staging/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "customer-churn-terraform-locks"
    encrypt        = true
  }
}
