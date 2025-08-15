import asyncio
import json
import logging
import random
import time
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.exceptions import ExtractionError, PDFProcessingError
from app.core.utils import get_expected_key, is_not_found_value
from app.models.requests import CodingSchemeItem
from app.models.responses import ExtractionResponse, ExtractionResultItem
from app.services.llm_service import LLMService
from app.services.pdf_processor import PDFProcessorFactory, PDFProcessorType

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


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
@limiter.limit("10 per minute")
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
        text = await pdf_processor.extract_text_from_pdf(contents)

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
                    chunk, [item.dict() for item in parsed_scheme]
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
        results = {}
        valid_extractions = 0
        for chunk_index, chunk_results in enumerate(chunk_results_list):
            for key, value in chunk_results.items():
                if value is not None and not is_not_found_value(value):
                    results[key] = value
                    valid_extractions += 1
                    logger.debug(f"🔍 Found '{key}' in chunk {chunk_index + 1}: {value}")

        logger.info(f"📊 Merged results: {valid_extractions} valid extractions found")

        extracted_data = {}
        found_count = 0
        not_found_count = 0

        for item in parsed_scheme:
            if item.include_in_extraction:
                expected_key = get_expected_key(item.name)
                value = results.get(expected_key)

                if is_not_found_value(value):
                    extracted_data[item.name] = ExtractionResultItem(
                        value="Not Found", confidence=None
                    )
                    not_found_count += 1
                    logger.debug(f"🔍 '{item.name}' not found in document")
                else:
                    # Generate random confidence score (placeholder)
                    confidence_score = random.uniform(0.7, 1.0)

                    extracted_data[item.name] = ExtractionResultItem(
                        value=value,
                        confidence=round(confidence_score, 3),
                    )
                    found_count += 1
                    logger.debug(
                        f"✅ '{item.name}' extracted with confidence {confidence_score:.3f}"
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
