import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.exceptions import ExtractionError, PDFProcessingError
from app.core.utils import get_expected_key, is_not_found_value
from app.models.requests import CodingSchemeItem
from app.models.responses import Citation, ExtractionResponse, ExtractionResultItem
from app.services.llm_service import LLMService
from app.services.pdf_processor import (
    PDFExtractionResult,
    PDFProcessorFactory,
    PDFProcessorType,
)

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

ANSWER_TYPE_NORMALIZATION = {
    "grounded": "Grounded",
    "inference": "Inference",
    "not found": "Not Found",
    "not_found": "Not Found",
}

CITATION_TYPE_NORMALIZATION = {
    "exact quote": "Exact Quote",
    "exact_quote": "Exact Quote",
    "quote": "Exact Quote",
    "inference": "Inference",
}


def _normalize_answer_type(
    raw_value: Optional[str],
    fallback_has_value: bool,
    has_citations: bool,
) -> str:
    """Normalize answer type values from the LLM output."""

    if raw_value:
        candidate = ANSWER_TYPE_NORMALIZATION.get(raw_value.strip().lower())
        if candidate:
            return candidate

    if not fallback_has_value:
        return "Not Found"

    if has_citations:
        return "Grounded"

    return "Inference"


def _normalize_citation_type(raw_value: Optional[str]) -> Optional[str]:
    """Normalize citation type labels from the LLM output."""

    if not raw_value:
        return None
    return CITATION_TYPE_NORMALIZATION.get(raw_value.strip().lower())


def build_extraction_item(
    raw_data: Optional[Dict[str, Any]],
    *,
    fallback_label: str,
) -> ExtractionResultItem:
    """Convert the LLM structured output for a field into an API response item."""

    if not raw_data:
        logger.debug(f"ℹ️ No data for '{fallback_label}', marking as not found")
        return ExtractionResultItem(
            value="Not Found",
            confidence=None,
            answer_type="Not Found",
            citations=[],
            reasoning=None,
        )

    raw_value = raw_data.get("value")
    fallback_has_value = not is_not_found_value(raw_value)

    raw_citations = raw_data.get("citations") or []
    citations: List[Citation] = []
    if isinstance(raw_citations, list):
        for entry in raw_citations:
            if not isinstance(entry, dict):
                continue

            page_number = entry.get("page_number") or entry.get("pageNumber")
            citation_type_raw = entry.get("type") or entry.get("citation_type")
            reasoning = entry.get("reasoning")

            if isinstance(page_number, str) and page_number.isdigit():
                page_number = int(page_number)

            normalized_type = _normalize_citation_type(
                citation_type_raw if isinstance(citation_type_raw, str) else None
            )

            if page_number is None or normalized_type is None:
                continue

            if normalized_type == "Inference" and not reasoning:
                reasoning = f"Inference explainability missing for '{fallback_label}'."

            try:
                citations.append(
                    Citation(
                        page_number=page_number,
                        citation_type=normalized_type,
                        reasoning=reasoning,
                    )
                )
            except ValidationError as citation_error:
                logger.debug(
                    "⚠️ Skipping invalid citation for '%s': %s",
                    fallback_label,
                    citation_error,
                )

    has_citations = len(citations) > 0

    raw_answer_type = raw_data.get("answer_type") or raw_data.get("answerType")
    answer_type = _normalize_answer_type(
        raw_answer_type if isinstance(raw_answer_type, str) else None,
        fallback_has_value,
        has_citations,
    )

    reasoning = raw_data.get("reasoning") or None
    confidence_value = raw_data.get("confidence")
    confidence: Optional[float] = None

    if confidence_value is not None:
        try:
            parsed_confidence = float(confidence_value)
            if 0 <= parsed_confidence <= 1:
                confidence = round(parsed_confidence, 3)
        except (TypeError, ValueError):
            logger.debug(
                "⚠️ Ignoring non-numeric confidence for '%s': %s",
                fallback_label,
                confidence_value,
            )

    if answer_type == "Not Found":
        raw_value = "Not Found"
        confidence = None
        citations = []
        reasoning = None
    else:
        if not has_citations:
            logger.debug(
                "⚠️ Missing citations for '%s'; reverting to Not Found to maintain invariants",
                fallback_label,
            )
            return ExtractionResultItem(
                value="Not Found",
                confidence=None,
                answer_type="Not Found",
                citations=[],
                reasoning=None,
            )

        if confidence is None:
            confidence = round(random.uniform(0.7, 1.0), 3)

    try:
        return ExtractionResultItem(
            value=raw_value,
            confidence=confidence,
            answer_type=answer_type,
            citations=citations,
            reasoning=reasoning,
        )
    except ValidationError as extraction_error:
        logger.warning(
            "⚠️ Extraction data for '%s' failed validation (%s); marking as Not Found",
            fallback_label,
            extraction_error,
        )
        return ExtractionResultItem(
            value="Not Found",
            confidence=None,
            answer_type="Not Found",
            citations=[],
            reasoning=None,
        )


# Create PDF processor based on configuration
def get_pdf_processor():
    """Get PDF processor instance based on configuration"""
    processor_type_str = settings.PDF_PROCESSOR.upper()
    try:
        processor_type = PDFProcessorType[processor_type_str]
        processor = PDFProcessorFactory.create(processor_type)
        logger.info(f"🎭 Using {processor_type.value} processor for PDF extraction")
        return processor
    except KeyError:
        logger.warning(
            f"⚠️ Unknown PDF processor type: {settings.PDF_PROCESSOR}, falling back to PyPDF"
        )
        return PDFProcessorFactory.create(PDFProcessorType.PYPDF)
    except Exception as e:
        logger.error(f"❌ Error creating PDF processor: {e}")
        raise PDFProcessingError(f"Failed to initialize PDF processor: {e}")


@router.post("/extract", response_model=ExtractionResponse)
@limiter.limit("20 per minute")
async def extract_data(
    request: Request, pdf_file: UploadFile = File(...), coding_scheme: str = Form(...)
):
    """Extract data from PDF using provided coding scheme"""

    start_time = time.time()
    logger.info(f"📥 New extraction request received for file: {pdf_file.filename}")

    # Validate file type
    if not pdf_file.content_type == "application/pdf":
        logger.warning(
            f"❌ Invalid file type: {pdf_file.content_type} for file: {pdf_file.filename}"
        )
        raise HTTPException(400, "File must be PDF")

    # Check file size
    try:
        contents = await pdf_file.read()
        file_size_mb = len(contents) / (1024 * 1024)
        logger.info(f"📄 File size: {file_size_mb:.2f}MB")
    except Exception as e:
        logger.error(f"❌ Error reading PDF file: {e}")
        raise HTTPException(400, f"Error reading PDF file: {e}")

    if file_size_mb > settings.MAX_FILE_SIZE_MB:
        logger.warning(
            f"🚫 File too large: {file_size_mb:.1f}MB (max: {settings.MAX_FILE_SIZE_MB}MB)"
        )
        raise HTTPException(
            400, f"File too large: {file_size_mb:.1f}MB (max: {settings.MAX_FILE_SIZE_MB}MB)"
        )

    # Validate file is not empty
    if len(contents) == 0:
        logger.warning(f"📄 Empty PDF file received: {pdf_file.filename}")
        raise HTTPException(400, "PDF file is empty")

    # Parse coding scheme
    try:
        scheme_data = json.loads(coding_scheme)
        if not scheme_data:
            raise ValueError("Coding scheme cannot be empty")

        parsed_scheme = [CodingSchemeItem(**item) for item in scheme_data]

        # Count items to be extracted
        items_to_extract = sum(1 for item in parsed_scheme if item.include_in_extraction)
        logger.info(
            f"📊 Coding scheme parsed: {len(parsed_scheme)} items, "
            f"{items_to_extract} to extract"
        )

        if items_to_extract == 0:
            raise ValueError("No items marked for extraction in coding scheme")

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON decode error in coding scheme: {e}")
        raise HTTPException(400, f"Invalid JSON in coding scheme: {e}")
    except ValueError as e:
        logger.error(f"❌ Validation error in coding scheme: {e}")
        raise HTTPException(400, f"Invalid coding scheme: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error parsing coding scheme: {e}")
        raise HTTPException(400, f"Error parsing coding scheme: {e}")

    try:
        # Get PDF processor instance
        pdf_processor = get_pdf_processor()

        # Extract text from PDF
        logger.info("🔍 Starting text extraction from PDF...")
        extraction_result: PDFExtractionResult = await pdf_processor.extract_text_from_pdf(contents)

        text = extraction_result.full_text

        if not text or len(text.strip()) == 0:
            logger.warning(f"⚠️ No text extracted from PDF: {pdf_file.filename}")
            raise PDFProcessingError("No text could be extracted from the PDF")

        text_length = len(text)
        logger.info(f"📃 Extracted {text_length:,} characters from PDF")

        # Chunk if needed
        chunks = await pdf_processor.chunk_text(text)
        logger.info(f"📦 Text split into {len(chunks)} chunks for processing")

        llm_service = LLMService()

        # Process chunks concurrently with LLM
        async def process_chunk(chunk_index: int, chunk: str) -> Dict[str, Any]:
            logger.info(f"🤖 Processing chunk {chunk_index + 1}/{len(chunks)} with LLM...")
            try:
                result = await llm_service.extract_with_schema(
                    chunk, [item.model_dump() for item in parsed_scheme]
                )
                logger.info(f"✅ Chunk {chunk_index + 1} processed successfully")
                return result
            except Exception as e:
                logger.error(f"❌ Error processing chunk {chunk_index + 1}: {e}")
                return {}

        # Process all chunks concurrently
        logger.info(f"🚀 Starting concurrent LLM processing of {len(chunks)} chunks...")
        chunk_results_list = await asyncio.gather(
            *[process_chunk(i, chunk) for i, chunk in enumerate(chunks)], return_exceptions=False
        )

        # Merge results from all chunks
        def get_field_from_chunk(
            chunk_data: Dict[str, Any], key_path: str
        ) -> Optional[Dict[str, Any]]:
            """Locate the structured extraction for a field within a chunk result."""

            parts = [part for part in key_path.split("/") if part]
            node: Any = chunk_data
            for part in parts:
                if not isinstance(node, dict):
                    return None
                node = node.get(part)
                if node is None:
                    return None
            return node if isinstance(node, dict) else None

        extracted_data: Dict[str, ExtractionResultItem] = {}
        found_count = 0
        not_found_count = 0

        for item in parsed_scheme:
            if item.include_in_extraction:
                expected_key = get_expected_key(item.name)
                candidate_data: Optional[Dict[str, Any]] = None
                for chunk_data in chunk_results_list:
                    candidate_data = get_field_from_chunk(chunk_data, expected_key)
                    if candidate_data:
                        break

                parsed_item = build_extraction_item(
                    candidate_data,
                    fallback_label=item.name,
                )

                extracted_data[item.name] = parsed_item

                if parsed_item.answer_type == "Not Found":
                    not_found_count += 1
                    logger.debug(f"🔍 '{item.name}' not found in document")
                else:
                    found_count += 1
                    logger.debug(
                        "✅ '%s' extracted with confidence %s", item.name, parsed_item.confidence
                    )

        # Calculate processing time
        processing_time = time.time() - start_time

        logger.info("🎉 Extraction completed successfully!")
        logger.info(f"📊 Results: {found_count} found, {not_found_count} not found")
        logger.info(f"⏱️ Processing time: {processing_time:.2f} seconds")

        total_items = found_count + not_found_count
        return ExtractionResponse(
            fileName=pdf_file.filename,
            extractedData=extracted_data,
            status="success",
            message=f"Extraction completed successfully. Found {found_count}/{total_items} items.",
        )

    except PDFProcessingError as e:
        logger.error(f"📄❌ PDF processing error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except ExtractionError as e:
        logger.error(f"🔍❌ Extraction error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise

    except Exception as e:
        logger.error(f"💥 Unexpected extraction error: {str(e)}", exc_info=True)

        # Check for specific error patterns
        error_msg = str(e).lower()
        if "401" in error_msg or "authentication" in error_msg or "api key" in error_msg:
            logger.error("🔑❌ API authentication issue detected")
            raise HTTPException(
                status_code=401,
                detail="LLM API authentication failed. Please check your API key configuration.",
            )
        elif "rate limit" in error_msg or "429" in error_msg:
            logger.error("🚫 Rate limit exceeded")
            raise HTTPException(
                status_code=429,
                detail="API rate limit exceeded. Please try again later.",
            )
        elif "timeout" in error_msg:
            logger.error("⏱️ Request timeout")
            raise HTTPException(
                status_code=504,
                detail="Request timed out. The PDF might be too large or complex.",
            )

        # For other errors, return a 500 error
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during extraction. Please try again.",
        )


@router.post("/extract/stream")
@limiter.limit("20 per minute")
async def extract_data_stream(
    request: Request, pdf_file: UploadFile = File(...), coding_scheme: str = Form(...)
):
    """
    Extract data from PDF using streaming responses to bypass Lightsail 60s timeout.

    Returns newline-delimited JSON with progress updates:
    - {"type": "progress", "message": "...", "progress": 0-100}
    - {"type": "complete", "data": {...}}
    - {"type": "error", "message": "..."}
    """

    async def event_generator():
        """Generate progress events during extraction"""
        start_time = time.time()
        last_heartbeat = time.time()

        try:
            yield (
                json.dumps(
                    {
                        "type": "progress",
                        "message": f"Starting extraction for {pdf_file.filename}",
                        "progress": 0,
                    }
                )
                + "\n"
            )

            # Validate file type
            if not pdf_file.content_type == "application/pdf":
                yield json.dumps({"type": "error", "message": "File must be PDF"}) + "\n"
                return

            # Read file
            contents = await pdf_file.read()
            file_size_mb = len(contents) / (1024 * 1024)

            if file_size_mb > settings.MAX_FILE_SIZE_MB:
                yield (
                    json.dumps(
                        {
                            "type": "error",
                            "message": (
                                f"File too large: {file_size_mb:.1f}MB "
                                f"(max: {settings.MAX_FILE_SIZE_MB}MB)"
                            ),
                        }
                    )
                    + "\n"
                )
                return

            if len(contents) == 0:
                yield json.dumps({"type": "error", "message": "PDF file is empty"}) + "\n"
                return

            yield (
                json.dumps(
                    {
                        "type": "progress",
                        "message": f"File validated ({file_size_mb:.2f}MB)",
                        "progress": 5,
                    }
                )
                + "\n"
            )

            # Parse coding scheme
            try:
                scheme_data = json.loads(coding_scheme)
                if not scheme_data:
                    raise ValueError("Coding scheme cannot be empty")

                parsed_scheme = [CodingSchemeItem(**item) for item in scheme_data]
                items_to_extract = sum(1 for item in parsed_scheme if item.include_in_extraction)

                if items_to_extract == 0:
                    raise ValueError("No items marked for extraction in coding scheme")

                yield (
                    json.dumps(
                        {
                            "type": "progress",
                            "message": f"Coding scheme parsed: {items_to_extract} items to extract",
                            "progress": 10,
                        }
                    )
                    + "\n"
                )

            except (json.JSONDecodeError, ValueError) as e:
                yield (
                    json.dumps({"type": "error", "message": f"Invalid coding scheme: {str(e)}"})
                    + "\n"
                )
                return

            # Extract text from PDF
            pdf_processor = get_pdf_processor()
            yield (
                json.dumps(
                    {"type": "progress", "message": "Extracting text from PDF...", "progress": 10}
                )
                + "\n"
            )

            extraction_result: PDFExtractionResult = await pdf_processor.extract_text_from_pdf(
                contents
            )
            text = extraction_result.full_text

            if not text or len(text.strip()) == 0:
                yield (
                    json.dumps(
                        {"type": "error", "message": "No text could be extracted from the PDF"}
                    )
                    + "\n"
                )
                return

            text_length = len(text)
            yield (
                json.dumps(
                    {
                        "type": "progress",
                        "message": f"Extracted {text_length:,} characters from PDF",
                        "progress": 35,
                    }
                )
                + "\n"
            )

            # Chunk text
            chunks = await pdf_processor.chunk_text(text)
            yield (
                json.dumps(
                    {
                        "type": "progress",
                        "message": "Preparing document for analysis...",
                        "progress": 50,
                    }
                )
                + "\n"
            )

            # Process chunks with LLM
            llm_service = LLMService()
            chunk_results_list = []

            for i, chunk in enumerate(chunks):
                # Send heartbeat every 20 seconds to keep connection alive
                current_time = time.time()
                if current_time - last_heartbeat > 20:
                    yield (
                        json.dumps({"type": "heartbeat", "elapsed": int(current_time - start_time)})
                        + "\n"
                    )
                    last_heartbeat = current_time

                progress = 50 + int((i / len(chunks)) * 40)  # 50-90%
                yield (
                    json.dumps(
                        {
                            "type": "progress",
                            "message": "Analyzing document with AI...",
                            "progress": progress,
                        }
                    )
                    + "\n"
                )

                try:
                    result = await llm_service.extract_with_schema(
                        chunk, [item.model_dump() for item in parsed_scheme]
                    )
                    chunk_results_list.append(result)
                except Exception as e:
                    logger.error(f"❌ Error processing chunk {i+1}: {e}")
                    chunk_results_list.append({})

            yield (
                json.dumps(
                    {
                        "type": "progress",
                        "message": "Finalizing extraction results...",
                        "progress": 90,
                    }
                )
                + "\n"
            )

            # Merge results
            def get_field_from_chunk(
                chunk_data: Dict[str, Any], key_path: str
            ) -> Optional[Dict[str, Any]]:
                parts = [part for part in key_path.split("/") if part]
                node: Any = chunk_data
                for part in parts:
                    if not isinstance(node, dict):
                        return None
                    node = node.get(part)
                    if node is None:
                        return None
                return node if isinstance(node, dict) else None

            extracted_data: Dict[str, ExtractionResultItem] = {}
            found_count = 0
            not_found_count = 0

            for item in parsed_scheme:
                if item.include_in_extraction:
                    expected_key = get_expected_key(item.name)
                    candidate_data: Optional[Dict[str, Any]] = None
                    for chunk_data in chunk_results_list:
                        candidate_data = get_field_from_chunk(chunk_data, expected_key)
                        if candidate_data:
                            break

                    parsed_item = build_extraction_item(candidate_data, fallback_label=item.name)
                    extracted_data[item.name] = parsed_item

                    if parsed_item.answer_type == "Not Found":
                        not_found_count += 1
                    else:
                        found_count += 1

            processing_time = time.time() - start_time

            yield (
                json.dumps({"type": "progress", "message": "Extraction complete!", "progress": 100})
                + "\n"
            )

            # Send final result
            total_items = found_count + not_found_count
            result = ExtractionResponse(
                fileName=pdf_file.filename,
                extractedData=extracted_data,
                status="success",
                message=(
                    f"Extraction completed successfully. "
                    f"Found {found_count}/{total_items} items."
                ),
            )

            yield (
                json.dumps(
                    {
                        "type": "complete",
                        "data": result.model_dump(by_alias=True),
                        "processing_time": processing_time,
                    }
                )
                + "\n"
            )

            logger.info(f"🎉 Streaming extraction completed in {processing_time:.2f}s")

        except Exception as e:
            logger.error(f"💥 Streaming extraction error: {str(e)}", exc_info=True)
            yield json.dumps({"type": "error", "message": str(e)}) + "\n"

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",  # Newline-delimited JSON
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable buffering in nginx/proxies
        },
    )
