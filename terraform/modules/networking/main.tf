# =============================================================================
# Networking Module — VPC, Subnets, NAT, Security Groups, VPC Endpoints
# =============================================================================
# Creates an isolated VPC with public/private subnets across 2+ AZs.
# SageMaker resources run in private subnets (no public IP, outbound via NAT).
# VPC endpoints keep S3/ECR/CloudWatch/SageMaker traffic inside AWS network.
#
# Design decisions:
#   - Public subnets: NAT Gateway only (no workloads deployed here)
#   - Private subnets: All SageMaker, training, inference resources
#   - Security groups: Least-privilege, inbound HTTPS only from VPC CIDR
#   - VPC endpoints: S3 (free, always on), Interface endpoints (per-env toggle)
#   - NAT: Single for dev ($32/mo savings), per-AZ for prod (HA)
# =============================================================================

# =============================================================================
# Data Sources
# =============================================================================

data "aws_region" "current" {}

# =============================================================================
# VPC
# =============================================================================

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc"
  })
}

# =============================================================================
# Subnets — Public + Private (across AZs for HA)
# =============================================================================

resource "aws_subnet" "public" {
  count = length(var.availability_zones)

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-${var.availability_zones[count.index]}"
    Type = "public"
    Tier = "public"
  })
}

resource "aws_subnet" "private" {
  count = length(var.availability_zones)

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + length(var.availability_zones))
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-${var.availability_zones[count.index]}"
    Type = "private"
    Tier = "private"
  })
}

# =============================================================================
# Internet Gateway (for public subnets)
# =============================================================================

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-igw"
  })
}

# =============================================================================
# NAT Gateway (private subnet outbound internet access)
# =============================================================================
# Dev: 1 NAT (saves ~$32/month)
# Prod: 1 NAT per AZ for HA (if us-east-1a NAT fails, 1b still works)

resource "aws_eip" "nat" {
  count  = var.single_nat_gateway ? 1 : length(var.availability_zones)
  domain = "vpc"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-eip-${count.index}"
  })
}

resource "aws_nat_gateway" "main" {
  count = var.single_nat_gateway ? 1 : length(var.availability_zones)

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id

  depends_on = [aws_internet_gateway.main]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-nat-${count.index}"
  })
}

# =============================================================================
# Route Tables
# =============================================================================

# Public route table — routes to Internet Gateway
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-rt"
    Type = "public"
  })
}

resource "aws_route_table_association" "public" {
  count = length(var.availability_zones)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Private route tables — route to NAT Gateway
resource "aws_route_table" "private" {
  count = var.single_nat_gateway ? 1 : length(var.availability_zones)

  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-rt-${count.index}"
    Type = "private"
  })
}

resource "aws_route_table_association" "private" {
  count = length(var.availability_zones)

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[var.single_nat_gateway ? 0 : count.index].id
}

# =============================================================================
# Security Groups
# =============================================================================

# SageMaker Security Group — controls access to SageMaker resources
resource "aws_security_group" "sagemaker" {
  name_prefix = "${local.name_prefix}-sagemaker-"
  description = "Security group for SageMaker resources in ${var.environment}"
  vpc_id      = aws_vpc.main.id

  # Allow all outbound (SageMaker needs to pull images, access S3, etc.)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  # Allow inbound HTTPS from within VPC (for VPC endpoint access)
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Allow HTTPS from within VPC"
  }

  # Allow inbound from self (SageMaker inter-node communication for distributed training)
  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
    description = "Allow all traffic between SageMaker instances"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-sagemaker-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# VPC Endpoint Security Group
resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${local.name_prefix}-vpce-"
  description = "Security group for VPC endpoints in ${var.environment}"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Allow HTTPS from within VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpce-sg"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# VPC Endpoints — Keep AWS traffic private (no internet traversal)
# =============================================================================

# S3 Gateway Endpoint (FREE — always create)
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${data.aws_region.current.name}.s3"

  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-s3-endpoint"
  })
}

# SageMaker API Interface Endpoint (costs ~$0.01/hr — prod/staging only)
resource "aws_vpc_endpoint" "sagemaker_api" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.sagemaker.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-sagemaker-api-endpoint"
  })
}

# SageMaker Runtime Interface Endpoint (inference calls stay private)
resource "aws_vpc_endpoint" "sagemaker_runtime" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.sagemaker.runtime"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-sagemaker-runtime-endpoint"
  })
}

# ECR API Interface Endpoint (Docker pulls stay private)
resource "aws_vpc_endpoint" "ecr_api" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.api"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecr-api-endpoint"
  })
}

# ECR Docker Interface Endpoint
resource "aws_vpc_endpoint" "ecr_dkr" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecr-dkr-endpoint"
  })
}

# CloudWatch Logs Interface Endpoint
resource "aws_vpc_endpoint" "cloudwatch_logs" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.logs"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-cw-logs-endpoint"
  })
}

# STS Interface Endpoint (required for OIDC/IAM in private subnets)
resource "aws_vpc_endpoint" "sts" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.sts"
  vpc_endpoint_type   = "Interface"
  private_dns_enabled = true

  subnet_ids         = aws_subnet.private[*].id
  security_group_ids = [aws_security_group.vpc_endpoints.id]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-sts-endpoint"
  })
}
