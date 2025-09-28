import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)


class Settings:
    # LLM Configuration
    LLM_API_URL: str = os.getenv("LLM_API_URL", "https://api.openai.com/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    # Default model, can be changed to any compatible LLM
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4.1-2025-04-14")

    _temperature_env = os.getenv("LLM_TEMPERATURE")
    if _temperature_env in (None, ""):
        TEMPERATURE: Optional[float] = 0.0
    else:
        try:
            TEMPERATURE = float(_temperature_env)
        except ValueError:
            logger.warning(
                "⚠️ Invalid LLM_TEMPERATURE value '%s'; falling back to default", _temperature_env
            )
            TEMPERATURE = None
    SEED: int = 42
    TOP_P: float = 0.95

    # CORS Configuration
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "https://metamate.online").split(",")

    # Processing Configuration
    TEXT_CHUNK_SIZE: int = 88_000
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

    def resolve_temperature(self, model: str) -> Optional[float]:
        """Return a temperature compatible with the configured model."""

        if not model:
            return self.TEMPERATURE

        normalized_model = model.lower()
        if normalized_model.startswith("gpt-5"):
            if self.TEMPERATURE not in (None, 1.0):
                logger.warning(
                    "⚠️ Ignoring temperature %s for model %s; only the default is supported",
                    self.TEMPERATURE,
                    model,
                )
            return None

        return self.TEMPERATURE

    def use_responses_api(self, model: str) -> bool:
        """Return True when the model should be called via the Responses API."""

        return bool(model and model.lower().startswith("gpt-5"))

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
        effective_chunk_size = self.resolve_chunk_size(self.LLM_MODEL)
        if self.TEXT_CHUNK_OVERLAP >= effective_chunk_size:
            errors.append("TEXT_CHUNK_OVERLAP must be less than the resolved chunk size")

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
        logger.info(f"  📦 Chunk size: {effective_chunk_size} characters")
        logger.info(f"  🌐 CORS origins: {self.CORS_ORIGINS}")

        return self

    def resolve_chunk_size(self, model: str) -> int:
        """Return a chunk size aligned with the configured model family."""

        normalized_model = (model or "").lower()

        if normalized_model.startswith("gpt-4.1"):
            chunk_size = 960_000
        elif normalized_model.startswith("gpt-5"):
            chunk_size = 360_000
        else:
            chunk_size = self.TEXT_CHUNK_SIZE

        return max(chunk_size, self.TEXT_CHUNK_OVERLAP + 1)


settings = Settings()
