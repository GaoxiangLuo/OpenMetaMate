# Repository Guidelines

OpenMetaMate combines a FastAPI backend with a Next.js frontend for AI-driven PDF extraction. Use these guardrails to keep contributions consistent.

## Project Structure & Module Organization
- `backend/app/api` exposes FastAPI routers; `backend/app/core`, `models`, and `services` hold config, schemas, and LLM/PDF orchestration.
- `frontend/app` implements App Router entrypoints, `frontend/components/ui` stores reusable primitives, `frontend/components/extraction` manages domain flows, and `frontend/lib` centralizes API calls and shared types.
- Assets reside in `assets/codebook`, infrastructure lives in `infra/`, and `docker-compose.yml` orchestrates full-stack runs. Add tests beside features (`backend/tests/...`, `frontend/__tests__/...`) to keep ownership clear.

## Build, Test, and Development Commands
```bash
uv sync                                           # install backend deps via uv
uv run uvicorn app.main:app --reload --port 8000 # backend dev server
uv run ruff check . && uv run ruff format --check .
pnpm install && pnpm dev                         # frontend dev server
pnpm lint && pnpm typecheck && pnpm prettier:check
docker-compose up                                # launch both services locally
```
Configure env vars with `.env` (see `.env.example`) and never commit secrets.

## Coding Style & Naming Conventions
- Python: Ruff enforces PEP 8 with a 100-character line limit; keep modules snake_case, adopt async/await for I/O, and annotate functions.
- TypeScript/React: Follow Prettier defaults, PascalCase components, camelCase hooks/utilities, and Tailwind utility classes. Co-locate component helpers unless shared.

## Testing Guidelines
CI currently runs linting and type-checking; treat failures as blockers. When adding automated tests, use `pytest` with `pytest-asyncio` under `backend/tests/` and React Testing Library (Vitest/Jest) under `frontend/__tests__/`. Keep filenames descriptive (`test_extraction_service.py`, `extraction-form.test.tsx`) and focus coverage on PDF parsing, LLM fallbacks, and API contracts. Re-enable the commented test stages in `.github/workflows/deploy.yml` once suites are in place.

## Commit & Pull Request Guidelines
Prefer Conventional Commits (`feat:`, `fix:`, `chore:`) in line with the current history. Keep subjects under 72 characters and add body context for riskier changes. Pull requests must include a problem summary, concise change list, linked issue, screenshots or curl traces for UI/API updates, and notes on migrations or env needs. Request reviews from each affected service when a change spans both frontend and backend.

## Security & Configuration Tips
Keep API keys in `.env` or platform secrets only. Update `.env.example` and Terraform templates when introducing configuration. After dependency bumps, run `pnpm check-deps` and `uv sync` to confirm lockfiles remain consistent, and document any new infrastructure variables in `infra/terraform.tfvars.example` before applying Terraform.
