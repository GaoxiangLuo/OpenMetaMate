# MetaMate Infrastructure

AWS infrastructure for MetaMate using Terraform and Lightsail.

## Architecture

- **Backend**: AWS Lightsail Container Service (FastAPI)
- **Frontend**: S3 + CloudFront CDN (Next.js)
- **Secrets**: AWS Secrets Manager
- **Domain**: CloudFlare DNS → CloudFront/Lightsail
- **Monitoring**: CloudWatch + Budget Alerts

## Quick Start

### Prerequisites

```bash
# Install required tools
brew install awscli terraform

# Configure AWS credentials
aws configure
```

### 1. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 2. Deploy Everything

```bash
# Make deploy script executable
chmod +x deploy.sh

# Deploy all infrastructure and applications
./deploy.sh all
```

## Individual Deployment Steps

### Infrastructure Only

```bash
# Initialize Terraform
terraform init

# Review changes
terraform plan

# Deploy infrastructure
terraform apply
```

### Backend Deployment

```bash
# Build and push Docker image
cd ../backend/
docker build -t metamate-backend:latest .

# Push to Lightsail
aws lightsail push-container-image \
  --service-name metamate-backend \
  --label backend \
  --image metamate-backend:latest

# Deploy via script
cd ../infra/
./deploy.sh backend
```

### Frontend Deployment

```bash
# Build frontend
cd ../frontend/
export NEXT_PUBLIC_API_URL=https://api.metamate.online
pnpm build

# Deploy to S3
aws s3 sync out/ s3://metamate-frontend/

# Invalidate CloudFront
aws cloudfront create-invalidation \
  --distribution-id YOUR_DISTRIBUTION_ID \
  --paths "/*"

# Or use script
cd ../infra/
./deploy.sh frontend
```

## Cost Breakdown

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| Lightsail Container | small (2GB/1vCPU) | $25 |
| S3 Storage | ~100MB | <$1 |
| CloudFront CDN | 100GB transfer | Free tier |
| Secrets Manager | 1 secret | $0.40 |
| **Total** | | **~$26.40** |

## CloudFlare DNS Setup

After deployment, configure your CloudFlare DNS:

1. **Main Domain (metamate.online)**
   - Type: CNAME
   - Name: @
   - Target: `<cloudfront-distribution>.cloudfront.net`
   - Proxy: OFF

2. **WWW Subdomain**
   - Type: CNAME
   - Name: www
   - Target: `<cloudfront-distribution>.cloudfront.net`
   - Proxy: OFF

3. **API Subdomain**
   - Type: CNAME
   - Name: api
   - Target: `<lightsail-container>.us-east-1.cs.amazonlightsail.com`
   - Proxy: ON

## Deployment Script Usage

```bash
# Deploy everything
./deploy.sh all

# Deploy only infrastructure
./deploy.sh infra

# Deploy only backend
./deploy.sh backend

# Deploy only frontend
./deploy.sh frontend

# Show deployment info
./deploy.sh info

# Destroy everything
./deploy.sh destroy
```

## GitHub Actions Setup

Add these secrets to your GitHub repository:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `FRONTEND_BUCKET_NAME` (from Terraform output)
- `CLOUDFRONT_DISTRIBUTION_ID` (from Terraform output)
- `CUSTOM_DOMAIN` (optional, e.g., metamate.online)

## Monitoring

### View Logs

```bash
# Backend logs
aws lightsail get-container-log \
  --service-name metamate-backend \
  --container-name api

# CloudFront logs (if enabled)
aws s3 ls s3://metamate-logs/cloudfront/
```

### Health Checks

- Backend: `https://api.metamate.online/health`
- Frontend: CloudFront monitoring in AWS Console

## Troubleshooting

### Container won't start

```bash
# Check logs
aws lightsail get-container-log --service-name metamate-backend

# Verify secrets
aws secretsmanager get-secret-value --secret-id metamate-secrets
```

### Frontend 404 errors

```bash
# Check S3 files
aws s3 ls s3://metamate-frontend/ --recursive

# Verify CloudFront distribution
aws cloudfront get-distribution --id YOUR_DISTRIBUTION_ID
```

### CORS errors

1. Check backend CORS_ORIGINS environment variable
2. Verify CloudFront forwards Origin header
3. Ensure API subdomain points to Lightsail

## Support

For issues or questions, check the [deployment plan](../plans/001-production-deployment.md) for detailed instructions.