# Plan 009: PDF Viewer Replacement and UI/UX Overhaul

**Date:** 2026-02-24 (backfilled 2026-11-19)
**Status:** ✅ Implemented in PR #9
**Issue:** PDF viewer lacked drag and search; CHI'26 user study feedback on the extraction workflow

## Problems

- PDF viewer (`react-pdf`, Plan 003) could not pan or search.
- Progress bar jumped; clicking a history item duplicated its chat message.
- Enhanced extraction was hidden behind a settings button.
- Coding scheme editor lost unsaved edits without warning.
- Names like `Group / Treatment` produced field names with stray underscores.
- Greek letters broke in CSV opened with Excel.

## Changes

| Area | Change | Files |
|---|---|---|
| PDF viewer | `react-pdf` → `@embedpdf/react-pdf-viewer` (drag, search, zoom built in); fit-to-width; citation highlight kept | `frontend/components/pdf-viewer-panel.tsx` |
| Progress | Interpolated between updates, animates to 100% | `frontend/app/page.tsx` |
| History | Collapsible panel; click scrolls to the original message | `frontend/app/page.tsx` |
| Enhanced extraction | Visible switch with tooltip | `frontend/app/page.tsx`, `frontend/components/ui/switch.tsx` |
| Scheme editor | Unsaved-changes dialog; download/upload explained | `frontend/components/coding-scheme-editor.tsx`, `frontend/components/ui/alert-dialog.tsx` |
| Scheme parsing | Trim around `/`, drop empty underscore segments; regression tests | `backend/app/services/pydantic_model_generator.py`, `backend/tests/test_coding_scheme_parsing.py` |
| CSV | UTF-8 BOM | `frontend/app/page.tsx` |
| Other | Default codebook cleanup, About dialog content, keyboard accessibility, no layout flicker on startup | — |

## Notes

- Why `react-pdf` was replaced rather than extended was not recorded.
- The switch was off by default here; Plan 010 turned it on.
