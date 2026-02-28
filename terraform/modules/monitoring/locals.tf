# =============================================================================
# Monitoring Module — Locals
# =============================================================================

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    Module      = "monitoring"
    ManagedBy   = "terraform"
  }

  # Whether endpoint-dependent resources should be created
  has_endpoint = var.endpoint_name != ""

  # Whether alarms should be created (requires both flag and endpoint)
  create_alarms = var.enable_alarms && local.has_endpoint
}
