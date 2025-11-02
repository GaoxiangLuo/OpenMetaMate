import asyncio
import logging
import os
import re
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import TokenTextSplitter

from app.core.config import settings
from app.core.exceptions import PDFProcessingError

logger = logging.getLogger(__name__)


@dataclass
class PDFPageContent:
    """Lightweight container for the text extracted from a single PDF page."""

    page_number: int
    text: str


@dataclass
class PDFExtractionResult:
    """Aggregate text content and per-page breakdown produced by a PDF processor."""

    full_text: str
    pages: List[PDFPageContent]


class PDFProcessorType(Enum):
    """Available PDF processor implementations."""

    PYPDF = "pypdf"
    MINERU = "mineru"


class BasePDFProcessor(ABC):
    """Abstract base class for PDF processors."""

    def __init__(self):
        self.chunk_size = settings.resolve_chunk_size(settings.LLM_MODEL)
        self.chunk_overlap = settings.TEXT_CHUNK_OVERLAP

    @abstractmethod
    async def extract_text_from_pdf(self, pdf_content: bytes) -> PDFExtractionResult:
        """Extract textual content for the entire PDF along with per-page metadata.

        Args:
            pdf_content: PDF file content represented as bytes.

        Returns:
            PDFExtractionResult containing full aggregated text and page-level slices.
        """
        raise NotImplementedError

    async def chunk_text(self, text: str) -> List[str]:
        """Split text into manageable chunks using TokenTextSplitter.

        Args:
            text: The full document text which may include page markers.

        Returns:
            List of text chunks appropriate for prompting the LLM.
        """

        def _chunk():
            if not text:
                logger.warning("⚠️ No text to chunk")
                return []

            text_splitter = TokenTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )

            # TokenTextSplitter operates in token units, so we inspect the tokenizer
            # directly to compare apples-to-apples with the configured chunk size.
            token_length = len(
                text_splitter._tokenizer.encode(  # type: ignore[attr-defined]
                    text,
                    allowed_special=text_splitter._allowed_special,  # type: ignore[attr-defined]
                    disallowed_special=text_splitter._disallowed_special,  # type: ignore[attr-defined]
                )
            )

            # If text is small enough, don't chunk
            if token_length <= self.chunk_size:
                logger.info(f"📦 Text fits in single chunk ({token_length:,} tokens)")
                return [text]

            logger.info(f"✂️ Splitting text ({token_length:,} tokens) into chunks")
            logger.debug(
                f"🔧 Chunk size: {self.chunk_size} tokens, overlap: {self.chunk_overlap} tokens"
            )

            chunks = text_splitter.split_text(text)

            logger.info(f"✅ Created {len(chunks)} chunks")
            for i, chunk in enumerate(chunks, 1):
                logger.debug(f"📦 Chunk {i}: {len(chunk):,} chars")

            return chunks

        return await asyncio.to_thread(_chunk)


class PyPDFProcessor(BasePDFProcessor):
    """PDF processor using PyPDF/langchain implementation."""

    async def extract_text_from_pdf(self, pdf_content: bytes) -> PDFExtractionResult:
        """Extract text from PDF bytes using PyPDFLoader with page annotations."""

        def _extract():
            if not pdf_content:
                logger.error("❌ [STAGE 3/6] Empty PDF content provided")
                raise PDFProcessingError("Empty PDF content")

            logger.info("📄 [STAGE 3/6] Starting PDF text extraction...")

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_file.write(pdf_content)
                tmp_path = tmp_file.name
                logger.debug(f"📝 Created temp file: {tmp_path}")

            try:
                loader = PyPDFLoader(tmp_path)
                pages = loader.load()

                if not pages:
                    logger.warning("⚠️ No pages found in PDF")
                    raise PDFProcessingError("PDF contains no pages")

                logger.info(f"📖 Loaded {len(pages)} pages from PDF")

                # Extract and clean text from all pages, preserving page order markers
                page_sections: List[PDFPageContent] = []
                annotated_parts: List[str] = []
                for i, page in enumerate(pages, 1):
                    if page.page_content:
                        cleaned_text = re.sub("\n\n+", "\n", page.page_content)
                        page_sections.append(PDFPageContent(page_number=i, text=cleaned_text))
                        annotated_parts.append(f"<<PAGE {i}>>\n{cleaned_text}\n<<END PAGE {i}>>")
                        logger.debug(f"📑 Page {i}: {len(page.page_content)} chars")
                    else:
                        logger.debug(f"📑 Page {i}: Empty")

                input_text = "\n\n".join(annotated_parts)

                if not input_text.strip():
                    logger.warning("❌ [STAGE 3/6] PDF contains no extractable text")
                    raise PDFProcessingError("No text could be extracted from PDF")

                logger.info(
                    f"✅ [STAGE 3/6] PDF extracted - {len(pages)} pages, {len(input_text):,} chars"
                )
                return PDFExtractionResult(full_text=input_text, pages=page_sections)

            except PDFProcessingError:
                raise
            except Exception as e:
                logger.error(f"❌ [STAGE 3/6] PDF extraction failed: {e}", exc_info=True)
                raise PDFProcessingError(f"Failed to extract text from PDF: {e}")

            finally:
                # Clean up temp file
                try:
                    os.unlink(tmp_path)
                    logger.debug(f"🗑️ Cleaned up temp file: {tmp_path}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to clean up temp file: {e}")

        return await asyncio.to_thread(_extract)


class PDFProcessorFactory:
    """Factory for creating PDF processor instances with automatic fallback"""

    _processors = {
        PDFProcessorType.PYPDF: PyPDFProcessor,
    }

    @classmethod
    def _register_mineru_processor(cls):
        """Lazily register MinerU processor (only if configured)"""
        if PDFProcessorType.MINERU not in cls._processors:
            try:
                from app.services.mineru_processor import MinerUPDFProcessor

                cls._processors[PDFProcessorType.MINERU] = MinerUPDFProcessor
                logger.debug("✅ MinerU processor registered")
            except ImportError as e:
                logger.warning(f"⚠️ Failed to import MinerU processor: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to register MinerU processor: {e}")

    @classmethod
    def create(cls, processor_type: PDFProcessorType = PDFProcessorType.PYPDF) -> BasePDFProcessor:
        """Create a PDF processor instance

        Args:
            processor_type: Type of processor to create

        Returns:
            PDF processor instance

        Raises:
            ValueError: If processor type is not supported
        """
        # Register MinerU if requested
        if processor_type == PDFProcessorType.MINERU:
            cls._register_mineru_processor()

        processor_class = cls._processors.get(processor_type)
        if not processor_class:
            logger.error(f"❌ Unknown processor type: {processor_type}")
            raise ValueError(f"Unknown processor type: {processor_type}")

        try:
            processor = processor_class()
            logger.info(f"🎭 Created {processor_type.value} PDF processor")
            return processor
        except Exception as e:
            logger.error(f"❌ Failed to create {processor_type.value} processor: {e}")
            raise

    @classmethod
    async def extract_with_fallback(
        cls, pdf_content: bytes, enhanced_extraction: bool = False
    ) -> PDFExtractionResult:
        """Extract text from PDF with automatic fallback.

        If enhanced_extraction is True and MinerU is configured, try MinerU first.
        Otherwise, use PyPDF directly.

        Args:
            pdf_content: PDF file content as bytes
            enhanced_extraction: If True, use MinerU for better table/figure extraction (slower)

        Returns:
            PDFExtractionResult from successful processor

        Raises:
            PDFProcessingError: If all processors fail
        """
        from app.core.config import settings

        # Determine if MinerU should be tried (only if user requested AND it's configured)
        use_mineru = enhanced_extraction and bool(
            settings.MINERU_API_KEY and settings.AWS_S3_TEMP_BUCKET
        )

        if use_mineru:
            # Try MinerU first
            try:
                logger.info(
                    "🚀 Attempting extraction with MinerU (will fallback to PyPDF if needed)"
                )
                mineru_processor = cls.create(PDFProcessorType.MINERU)
                result = await mineru_processor.extract_text_from_pdf(pdf_content)
                logger.info("✅ MinerU extraction successful")
                return result

            except PDFProcessingError as e:
                logger.warning(f"⚠️ MinerU extraction failed: {e}")
                logger.info("🔄 Falling back to PyPDF processor...")

            except Exception as e:
                logger.warning(f"⚠️ MinerU extraction failed unexpectedly: {e}")
                logger.info("🔄 Falling back to PyPDF processor...")

        # Use PyPDF (either as fallback or primary)
        try:
            if use_mineru:
                logger.info("📄 Using PyPDF fallback processor")
            elif enhanced_extraction:
                logger.info(
                    "📄 Using PyPDF processor "
                    "(MinerU not configured, but enhanced extraction requested)"
                )
            else:
                logger.info("📄 Using PyPDF processor (standard extraction)")

            pypdf_processor = cls.create(PDFProcessorType.PYPDF)
            result = await pypdf_processor.extract_text_from_pdf(pdf_content)
            logger.info("✅ PyPDF extraction successful")
            return result

        except Exception as e:
            logger.error(f"❌ PyPDF extraction failed: {e}")
            raise PDFProcessingError(f"All PDF processors failed. Last error: {e}")
