#!/bin/bash

# ============================================
# MetaMate Deployment Script
# ============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REGION=${AWS_REGION:-us-east-2}
APP_NAME="metamate"
ENVIRONMENT=${ENVIRONMENT:-prod}

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "ℹ $1"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install: brew install awscli"
    fi
    
    # Check Terraform
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform not found. Please install: brew install terraform"
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker Desktop"
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Run: aws configure"
    fi
    
    print_success "All prerequisites met"
}

# Initialize Terraform
init_terraform() {
    print_info "Initializing Terraform..."
    cd infra/
    
    if [ ! -f terraform.tfvars ]; then
        print_error "terraform.tfvars not found. Copy terraform.tfvars.example and add your values"
    fi
    
    terraform init
    print_success "Terraform initialized"
}

# Deploy infrastructure
deploy_infrastructure() {
    print_info "Deploying infrastructure..."
    
    # Plan first
    terraform plan -out=tfplan
    
    # Ask for confirmation
    read -p "Do you want to apply these changes? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        print_warning "Deployment cancelled"
        exit 0
    fi
    
    # Apply
    terraform apply tfplan
    rm tfplan
    
    print_success "Infrastructure deployed"
}

# Build and push backend
deploy_backend() {
    print_info "Building backend Docker image..."
    
    cd ../backend/
    
    # Build image
    docker build -t ${APP_NAME}-backend:latest .
    
    print_info "Pushing to Lightsail registry..."
    
    # Get container service name from Terraform
    cd ../infra/
    SERVICE_NAME=$(terraform output -raw container_service_name)
    
    # Push image
    aws lightsail push-container-image \
        --region ${REGION} \
        --service-name ${SERVICE_NAME} \
        --label backend \
        --image ${APP_NAME}-backend:latest
    
    # Get the pushed image name
    IMAGE=$(aws lightsail get-container-images \
        --region ${REGION} \
        --service-name ${SERVICE_NAME} \
        --query 'containerImages[0].image' \
        --output text)
    
    print_info "Deploying container with image: ${IMAGE}"
    
    # Create container config
    cat > /tmp/containers.json <<EOF
{
    "api": {
        "image": "${IMAGE}",
        "ports": {
            "8000": "HTTP"
        },
        "environment": {
            "PORT": "8000",
            "AWS_REGION": "${REGION}"
        }
    }
}
EOF
    
    # Create endpoint config
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
    
    # Deploy
    aws lightsail create-container-service-deployment \
        --region ${REGION} \
        --service-name ${SERVICE_NAME} \
        --containers file:///tmp/containers.json \
        --public-endpoint file:///tmp/endpoint.json
    
    # Clean up temp files
    rm /tmp/containers.json /tmp/endpoint.json
    
    print_success "Backend deployed"
    
    # Wait for deployment
    print_info "Waiting for deployment to complete (this may take 5-10 minutes)..."
    
    while true; do
        STATE=$(aws lightsail get-container-services \
            --region ${REGION} \
            --service-name ${SERVICE_NAME} \
            --query 'containerServices[0].state' \
            --output text)
        
        if [ "$STATE" == "READY" ]; then
            break
        elif [ "$STATE" == "DEPLOYING" ]; then
            echo -n "."
            sleep 10
        else
            print_error "Deployment failed. State: $STATE"
        fi
    done
    
    echo ""
    print_success "Backend is ready"
    
    # Get backend URL
    BACKEND_URL=$(terraform output -raw backend_url)
    print_info "Backend URL: ${BACKEND_URL}"
}

# Build and deploy frontend
deploy_frontend() {
    print_info "Building frontend..."
    
    cd ../frontend/
    
    # Get backend URL from Terraform
    cd ../infra/
    BACKEND_URL=$(terraform output -raw backend_api_url)
    BUCKET_NAME=$(terraform output -raw frontend_bucket_name)
    CDN_ID=$(terraform output -raw cloudfront_distribution_id 2>/dev/null || echo "")
    
    cd ../frontend/
    
    # Set environment variable
    export NEXT_PUBLIC_API_URL=${BACKEND_URL}
    
    # Install dependencies
    print_info "Installing dependencies..."
    pnpm install
    
    # Build
    print_info "Building frontend..."
    pnpm build
    
    # Export static files
    print_info "Exporting static files..."
    pnpm next export -o out
    
    # Deploy to S3
    print_info "Deploying to S3..."
    
    # Upload with cache headers for assets
    aws s3 sync out/ s3://${BUCKET_NAME}/ \
        --delete \
        --region ${REGION} \
        --cache-control "public, max-age=31536000, immutable" \
        --exclude "*.html" \
        --exclude "_next/data/*" \
        --exclude "_next/static/chunks/pages/*"
    
    # Upload HTML files with no-cache
    aws s3 sync out/ s3://${BUCKET_NAME}/ \
        --delete \
        --region ${REGION} \
        --cache-control "public, max-age=0, must-revalidate" \
        --exclude "*" \
        --include "*.html" \
        --include "_next/data/*" \
        --include "_next/static/chunks/pages/*"
    
    print_success "Frontend deployed to S3"
    
    # Invalidate CloudFront if enabled
    if [ ! -z "$CDN_ID" ] && [ "$CDN_ID" != "N/A" ]; then
        print_info "Invalidating CloudFront cache..."
        aws cloudfront create-invalidation \
            --distribution-id ${CDN_ID} \
            --paths "/*" \
            --query 'Invalidation.Id' \
            --output text
        print_success "CloudFront cache invalidated"
    fi
    
    # Get frontend URL
    cd ../infra/
    FRONTEND_URL=$(terraform output -raw frontend_custom_url 2>/dev/null || terraform output -raw frontend_cloudfront_url 2>/dev/null || terraform output -raw frontend_s3_url)
    print_info "Frontend URL: ${FRONTEND_URL}"
}

# Show deployment info
show_info() {
    print_info "Deployment Information:"
    echo "========================"
    
    cd infra/
    
    echo -e "\nFrontend:"
    terraform output frontend_custom_url 2>/dev/null || terraform output frontend_cloudfront_url 2>/dev/null || terraform output frontend_s3_url
    
    echo -e "\nBackend:"
    terraform output backend_api_url
    
    echo -e "\nCloudFront Distribution ID:"
    terraform output cloudfront_distribution_id 2>/dev/null || echo "N/A"
    
    echo -e "\nEstimated Costs:"
    terraform output estimated_monthly_cost
    
    echo -e "\nDNS Configuration:"
    terraform output dns_configuration
}

# Main deployment flow
main() {
    echo "============================================"
    echo "MetaMate Deployment Script"
    echo "============================================"
    echo ""
    
    # Parse arguments
    case "${1:-all}" in
        init)
            check_prerequisites
            init_terraform
            ;;
        infra)
            check_prerequisites
            init_terraform
            deploy_infrastructure
            show_info
            ;;
        backend)
            deploy_backend
            ;;
        frontend)
            deploy_frontend
            ;;
        all)
            check_prerequisites
            init_terraform
            deploy_infrastructure
            deploy_backend
            deploy_frontend
            show_info
            ;;
        info)
            show_info
            ;;
        destroy)
            cd infra/
            terraform destroy
            ;;
        *)
            echo "Usage: $0 [init|infra|backend|frontend|all|info|destroy]"
            echo ""
            echo "Commands:"
            echo "  init     - Initialize Terraform"
            echo "  infra    - Deploy infrastructure only"
            echo "  backend  - Deploy backend only"
            echo "  frontend - Deploy frontend only"
            echo "  all      - Deploy everything (default)"
            echo "  info     - Show deployment information"
            echo "  destroy  - Destroy all infrastructure"
            exit 1
            ;;
    esac
    
    echo ""
    print_success "Deployment complete!"
}

# Run main function
main "$@"