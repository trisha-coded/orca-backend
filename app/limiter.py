"""
API rate-limiting and concurrency management for the ORCA backend.
"""

import time
import asyncio
from typing import Dict, List
from fastapi import Request, HTTPException, status
from app.config import settings

# In-memory sliding window rate limiter
_request_history: Dict[str, List[float]] = {}
_limiter_lock = asyncio.Lock()

# Global semaphore for controlling concurrent agent runner workflows
workflow_semaphore = asyncio.Semaphore(50)


async def rate_limit_dependency(request: Request):
    """
    FastAPI dependency for sliding-window rate limiting per client IP.
    """
    client_ip = request.client.host if request.client else "127.0.0.1"
    now = time.time()
    window = 60.0  # 1 minute window
    limit = settings.RATE_LIMIT_PER_MINUTE

    async with _limiter_lock:
        if client_ip not in _request_history:
            _request_history[client_ip] = []

        # Filter out timestamps older than the sliding window
        _request_history[client_ip] = [
            ts for ts in _request_history[client_ip] if ts > now - window
        ]

        if len(_request_history[client_ip]) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: Max {limit} requests per minute. Please try again later."
            )

        _request_history[client_ip].append(now)
