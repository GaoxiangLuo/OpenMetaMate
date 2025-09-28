# Plan 004 — Extraction Answer Correction

## Context
- Users upload PDFs and the backend returns structured extraction results per coding scheme item.
- The chat UI renders the LLM-produced values inside `ExtractionItemDisplay`; users can download every session’s history as CSV via `convertAllExtractionsToCSV` in `frontend/app/page.tsx`.
- Today, there is no way to adjust incorrect values before export, so CSV output always mirrors raw LLM predictions.

## Goals
- Allow a user to edit the extracted value for any field in an extraction result message or history replay.
- Ensure manual overrides persist in the session (chat transcript + history sidebar) and flow through CSV export.
- Keep implementation client-side; no persistence beyond the current browser session is required.

## Non-goals / Out of Scope
- Backend storage or APIs for persisting corrections.
- Multi-user collaboration or conflict resolution.
- Auto-revalidation of citations/confidence after edits (values will not be re-sent to the LLM).

## Current Behaviour Overview
1. `processSingleFile` posts to `/api/v1/extract`, receives `ExtractionResult` objects, and updates a chat message (`type: "extraction-result"`).
2. `handleExtractData` later copies each successful result into `extractionHistory`, keeping the per-run coding scheme.
3. Viewing history re-injects a message with `msg.data = entry.data` (new message id).
4. CSV export iterates over `extractionHistory` entries, so any corrections must update this state to affect downloads.

## Proposed Changes
### State & Types
- Extend `ChatMessage` with optional `codingSchemeUsed` and `historyId` so messages know which scheme produced them and can sync edits with history.
- Extend `ProcessedFileResult` and history entries to store the originating message id for later updates.
- Add an optional `manualOverride` flag to `ExtractionResultItem` to surface manual edits in the UI (badge/note) and future-proof downstream logic.

### UI/UX
- Enhance `ExtractionItemDisplay` with an inline “Edit” affordance when an `onSave` callback is provided.
  - Editing opens an input tailored to the coding scheme data type (`Text` → textarea, `Numeric` → number input, `Boolean` → toggle/select).
  - Provide answer type selection (`Grounded`, `Inference`, `Not Found`) and optional reasoning field when `Inference` is chosen.
  - Display a subtle marker when a value has `manualOverride = true`.
- Reuse the component in both chat messages and history replays by passing `editable` props only when we can persist updates.

### Data Flow
- When an edit is saved, update:
  1. The target chat message data (all messages sharing the same `historyId`).
  2. The matching `extractionHistory` entry so CSV export reflects the change.
- Preserve existing citations/confidence unless the answer type becomes `Not Found`; clear citations when users set the value manually without evidence.

### Edge Cases & Safeguards
- If no coding scheme entry matches a field (e.g., scheme changed mid-session), default to text input.
- Guard numeric parsing and boolean coercion; show validation errors inline before accepting.
- Prevent edits while a message is still `isProcessing` (should not surface the edit UI until extraction completes).

## Work Breakdown
1. **Type & state plumbing** — update shared interfaces, return the `fileMessageId` from `processSingleFile`, and link history entries via `historyId`/`messageId`.
2. **Editable extraction item UI** — add edit mode, typed inputs, answer type controls, manual override indicators, and validation messaging.
3. **State synchronization** — add handlers on `MetaMateChatPage` to apply saved edits across chat messages + history entries; ensure CSV export consumes the updated state.
4. **Polish & testing** — manual QA covering editing scenarios (text/numeric/boolean), switching answer types, verifying CSV output, and regression check for non-editable views.

## Testing Strategy
- Manual: edit a value in the immediate extraction message, confirm chat + sidebar update, then download CSV and inspect corrected value.
- Repeat by re-opening a history item and editing there to ensure deduplicated updates.
- Run `pnpm lint` (and `pnpm typecheck` if time permits) to confirm type safety post-change.

## Open Questions
- Should we disable “Grounded” when no citations remain? (Initial implementation will allow it but can revisit based on UX feedback.)
- Future enhancement: surface manual corrections back to the backend for retraining or audit trails.

## Post-Implementation Notes
- Inline editor now ships in `ExtractionItemDisplay`, adapting inputs per data type and surfacing a manual override badge when saved.
- Saving an edit sets `manualOverride = true` and clears citations unless the answer type remains `Grounded`; confidence is preserved only for grounded values.
- Chat messages and history entries share `historyId`/`messageId` links so any correction updates both the transcript and the CSV export path.
- Backend LLM integration now routes gpt-5 models through the Responses API with minimal reasoning effort and low verbosity while keeping gpt-4.1 on deterministic chat completions, preserving structured output across both flows.
- gpt-5 calls use the dedicated `GPT_5_SYSTEM_PROMPT`, while gpt-4.1 continues with the prior system instructions, so both pathways stay aligned with their respective guidance.
- PDF chunking now scales by model family: gpt-4.1 uses 960k-character slices, gpt-5 uses 360k, and other models default to 88k, keeping splitting tuned without extra configuration.
- Chunk size thresholds now compare token counts (via the tokenizer) instead of raw characters so the splitter only re-chunks when the LLM would actually overflow, matching the token-based chunk configuration.
