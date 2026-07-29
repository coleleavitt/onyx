"""FastAPI exception handlers that build client-facing error responses.

These live outside ``onyx.main`` so they can be imported (and tested) without
pulling in the whole application graph and its import-time side effects.

The rule they share: a response body may carry author-written detail, never
whatever ``str()`` an internal exception happens to produce. Unhandled errors
render driver internals -- SQLAlchemy includes the full statement and its bound
parameters -- and ``RequestValidationError`` renders a source frame with
absolute server paths. Both belong in the log, not the response.
"""

import traceback
from typing import Any

from fastapi import HTTPException
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from onyx.server.utils import BasicAuthenticationError
from onyx.utils.logger import setup_logger

logger = setup_logger()


def log_http_error(request: Request, exc: Exception) -> JSONResponse:
    status_code = getattr(exc, "status_code", 500)

    if isinstance(exc, BasicAuthenticationError):
        # For BasicAuthenticationError, just log a brief message without stack trace
        # (almost always spammy)
        logger.debug("Authentication failed: %s", str(exc))

    elif status_code == 404 and request.url.path == "/metrics":
        # Log 404 errors for the /metrics endpoint with debug level
        logger.debug("404 error for /metrics endpoint: %s", str(exc))

    elif status_code >= 400:
        error_msg = f"{str(exc)}\n"
        error_msg += "".join(traceback.format_tb(exc.__traceback__))
        logger.error(error_msg)

    if isinstance(exc, HTTPException):
        # Author-written detail; safe to return as-is.
        detail = exc.detail
    elif status_code >= 500:
        # Starlette routes *every* unhandled exception to the handler registered
        # for 500, so `exc` here is an arbitrary internal error. Read the request
        # id off the scope-backed request state rather than the contextvar, which
        # is set inside a BaseHTTPMiddleware child context that ServerErrorMiddleware
        # -- sitting outside every user middleware -- cannot see.
        request_id = getattr(request.state, "onyx_request_id", None)
        detail = (
            "Internal server error (request id: %s)" % request_id
            if request_id
            else "Internal server error"
        )
    else:
        detail = str(exc)

    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
    )


def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        logger.error(
            "Unexpected exception type in validation_exception_handler - %s", type(exc)
        )
        raise exc

    # Project the structured errors instead of echoing `str(exc)`, which carries
    # a source frame -- absolute server paths -- into the response body. The full
    # exception still goes to the log.
    logger.exception("%s: %s", request, exc.errors())
    message = "; ".join(
        "%s: %s"
        % (".".join(str(part) for part in err.get("loc", ())), err.get("msg", ""))
        for err in exc.errors()
    )
    content: dict[str, Any] = {
        "status_code": 422,
        "message": message or "Validation error",
        "data": None,
    }
    return JSONResponse(content=content, status_code=422)


def value_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ValueError):
        logger.error("Unexpected exception type in value_error_handler - %s", type(exc))
        raise exc

    try:
        raise (exc)
    except Exception:
        # log stacktrace
        logger.exception("ValueError")
    return JSONResponse(
        status_code=400,
        content={"message": str(exc)},
    )
