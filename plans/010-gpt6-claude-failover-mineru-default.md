# Plan 010: GPT-6 Support, Claude Failover and MinerU by Default

**Date:** 2026-11-18 (backfilled 2026-11-19)
**Status:** ✅ Implemented in PR #59, production fix in PR #60
**Issue:** Work with more of the API access people already have, and get more out of each PDF

Supersedes the failover design in Plan 007 and the MinerU defaults in Plan 008.

## Problems

- `gpt-6*` models were not recognised.
- Failover covered one backup key, on 429 only; a bad key or provider outage stopped extraction.
- The MinerU parser dropped `header`, `footer`, `page_footnote` and `chart` blocks.
- Enhanced extraction was opt-in, so most runs used PyPDF.
- The production container had no S3 credentials, so MinerU always fell back to PyPDF silently.

## Changes

| Area | Change | Files |
|---|---|---|
| GPT-6 | Handled like `gpt-5*` (Responses API, reasoning `none`, 960k chunks); own prompt without the checklist line | `backend/app/core/config.py`, `backend/app/services/llm_service.py` |
| Failover chain | `LLM_API_KEY` → `BACKUP_LLM_API_KEY` → `CLAUDE_API_KEY`, unset keys skipped | `backend/app/services/llm_service.py` |
| Failover triggers | 429, 401/403, 5xx, connection errors; not timeouts or other 4xx | `backend/app/services/llm_service.py` |
| Claude step | Anthropic SDK, `claude-haiku-5-5`, thinking off, strict structured outputs; scheme split into batches of 20 fields, run in parallel, merged | `backend/app/services/llm_service.py` |
| Health | `/health/llm` uses the same chain | `backend/app/api/routes/health.py` |
| MinerU parsing | New blocks kept as `[HEADER]`, `[FOOTER]`, `[FOOTNOTE]`, `[CHART]`; digits-only headers/footers dropped | `backend/app/services/mineru_processor.py` |
| MinerU default | Enhanced extraction on by default in the UI and both endpoints; PyPDF fallback unchanged | `backend/app/api/routes/extraction.py`, `frontend/app/page.tsx` |
| S3 access (#60) | IAM user limited to `temp/` in the temp bucket; key passed to the container via `S3_TEMP_AWS_*` secrets | `infra/main.tf`, `.github/workflows/deploy.yml` |

## Decisions

| Decision | Reason |
|---|---|
| GPT-6 prompt without checklist | GPT-6 wrote the bullets before the JSON, breaking parsing in about 1 of 40 runs |
| Claude is fallback only | Claude-only setups are intentionally unsupported |
| Batches of 20 fields | Claude rejects schemas beyond roughly 30 fields |
| Drop digits-only headers/footers | They collide with the page markers used for citations |
| Separate IAM user | The public-facing container should not hold deploy credentials |
| Access key created outside Terraform | Keeps the secret out of state |

## Open Items

- Enhanced-by-default UI was not checked in a browser.
- MinerU in production is confirmed only once the IAM user and secrets exist and a run logs `MinerU extraction successful`.
