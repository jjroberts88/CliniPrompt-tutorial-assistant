from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from ..services.session_manager import SessionManagerError, SessionNotFoundError, ConcurrencyLimitError
from .sessions import router as sessions_router
from .health import router as health_router


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Starting ClinIPrompt Tutorial Assistant API")
    yield
    # Shutdown
    logger.info("Shutting down ClinIPrompt Tutorial Assistant API")


# Create FastAPI app
app = FastAPI(
    title="ClinIPrompt Tutorial Assistant API",
    description="REST API for medical tutorial processing and podcast-style summary generation",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],  # Streamlit and dev frontends
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(SessionNotFoundError)
async def session_not_found_handler(request: Request, exc: SessionNotFoundError):
    """Handle session not found errors"""
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "SESSION_NOT_FOUND",
                "message": str(exc),
                "timestamp": datetime.now().isoformat()
            }
        }
    )


@app.exception_handler(ConcurrencyLimitError)  
async def concurrency_limit_handler(request: Request, exc: ConcurrencyLimitError):
    """Handle concurrency limit errors"""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "CONCURRENCY_LIMIT_EXCEEDED",
                "message": str(exc),
                "timestamp": datetime.now().isoformat()
            }
        }
    )


@app.exception_handler(SessionManagerError)
async def session_manager_error_handler(request: Request, exc: SessionManagerError):
    """Handle general session manager errors"""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "SESSION_MANAGER_ERROR", 
                "message": str(exc),
                "timestamp": datetime.now().isoformat()
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "timestamp": datetime.now().isoformat()
            }
        }
    )


# Include routers
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "ClinIPrompt Tutorial Assistant API",
        "version": "0.1.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }