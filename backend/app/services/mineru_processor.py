"""MinerU PDF processor with API integration."""

import asyncio
import io
import json
import logging
import os
import re
import tempfile
import zipfile
from pathlib import Path
from typing import List

import httpx

from app.core.config import settings
from app.core.exceptions import PDFProcessingError
from app.services.pdf_processor import BasePDFProcessor, PDFExtractionResult, PDFPageContent
from app.services.s3_temp_storage import S3TempStorage

logger = logging.getLogger(__name__)

# MinerU API constants (hardcoded defaults)
MINERU_API_URL = "https://mineru.net/api/v4/extract/task"
MINERU_POLL_INTERVAL = 5  # seconds
MINERU_MAX_WAIT_TIME = 600  # 10 minutes
MINERU_MAX_FILE_SIZE_MB = 200  # MinerU limit
MINERU_MAX_PAGES = 600  # MinerU limit


class MinerUPDFProcessor(BasePDFProcessor):
    """PDF processor using MinerU API with S3 temporary storage."""

    def __init__(self):
        """Initialize MinerU processor."""
        super().__init__()

        if not settings.MINERU_API_KEY:
            raise ValueError("MINERU_API_KEY not configured")
        if not settings.AWS_S3_TEMP_BUCKET:
            raise ValueError("AWS_S3_TEMP_BUCKET not configured")

        self.api_key = settings.MINERU_API_KEY
        self.api_url = MINERU_API_URL
        self.s3_storage = S3TempStorage()

        logger.info("🚀 MinerUPDFProcessor initialized")

    async def extract_text_from_pdf(self, pdf_content: bytes) -> PDFExtractionResult:
        """Extract text from PDF using MinerU API.

        Args:
            pdf_content: PDF file content as bytes

        Returns:
            PDFExtractionResult containing extracted text and pages

        Raises:
            PDFProcessingError: If extraction fails (triggers fallback to PyPDF)
        """
        s3_key = None

        try:
            if not pdf_content:
                logger.error("❌ [STAGE 3/6] Empty PDF content provided")
                raise PDFProcessingError("Empty PDF content")

            # Check file size (MinerU limit: 200MB)
            file_size_mb = len(pdf_content) / (1024 * 1024)
            if file_size_mb > MINERU_MAX_FILE_SIZE_MB:
                logger.warning(
                    f"⚠️ [STAGE 3/6] PDF too large for MinerU "
                    f"({file_size_mb:.1f}MB > {MINERU_MAX_FILE_SIZE_MB}MB), will fallback to PyPDF"
                )
                raise PDFProcessingError(
                    f"PDF exceeds MinerU size limit ({MINERU_MAX_FILE_SIZE_MB}MB)"
                )

            logger.info("📄 [STAGE 3/6] Starting PDF extraction with MinerU API...")

            # Step 1: Upload to S3 and get presigned URL
            s3_key, pdf_url = await self.s3_storage.upload_and_get_url(pdf_content)
            logger.info("✅ PDF uploaded to S3, generated presigned URL")

            # Step 2: Submit to MinerU API
            task_id = await self._submit_task(pdf_url)
            logger.info(f"✅ MinerU task submitted: {task_id}")

            # Step 3: Poll for completion
            result_zip_url = await self._poll_task(task_id)
            logger.info("✅ MinerU processing complete, downloading results...")

            # Step 4: Download and extract text
            result = await self._download_and_extract_text(result_zip_url)

            logger.info(
                f"✅ [STAGE 3/6] MinerU extraction complete - "
                f"{len(result.pages)} pages, {len(result.full_text):,} chars"
            )

            return result

        except PDFProcessingError:
            # Re-raise to trigger fallback
            raise
        except Exception as e:
            logger.error(f"❌ [STAGE 3/6] MinerU extraction failed: {e}", exc_info=True)
            raise PDFProcessingError(f"MinerU extraction failed: {e}")

        finally:
            # Clean up S3 temp file
            if s3_key:
                await self.s3_storage.delete_pdf(s3_key)

    async def _submit_task(self, pdf_url: str) -> str:
        """Submit PDF parsing task to MinerU API.

        Args:
            pdf_url: Publicly accessible URL to PDF

        Returns:
            Task ID

        Raises:
            PDFProcessingError: If submission fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "url": pdf_url,
            "is_ocr": True,  # Enable OCR for scanned PDFs
            "enable_formula": True,  # Enable formula recognition
            "enable_table": True,  # Enable table recognition
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)

                if response.status_code != 200:
                    error_msg = (
                        f"MinerU API returned status {response.status_code}: {response.text}"
                    )
                    logger.error(f"❌ {error_msg}")
                    raise PDFProcessingError(error_msg)

                data = response.json()

                if data.get("code") != 0:
                    error_msg = f"MinerU API error: {data.get('msg', 'Unknown error')}"
                    logger.error(f"❌ {error_msg}")
                    raise PDFProcessingError(error_msg)

                task_id = data["data"]["task_id"]
                return task_id

        except httpx.HTTPError as e:
            error_msg = f"HTTP error submitting to MinerU: {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)
        except KeyError as e:
            error_msg = f"Unexpected MinerU API response format: missing {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)

    async def _poll_task(self, task_id: str) -> str:
        """Poll MinerU task until completion.

        Args:
            task_id: Task ID from submission

        Returns:
            URL to result ZIP file

        Raises:
            PDFProcessingError: If polling fails or times out
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        query_url = f"{self.api_url}/{task_id}"
        max_retries = MINERU_MAX_WAIT_TIME // MINERU_POLL_INTERVAL
        retry_count = 0

        logger.info(f"🔄 Polling MinerU task (max wait: {MINERU_MAX_WAIT_TIME}s)...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while retry_count < max_retries:
                    response = await client.get(query_url, headers=headers)

                    if response.status_code != 200:
                        error_msg = (
                            f"MinerU API returned status {response.status_code}: {response.text}"
                        )
                        logger.error(f"❌ {error_msg}")
                        raise PDFProcessingError(error_msg)

                    data = response.json()

                    if data.get("code") != 0:
                        error_msg = f"MinerU API error: {data.get('msg', 'Unknown error')}"
                        logger.error(f"❌ {error_msg}")
                        raise PDFProcessingError(error_msg)

                    state = data["data"]["state"]

                    if state == "done":
                        zip_url = data["data"]["full_zip_url"]
                        logger.info("✅ MinerU task completed")
                        return zip_url

                    elif state == "failed":
                        error_msg = data["data"].get("err_msg", "Unknown error")
                        logger.error(f"❌ MinerU task failed: {error_msg}")
                        raise PDFProcessingError(f"MinerU processing failed: {error_msg}")

                    elif state in ["pending", "running", "converting"]:
                        # Log progress if available
                        if "extract_progress" in data["data"]:
                            progress = data["data"]["extract_progress"]
                            extracted = progress.get("extracted_pages", "?")
                            total = progress.get("total_pages", "?")
                            logger.info(f"🔄 MinerU progress: {extracted}/{total} pages processed")
                        else:
                            logger.info(f"🔄 MinerU status: {state}")

                        # Wait before next poll
                        await asyncio.sleep(MINERU_POLL_INTERVAL)
                        retry_count += 1

                    else:
                        error_msg = f"Unknown MinerU task state: {state}"
                        logger.error(f"❌ {error_msg}")
                        raise PDFProcessingError(error_msg)

                # Timeout reached
                error_msg = f"MinerU task timeout ({MINERU_MAX_WAIT_TIME}s)"
                logger.error(f"❌ {error_msg}")
                raise PDFProcessingError(error_msg)

        except httpx.HTTPError as e:
            error_msg = f"HTTP error polling MinerU: {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)
        except KeyError as e:
            error_msg = f"Unexpected MinerU API response format: missing {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)

    async def _download_and_extract_text(self, zip_url: str) -> PDFExtractionResult:
        """Download ZIP from MinerU and extract text.

        Args:
            zip_url: URL to result ZIP file

        Returns:
            PDFExtractionResult with extracted text

        Raises:
            PDFProcessingError: If download or extraction fails
        """
        try:
            # Download ZIP
            logger.info("📥 Downloading MinerU results...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(zip_url)

                if response.status_code != 200:
                    error_msg = f"Failed to download ZIP (status {response.status_code})"
                    logger.error(f"❌ {error_msg}")
                    raise PDFProcessingError(error_msg)

                zip_bytes = response.content
                logger.info(f"✅ Downloaded ZIP ({len(zip_bytes) / 1024 / 1024:.1f}MB)")

            # Extract text from ZIP
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract ZIP
                with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                    zf.extractall(temp_dir)

                # Find content_list.json (has page information)
                content_list_files = list(Path(temp_dir).glob("*_content_list.json"))

                if not content_list_files:
                    logger.warning("⚠️ No content_list.json found, falling back to full.md")
                    # Fallback to markdown
                    return await self._extract_from_markdown(temp_dir)

                content_list_file = content_list_files[0]
                logger.debug(f"Using content list: {content_list_file.name}")

                # Read and parse JSON
                with open(content_list_file, "r", encoding="utf-8") as f:
                    content_list = json.loads(f.read())

                logger.info(f"✅ Loaded content list: {len(content_list)} blocks")

                # Count block types
                type_counts = {}
                for block in content_list:
                    block_type = block.get("type", "unknown")
                    type_counts[block_type] = type_counts.get(block_type, 0) + 1

                logger.info(
                    f"   Block types: {dict(sorted(type_counts.items()))} "
                    f"(tables={type_counts.get('table', 0)}, "
                    f"images={type_counts.get('image', 0)}, "
                    f"equations={type_counts.get('equation', 0)})"
                )

                # Group content by page (include tables, figures, equations)
                pages_dict = {}
                for block in content_list:
                    block_type = block.get("type")
                    page_idx = block.get("page_idx", 0)
                    text = None

                    # Extract text based on block type
                    if block_type in ["text", "title"]:
                        text = block.get("text", "").strip()

                    elif block_type == "table":
                        # Include table with caption and body
                        # Note: caption and footnote are lists of strings
                        caption = block.get("table_caption", [])
                        body = block.get("table_body", "").strip()
                        footnote = block.get("table_footnote", [])

                        parts = []
                        if caption:
                            caption_text = (
                                " ".join(caption) if isinstance(caption, list) else str(caption)
                            )
                            parts.append(f"[TABLE CAPTION] {caption_text.strip()}")
                        if body:
                            parts.append(f"[TABLE]\n{body}\n[/TABLE]")
                        if footnote:
                            footnote_text = (
                                " ".join(footnote) if isinstance(footnote, list) else str(footnote)
                            )
                            if footnote_text.strip():
                                parts.append(f"[TABLE FOOTNOTE] {footnote_text.strip()}")

                        text = "\n".join(parts) if parts else None

                    elif block_type == "image":
                        # Include figure with caption
                        # Note: caption and footnote are lists of strings
                        caption = block.get("image_caption", [])
                        footnote = block.get("image_footnote", [])
                        img_path = block.get("img_path", "").strip()

                        parts = []
                        if caption:
                            caption_text = (
                                " ".join(caption) if isinstance(caption, list) else str(caption)
                            )
                            parts.append(f"[FIGURE] {caption_text.strip()}")
                        else:
                            parts.append("[FIGURE]")

                        if img_path:
                            parts.append(f"(Image: {img_path})")
                        if footnote:
                            footnote_text = (
                                " ".join(footnote) if isinstance(footnote, list) else str(footnote)
                            )
                            if footnote_text.strip():
                                parts.append(f"[FIGURE FOOTNOTE] {footnote_text.strip()}")

                        text = " ".join(parts) if parts else None

                    elif block_type == "equation":
                        # Include LaTeX equation
                        eq_text = block.get("text", "").strip()
                        if eq_text:
                            text = f"[EQUATION]\n{eq_text}\n[/EQUATION]"

                    elif block_type == "code":
                        # Include code block with optional caption
                        caption = block.get("code_caption", [])
                        body = block.get("code_body", "").strip()
                        sub_type = block.get("sub_type", "")

                        parts = []
                        if caption:
                            caption_text = (
                                " ".join(caption) if isinstance(caption, list) else caption
                            )
                            parts.append(f"[CODE CAPTION] {caption_text}")

                        if body:
                            if sub_type == "algorithm":
                                parts.append(f"[ALGORITHM]\n{body}\n[/ALGORITHM]")
                            else:
                                parts.append(f"[CODE]\n{body}\n[/CODE]")

                        text = "\n".join(parts) if parts else None

                    elif block_type == "list":
                        # Include list items
                        list_items = block.get("list_items", [])
                        sub_type = block.get("sub_type", "")

                        if list_items:
                            if sub_type == "ref_text":
                                header = "[REFERENCES]"
                            else:
                                header = "[LIST]"

                            items_text = "\n".join(f"- {item}" for item in list_items)
                            text = f"{header}\n{items_text}\n[/LIST]"

                    # Add to page
                    if text:
                        if page_idx not in pages_dict:
                            pages_dict[page_idx] = []
                        pages_dict[page_idx].append(text)

                # Convert to PDFPageContent objects (1-indexed page numbers)
                pages = []
                for page_idx in sorted(pages_dict.keys()):
                    page_text = "\n".join(pages_dict[page_idx])
                    pages.append(PDFPageContent(page_number=page_idx + 1, text=page_text))

                logger.info(f"✅ Extracted {len(pages)} pages")

                # Create annotated text with page markers (for consistency with PyPDF)
                annotated_parts = []
                for page in pages:
                    annotated_parts.append(
                        f"<<PAGE {page.page_number}>>\n{page.text}\n<<END PAGE {page.page_number}>>"
                    )

                full_text = "\n\n".join(annotated_parts)

                logger.info(f"✅ Total text: {len(full_text):,} chars")

                return PDFExtractionResult(full_text=full_text, pages=pages)

        except httpx.HTTPError as e:
            error_msg = f"HTTP error downloading ZIP: {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)
        except zipfile.BadZipFile as e:
            error_msg = f"Invalid ZIP file: {e}"
            logger.error(f"❌ {error_msg}")
            raise PDFProcessingError(error_msg)
        except Exception as e:
            error_msg = f"Error extracting text from ZIP: {e}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            raise PDFProcessingError(error_msg)

    async def _extract_from_markdown(self, temp_dir: str) -> PDFExtractionResult:
        """Fallback: Extract text from markdown file.

        Args:
            temp_dir: Temporary directory with extracted ZIP

        Returns:
            PDFExtractionResult

        Raises:
            PDFProcessingError: If markdown file not found
        """
        # Find markdown file
        md_file = os.path.join(temp_dir, "full.md")

        if not os.path.exists(md_file):
            md_files = list(Path(temp_dir).rglob("*.md"))
            if not md_files:
                logger.error("❌ No markdown file found in MinerU output")
                raise PDFProcessingError("Invalid MinerU output: no markdown file found")
            md_file = md_files[0]

        # Read markdown content
        with open(md_file, "r", encoding="utf-8") as f:
            markdown_text = f.read()

        logger.info(f"✅ Extracted text from markdown ({len(markdown_text):,} chars)")

        # Parse pages from markdown (best effort)
        pages = self._parse_pages_from_markdown(markdown_text)

        # Create annotated text with page markers
        annotated_parts = []
        for page in pages:
            annotated_parts.append(
                f"<<PAGE {page.page_number}>>\n{page.text}\n<<END PAGE {page.page_number}>>"
            )

        full_text = "\n\n".join(annotated_parts)

        return PDFExtractionResult(full_text=full_text, pages=pages)

    def _parse_pages_from_markdown(self, markdown_text: str) -> List[PDFPageContent]:
        """Parse page content from markdown text.

        MinerU may include page markers in markdown. If not present,
        treat entire text as single page.

        Args:
            markdown_text: Markdown text from MinerU

        Returns:
            List of PDFPageContent objects
        """
        # Try to find page markers (e.g., "# Page 1", "## Page 1", etc.)
        # This is best-effort; MinerU format may vary
        page_pattern = r"#+ Page (\d+)"
        matches = list(re.finditer(page_pattern, markdown_text, re.IGNORECASE))

        if matches:
            logger.debug(f"Found {len(matches)} page markers in markdown")
            pages = []

            for i, match in enumerate(matches):
                page_num = int(match.group(1))
                start_pos = match.end()

                # Find end position (start of next page or end of text)
                if i + 1 < len(matches):
                    end_pos = matches[i + 1].start()
                else:
                    end_pos = len(markdown_text)

                page_text = markdown_text[start_pos:end_pos].strip()

                if page_text:
                    pages.append(PDFPageContent(page_number=page_num, text=page_text))

            if pages:
                return pages

        # No page markers found, treat as single page
        logger.debug("No page markers found in markdown, treating as single page")
        return [PDFPageContent(page_number=1, text=markdown_text)]
