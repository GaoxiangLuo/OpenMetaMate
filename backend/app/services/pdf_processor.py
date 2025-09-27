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


class BasePDFProcessor(ABC):
    """Abstract base class for PDF processors."""

    def __init__(self):
        self.chunk_size = settings.TEXT_CHUNK_SIZE
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

            text_length = len(text)

            # If text is small enough, don't chunk
            if text_length <= self.chunk_size:
                logger.info(f"📦 Text fits in single chunk ({text_length:,} chars)")
                return [text]

            logger.info(f"✂️ Splitting text ({text_length:,} chars) into chunks")
            logger.debug(f"🔧 Chunk size: {self.chunk_size}, overlap: {self.chunk_overlap}")

            text_splitter = TokenTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
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
                logger.error("📄 Empty PDF content provided")
                raise PDFProcessingError("Empty PDF content")

            logger.info(f"📄 Processing PDF ({len(pdf_content):,} bytes)")

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
                    logger.warning("⚠️ PDF contains no extractable text")
                    raise PDFProcessingError("No text could be extracted from PDF")

                logger.info(f"✅ Successfully extracted {len(input_text):,} characters from PDF")
                return PDFExtractionResult(full_text=input_text, pages=page_sections)

            except PDFProcessingError:
                raise
            except Exception as e:
                logger.error(f"❌ PyPDF extraction failed: {e}", exc_info=True)
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
    """Factory for creating PDF processor instances"""

    _processors = {
        PDFProcessorType.PYPDF: PyPDFProcessor,
    }

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
