"""Error responses must not echo server internals to the client.

Two handlers in `onyx.error_handling.handlers` build response bodies out of
exception objects:

* `log_http_error` -- registered for status 500, which Starlette also uses as
  the handler for *every* unhandled exception. It used to return `str(exc)`,
  so an unhandled SQLAlchemy error sent the full statement, the bound
  parameters, and the caller's user UUID to the client.
* `validation_exception_handler` -- used to return `str(exc)`, which carries a
  source frame (absolute server paths).

Both must stay quiet about internals while keeping author-written 4xx detail
intact.
"""

from typing import Any

import pytest
from fastapi import HTTPException
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from onyx.error_handling.handlers import log_http_error
from onyx.error_handling.handlers import validation_exception_handler

_LEAKY_DB_ERROR = (
    "(psycopg2.errors.InvalidRowCountInResultOffsetClause) OFFSET must not be "
    "negative\n[SQL: SELECT chat_session.id, chat_session.user_id FROM chat_session "
    "LIMIT %(param_1)s OFFSET %(param_2)s]\n"
    "[parameters: {'user_id_2': '55827feb-e7d1-474c-a06b-079b64b0d30b'}]"
)


def _request(request_id: str | None = None) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "path": "/chat/search",
        "headers": [],
        "query_string": b"",
        "state": {},
    }
    request = Request(scope)
    if request_id is not None:
        request.state.onyx_request_id = request_id
    return request


def _body(response: Any) -> str:
    return response.body.decode()


def test_unhandled_exception_does_not_leak_sql_or_parameters() -> None:
    response = log_http_error(_request("abc:12345678"), ValueError(_LEAKY_DB_ERROR))

    assert response.status_code == 500
    body = _body(response)
    assert "psycopg2" not in body
    assert "SELECT" not in body
    assert "55827feb-e7d1-474c-a06b-079b64b0d30b" not in body
    # The request id is the operator's handle on the logged stacktrace.
    assert "abc:12345678" in body


def test_unhandled_exception_without_request_id_omits_the_placeholder() -> None:
    """A missing id must not render as the literal string 'None'."""
    response = log_http_error(_request(), ValueError(_LEAKY_DB_ERROR))

    body = _body(response)
    assert "None" not in body
    assert "Internal server error" in body


@pytest.mark.parametrize("status_code", [400, 403, 404])
def test_author_written_http_exception_detail_is_preserved(status_code: int) -> None:
    """4xx detail is written by us and is what the UI shows the user."""
    response = log_http_error(
        _request("abc:12345678"),
        HTTPException(status_code=status_code, detail="Job not found."),
    )

    assert response.status_code == status_code
    assert "Job not found." in _body(response)


def test_validation_error_reports_the_field_without_a_source_path() -> None:
    exc = RequestValidationError(
        [
            {
                "type": "greater_than_equal",
                "loc": ("query", "page"),
                "msg": "Input should be greater than or equal to 1",
                "input": "0",
            }
        ]
    )

    response = validation_exception_handler(_request(), exc)

    assert response.status_code == 422
    body = _body(response)
    assert "query.page" in body
    assert "Input should be greater than or equal to 1" in body
    # No absolute server path / source frame.
    assert "/home/" not in body
    assert ".py" not in body
    assert "line " not in body
