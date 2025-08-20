# OpenMetaMate - AI-Powered PDF Data Extraction

Extract structured data from PDFs using AI (GPT-4, Claude, etc.) for systematic reviews and meta-analyses.

## Features

- 📄 **PDF Data Extraction**: Intelligent extraction using state-of-the-art LLMs
- 📊 **Customizable Coding Schemes**: Define your own data extraction templates
- 📥 **CSV Export**: Export results for statistical analysis
- ⚡ **Batch Processing**: Process multiple PDFs simultaneously
- 🎯 **High Accuracy**: Leverages advanced AI for precise data extraction
- 🔄 **Real-time Updates**: Live extraction progress and results

## Quick Start

### Prerequisites

- Docker and Docker Compose (for containerized deployment)
- OR:
  - Python 3.11 with uv
  - Node.js 18+ with pnpm

### Local Development

#### Option 1: Using Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/OpenMetaMate.git
cd OpenMetaMate

# 2. Set up your environment
cp .env.example .env
# Edit .env and add your LLM API key (OpenAI, Anthropic, etc.)

# 3. Build and start services
docker-compose up --build

# The application will be available at:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
```

To stop the services:
```bash
docker-compose down
```

#### Option 2: Manual Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/OpenMetaMate.git
cd OpenMetaMate

# 2. Set up environment variables
cp .env.example .env
# Edit .env and configure your LLM API key

# 3. Backend Setup (using uv for dependency management)
cd backend

# Install uv if not already installed
pip install uv

# Install dependencies and create virtual environment
uv sync

# Activate virtual environment and start backend
uv run uvicorn app.main:app --reload --port 8000

# 4. Frontend Setup (in a new terminal)
cd frontend

# Install dependencies
pnpm install

# Start development server
pnpm dev
```

Visit http://localhost:3000 to access the application.

## Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# LLM Configuration (Required)
LLM_API_URL=https://api.openai.com/v1  # Default to OpenAI
LLM_API_KEY=your-api-key-here        # OpenAI, Anthropic, OpenRouter or self-hosted LLM with vLLM or Ollama
LLM_MODEL=gpt-4o-2025-08-13          # Model to use (gpt-4o, claude-3-opus, etc)

# Backend Configuration
CORS_ORIGINS=http://localhost:3000   # Allowed CORS origins
MAX_FILE_SIZE_MB=10                  # Maximum PDF file size

# Frontend Configuration (automatically set in Docker)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Project Structure

```
OpenMetaMate/
├── assets/                 # Shared assets
│   └── codebook/          # Default coding schemes
│       └── default.json   # Comprehensive default template
├── backend/               # FastAPI backend
│   ├── app/              # Application code
│   │   ├── api/          # API routes
│   │   ├── core/         # Core configuration
│   │   ├── models/       # Pydantic models
│   │   └── services/     # Business logic
│   ├── pyproject.toml    # Python dependencies
│   ├── uv.lock          # Locked dependencies
│   └── Dockerfile       # Container configuration
├── frontend/             # Next.js frontend
│   ├── app/             # Next.js app directory
│   ├── components/      # React components
│   │   ├── ui/         # Reusable UI components
│   │   └── extraction/ # Extraction-specific components
│   ├── lib/            # Utilities and types
│   └── Dockerfile      # Container configuration
├── infra/              # Infrastructure as Code (AWS Lightsail + S3/CloudFront)
│   ├── main.tf         # Terraform main configuration
│   ├── variables.tf    # Input variables
│   ├── outputs.tf      # Output values
│   ├── terraform.tfvars.example  # Configuration template
│   └── deploy.sh       # Manual deployment script
├── docker-compose.yml  # Local development orchestration
└── .env.example       # Environment template
```

## Development

### Code Quality
```bash
# Backend - Linting and Formatting
cd backend
uv run ruff check .     # Check for code issues
uv run ruff format .    # Format code automatically

# Frontend - Linting and Formatting
cd frontend
pnpm lint        # Check for code issues
pnpm prettier    # Format code with Prettier

# Frontend - Dependency Management
pnpm audit       # Check for security vulnerabilities
pnpm outdated    # Check for outdated packages
pnpm update      # Update dependencies within semver ranges
pnpm dedupe      # Deduplicate dependencies
```

## Production Deployment

### AWS Lightsail + S3/CloudFront

OpenMetaMate includes production-ready infrastructure using:
- **Backend**: AWS Lightsail Container Service ($10-25/month)
- **Frontend**: S3 + CloudFront CDN (~$2/month)
- **Total Cost**: ~$12-27/month

#### Quick Production Setup

1. **Prerequisites**
   ```bash
   # Install required tools
   brew install awscli terraform
   aws configure  # Set up AWS credentials
   ```

2. **Deploy Infrastructure**
   ```bash
   cd infra/
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your domain and LLM API key
   
   terraform init
   terraform apply
   ```

3. **Setup GitHub Actions (Automatic Deployment)**
   - Go to GitHub repo → Settings → Secrets and variables → Actions
   - Add these repository secrets:
     - `AWS_ACCESS_KEY_ID` - Your AWS access key
     - `AWS_SECRET_ACCESS_KEY` - Your AWS secret key
     - `LLM_API_KEY` - Your LLM API key
     - `LLM_API_URL` - `https://api.openai.com/v1`
     - `LLM_MODEL` - `gpt-4o-2025-08-13`
     - `FRONTEND_BUCKET_NAME` - From terraform output
     - `CLOUDFRONT_DISTRIBUTION_ID` - From terraform output
     - `CUSTOM_DOMAIN` - Your domain name

4. **Automatic Deployment**
   - Every push to `main` branch automatically deploys both backend and frontend
   - GitHub Actions runs tests, builds, and deploys to AWS
   - Zero-downtime deployments with health checks

#### Manual Deployment

For step-by-step manual deployment, see [`plans/002-lightsail-migration-guide.md`](plans/002-lightsail-migration-guide.md).

### Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   CloudFlare    │    │   CloudFront     │    │  Lightsail      │
│   DNS + SSL     │───▶│   CDN + SSL      │───▶│  Container      │
│                 │    │                  │    │  (Backend API)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │     S3 Bucket    │
                       │  (Frontend SPA)  │
                       └──────────────────┘
```

### CI/CD Pipeline

The GitHub Actions workflow automatically:

1. **Tests**: Runs linting and type checking for both backend and frontend
2. **Backend Deploy**: Builds Docker image and deploys to Lightsail
3. **Frontend Deploy**: Builds Next.js app and deploys to S3/CloudFront  
4. **Health Checks**: Verifies deployment success with proper timeouts
5. **Cache Invalidation**: Updates CloudFront for immediate changes

## License

MIT License - see LICENSE file

---

Built with ❤️ using FastAPI, Next.js, and LLMs