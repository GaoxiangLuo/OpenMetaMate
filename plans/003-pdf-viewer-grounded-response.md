# PDF Viewer Grounded Response Feature

> User: I want a PDF viewer that can open the uploaded PDF files and display the content. I also want whenever I click on an extracted data element, the PDF viewer will bring me to the specific page and highlight the text. I think it requires some major changes to the frontend and the backend. For the frontend, of course we need to add a new component to display the PDF. For the backend, we need to add new attributes to each Extracted Element. I'm thinking of naming it as Citations as a list of Citation Object. Each Citation Object will have a page number that the PDF viewer can use to jump to the specific page and a text snippet that the PDF viewer can use to highlight the text. Why it's a list? Because one extracted element can have multiple citations. In order to achieve this, we probably need to prompt the LLM together with the page number along with the context of each page. Meanwhile, I want my extracted element has a new attributed called "AnswerType" which can be "Grounded" (means the answer can be found explicitly in the text) or "Inference" (means the answer is inferred from the text) and of course "Not Found".

## Implementation Plan

### Updated Objectives
- Keep the right-hand history sidebar fixed width and dedicate the remaining space to a two-column layout where the chat window and PDF viewer always split the width evenly, regardless of screen size.
- Maintain the permanent PDF viewer panel so that clicking any citation jumps directly to the referenced page.

### Backend Requirements (to implement later)
- Each `ExtractionResultItem` must include:
  * `answerType` = `"Grounded" | "Inference" | "Not Found"`.
  * `citations`: list of objects with `pageNumber: int` and `type: "Exact Quote" | "Inference"` plus optional `reasoning: string`.
  * Enforce invariants:
    - If `answerType === "Not Found"`, the citations array must be empty.
    - If `answerType !== "Not Found"`, every citation needs a valid `pageNumber` and `type`.
    - If a citation’s `type` is `"Inference"`, the `reasoning` string must be present.
  * Preserve existing `value`, `confidence`, and per-field reasoning (used by the UI).
- Future backend work should ensure the above invariants before returning JSON from `/extract`.

### Frontend Changes (current task)
- Adjust layout so chat and viewer always render at `flex: 1` side-by-side next to the fixed history sidebar.
- Update TypeScript types and components to consume the new citation shape.
- Display citation `type` (and optional reasoning) in the extraction detail view and viewer sidebar; highlighting specific text is no longer required because no snippet is provided.
- Continue showing per-field confidence and inference reasoning so the chat card stays informative.

## Current Status
- Backend now attaches `answerType` plus structured citations and validates invariants before returning `/extract` responses.
- PDF text sent to the LLM wraps each page in `<<PAGE N>> … <<END PAGE N>>` markers, and the prompt instructs the model to cite those physical page indices verbatim, eliminating numbering drift.
- Frontend chat cards surface the new citation metadata, and the PDF viewer reconciles citation numbers with PDF page labels so navigation lands on the correct page while using a stable zoom strategy.

## Outstanding Issues
- None. The prior pagination mismatch and zoom instability have been resolved.
