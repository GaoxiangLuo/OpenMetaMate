# Repository Guidelines

OpenMetaMate combines a FastAPI backend with a Next.js frontend for AI-driven PDF extraction. Use these guardrails to keep contributions consistent.

## Project Structure & Module Organization
- `backend/app/api/routes` exposes FastAPI routers (extraction, health); `backend/app/core`, `models`, and `services` hold config, schemas, and LLM/PDF orchestration.
- `frontend/app` implements App Router entrypoints, `frontend/components/ui` stores reusable primitives, `frontend/components` holds domain components, and `frontend/lib` centralizes API calls and shared types.
- Assets reside in `assets/codebook`, infrastructure lives in `infra/`, and `docker-compose.yml` orchestrates full-stack runs. Add tests beside features (`backend/tests/...`, `frontend/__tests__/...`) to keep ownership clear.

## Architecture
- **PDF processing** (`backend/app/services/pdf_processor.py`, `mineru_processor.py`): MinerU when `MINERU_API_KEY` and `AWS_S3_TEMP_BUCKET` are set, with automatic fallback to PyPDF.
- **LLM failover** (`backend/app/services/llm_service.py`): `LLM_API_KEY` → `BACKUP_LLM_API_KEY` → `CLAUDE_API_KEY`; unset keys are skipped. Triggers: 429, 401/403, 5xx, connection errors. Timeouts and other 4xx do not fail over.
- **Claude step**: native Anthropic SDK, `claude-haiku-5-5`, thinking disabled; the coding scheme is split into batches of 20 fields, sent in parallel and merged.
- **GPT-5/GPT-6**: Responses API with reasoning effort `none`.
- **Logging**: six `STAGE` markers (validation, scheme parsing, PDF text, LLM, post-processing, response). Use `grep "STAGE"` or `grep "❌"` to find failures.

## Build, Test, and Development Commands
```bash
uv sync                                           # install backend deps via uv
uv run uvicorn app.main:app --reload --port 8000 # backend dev server
uv run ruff check . && uv run ruff format --check .
pnpm install && pnpm dev                         # frontend dev server
pnpm lint && pnpm typecheck && pnpm prettier:check
pnpm build                                       # production build (static export)
docker-compose up                                # launch both services locally
```
Configure env vars with `.env` (see `.env.example`) and never commit secrets. Required: `LLM_API_KEY`, `LLM_API_URL`, `LLM_MODEL`. Optional: `BACKUP_LLM_API_KEY`, `CLAUDE_API_KEY`, `MINERU_API_KEY`, `AWS_S3_TEMP_BUCKET`.

## Coding Style & Naming Conventions
- Python: Ruff enforces PEP 8 with a 100-character line limit; keep modules snake_case, adopt async/await for I/O, and annotate functions.
- TypeScript/React: Follow Prettier defaults, PascalCase components, camelCase hooks/utilities, and Tailwind utility classes. Co-locate component helpers unless shared.

## Testing Guidelines
CI runs linting, formatting, type-checking and builds; treat failures as blockers. Backend tests live in `backend/tests/` and run with `uv run pytest`, but not in CI yet: the test step in `.github/workflows/deploy.yml` is still commented out. `tests/test_mineru_direct.py` is a manual script against the live MinerU API and is not collected. The frontend has no tests; use Jest with React Testing Library under `frontend/__tests__/`. Keep filenames descriptive (`test_llm_service.py`, `extraction-form.test.tsx`) and focus coverage on PDF parsing, LLM fallbacks, and API contracts.

## Commit & Pull Request Guidelines
Prefix commits with `add:`, `fix:`, or `update:` in line with the current history (not `feat:`), and write subjects in the imperative. Keep subjects under 72 characters and add body context for riskier changes. Pull requests must include a problem summary, concise change list, linked issue, screenshots or curl traces for UI/API updates, and notes on migrations or env needs. Request reviews from each affected service when a change spans both frontend and backend.

## Plans & Architecture Decision Records
The `plans/` directory contains architecture decision records for significant features. Before implementing a complex feature, write a plan document (e.g., `plans/011-feature-name.md`) covering the problem, proposed solution, implementation steps, and files to modify. This keeps large changes focused and serves as documentation for future contributors. Review existing plans to understand past design decisions.

## Deployment
Pushing to `main` deploys to production through `.github/workflows/deploy.yml`: backend to AWS Lightsail, then frontend to S3/CloudFront, with health checks. Infrastructure is Terraform in `infra/`. New configuration needs a matching GitHub secret and an entry in the container config in `deploy.yml`.

## Security & Configuration Tips
Keep API keys in `.env` or platform secrets only. Update `.env.example` and Terraform templates when introducing configuration. After dependency bumps, run `pnpm check-deps` and `uv sync` to confirm lockfiles remain consistent, and document any new infrastructure variables in `infra/terraform.tfvars.example` before applying Terraform.
