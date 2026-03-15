# Cloud Deployment Guide

This guide covers deploying OpenMetaMate to your own AWS infrastructure. For local Docker deployment, see the [main README](../README.md).

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CloudFlare    │    │   CloudFront     │    │  Lightsail      │
│   DNS + SSL     │───>│   CDN + SSL      │───>│  Container      │
│                 │    │                  │    │  (Backend API)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                v
                       ┌──────────────────┐
                       │     S3 Bucket    │
                       │  (Frontend SPA)  │
                       └──────────────────┘
```

- **Backend**: AWS Lightsail Container Service (FastAPI)
- **Frontend**: S3 + CloudFront CDN (Next.js static export)
- **Secrets**: AWS Secrets Manager
- **DNS**: CloudFlare (or any DNS provider)

## Prerequisites

```bash
brew install awscli terraform
aws configure  # Set up your AWS credentials
```

## Deploy with Terraform

### 1. Configure Variables

```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your domain, API keys, etc.
```

Key variables to set:
- `domain_name` — your domain
- `llm_api_key` — your LLM API key
- `llm_api_url` — API endpoint (default: OpenAI)
- `llm_model` — model to use
- `aws_region` — AWS region (us-east-1 recommended for CloudFront)

### 2. Create Terraform State Bucket

S3 bucket names are globally unique. Create your own:

```bash
aws s3api create-bucket --bucket your-project-terraform-state --region us-east-1
aws s3api put-bucket-versioning --bucket your-project-terraform-state \
  --versioning-configuration Status=Enabled
```

Then update the backend bucket name in `infra/main.tf` to match.

### 3. Deploy Infrastructure

```bash
cd infra/
terraform init
terraform plan    # Review what will be created
terraform apply   # Deploy (takes 10-15 minutes)
```

### 4. Set Up CI/CD (GitHub Actions)

Add these secrets to your GitHub repository (Settings > Secrets > Actions):

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `LLM_API_KEY` | Your LLM API key |
| `LLM_API_URL` | API endpoint URL |
| `LLM_MODEL` | Model name |
| `FRONTEND_BUCKET_NAME` | From `terraform output` |
| `CLOUDFRONT_DISTRIBUTION_ID` | From `terraform output` |
| `CUSTOM_DOMAIN` | Your domain name |

Every push to `main` automatically deploys both backend and frontend with health checks.

### 5. Configure DNS

After deployment, point your domain to the infrastructure. See [infra/README.md](../infra/README.md) for CloudFlare DNS setup instructions.

## CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/deploy.yml`) automatically:

1. **Tests**: Runs linting and type checking for both backend and frontend
2. **Backend Deploy**: Builds Docker image and deploys to Lightsail
3. **Frontend Deploy**: Builds Next.js app and deploys to S3/CloudFront
4. **Health Checks**: Verifies deployment success with proper timeouts
5. **Cache Invalidation**: Updates CloudFront for immediate changes

## Manual Deployment

For step-by-step manual deployment instructions, see [`plans/002-lightsail-migration-guide.md`](../plans/002-lightsail-migration-guide.md).

For the deployment script:

```bash
cd infra/
chmod +x deploy.sh
./deploy.sh all       # Deploy everything
./deploy.sh backend   # Backend only
./deploy.sh frontend  # Frontend only
./deploy.sh info      # Show deployment info
```

## Monitoring

See [infra/README.md](../infra/README.md) for log access, health checks, and troubleshooting.
