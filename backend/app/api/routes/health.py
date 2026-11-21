import asyncio
import logging
import time
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)
router = APIRouter()

# This public endpoint makes a paid LLM call, so only one probe runs at a time and the
# result is cached (success 5 min, failure 1 min) no matter how often it is requested.
_llm_lock = asyncio.Lock()
_llm_cache = {"ok": False, "until": 0.0}


@router.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    logger.info("🏥 Health check requested")

    # Check various system components
    api_key_configured = bool(settings.LLM_API_KEY and len(settings.LLM_API_KEY) > 10)

    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "MetaMate Extraction API",
        "version": "1.1.0",
        "components": {
            "llm_api_key": "✅ Configured" if api_key_configured else "❌ Not configured",
            "pdf_processor": f"🎭 {settings.PDF_PROCESSOR}",
            "llm_model": f"🤖 {settings.LLM_MODEL}",
            "cors_origins": f"🌐 {len(settings.CORS_ORIGINS)} origin(s)",
            "rate_limiting": "✅ Enabled",
            "max_file_size": f"📄 {settings.MAX_FILE_SIZE_MB}MB",
        },
        "limits": {
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "max_files_per_batch": settings.MAX_FILES_PER_BATCH,
            "extraction_rate_limit_per_minute": settings.EXTRACTION_RATE_LIMIT_PER_MINUTE,
        },
        "api_key_configured": api_key_configured,
        "api_key_length": len(settings.LLM_API_KEY) if settings.LLM_API_KEY else 0,
    }

    if not api_key_configured:
        logger.warning("⚠️ Health check: LLM API key not configured")
        health_status["status"] = "degraded"
        health_status["warning"] = "LLM API key not configured"

    logger.info(f"🏥 Health status: {health_status['status']}")
    return health_status


@router.get("/health/llm")
async def llm_health_check():
    """End-to-end check: returns 503 if the LLM can't serve an extraction (details only logged)."""
    async with _llm_lock:
        if time.monotonic() > _llm_cache["until"]:
            try:
                ping = [{"name": "ok", "data_type": "Text", "include_in_extraction": True}]
                if not await LLMService().extract_with_schema("ping", ping):
                    raise RuntimeError("empty LLM result")
                _llm_cache.update(ok=True, until=time.monotonic() + 300)
            except Exception as e:
                logger.error(f"❌ LLM health check failed: {e}")
                _llm_cache.update(ok=False, until=time.monotonic() + 60)
    if not _llm_cache["ok"]:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "operational"}
