import logging
from datetime import datetime

from fastapi import APIRouter

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


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
        "version": "2.0.0",
        "components": {
            "llm_api_key": "✅ Configured" if api_key_configured else "❌ Not configured",
            "pdf_processor": f"🎭 {settings.PDF_PROCESSOR}",
            "llm_model": f"🤖 {settings.LLM_MODEL}",
            "cors_origins": f"🌐 {len(settings.CORS_ORIGINS)} origin(s)",
            "rate_limiting": "✅ Enabled",
            "max_file_size": f"📄 {settings.MAX_FILE_SIZE_MB}MB",
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
