import structlog
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import Request, Response
import time

# Configuration de structlog pour des logs au format JSON
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

def get_logger(name: str = "nova_systems"):
    """Retourne un logger structuré"""
    return structlog.get_logger(name)

# Middleware pour logger chaque requête HTTP
async def logging_middleware(request: Request, call_next):
    logger = get_logger("http")
    start_time = time.time()
    
    # On logue le début de la requête (optionnel)
    logger.info(
        "request_start",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else "unknown"
    )
    
    response = await call_next(request)
    
    # On logue la fin avec la durée
    duration_ms = (time.time() - start_time) * 1000
    logger.info(
        "request_end",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
        client_ip=request.client.host if request.client else "unknown"
    )
    
    return response