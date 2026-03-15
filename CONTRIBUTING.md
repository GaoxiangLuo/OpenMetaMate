# Contributing to OpenMetaMate

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Agent-Driven Development

This project is built and maintained using AI code agents. We recommend contributors do the same — it's faster and produces more consistent code.

### How We Use Agents

- **[CLAUDE.md](CLAUDE.md)** — Context file for [Claude Code](https://claude.ai/code). Loaded automatically when Claude Code opens this repo. Contains architecture, commands, design patterns, and file locations.
- **[AGENTS.md](AGENTS.md)** — General agent guidelines. Works with Claude Code, Cursor, Windsurf, Copilot, and other AI coding assistants. Covers coding style, naming conventions, and commit standards.
- **[plans/](plans/)** — Architecture decision records. Before implementing a feature, we write a plan document that the agent follows. This keeps complex changes focused and well-documented.

### Recommended Workflow

1. **Open the repo in an agent-enabled editor** (Claude Code, Cursor, etc.)
2. The agent automatically reads `CLAUDE.md` and/or `AGENTS.md` for context
3. For larger features, write a plan in `plans/` first, then have the agent implement it
4. The agent runs code quality checks before committing

Any AI coding assistant will work — the `CLAUDE.md` and `AGENTS.md` files provide the context it needs to write code that fits this project.

## Development Setup

### Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Node.js 18+ with [pnpm](https://pnpm.io/)
- Docker and Docker Compose (for full-stack development)

### Getting Started

```bash
# Clone the repository
git clone https://github.com/GaoxiangLuo/OpenMetaMate.git
cd OpenMetaMate

# Set up environment
cp .env.example .env
# Edit .env with your LLM API key

# Option A: Docker (recommended)
docker-compose up --build

# Option B: Run services separately (each in its own terminal)
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
# In a new terminal:
cd frontend && pnpm install && pnpm dev
```

## CI Checks (Required)

These checks run on every push and pull request. **All must pass before merging.** This applies to maintainers and contributors alike — no exceptions.

| Check | Command | What it does |
|-------|---------|-------------|
| Backend lint | `cd backend && uv run ruff check .` | Catches code issues |
| Backend format | `cd backend && uv run ruff format --check .` | Enforces consistent formatting |
| Frontend lint | `cd frontend && pnpm lint` | ESLint checks |
| Frontend format | `cd frontend && pnpm prettier:check` | Prettier formatting |

Run them all locally before pushing:

```bash
# Backend
cd backend
uv run ruff check .          # Lint
uv run ruff format .         # Auto-fix formatting

# Frontend
cd frontend
pnpm lint                    # ESLint
pnpm prettier                # Auto-fix formatting
```

## Coding Style

### Python (Backend)
- Ruff enforces PEP 8 with a 100-character line limit
- Use `async/await` for all I/O operations
- Add type hints to all functions
- Use Pydantic models for API inputs/outputs

### TypeScript (Frontend)
- Prettier defaults for formatting
- PascalCase for components, camelCase for hooks/utilities
- Tailwind CSS utility classes for styling
- Radix UI primitives + shadcn/ui for components

## Pull Request Process

1. **Fork the repository** and create a feature branch from `main`
2. **Make your changes** — using a code agent is recommended but not required
3. **Pass all CI checks** (see [CI Checks](#ci-checks-required) above)
4. **Commit with a clear message** using [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` for new features
   - `fix:` for bug fixes
   - `chore:` for maintenance tasks
   - Keep the subject under 72 characters
5. **Open a pull request** with:
   - A summary of what changed and why
   - Screenshots for UI changes
   - Any new environment variables or configuration needed

## Project Architecture

```
Frontend (Next.js)  ->  Backend API (FastAPI)  ->  LLM Service (OpenAI/Gemini/etc.)
                                               ->  PDF Processor (PyPDF / MinerU)
```

**Key files to know:**
- `backend/app/services/llm_service.py` — LLM integration with automatic failover
- `backend/app/services/pdf_processor.py` — PDF processing with MinerU/PyPDF fallback
- `backend/app/api/routes/extraction.py` — Main extraction API endpoint
- `frontend/app/page.tsx` — Main application page
- `frontend/lib/api.ts` — Backend API client

For the full architecture, design patterns, and file map, see [CLAUDE.md](CLAUDE.md).

## Reporting Issues

- Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md) for bugs
- Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md) for suggestions

## Questions?

Open a [GitHub Discussion](https://github.com/GaoxiangLuo/OpenMetaMate/discussions) or file an issue.
