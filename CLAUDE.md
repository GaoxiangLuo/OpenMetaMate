# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OpenMetaMate is an AI-powered PDF data extraction platform for systematic reviews and meta-analyses. It uses a microservices architecture with a FastAPI backend and Next.js frontend.

## Essential Commands

### Backend Development
```bash
# Start development server
uv run uvicorn app.main:app --reload --port 8000

# Code quality checks (run before committing)
uv run ruff check .     # Linting
uv run ruff format .    # Auto-format code
```

### Frontend Development
```bash
# Start development server
pnpm dev

# Code quality checks (run before committing)
pnpm lint             # ESLint
pnpm typecheck        # TypeScript type checking
pnpm prettier         # Format code
pnpm prettier:check   # Check formatting

# Build for production
pnpm build
```

### Full-Stack Development
```bash
# Start both frontend and backend
docker-compose up

# Environment setup required: Create .env file with:
# LLM_API_KEY=your-api-key
# LLM_API_URL=https://api.openai.com/v1
# LLM_MODEL=gpt-4o-2025-08-13
# BACKUP_LLM_API_KEY=your-backup-api-key  # Optional: for automatic failover
# CORS_ORIGINS=http://localhost:3000
# MAX_FILE_SIZE_MB=10
# PDF_PROCESSOR=pypdf
# MINERU_API_KEY=your-mineru-key  # Optional: for advanced PDF extraction with MinerU
# AWS_S3_TEMP_BUCKET=your-bucket  # Required if using MinerU
```

## Architecture Overview

### Service Architecture
- **Backend**: FastAPI service at `backend/` (port 8000)
  - Routes in `app/api/routes/` - API endpoints for extraction and health checks
  - Services in `app/services/` - LLM integration and PDF processing logic
  - Models in `app/models/` - Pydantic schemas for request/response validation
  
- **Frontend**: Next.js app at `frontend/` (port 3000)
  - App Router pages in `app/` - file-based routing with React Server Components
  - Components in `components/` - UI components using Radix UI + shadcn/ui
  - API client in `lib/api.ts` - centralized backend communication

### Key Design Patterns

1. **PDF Processing Factory**: Multiple processors (PyPDF, MinerU) with automatic fallback
   - Implementation: `backend/app/services/pdf_processor.py`, `backend/app/services/mineru_processor.py`
   - **MinerU Integration** (optional): Advanced cloud-based PDF extraction
     - Features: OCR for scanned PDFs, formula recognition, table extraction
     - Free tier: 2000 pages/day at highest priority
     - Requires: `MINERU_API_KEY` and `AWS_S3_TEMP_BUCKET`
     - Automatic fallback to PyPDF on failure (network issues, quota exceeded, etc.)
     - S3 temporary storage: `backend/app/services/s3_temp_storage.py`
   - **Fallback Logic**: If MinerU configured, try MinerU → fallback to PyPDF. Otherwise, PyPDF only

2. **LLM Service Layer**: Abstracted LLM integration with automatic failover
   - Implementation: `backend/app/services/llm_service.py`
   - Supports OpenAI, Anthropic, OpenRouter, and self-hosted models
   - **Automatic Failover**: Configure `BACKUP_LLM_API_KEY` for redundancy
   - Failover triggers: HTTP 429 (rate limit/quota), 5xx (server errors)
   - Same URL/model for backup, only API key differs

3. **Component Architecture**: Composition pattern with Radix UI primitives
   - UI components: `frontend/components/ui/`
   - Domain components: `frontend/components/extraction/`

4. **Configuration Management**: Environment-based with validation
   - Backend: `backend/app/core/config.py` using Pydantic
   - Frontend: `frontend/lib/config.ts` with TypeScript interfaces

5. **Stage-Based Logging**: 6-stage pipeline logging for debugging
   - STAGE 1: Request validation (file type, size)
   - STAGE 2: Coding scheme parsing
   - STAGE 3: PDF text extraction
   - STAGE 4: LLM extraction (with primary/backup API tracking)
   - STAGE 5: Output post-processing/transformation
   - STAGE 6: Response complete
   - Use `grep "STAGE"` or `grep "❌"` to quickly identify failure points

## Development Guidelines

### Backend Development
- Use UV package manager for Python dependencies
- Follow async/await patterns for all I/O operations
- Add type hints to all functions
- Use Pydantic models for all API inputs/outputs
- Handle errors with custom exceptions in `app/core/exceptions.py`

### Frontend Development
- Use PNPM for package management
- Follow Next.js App Router conventions
- Use TypeScript with strict mode enabled
- Style with Tailwind CSS utility classes
- Component structure: Radix UI for behavior, shadcn/ui for styling

### API Development
- All endpoints return structured JSON responses
- Use FastAPI dependency injection for services
- Implement rate limiting with SlowAPI
- Document endpoints with OpenAPI schemas

## Testing & Quality Assurance

**Current State**: The project focuses on code quality through linting and type checking rather than unit tests.

**Quality Checks (run automatically in CI/CD)**:
- Backend: `uv run ruff check .` (linting) + `uv run ruff format --check .` (formatting)
- Frontend: `pnpm lint` (ESLint) + `pnpm prettier:check` (formatting) + `pnpm typecheck` (TypeScript)

**When adding tests** (future):
- Backend: Use pytest with async support (`uv pip install pytest pytest-asyncio httpx`)
- Frontend: Use Jest + React Testing Library
- API: Test with FastAPI TestClient
- CI/CD: Uncomment test steps in `.github/workflows/deploy.yml`

**Production Deployment Testing**:
- Health checks: Backend `/health` endpoint monitoring
- Deployment verification: Automatic rollback on health check failures
- Smoke testing: Manual verification of core extraction functionality

## Deployment

### Local Development
```bash
docker-compose up  # Starts both services
```

### Production (AWS Lightsail + S3/CloudFront)

**Infrastructure**: Production deployment uses Terraform for Infrastructure as Code:
- **Backend**: AWS Lightsail Container Service (Docker-based, $10-25/month)
- **Frontend**: S3 static hosting + CloudFront CDN (~$2/month)
- **DNS**: CloudFlare DNS management
- **SSL**: AWS ACM certificates (free)
- **Cost**: ~$12-27/month total

**Manual Deployment**:
```bash
cd infra/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your domain and LLM API key
terraform init
terraform apply  # Deploys complete infrastructure
```

**Automatic Deployment (CI/CD)**:
- GitHub Actions workflow in `.github/workflows/deploy.yml`
- Triggers on push to `main` branch
- Runs tests → deploys backend → deploys frontend → notifies
- Zero-downtime deployments with health checks

### CI/CD Pipeline

The GitHub Actions workflow automatically:
1. **Tests**: Runs linting (ruff, eslint) and type checking for both services
2. **Backend Deploy**: Builds Docker image and pushes to Lightsail Container Service
3. **Frontend Deploy**: Builds Next.js static export and deploys to S3/CloudFront
4. **Health Checks**: Waits for deployment completion with proper timeouts
5. **Cache Invalidation**: Updates CloudFront for immediate content updates

**Required GitHub Secrets** (for automatic deployment):
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` - AWS credentials
- `LLM_API_KEY`, `LLM_API_URL`, `LLM_MODEL` - LLM configuration
- `FRONTEND_BUCKET_NAME`, `CLOUDFRONT_DISTRIBUTION_ID` - From Terraform outputs
- `CUSTOM_DOMAIN`, `BUCKET_SUFFIX` - Domain and infrastructure naming

**Workflow Details**:
- **Triggers**: Push to `main` branch or manual dispatch
- **Parallel Jobs**: Backend and frontend tests run simultaneously
- **Sequential Deploy**: Backend deploys first, then frontend (depends on backend URL)
- **Deployment Region**: us-east-1 (required for CloudFront ACM certificates)
- **Container Config**: Includes all LLM environment variables and CORS settings
- **Health Monitoring**: 10-minute timeout with 30-second interval health checks
- **Frontend Build**: Uses Next.js static export (`output: "export"` in next.config.mjs)

## Important File Locations

**Backend Core**:
- API routes: `backend/app/api/routes/extraction.py`
- LLM service: `backend/app/services/llm_service.py`
- PDF processors: `backend/app/services/pdf_processor.py`, `backend/app/services/mineru_processor.py`
- S3 temporary storage: `backend/app/services/s3_temp_storage.py`
- Configuration: `backend/app/core/config.py`

**Frontend Core**:
- API client: `frontend/lib/api.ts`
- Configuration: `frontend/lib/config.ts`
- UI components: `frontend/components/ui/`
- Extraction components: `frontend/components/extraction/`

**Infrastructure & Deployment**:
- Terraform main: `infra/main.tf`
- Terraform variables: `infra/variables.tf`, `infra/terraform.tfvars`
- GitHub Actions: `.github/workflows/deploy.yml`
- Docker configs: `backend/Dockerfile`, `frontend/Dockerfile`
- Environment: `.env` (local), `infra/terraform.tfvars` (production)

**Configuration Files**:
- Package management: `backend/pyproject.toml`, `frontend/package.json`
- Next.js config: `frontend/next.config.mjs` (static export enabled)
- Docker orchestration: `docker-compose.yml`