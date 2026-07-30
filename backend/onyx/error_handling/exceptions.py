"""OnyxError — the single exception type for all Onyx business errors.

Raise ``OnyxError`` instead of ``HTTPException`` in business code.  A global
FastAPI exception handler (registered via ``register_onyx_exception_handlers``)
converts it into a JSON response with the standard
``{"error_code": "...", "detail": "..."}`` shape.

Usage::

    from onyx.error_handling.error_codes import OnyxErrorCode
    from onyx.error_handling.exceptions import OnyxError

    raise OnyxError(OnyxErrorCode.NOT_FOUND, "Session not found")

For upstream errors with a dynamic HTTP status (e.g. billing service),
use ``status_code_override``::

    raise OnyxError(
        OnyxErrorCode.BAD_GATEWAY,
        detail,
        status_code_override=upstream_status,
    )
"""

from fastapi import FastAPI
from fastapi import Request
from fastapi.responses import JSONResponse

from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.utils.logger import setup_logger

logger = setup_logger()


class OnyxError(Exception):
    """Structured error that maps to a specific ``OnyxErrorCode``.

    Attributes:
        error_code: The ``OnyxErrorCode`` enum member.
        detail: Human-readable detail (defaults to the error code string).
        status_code: HTTP status — either overridden or from the error code.
    """

    def __init__(
        self,
        error_code: OnyxErrorCode,
        detail: str | None = None,
        *,
        status_code_override: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        resolved_detail = detail or error_code.code
        super().__init__(resolved_detail)
        self.error_code = error_code
        self.detail = resolved_detail
        self._status_code_override = status_code_override
        self.headers = headers

    @property
    def status_code(self) -> int:
        return self._status_code_override or self.error_code.status_code


def onyx_error_from_status(
    status_code: int,
    detail: str | None = None,
    *,
    headers: dict[str, str] | None = None,
) -> OnyxError:
    """Build an ``OnyxError`` for legacy status-code based branches.

    New endpoint code should choose a specific ``OnyxErrorCode`` directly. This
    adapter is for migrations away from ``HTTPException`` where preserving the
    existing status/detail is safer than changing endpoint behavior at the same
    time.
    """
    resolved_status_code = int(status_code)
    error_code = {
        400: OnyxErrorCode.VALIDATION_ERROR,
        401: OnyxErrorCode.UNAUTHENTICATED,
        402: OnyxErrorCode.FEATURE_NOT_AVAILABLE,
        403: OnyxErrorCode.INSUFFICIENT_PERMISSIONS,
        404: OnyxErrorCode.NOT_FOUND,
        409: OnyxErrorCode.CONFLICT,
        413: OnyxErrorCode.PAYLOAD_TOO_LARGE,
        422: OnyxErrorCode.VALIDATION_ERROR,
        429: OnyxErrorCode.RATE_LIMITED,
        500: OnyxErrorCode.INTERNAL_ERROR,
        501: OnyxErrorCode.NOT_IMPLEMENTED,
        502: OnyxErrorCode.BAD_GATEWAY,
        503: OnyxErrorCode.SERVICE_UNAVAILABLE,
        504: OnyxErrorCode.GATEWAY_TIMEOUT,
    }.get(resolved_status_code, OnyxErrorCode.INTERNAL_ERROR)
    return OnyxError(
        error_code,
        detail,
        status_code_override=resolved_status_code,
        headers=headers,
    )


def log_onyx_error(exc: OnyxError) -> None:
    detail = exc.detail
    status_code = exc.status_code
    if status_code >= 500:
        logger.error("OnyxError %s: %s", exc.error_code.code, detail)
    elif status_code >= 400:
        logger.warning("OnyxError %s: %s", exc.error_code.code, detail)


def onyx_error_to_json_response(exc: OnyxError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.error_code.detail(exc.detail),
        headers=exc.headers,
    )


def register_onyx_exception_handlers(app: FastAPI) -> None:
    """Register a global handler that converts ``OnyxError`` to JSON responses.

    Must be called *after* the app is created but *before* it starts serving.
    The handler logs at WARNING for 4xx and ERROR for 5xx.
    """

    @app.exception_handler(OnyxError)
    async def _handle_onyx_error(
        request: Request,  # noqa: ARG001
        exc: OnyxError,
    ) -> JSONResponse:
        log_onyx_error(exc)
        return onyx_error_to_json_response(exc)
