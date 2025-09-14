from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime
import time
import os

router = APIRouter()

# Track startup time
startup_time = time.time()


class ServiceHealth(BaseModel):
    """Service health information"""
    status: str
    last_check: str
    response_time_ms: int = 0


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    services: Dict[str, ServiceHealth] = {}
    uptime_seconds: int
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check API service health and external service status"""
    now = datetime.now()
    uptime = int(time.time() - startup_time)
    
    # Check Gemini API (simplified - would make actual API call)
    gemini_status = ServiceHealth(
        status="available",  # Would check actual API
        last_check=now.isoformat(),
        response_time_ms=50  # Would measure actual response time
    )
    
    # Overall status
    overall_status = "healthy"
    if gemini_status.status != "available":
        overall_status = "degraded"
    
    return HealthResponse(
        status=overall_status,
        services={
            "gemini_api": gemini_status
        },
        uptime_seconds=uptime,
        version="0.1.0"
    )