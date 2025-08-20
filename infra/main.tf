# ============================================
# MAIN TERRAFORM CONFIGURATION - MetaMate
# ============================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
  
  # Optional: Store state in S3 (uncomment after creating bucket)
  # backend "s3" {
  #   bucket = "metamate-terraform-state"
  #   key    = "prod/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# ============================================
# PROVIDERS
# ============================================

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = var.tags
  }
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1" # Required for CloudFront
}

# ============================================
# DATA SOURCES
# ============================================

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ============================================
# SECRETS MANAGER
# ============================================

resource "random_id" "secret_suffix" {
  byte_length = 4
}

resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${var.app_name}-secrets-${random_id.secret_suffix.hex}"
  recovery_window_in_days = 0 # For dev/testing. Use 30 for production
  
  tags = {
    Name = "${var.app_name}-secrets"
  }
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    LLM_API_KEY = var.llm_api_key
    LLM_API_URL = var.llm_api_url
    LLM_MODEL   = var.llm_model
  })
}

# ============================================
# S3 BUCKETS
# ============================================

# Frontend hosting bucket
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "frontend" {
  bucket = "${var.app_name}-frontend-${random_id.bucket_suffix.hex}"
  
  tags = {
    Name = "${var.app_name}-frontend"
  }
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  
  index_document {
    suffix = "index.html"
  }
  
  error_document {
    key = "404.html"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      }
    ]
  })
  
  depends_on = [aws_s3_bucket_public_access_block.frontend]
}

# Logs bucket for CloudFront
resource "aws_s3_bucket" "logs" {
  bucket = "${var.app_name}-logs-${random_id.bucket_suffix.hex}"
  
  tags = {
    Name = "${var.app_name}-logs"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "logs" {
  bucket = aws_s3_bucket.logs.id
  
  rule {
    id     = "delete-old-logs"
    status = "Enabled"
    
    expiration {
      days = 30
    }
  }
}

# ============================================
# CLOUDFRONT CDN
# ============================================

resource "aws_cloudfront_origin_access_control" "frontend" {
  count = var.enable_cdn ? 1 : 0
  
  name                              = "${var.app_name}-oac"
  description                       = "OAC for ${var.app_name} frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  count = var.enable_cdn ? 1 : 0
  
  enabled             = true
  is_ipv6_enabled    = true
  default_root_object = "index.html"
  price_class        = "PriceClass_100" # Use only NA and EU edge locations (cheaper)
  
  aliases = var.domain_name != "" ? [var.domain_name, "www.${var.domain_name}"] : []
  
  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "S3-${aws_s3_bucket.frontend.id}"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend[0].id
  }
  
  default_cache_behavior {
    target_origin_id       = "S3-${aws_s3_bucket.frontend.id}"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress              = true
    
    forwarded_values {
      query_string = false
      headers      = ["Origin"]
      
      cookies {
        forward = "none"
      }
    }
    
    min_ttl     = 0
    default_ttl = 86400
    max_ttl     = 31536000
  }
  
  # Custom error pages for SPAs
  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 300
  }
  
  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 300
  }
  
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  
  viewer_certificate {
    cloudfront_default_certificate = var.domain_name == "" ? true : false
    acm_certificate_arn            = var.domain_name != "" ? aws_acm_certificate.cert[0].arn : null
    ssl_support_method             = var.domain_name != "" ? "sni-only" : null
    minimum_protocol_version       = "TLSv1.2_2021"
  }
  
  logging_config {
    bucket          = aws_s3_bucket.logs.bucket_domain_name
    prefix          = "cloudfront/"
    include_cookies = false
  }
  
  tags = {
    Name = "${var.app_name}-cdn"
  }
  
  depends_on = [
    aws_acm_certificate_validation.cert
  ]
}

# ============================================
# ACM CERTIFICATE (for custom domain)
# ============================================

resource "aws_acm_certificate" "cert" {
  count    = var.domain_name != "" ? 1 : 0
  provider = aws.us_east_1 # CloudFront requires cert in us-east-1
  
  domain_name               = var.domain_name
  subject_alternative_names = ["www.${var.domain_name}", "api.${var.domain_name}"]
  validation_method         = "DNS"
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name = "${var.app_name}-cert"
  }
}

resource "aws_acm_certificate_validation" "cert" {
  count                   = var.domain_name != "" ? 1 : 0
  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.cert[0].arn
  validation_record_fqdns = [for record in aws_acm_certificate.cert[0].domain_validation_options : record.resource_record_value]
}

# ============================================
# LIGHTSAIL CONTAINER SERVICE
# ============================================

resource "aws_lightsail_container_service" "backend" {
  name  = "${var.app_name}-backend"
  power = var.container_service_power
  scale = var.container_service_scale
  
  tags = {
    Name = "${var.app_name}-backend"
  }
}

# Note: Actual container deployment requires the container image to be pushed first
# This will be done via deployment script after infrastructure is created

resource "aws_lightsail_container_service_deployment_version" "backend" {
  service_name = aws_lightsail_container_service.backend.name
  
  container {
    container_name = "api"
    image         = "${var.app_name}-backend:latest"
    
    ports = {
      8000 = "HTTP"
    }
    
    environment = {
      PORT           = "8000"
      CORS_ORIGINS   = var.domain_name != "" ? "https://${var.domain_name},https://www.${var.domain_name}" : "*"
      SECRET_ARN     = aws_secretsmanager_secret.app_secrets.arn
      AWS_REGION     = var.aws_region
      ENVIRONMENT    = var.environment
    }
  }
  
  public_endpoint {
    container_name = "api"
    container_port = 8000
    
    health_check {
      healthy_threshold   = 2
      unhealthy_threshold = 2
      timeout_seconds     = 5
      interval_seconds    = 30
      path               = "/health"
      success_codes      = "200-299"
    }
  }
  
  lifecycle {
    ignore_changes = [container[0].image] # Allow image updates without Terraform
  }
}

# ============================================
# IAM ROLE FOR LIGHTSAIL (Secrets Access)
# ============================================

resource "aws_iam_role" "lightsail_task" {
  name = "${var.app_name}-lightsail-task-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lightsail.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lightsail_secrets" {
  name = "${var.app_name}-secrets-policy"
  role = aws_iam_role.lightsail_task.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.app_secrets.arn
      }
    ]
  })
}

# ============================================
# BUDGET ALERT
# ============================================

resource "aws_budgets_budget" "monthly" {
  count = var.budget_email != "" ? 1 : 0
  
  name         = "${var.app_name}-monthly-budget"
  budget_type  = "COST"
  limit_amount = var.budget_amount
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
  
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_email_addresses = [var.budget_email]
  }
}