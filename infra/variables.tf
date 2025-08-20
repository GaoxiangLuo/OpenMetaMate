# ============================================
# VARIABLES - MetaMate Infrastructure
# ============================================

# AWS Configuration
variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
  default     = "prod"
}

# Domain Configuration
variable "domain_name" {
  description = "Your domain name for the application"
  type        = string
  default     = "metamate.online"
}

variable "enable_cdn" {
  description = "Enable CloudFront CDN for frontend"
  type        = bool
  default     = true
}

# Application Configuration
variable "app_name" {
  description = "Application name"
  type        = string
  default     = "metamate"
}

# Lightsail Configuration
variable "container_service_power" {
  description = "Lightsail container service power (nano/micro/small/medium/large/xlarge)"
  type        = string
  default     = "small" # 2GB RAM, 1 vCPU = $25/month
}

variable "container_service_scale" {
  description = "Number of container instances"
  type        = number
  default     = 1
}

# LLM Configuration (Sensitive)
variable "llm_api_key" {
  description = "LLM API key (OpenAI, Anthropic, etc.)"
  type        = string
  sensitive   = true
}

variable "llm_api_url" {
  description = "LLM API endpoint URL"
  type        = string
  default     = "https://api.openai.com/v1"
}

variable "llm_model" {
  description = "LLM model to use"
  type        = string
  default     = "gpt-4o"
}

# Frontend Configuration
variable "frontend_build_command" {
  description = "Command to build frontend"
  type        = string
  default     = "pnpm build"
}

# Security Configuration
variable "allowed_origins" {
  description = "Allowed CORS origins"
  type        = list(string)
  default     = []
}

# Monitoring
variable "enable_monitoring" {
  description = "Enable CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "enable_logging" {
  description = "Enable application logging"
  type        = bool
  default     = true
}

# Cost Management
variable "budget_amount" {
  description = "Monthly budget amount in USD"
  type        = number
  default     = 30
}

variable "budget_email" {
  description = "Email for budget alerts"
  type        = string
  default     = ""
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "MetaMate"
    ManagedBy   = "Terraform"
    Environment = "Production"
  }
}