# MetaMate Lightsail Migration Guide

## Quick Overview
Migrating MetaMate from EC2 to a more scalable and cost-effective infrastructure:
- **Backend**: AWS Lightsail Container Service ($25/month)
- **Frontend**: S3 + CloudFront CDN (< $2/month)
- **Domain**: CloudFlare DNS (existing)
- **Total Cost**: ~$27/month (vs current EC2 costs)

## Migration Steps

### Step 1: Prerequisites Setup (15 minutes)

#### 1.1 Install Required Tools
```bash
# Install AWS CLI
brew install awscli

# Install Terraform
brew install terraform

# Verify Docker is installed
docker --version

# Install pnpm if not already installed
curl -fsSL https://get.pnpm.io/install.sh | sh -
```

#### 1.2 Configure AWS Credentials
```bash
# Configure AWS CLI
aws configure

# You'll need:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: us-east-1
# - Default output: json
```

#### 1.3 Create Terraform State Bucket
```bash
# Create S3 bucket for Terraform state
aws s3api create-bucket \
  --bucket metamate-terraform-state \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket metamate-terraform-state \
  --versioning-configuration Status=Enabled
```

### Step 2: Configure Terraform (5 minutes)

#### 2.1 Prepare Configuration
```bash
cd infra/

# Copy example configuration
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
nano terraform.tfvars
```

#### 2.2 Required Configuration Values
Edit `terraform.tfvars` with:
```hcl
# Your LLM API Key (required)
llm_api_key = "sk-proj-YOUR_OPENAI_KEY_HERE"

# LLM Configuration
llm_api_url = "https://api.openai.com/v1"
llm_model   = "gpt-4o"

# Your domain
domain_name = "metamate.online"
enable_cdn  = true

# AWS Configuration
aws_region  = "us-east-1"
environment = "prod"

# Container sizing (recommended)
container_service_power = "small"  # 2GB RAM, 1 vCPU ($25/month)
container_service_scale = 1

# Budget alerts (optional but recommended)
budget_amount = 30
budget_email  = "your-email@example.com"
```

#### 2.3 Enable Terraform Backend
Edit `infra/main.tf` and uncomment lines 20-24:
```hcl
backend "s3" {
  bucket = "metamate-terraform-state"
  key    = "prod/terraform.tfstate"
  region = "us-east-1"
}
```

### Step 3: Deploy Infrastructure (20 minutes)

#### 3.1 Initialize Terraform
```bash
cd infra/
terraform init
```

#### 3.2 Review Infrastructure Plan
```bash
# See what will be created
terraform plan

# Review the output carefully
# You should see:
# - Lightsail container service
# - S3 buckets (frontend + logs)
# - CloudFront distribution
# - Secrets Manager
# - ACM certificate
```

#### 3.3 Deploy Infrastructure
```bash
# Apply the infrastructure
terraform apply

# Type 'yes' when prompted
# This will take 10-15 minutes
```

#### 3.4 Save Important Outputs
```bash
# Save these for later use
terraform output > deployment-info.txt

# Key outputs to note:
terraform output frontend_bucket_name
terraform output container_service_name
terraform output cloudfront_distribution_id
```

### Step 4: Deploy Backend to Lightsail (15 minutes)

#### 4.1 Build Backend Docker Image
```bash
cd ../backend/

# Build the Docker image
docker build -t metamate-backend:latest .
```

#### 4.2 Push to Lightsail Registry
```bash
# Get the container service name
cd ../infra/
SERVICE_NAME=$(terraform output -raw container_service_name)

# Push image to Lightsail
aws lightsail push-container-image \
  --region us-east-1 \
  --service-name ${SERVICE_NAME} \
  --label backend \
  --image metamate-backend:latest
```

#### 4.3 Deploy Container
```bash
# Get the pushed image name
IMAGE=$(aws lightsail get-container-images \
  --region us-east-1 \
  --service-name ${SERVICE_NAME} \
  --query 'containerImages[0].image' \
  --output text)

# Create container configuration
cat > /tmp/containers.json <<EOF
{
  "api": {
    "image": "${IMAGE}",
    "ports": {
      "8000": "HTTP"
    },
    "environment": {
      "PORT": "8000",
      "AWS_REGION": "us-east-1",
      "ENVIRONMENT": "prod"
    }
  }
}
EOF

# Create endpoint configuration
cat > /tmp/endpoint.json <<EOF
{
  "containerName": "api",
  "containerPort": 8000,
  "healthCheck": {
    "healthyThreshold": 2,
    "unhealthyThreshold": 2,
    "timeoutSeconds": 5,
    "intervalSeconds": 30,
    "path": "/health",
    "successCodes": "200-299"
  }
}
EOF

# Deploy the container
aws lightsail create-container-service-deployment \
  --region us-east-1 \
  --service-name ${SERVICE_NAME} \
  --containers file:///tmp/containers.json \
  --public-endpoint file:///tmp/endpoint.json
```

#### 4.4 Wait for Deployment
```bash
# Check deployment status (wait until READY)
aws lightsail get-container-services \
  --region us-east-1 \
  --service-name ${SERVICE_NAME} \
  --query 'containerServices[0].state' \
  --output text

# Get backend URL when ready
terraform output backend_url
```

### Step 5: Deploy Frontend to S3/CloudFront (10 minutes)

#### 5.1 Build Frontend
```bash
cd ../frontend/

# Get backend URL from Terraform
cd ../infra/
export NEXT_PUBLIC_API_URL=https://api.metamate.online

# Build frontend
cd ../frontend/
pnpm install
pnpm build
```

#### 5.2 Export Static Files
```bash
# Export Next.js static files
pnpm next export -o out
```

#### 5.3 Deploy to S3
```bash
# Get bucket name
cd ../infra/
BUCKET_NAME=$(terraform output -raw frontend_bucket_name)

# Sync files to S3
cd ../frontend/
aws s3 sync out/ s3://${BUCKET_NAME}/ \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "*.html" \
  --exclude "_next/data/*" \
  --exclude "_next/static/chunks/pages/*"

# Sync HTML files with no-cache
aws s3 sync out/ s3://${BUCKET_NAME}/ \
  --delete \
  --cache-control "public, max-age=0, must-revalidate" \
  --exclude "*" \
  --include "*.html" \
  --include "_next/data/*" \
  --include "_next/static/chunks/pages/*"
```

#### 5.4 Invalidate CloudFront Cache
```bash
# Get distribution ID
cd ../infra/
DISTRIBUTION_ID=$(terraform output -raw cloudfront_distribution_id)

# Create invalidation
aws cloudfront create-invalidation \
  --distribution-id ${DISTRIBUTION_ID} \
  --paths "/*"
```

### Step 6: Configure CloudFlare DNS (10 minutes)

#### 6.1 Get DNS Configuration
```bash
cd infra/
terraform output dns_configuration
```

#### 6.2 CloudFlare Setup
1. Login to [CloudFlare Dashboard](https://dash.cloudflare.com)
2. Select your domain: `metamate.online`
3. Go to **DNS** → **Records**

#### 6.3 Add DNS Records

**Delete/Update existing A record pointing to EC2**

**Add Frontend Records:**
- **Root domain:**
  - Type: `CNAME`
  - Name: `@` (or `metamate.online`)
  - Target: `[CloudFront distribution domain from terraform output]`
  - Proxy: **OFF** (Gray cloud)
  - TTL: Auto

- **WWW subdomain:**
  - Type: `CNAME`
  - Name: `www`
  - Target: `[Same CloudFront distribution domain]`
  - Proxy: **OFF** (Gray cloud)
  - TTL: Auto

**Add API Backend Record:**
- Type: `CNAME`
- Name: `api`
- Target: `[Lightsail container URL from terraform output]`
- Proxy: **ON** (Orange cloud)
- TTL: Auto

#### 6.4 SSL/TLS Settings
1. Go to **SSL/TLS** → **Overview**
2. Set encryption mode to **"Full"**

### Step 7: Verify Deployment (5 minutes)

#### 7.1 Test Endpoints
```bash
# Test frontend
curl -I https://metamate.online

# Test API health
curl https://api.metamate.online/health

# Open in browser
open https://metamate.online
```

#### 7.2 Check All Services
- [ ] Frontend loads at https://metamate.online
- [ ] API responds at https://api.metamate.online/health
- [ ] File upload works
- [ ] LLM extraction works
- [ ] Results display correctly

### Step 8: Setup GitHub Actions CI/CD (5 minutes)

#### 8.1 Add GitHub Secrets
Go to your GitHub repository → Settings → Secrets and add:

- `AWS_ACCESS_KEY_ID`: Your AWS access key
- `AWS_SECRET_ACCESS_KEY`: Your AWS secret key
- `FRONTEND_BUCKET_NAME`: From terraform output
- `CLOUDFRONT_DISTRIBUTION_ID`: From terraform output
- `CUSTOM_DOMAIN`: metamate.online

#### 8.2 Test CI/CD
```bash
# Make a small change and push
git add .
git commit -m "Test CI/CD deployment"
git push origin main

# Monitor GitHub Actions
```

### Step 9: Migration Cleanup (5 minutes)

#### 9.1 Stop EC2 Instance (Don't terminate yet!)
1. Go to AWS EC2 Console
2. Stop (don't terminate) your existing instance
3. Monitor the new deployment for 24 hours

#### 9.2 After 24 Hours Verification
If everything works correctly:
```bash
# Backup any data from EC2 if needed
# Then terminate the EC2 instance
# Release any Elastic IPs
# Delete old security groups
```

## Rollback Plan

If anything goes wrong:

### Quick Rollback to EC2
1. Update CloudFlare DNS to point back to EC2 IP
2. Start EC2 instance
3. Service restored in 5 minutes

### Destroy Lightsail Infrastructure
```bash
cd infra/
terraform destroy
```

## Cost Comparison

| Service | EC2 Setup | Lightsail Setup | Savings |
|---------|-----------|-----------------|---------|
| Compute | t2.micro/small (~$10-20) | Lightsail small ($25) | Similar |
| Storage | EBS (~$2-5) | S3 (<$1) | -$2-4 |
| Static IP | $3.60 | Included | -$3.60 |
| Data Transfer | Variable | Included | Predictable |
| **Total** | ~$15-30 | ~$27 | Predictable |

## Benefits of New Architecture

1. **Scalability**: Easy to scale Lightsail containers
2. **Performance**: CloudFront CDN for global delivery
3. **Reliability**: Managed container service with health checks
4. **Security**: Secrets in AWS Secrets Manager
5. **Simplicity**: Infrastructure as Code with Terraform
6. **CI/CD**: Automated deployments with GitHub Actions

## Monitoring

### Check Service Health
```bash
# Backend health
curl https://api.metamate.online/health

# Container logs
aws lightsail get-container-log \
  --service-name metamate-backend \
  --container-name api

# CloudFront metrics
# Check in AWS Console → CloudFront → Monitoring
```

### Cost Monitoring
- AWS Budget alerts configured at $30/month
- Check AWS Cost Explorer weekly
- Review Lightsail metrics dashboard

## Support & Troubleshooting

### Common Issues

**Container won't start:**
- Check logs: `aws lightsail get-container-log --service-name metamate-backend`
- Verify environment variables in Secrets Manager
- Ensure Docker image built correctly

**Frontend 404 errors:**
- Verify S3 bucket has files: `aws s3 ls s3://[bucket-name]/ --recursive`
- Check CloudFront origin configuration
- Ensure DNS records point to correct CloudFront distribution

**CORS errors:**
- Verify backend CORS_ORIGINS environment variable includes your domain
- Check CloudFlare SSL mode is "Full"
- Ensure api subdomain uses CloudFlare proxy (orange cloud)

## Next Steps After Migration

1. **Set up monitoring dashboards**
2. **Configure automated backups**
3. **Implement staging environment**
4. **Add custom error pages**
5. **Optimize container size based on usage**

---

**Ready to start?** Follow the steps above in order. The entire migration should take about 1-2 hours.

**Need help?** Check the logs and error messages carefully. Most issues are related to DNS propagation or environment variables.