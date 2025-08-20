# MetaMate Lightsail Migration Guide

## Quick Overview
Migrating MetaMate from EC2 to a more scalable and cost-effective infrastructure:
- **Backend**: AWS Lightsail Container Service ($10-25/month)
- **Frontend**: S3 + CloudFront CDN (< $2/month)
- **Domain**: CloudFlare DNS (existing)
- **Total Cost**: ~$12-27/month (vs current EC2 costs)

## ⚠️ Important Region Choice

**CloudFront Requirement**: CloudFront requires ACM certificates to be in us-east-1. You have two options:
- **Option A (Recommended)**: All resources in us-east-1 (simpler management)
- **Option B**: Mixed regions (certificate in us-east-1, everything else in us-east-2)

This guide uses **us-east-1 for everything** for simplicity.

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

#### 1.3 Install AWS Lightsail CLI Plugin
```bash
# Install the lightsailctl plugin (required for pushing Docker images)
mkdir -p ~/.local/bin
curl "https://s3.us-west-2.amazonaws.com/lightsailctl/latest/linux-amd64/lightsailctl" \
  -o "$HOME/.local/bin/lightsailctl"
chmod +x "$HOME/.local/bin/lightsailctl"
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
lightsailctl --version

# Add to your shell profile to persist PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc  # or ~/.zshrc
```

#### 1.4 Create Terraform State Bucket
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

**Note**: If you get "BucketAlreadyOwnedByYou" error, the bucket exists from a previous attempt. Just run the versioning command.

**If switching regions**: Delete the old bucket to avoid conflicts:
```bash
# Delete old bucket (if switching from us-east-2 to us-east-1)
aws s3 rm s3://metamate-terraform-state --recursive --region us-east-2
aws s3api delete-bucket --bucket metamate-terraform-state --region us-east-2
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

# If you get errors about missing Docker images, that's expected
# Continue to Step 4 to build and push the images
```

**⚠️ If terraform apply is interrupted (power outage, etc.):**
```bash
# terraform apply is safe to re-run
terraform plan  # Check what needs to be done
terraform apply # Continue where it left off

# If container service exists but terraform doesn't know about it:
terraform import aws_lightsail_container_service.backend metamate-backend
```

**Common Issues at this Step:**
- **ACM Certificate Validation**: You'll need to add DNS validation records (covered in Step 6.3)
- **Container Deployment Failed**: Expected if no Docker image exists yet (fixed in Step 4)
- **DNS Validation Timeout**: DNS records take 2-10 minutes to propagate
- **Lightsail Container Already Exists**: Use `terraform import` command above

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

#### 4.1 Verify Container Service Created
```bash
cd infra/
# Check if container service was created successfully
terraform output container_service_name
terraform output container_service_state

# Should show: metamate-backend (name) and READY (state)
```

#### 4.2 Build Backend Docker Image
```bash
# CRITICAL: Build from project root directory (not backend/)
cd /path/to/OpenMetaMate  # Go to project root

# Build the Docker image with correct context
docker build -f backend/Dockerfile -t metamate-backend:latest .

# The Dockerfile paths are designed for root directory context
```

#### 4.3 Push to Lightsail Registry
```bash
# Get the container service name
cd infra/
SERVICE_NAME=$(terraform output -raw container_service_name)

# Ensure lightsailctl is in PATH (from Step 1.3)
export PATH="$HOME/.local/bin:$PATH"

# Push image to Lightsail
aws lightsail push-container-image \
  --region us-east-1 \
  --service-name ${SERVICE_NAME} \
  --label backend \
  --image metamate-backend:latest

# The output will show: Refer to this image as ":metamate-backend.backend.1"
# This exact name must match what's in your Terraform configuration
```

#### 4.4 Update Container Deployment (if needed)
```bash
# Re-run terraform apply to deploy the pushed image
terraform apply

# Should show container deployment successful
# Check deployment status
aws lightsail get-container-services \
  --region us-east-1 \
  --service-name ${SERVICE_NAME} \
  --query 'containerServices[0].state' \
  --output text
```

#### 4.5 Verify Backend Health
```bash
# Get the backend URL
BACKEND_URL=$(terraform output -raw backend_url)
echo "Backend URL: $BACKEND_URL"

# Test health endpoint (should return JSON with status: healthy)
curl ${BACKEND_URL%/}/health

# Example output:
# {"status":"healthy","timestamp":"...","service":"MetaMate Extraction API"...}
```

#### 4.4 Deploy Container
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

#### 4.5 Wait for Deployment
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

#### 5.1 Install Frontend Dependencies
```bash
cd ../frontend/

# Install pnpm if not already available
npm install -g pnpm

# Install dependencies
pnpm install
```

#### 5.2 Build Frontend (Critical: Correct API URL)
```bash
# Option A: Use Custom Domain (requires CloudFlare proxy setup)
export NEXT_PUBLIC_API_URL=https://api.metamate.online

# Option B: Use Direct Lightsail URL (recommended, bypasses proxy issues)
cd ../infra/
DIRECT_URL=$(terraform output -raw backend_url | sed 's|https://https://||')
export NEXT_PUBLIC_API_URL=https://${DIRECT_URL}

# Build frontend with correct API URL
cd ../frontend/
rm -rf .next  # Clean previous builds
NODE_ENV=production pnpm build

# Verify the API URL is correct in build
grep -r "apiUrl" .next/server/app/page.js | head -1
```

#### 5.3 Deploy to S3
```bash
# Get bucket name
cd ../infra/
BUCKET_NAME=$(terraform output -raw frontend_bucket_name)

# Deploy static assets and HTML files
cd ../frontend/
aws s3 sync .next/static s3://${BUCKET_NAME}/_next/static \
  --delete \
  --cache-control "public, max-age=31536000, immutable"

aws s3 sync out s3://${BUCKET_NAME}/ \
  --delete \
  --cache-control "public, max-age=0, must-revalidate"
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

#### 6.3 Add ACM Certificate Validation Records (if using custom domain with CloudFront)

**Option A: Via CloudFlare Dashboard**
When Terraform creates an ACM certificate for CloudFront, you'll need to add validation records:
1. Check Terraform output or AWS Console for the validation CNAME records
2. Add each validation record in CloudFlare:
   - Type: `CNAME`
   - Name: `_[validation-string]` (e.g., `_d4fa2c195a2dd1a4860f74b2cfd80b58`)
   - Target: `_[validation-target].acm-validations.aws`
   - Proxy status: **DNS only** (gray cloud)

**Option B: Via CloudFlare API**
```bash
# Set your CloudFlare credentials
export CLOUDFLARE_API_TOKEN="your-api-token"
export CLOUDFLARE_ZONE_ID="your-zone-id"

# Get validation records from Terraform
cd infra/
terraform show -json | jq '.values.root_module.resources[] | select(.type == "aws_acm_certificate") | .values.domain_validation_options'

# For each validation record, add to CloudFlare:
curl -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{
    "type": "CNAME",
    "name": "[validation-name-from-terraform]",
    "content": "[validation-target-from-terraform]",
    "proxied": false
  }'
```

Wait for validation to complete (usually 2-10 minutes), then continue with terraform apply.

#### 6.4 Add DNS Records

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
- Proxy: **OFF** (Gray cloud) - **Important!**
- TTL: Auto

**⚠️ API Proxy Setting**: 
- **Recommended**: Use Proxy OFF (gray cloud) and direct Lightsail URL
- **Alternative**: Use Proxy ON (orange cloud) but requires CloudFlare SSL configuration

#### 6.5 SSL/TLS Settings
1. Go to **SSL/TLS** → **Overview**
2. Set encryption mode to **"Full"**

### Step 7: Verify Deployment (5 minutes)

#### 7.1 Test Backend Health
```bash
# Test direct Lightsail URL first
BACKEND_URL=$(terraform output -raw backend_url | sed 's|https://https://||')
curl https://${BACKEND_URL}/health

# Should return JSON: {"status":"healthy",...}
```

#### 7.2 Test Frontend
```bash
# Test CloudFront distribution
CLOUDFRONT_URL=$(terraform output -raw frontend_cloudfront_url)
curl -I ${CLOUDFRONT_URL}

# Test custom domain (after DNS propagates)
curl -I https://metamate.online
```

#### 7.3 End-to-End Functional Test
1. **Open** https://metamate.online in browser
2. **Upload** a PDF file
3. **Verify** extraction starts (not "Processing..." forever)
4. **Check** extraction results appear
5. **Monitor** backend logs for API requests:
   ```bash
   aws lightsail get-container-log --service-name metamate-backend --container-name api
   ```

#### 7.4 Final Validation Checklist
- [ ] Frontend loads at https://metamate.online
- [ ] Backend responds at direct Lightsail URL
- [ ] PDF upload triggers API requests (visible in logs)
- [ ] LLM extraction completes successfully
- [ ] Results display with confidence scores
- [ ] CSV export works

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

### Critical Deployment Issues

#### 1. Container Deployment Fails: "LLM_API_KEY required"
**Problem**: Backend container fails with missing LLM_API_KEY
```bash
# Check logs
aws lightsail get-container-log --service-name metamate-backend --container-name api
```
**Solution**: Ensure terraform configuration includes LLM environment variables:
```hcl
environment = {
  LLM_API_KEY = var.llm_api_key
  LLM_API_URL = var.llm_api_url  
  LLM_MODEL   = var.llm_model
  # ... other vars
}
```

#### 2. Frontend Shows "Failed to fetch" 
**Problem**: API requests not reaching backend
**Debugging Steps**:
```bash
# 1. Check browser console Network tab for failed requests
# 2. Test backend directly
curl https://[your-lightsail-url]/health

# 3. Check DNS resolution
nslookup api.metamate.online

# 4. Verify CORS headers
curl -H "Origin: https://metamate.online" https://[backend-url]/health
```

**Solutions**:
- **Option A**: Use direct Lightsail URL in frontend build:
  ```bash
  NEXT_PUBLIC_API_URL=https://[lightsail-url] pnpm build
  ```
- **Option B**: Fix CloudFlare proxy (turn OFF proxy for API subdomain)

#### 3. DNS Validation Records Not Working
**Problem**: ACM certificate validation fails
**Check DNS propagation**:
```bash
# Test each validation record
nslookup -type=CNAME _[validation-string].metamate.online 8.8.8.8
```
**Solution**: 
- Records take 2-10 minutes to propagate
- Ensure CloudFlare proxy is OFF (gray cloud) for validation records
- Use CloudFlare API if dashboard doesn't work

#### 4. CloudFront SSL Certificate Error
**Problem**: "SSL certificate doesn't exist, isn't in us-east-1"
**Solution**: ACM certificates for CloudFront MUST be in us-east-1
```bash
# Check certificate region
terraform show | grep "provider.*aws"
# Should show aws.us_east_1 for certificate resources
```

#### 5. S3 Logs Bucket ACL Error
**Problem**: CloudFront can't write to logs bucket
**Solution**: Add ACL configuration to Terraform:
```hcl
resource "aws_s3_bucket_ownership_controls" "logs" {
  bucket = aws_s3_bucket.logs.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "logs" {
  bucket = aws_s3_bucket.logs.id
  acl    = "log-delivery-write"
  depends_on = [aws_s3_bucket_ownership_controls.logs]
}
```

### Common Issues

**Container won't start:**
- Check logs: `aws lightsail get-container-log --service-name metamate-backend --container-name api`
- Verify environment variables include LLM_API_KEY
- Ensure Docker image built from project root directory

**"Processing..." Forever:**
- Check browser Network tab for failed API requests
- Verify frontend API URL matches backend URL
- Rebuild frontend if API URL changed

**DNS Issues:**
- DNS records take 2-10 minutes to propagate globally
- Test with `nslookup [domain] 8.8.8.8` to check propagation
- CloudFlare proxy OFF for validation records, optional for main domains

**CloudFlare API Proxy Issues:**
- If using api.metamate.online with proxy ON, set SSL mode to "Full"
- **Recommended**: Use proxy OFF and direct Lightsail URL for API
- Avoid mixing SSL termination between CloudFlare and Lightsail

## Next Steps After Migration

1. **Set up monitoring dashboards**
2. **Configure automated backups**
3. **Implement staging environment**
4. **Add custom error pages**
5. **Optimize container size based on usage**

## 🔑 Critical Success Factors

### 1. Region Consistency
- **Use us-east-1 for everything** (ACM certificates for CloudFront must be in us-east-1)
- Don't mix regions unless you understand the SSL certificate implications

### 2. Docker Build Context
- **Always build from project root**: `docker build -f backend/Dockerfile .`
- The Dockerfile paths expect root directory context

### 3. Frontend API Configuration  
- **Environment variables are baked in at build time**
- Use direct Lightsail URL to avoid CloudFlare proxy issues
- Clean builds when changing API URLs: `rm -rf .next && NEXT_PUBLIC_API_URL=... pnpm build`

### 4. DNS Validation
- **ACM validation records**: Use CloudFlare dashboard, proxy OFF (gray cloud)
- **Main DNS records**: Frontend proxy OFF, API proxy OFF (recommended)
- Allow 2-10 minutes for DNS propagation

### 5. Container Deployment
- **Push image before terraform apply**: Terraform expects the image to exist
- **LLM environment variables**: Must be configured in Terraform container environment
- **Health checks**: Always verify `/health` endpoint responds

---

**Ready to start?** Follow the steps above in order. The entire migration should take about 1-2 hours.

**Need help?** Check the troubleshooting section above. Most issues are resolved by proper API URL configuration and DNS setup.