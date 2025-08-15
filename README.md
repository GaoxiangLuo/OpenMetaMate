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
LLM_MODEL=gpt-5                   # Model to use (gpt-5, claude-4-opus, etc)

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
├── infra/              # Infrastructure as Code
│   └── terraform/      # Terraform configurations
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
## License

MIT License - see LICENSE file

---

Built with ❤️ using FastAPI, Next.js, and LLMs