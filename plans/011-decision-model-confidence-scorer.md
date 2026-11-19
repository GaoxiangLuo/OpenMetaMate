# Plan 011: Confidence Scoring with a Decision Model

**Date:** 2026-11-19
**Status:** ✅ Implemented on branch `add/decision-confidence-scorer`, not merged
**Issue:** The confidence shown next to each extracted value is not a measurement

## Problems

- The confidence is whatever number the extraction model writes into its JSON (`LLMExtractionField.confidence`), which is generated text, not a probability.
- When the model omits it, `build_extraction_item` fills in `random.uniform(0.7, 1.0)` (`backend/app/api/routes/extraction.py:179`), so some displayed scores are random.
- Reviewers use the indicator to decide which values to check, so it should rank likely errors first.

## Approach

After extraction, make one call to OpenAI's Decisions API (`POST /v1/decisions`, `gpt-6-luna`) per paper: the PDF text as `input`, one `predicate` question per extracted value. The returned `probability` becomes that field's `confidence`. Extraction itself is unchanged; the decision model cannot produce numeric or free-text values or citations.

```
STAGE 4  LLM extraction (unchanged)
STAGE 5  merge chunks → build items → score found values → response
```

Request shape:

```json
{
  "model": "gpt-6-luna",
  "input": [
    {"role": "developer", "content": "<page-marker rules + the three domain reminders>"},
    {"role": "user", "content": "<<PAGE 1>> ... <<END PAGE 12>>"}
  ],
  "questions": [
    {"type": "predicate", "name": "q0",
     "instructions": "Field: Sample Size. Definition: <description>. Extracted value: 142. The extracted value is correct for this field: it is either stated in the document or follows from the document by the calculation or coding rule in the definition."}
  ]
}
```

Questions are named `q0…qN` and mapped back to fields by index, since field names contain spaces and slashes.

Boolean fields are asked directly instead of having their extracted answer checked: the question is "According to the document and this definition, the field should be coded True", and the confidence is the returned probability when the extracted answer is `True` and one minus it when `False`. The extraction's reasoning is not shown to the decision model.

## Changes

| Area | Change | Files |
|---|---|---|
| Scorer service | New `ConfidenceScorer.score(text, scheme, items) -> Dict[str, float]`; builds predicates, calls the endpoint, maps answers back; never raises | `backend/app/services/confidence_scorer.py` (new) |
| Client | Reuse the `AsyncOpenAI` clients (primary, then backup key on the existing failover triggers); 45s timeout and no SDK retries, so the added wait is bounded; use `client.post("/decisions", ...)` if the pinned SDK has no `decisions` resource | `backend/app/services/llm_service.py`, `backend/app/services/confidence_scorer.py` |
| Config | `DECISION_MODEL` (default `gpt-6-luna`, empty disables); scorer runs only when `LLM_API_URL` is `api.openai.com` | `backend/app/core/config.py` |
| Pipeline | Call the scorer after the merge loop in both `/extract` and `/extract/stream`; overwrite `confidence` on scored items; log under `[STAGE 5/6]` | `backend/app/api/routes/extraction.py` |
| Streaming | Progress message "Checking extracted values…"; run inside the same 15s heartbeat loop used for extraction | `backend/app/api/routes/extraction.py` |
| Random fallback | Remove `random.uniform(0.7, 1.0)`; a missing score stays `None` and the UI shows no indicator | `backend/app/api/routes/extraction.py` |
| Self-reported confidence | Drop `confidence` from the system prompts and from `LLMExtractionField`, and stop reading it in `build_extraction_item`; the decision probability is the only source | `backend/app/services/llm_service.py`, `backend/app/models/llm.py`, `backend/app/api/routes/extraction.py` |
| Frontend | A manually saved value gets `confidence = 1` (today a `Grounded` edit keeps the old score and an `Inference` edit clears it); a manual `Not Found` stays without a score; update the confidence wording in the author info modal | `frontend/components/extraction-item-display.tsx`, `frontend/components/author-info-modal.tsx` |
| Tests | Mocked-client unit tests: question building per data type, index mapping, refusal → `None`, API error → `None`, `Not Found` skipped, non-OpenAI URL skipped, >400 fields batched | `backend/tests/test_confidence_scorer.py` (new) |
| Docs | Add the scorer to the LLM service section and env list | `CLAUDE.md`, `AGENTS.md` |

## Behaviour

| Situation | Confidence shown |
|---|---|
| Scorer ran, question answered | Decision probability |
| Question refused | None |
| Scorer call failed or timed out | None; extraction still succeeds |
| `LLM_API_URL` is not OpenAI (Gemini, OpenRouter, self-hosted) | None |
| Extraction fell back to Claude because the OpenAI keys failed | Usually none, since the decision call uses the same keys |
| Document needed more than one chunk | None (v1 does not score chunked documents) |
| Field is `Not Found` | None (unchanged; not sent to the scorer) |
| User edited and saved the value | 100% |

Call count: normally two per paper, one extraction and one decision. Exceptions are the Claude failover step (one extraction request per 20 fields) and documents split into several chunks (one extraction per chunk, no scoring).

## Decisions

| Decision | Reason |
|---|---|
| Post-hoc check, not extraction | The API only answers closed-set questions and returns no citations |
| `predicate` for all three data types | One comparable score for Boolean, Numeric and Text fields |
| Boolean fields asked directly | "Is the answer False correct?" is a double negative; asking the field itself gave fewer false alarms |
| Extraction reasoning withheld from the scorer | It made the scorer agree with wrong values |
| Indicator keeps showing the percentage with the colour band | After accounting for label errors the top band is reliable; a low score is a prompt to check the value |
| One call per paper | Up to 400 questions per request; the paper is billed once, not per question |
| Scorer failure never fails the request | Confidence is an aid; the extracted values are the product |
| No fallback to self-reported confidence | One indicator should have one meaning; deployments on non-OpenAI providers show no confidence |
| Remove the random fallback | A fabricated score is worse than no score |
| Manual edits show 100% | The reviewer has confirmed the value |
| `Not Found` fields are not scored | They are left out of the `questions` array and keep no confidence, as today; a probability on a missing value would worry users without telling them what to do |
| No new secrets or infra | Uses the existing OpenAI keys; `DECISION_MODEL` has a working default |
| Same repeated domain rules in the scorer input | The verifier should judge by the rules the extractor followed (post-attrition N, age vs grade) |

## Order of Work

1. Smoke test: confirm the endpoint works with our key and SDK, a full-length paper fits in one request, and measure latency.
2. Offline validation on human-coded papers. No confidence ground truth is needed: each extracted value is already known to be correct or wrong, so the test is whether the decision probability separates the two (AUROC, and accuracy per probability bin).
3. If it does, build the service, pipeline wiring, tests and frontend changes.
4. Set the UI colour thresholds (currently 0.85 / 0.65 in `ConfidenceIndicator`) from the measured distribution.

## Validation Results

Offline run on human-coded papers: 7,655 extracted values (79% correct by the human labels), each scored by the production scorer code against the same text the extraction saw.

| Measure | Result |
|---|---|
| AUROC, all values | 0.75 (0.5 = no signal, 1.0 = perfect ranking) |
| AUROC by type | Text 0.78, Boolean 0.70, Numeric 0.69 |
| Refused questions | 0 |
| Added latency per paper | Median 0.9s, max 2.4s |

| Score | Share of values | Correct by the labels |
|---|---|---|
| 0.99 and above | 66% | 90% |
| 0.85 to 0.99 | 15% | 74% |
| Below 0.85 | 19% | 47% |

- Reviewing only the values below 0.85 (19% of all values) finds 49% of the values labelled wrong.
- UI colour bands were set from this table: green from 0.99, yellow from 0.85, red below.
- Not compared against the old self-reported confidence, which the saved runs did not record.

### Why the score is not a calibrated probability

48 disagreements between score and label were sampled from the two extremes and adjudicated against the full paper by a stronger reasoning model, with its quotes checked against the paper text. This is model adjudication on a small sample, not human review.

| Sampled group | Extraction actually right | Extraction actually wrong |
|---|---|---|
| Score 0.99 or above, labelled wrong (24) | 21 | 3 |
| Score below 0.1, labelled correct (24) | 17 | 7 |

- **Top end: mostly label errors.** The human coding left reported values blank, held a wrong value, or followed a different convention. If the sampled rate holds, the top band is right well above 95% of the time and AUROC on corrected labels would be roughly 0.85 to 0.90 (simulated, not measured).
- **Low end: real false alarms.** The scorer gives near-zero scores to correct values that need a calculation (total hours, percentages from counts), to `False` on fields that code the absence of something, and to judgment-call categories.

### Question variants tried

| Variant | AUROC |
|---|---|
| Check every value ("the extracted value is correct") | 0.74 |
| Same, with wording that explicitly allows calculated values | 0.73 |
| Boolean fields asked directly ("the field should be coded True"), confidence taken as P or 1 - P | 0.75 |

- The direct Boolean question is what ships. It cut Boolean false alarms (score below 0.1 on a value labelled correct) from 114 to 78.
- Showing the scorer the extraction's reasoning was tested on six calculated values and rejected: it raised the score of wrong values with wrong arithmetic as much as right ones (one went from 0.01 to 0.99).

## Risks

- **Calibration is undocumented.** OpenAI does not define what the probability means; one independent test saw values pegged at 1.0. Step 2 decides whether the feature ships.
- **Correlated errors.** The verifier is the same `gpt-6-luna` that extracted the value, and published results show decision models and LLM judges repeat each other's confident errors. Treat the score as a review-priority ranking, not a probability of correctness.
- **Input size.** The docs give a character limit (about 10M) but no token context window.
- **Latency.** One extra call per paper on the streaming path; expected to be short because nothing is generated, but unmeasured.
- **Rate limits.** Each paper's text is sent to OpenAI twice, so bulk uploads use roughly double the input tokens per minute and may hit 429s sooner.
- **Cost.** Reported as $0.10 per 1M input tokens with no output charge (third-party source), so roughly the paper's input tokens billed once more.

## Open Items

- Calculated numeric fields (total hours, percentages from counts) get low scores even when right. Not addressed here: a single forward pass cannot be relied on for arithmetic. Left for a future agentic version with math tools.
- Measure AUROC on corrected labels with a random sample across the whole score range.
- Not checked in a browser: the new progress message, the colour bands and the 100% on manual edits.
