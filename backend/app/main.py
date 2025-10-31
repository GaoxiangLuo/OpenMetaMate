import logging
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.routes import extraction, health
from app.core.config import settings
from app.core.exceptions import ExtractionError, MetaMateException, PDFProcessingError

# Configure logging with emoji support
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Validate settings on startup
try:
    settings.validate()
    logger.info("✅ Settings validated successfully")
except ValueError as e:
    logger.error(f"❌ Settings validation failed: {e}")
    sys.exit(1)

limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute", "2000 per hour"])

app = FastAPI(
    title="MetaMate Extraction API",
    description="Automated PDF data extraction for systematic reviews",
    version="2.0.0",
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
# Note: Using allow_credentials=True requires specific origins, not "*"
# This is critical for cross-origin requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


# Add middleware to log CORS requests for debugging
@app.middleware("http")
async def log_cors_requests(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin:
        logger.info(f"🌐 CORS request from origin: {origin} to path: {request.url.path}")
        logger.info(f"   Method: {request.method}, Headers: {dict(request.headers)}")

    response = await call_next(request)

    if origin:
        logger.info(f"   Response status: {response.status_code}")
        cors_headers = [h for h in response.headers.items() if "access-control" in h[0].lower()]
        logger.info(f"   CORS headers: {cors_headers}")

    return response


# Include routes
app.include_router(health.router, tags=["health"])
app.include_router(extraction.router, prefix="/api/v1", tags=["extraction"])


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 MetaMate API starting up...")
    logger.info(f"🔧 LLM Model: {settings.LLM_MODEL}")
    logger.info(f"🔧 PDF Processor: {settings.PDF_PROCESSOR}")
    logger.info(f"🌐 CORS origins: {settings.CORS_ORIGINS}")
    logger.info(f"📊 Max file size: {settings.MAX_FILE_SIZE_MB}MB")
    logger.info(f"📄 Max files per batch: {settings.MAX_FILES_PER_BATCH}")
    logger.info(f"🔑 API Key configured: {'✅' if settings.LLM_API_KEY else '❌'}")
    logger.info("✨ MetaMate API ready to serve requests!")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 MetaMate API shutting down...")


# Global exception handler for MetaMate exceptions
@app.exception_handler(MetaMateException)
async def metamate_exception_handler(request: Request, exc: MetaMateException):
    logger.error(f"❌ MetaMate exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc), "type": exc.__class__.__name__},
    )


# Global exception handler for PDF processing errors
@app.exception_handler(PDFProcessingError)
async def pdf_processing_exception_handler(request: Request, exc: PDFProcessingError):
    logger.error(f"📄❌ PDF processing error: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": f"PDF processing failed: {str(exc)}",
            "type": "PDFProcessingError",
        },
    )


# Global exception handler for extraction errors
@app.exception_handler(ExtractionError)
async def extraction_exception_handler(request: Request, exc: ExtractionError):
    logger.error(f"🔍❌ Extraction error: {exc}")
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": f"Data extraction failed: {str(exc)}",
            "type": "ExtractionError",
        },
    )


# Global exception handler for unexpected errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"💥 Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "An unexpected error occurred. Please try again later.",
            "type": "InternalServerError",
        },
    )
