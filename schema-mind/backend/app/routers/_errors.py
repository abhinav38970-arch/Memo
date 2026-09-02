"""Shared error handling for the API routers.

Maps service-layer failures to HTTP responses with clear ``detail`` strings
(the frontend shows ``detail`` verbatim) and the *right* status codes:

  * GroqRateLimitError        -> 429 (+ Retry-After)
  * GroqRequestTooLargeError  -> 413
  * other GroqError           -> 502 (upstream failure)
  * anything else             -> 500 (logged with traceback)
"""
import math
import traceback
from typing import Optional

from fastapi import HTTPException

from app.services.groq_client import GroqError


def http_error_from_exception(exc: Exception, *, action: str) -> HTTPException:
    """Translate ``exc`` (raised while doing ``action``) into an HTTPException."""
    if isinstance(exc, HTTPException):
        return exc
    if isinstance(exc, GroqError):
        headers: Optional[dict] = None
        if exc.retry_after:
            headers = {"Retry-After": str(int(math.ceil(exc.retry_after)))}
        print(f"[api] {action} failed ({exc.status_code}): {exc}", flush=True)
        return HTTPException(status_code=exc.status_code, detail=str(exc), headers=headers)
    traceback.print_exc()
    return HTTPException(
        status_code=500,
        detail=f"{action.capitalize()} failed: {exc}",
    )
