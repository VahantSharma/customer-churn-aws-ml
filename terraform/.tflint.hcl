# =============================================================================
# TFLint Configuration — Customer Churn ML Platform
# =============================================================================
# Enforced in CI/CD pipeline. Run locally with: tflint --init && tflint
# =============================================================================

config {
  # Enable module inspection (descend into module blocks)
  call_module_type = "local"
}

# -----------------------------------------------------------------------------
# AWS Plugin — Catches AWS-specific misconfigurations at lint time
# -----------------------------------------------------------------------------
plugin "aws" {
  enabled = true
  version = "0.31.0"
  source  = "github.com/terraform-linters/tflint-ruleset-aws"
}

# -----------------------------------------------------------------------------
# Terraform Plugin — General HCL best practices
# -----------------------------------------------------------------------------
plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

# -----------------------------------------------------------------------------
# Custom Rules
# -----------------------------------------------------------------------------

# Enforce consistent naming conventions
rule "terraform_naming_convention" {
  enabled = true
  format  = "snake_case"
}

# Require descriptions on all variables and outputs
rule "terraform_documented_variables" {
  enabled = true
}

rule "terraform_documented_outputs" {
  enabled = true
}

# Require type declarations on all variables
rule "terraform_typed_variables" {
  enabled = true
}

# Disallow deprecated syntax
rule "terraform_deprecated_interpolation" {
  enabled = true
}

# Enforce standard module structure
rule "terraform_standard_module_structure" {
  enabled = true
}

# Warn on unused declarations
rule "terraform_unused_declarations" {
  enabled = true
}

# Disallow terraform workspace usage (we use directory-based envs)
rule "terraform_workspace_remote" {
  enabled = true
}
