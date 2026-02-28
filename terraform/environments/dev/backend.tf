# ============================================================================
# Dev Environment — Backend Configuration
# ============================================================================
# Points to the S3 bucket + DynamoDB table created by terraform/backend/
# Each environment uses a DIFFERENT key path to keep state files separate.
# ============================================================================

terraform {
  backend "s3" {
    bucket         = "customer-churn-terraform-state-231284356634"
    key            = "environments/dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "customer-churn-terraform-locks"
    encrypt        = true
  }
}
