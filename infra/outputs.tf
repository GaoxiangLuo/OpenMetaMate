# ============================================
# OUTPUTS - MetaMate Infrastructure
# ============================================

# Frontend URLs
output "frontend_s3_url" {
  description = "S3 website URL (direct access)"
  value       = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
}

output "frontend_cloudfront_url" {
  description = "CloudFront CDN URL"
  value       = var.enable_cdn ? "https://${aws_cloudfront_distribution.frontend[0].domain_name}" : "N/A - CDN disabled"
}

output "frontend_custom_url" {
  description = "Custom domain URL"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "N/A - No custom domain"
}

# Backend URLs
output "backend_url" {
  description = "Lightsail container service URL"
  value       = aws_lightsail_container_service.backend.url
}

output "backend_api_url" {
  description = "API endpoint URL"
  value       = var.domain_name != "" ? "https://api.${var.domain_name}" : aws_lightsail_container_service.backend.url
}

# CloudFront Distribution
output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidation)"
  value       = var.enable_cdn ? aws_cloudfront_distribution.frontend[0].id : "N/A"
}

output "cloudfront_distribution_arn" {
  description = "CloudFront distribution ARN"
  value       = var.enable_cdn ? aws_cloudfront_distribution.frontend[0].arn : "N/A"
}

# S3 Buckets
output "frontend_bucket_name" {
  description = "Frontend S3 bucket name"
  value       = aws_s3_bucket.frontend.id
}

output "logs_bucket_name" {
  description = "Logs S3 bucket name"
  value       = aws_s3_bucket.logs.id
}

# Lightsail Container Service
output "container_service_name" {
  description = "Lightsail container service name"
  value       = aws_lightsail_container_service.backend.name
}

output "container_service_state" {
  description = "Lightsail container service state"
  value       = aws_lightsail_container_service.backend.state
}

# Secrets
output "secrets_arn" {
  description = "AWS Secrets Manager secret ARN"
  value       = aws_secretsmanager_secret.app_secrets.arn
  sensitive   = true
}

# DNS Configuration Instructions
output "dns_configuration" {
  description = "DNS configuration instructions for CloudFlare"
  value = var.domain_name != "" ? (
    <<-EOT
    
    ===== CloudFlare DNS Configuration =====
    
    1. Frontend (main site):
       Type: CNAME
       Name: @ (or metamate.online)
       Target: ${var.enable_cdn ? aws_cloudfront_distribution.frontend[0].domain_name : aws_s3_bucket_website_configuration.frontend.website_endpoint}
       Proxy: ${var.enable_cdn ? "OFF (use CloudFront SSL)" : "ON"}
    
    2. Frontend (www):
       Type: CNAME
       Name: www
       Target: ${var.enable_cdn ? aws_cloudfront_distribution.frontend[0].domain_name : aws_s3_bucket_website_configuration.frontend.website_endpoint}
       Proxy: ${var.enable_cdn ? "OFF (use CloudFront SSL)" : "ON"}
    
    3. Backend API:
       Type: CNAME
       Name: api
       Target: ${aws_lightsail_container_service.backend.url}
       Proxy: ON (use CloudFlare SSL)
    
    4. ACM Certificate Validation (if using CloudFront):
       ${var.enable_cdn ? join("\n       ", [for record in aws_acm_certificate.cert[0].domain_validation_options : "Type: ${record.resource_record_type}, Name: ${record.resource_record_name}, Value: ${record.resource_record_value}"]) : "N/A"}
    
    EOT
  ) : "N/A - No custom domain configured"
}

# Deployment Commands
output "deployment_commands" {
  description = "Commands for deploying the application"
  value = <<-EOT
    
    ===== Backend Deployment =====
    
    1. Build Docker image:
       cd backend/
       docker build -t ${var.app_name}-backend:latest .
    
    2. Push to Lightsail:
       aws lightsail push-container-image \
         --region ${var.aws_region} \
         --service-name ${aws_lightsail_container_service.backend.name} \
         --label backend \
         --image ${var.app_name}-backend:latest
    
    3. Deploy container:
       aws lightsail create-container-service-deployment \
         --region ${var.aws_region} \
         --service-name ${aws_lightsail_container_service.backend.name} \
         --containers file://container.json \
         --public-endpoint file://endpoint.json
    
    ===== Frontend Deployment =====
    
    1. Build frontend:
       cd frontend/
       export NEXT_PUBLIC_API_URL=${var.domain_name != "" ? "https://api.${var.domain_name}" : aws_lightsail_container_service.backend.url}
       pnpm install
       pnpm build
    
    2. Deploy to S3:
       aws s3 sync out/ s3://${aws_s3_bucket.frontend.id}/ \
         --delete \
         --cache-control "public, max-age=31536000, immutable" \
         --exclude "*.html" \
         --exclude "_next/data/*" \
         --exclude "_next/static/chunks/pages/*"
       
       aws s3 sync out/ s3://${aws_s3_bucket.frontend.id}/ \
         --delete \
         --cache-control "public, max-age=0, must-revalidate" \
         --exclude "*" \
         --include "*.html" \
         --include "_next/data/*" \
         --include "_next/static/chunks/pages/*"
    
    3. Invalidate CloudFront (if enabled):
       ${var.enable_cdn ? "aws cloudfront create-invalidation --distribution-id ${aws_cloudfront_distribution.frontend[0].id} --paths '/*'" : "# CDN not enabled"}
    
  EOT
}

# Environment Variables
output "backend_env_vars" {
  description = "Environment variables for backend"
  value = {
    PORT         = "8000"
    CORS_ORIGINS = var.domain_name != "" ? "https://${var.domain_name},https://www.${var.domain_name}" : "*"
    SECRET_ARN   = aws_secretsmanager_secret.app_secrets.arn
    AWS_REGION   = var.aws_region
    ENVIRONMENT  = var.environment
  }
  sensitive = true
}

output "frontend_env_vars" {
  description = "Environment variables for frontend build"
  value = {
    NEXT_PUBLIC_API_URL = var.domain_name != "" ? "https://api.${var.domain_name}" : aws_lightsail_container_service.backend.url
  }
}

# Cost Estimation
output "estimated_monthly_cost" {
  description = "Estimated monthly AWS costs"
  value = <<-EOT
    
    ===== Estimated Monthly Costs =====
    
    Lightsail Container (${var.container_service_power}): $${
      var.container_service_power == "nano" ? "7" :
      var.container_service_power == "micro" ? "10" :
      var.container_service_power == "small" ? "25" :
      var.container_service_power == "medium" ? "50" :
      var.container_service_power == "large" ? "100" :
      var.container_service_power == "xlarge" ? "200" : "unknown"
    }
    S3 Storage (100MB): $0.02
    CloudFront CDN: $0 (free tier)
    Secrets Manager: $0.40
    Data Transfer: ~$1-5 (depends on usage)
    
    Total: ~$${
      var.container_service_power == "small" ? "26-30" :
      var.container_service_power == "medium" ? "51-55" : "varies"
    }/month
    
    Note: Actual costs may vary based on usage.
  EOT
}