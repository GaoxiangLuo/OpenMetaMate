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

1. **PDF Processing Factory**: Multiple processors (PyPDF, Docling, MinerU) with automatic fallback
   - Implementation: `backend/app/services/pdf_processor.py`
   - Factory selection based on configuration

2. **LLM Service Layer**: Abstracted LLM integration supporting multiple providers
   - Implementation: `backend/app/services/llm_service.py`
   - Supports OpenAI, Anthropic, OpenRouter, and self-hosted models

3. **Component Architecture**: Composition pattern with Radix UI primitives
   - UI components: `frontend/components/ui/`
   - Domain components: `frontend/components/extraction/`

4. **Configuration Management**: Environment-based with validation
   - Backend: `backend/app/core/config.py` using Pydantic
   - Frontend: `frontend/lib/config.ts` with TypeScript interfaces

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

## Testing Approach

Currently, the project doesn't have automated tests. When adding tests:
- Backend: Use pytest with async support
- Frontend: Use Jest + React Testing Library
- API: Test with FastAPI TestClient

## Deployment

### Local Development
```bash
docker-compose up  # Starts both services
```

### Production (AWS)
```bash
cd infra/
terraform init
terraform apply  # Deploys to AWS Lightsail + S3/CloudFront
```

## Important File Locations

- API routes: `backend/app/api/routes/extraction.py`
- LLM service: `backend/app/services/llm_service.py`
- PDF processors: `backend/app/services/pdf_processor.py`
- Frontend API client: `frontend/lib/api.ts`
- UI components: `frontend/components/ui/`
- Extraction components: `frontend/components/extraction/`
- Configuration: `backend/app/core/config.py`, `frontend/lib/config.ts`