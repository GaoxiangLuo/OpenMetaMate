import logging
import os
from typing import List

logger = logging.getLogger(__name__)


class Settings:
    # LLM Configuration
    LLM_API_URL: str = os.getenv("LLM_API_URL", "https://api.openai.com/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    # Default model, can be changed to any compatible LLM
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4.1-2025-04-14")
    TEMPERATURE: float = 0.0
    SEED: int = 42
    TOP_P: float = 0.95

    # CORS Configuration
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "https://metamate.online").split(",")

    # Processing Configuration
    TEXT_CHUNK_SIZE: int = 960000
    TEXT_CHUNK_OVERLAP: int = 200
    MAX_FILE_SIZE_MB: float = float(os.getenv("MAX_FILE_SIZE_MB", 10))
    MAX_FILES_PER_BATCH: int = 100

    # PDF Processor Configuration
    # Options: pypdf, docling, mineru, mathpix, textract
    PDF_PROCESSOR: str = os.getenv("PDF_PROCESSOR", "pypdf")

    # Default thresholds for "not found" values
    NOT_FOUND_STRINGS: List[str] = ["", "na", "n/a", "null", "none", "not found", "not available"]
    NOT_FOUND_NUMERIC_VALUE: int = -1

    # Server Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    def validate(self):
        """Validate required settings"""
        logger.info("🔍 Validating configuration settings...")

        errors = []
        warnings = []

        # Required settings
        if not self.LLM_API_KEY:
            errors.append("LLM_API_KEY environment variable is required")
        elif len(self.LLM_API_KEY) < 10:
            warnings.append("LLM_API_KEY seems too short")

        # Validate PDF processor
        valid_processors = ["pypdf", "docling", "mineru", "mathpix", "textract"]
        if self.PDF_PROCESSOR.lower() not in valid_processors:
            warnings.append(f"Unknown PDF processor '{self.PDF_PROCESSOR}', will use pypdf")

        # Validate numeric settings
        if self.MAX_FILE_SIZE_MB <= 0:
            errors.append("MAX_FILE_SIZE_MB must be positive")
        elif self.MAX_FILE_SIZE_MB > 100:
            warnings.append(f"MAX_FILE_SIZE_MB is very large ({self.MAX_FILE_SIZE_MB}MB)")

        if self.MAX_FILES_PER_BATCH <= 0:
            errors.append("MAX_FILES_PER_BATCH must be positive")
        elif self.MAX_FILES_PER_BATCH > 1000:
            warnings.append(f"MAX_FILES_PER_BATCH is very large ({self.MAX_FILES_PER_BATCH})")

        if self.TEXT_CHUNK_SIZE <= 0:
            errors.append("TEXT_CHUNK_SIZE must be positive")

        if self.TEXT_CHUNK_OVERLAP < 0:
            errors.append("TEXT_CHUNK_OVERLAP cannot be negative")
        elif self.TEXT_CHUNK_OVERLAP >= self.TEXT_CHUNK_SIZE:
            errors.append("TEXT_CHUNK_OVERLAP must be less than TEXT_CHUNK_SIZE")

        # Validate CORS origins
        if not self.CORS_ORIGINS:
            warnings.append("No CORS origins configured, API may not be accessible from web")

        # Log warnings
        for warning in warnings:
            logger.warning(f"⚠️ {warning}")

        # Raise error if any critical issues
        if errors:
            for error in errors:
                logger.error(f"❌ {error}")
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")

        logger.info("✅ Configuration validated successfully")
        logger.info("🔧 Settings summary:")
        logger.info(f"  🤖 LLM Model: {self.LLM_MODEL}")
        logger.info(f"  🎭 PDF Processor: {self.PDF_PROCESSOR}")
        logger.info(f"  📄 Max file size: {self.MAX_FILE_SIZE_MB}MB")
        logger.info(f"  📦 Chunk size: {self.TEXT_CHUNK_SIZE} tokens")
        logger.info(f"  🌐 CORS origins: {self.CORS_ORIGINS}")

        return self


settings = Settings()
