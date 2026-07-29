"""Signed GraphQL client for the ERS API."""

import json
from typing import Any

import requests

from onyx.connectors.ers.signing import load_private_key
from onyx.connectors.ers.signing import signed_headers
from onyx.connectors.exceptions import ConnectorValidationError
from onyx.connectors.exceptions import CredentialInvalidError
from onyx.utils.logger import setup_logger
from onyx.utils.retry_wrapper import retry_builder

logger = setup_logger()

DEFAULT_BASE_URL = "https://api-ers.fiwealth.com"
GRAPHQL_PATH = "/graphql"

_TIMEOUT = 60
_NUM_RETRIES = 5


class ErsTransientError(Exception):
    """Retryable upstream failure (5xx)."""


class ErsGraphQLError(Exception):
    """The server accepted the request but the query itself failed."""


class ErsClient:
    """Issues Ed25519-signed GraphQL requests against ERS.

    Every request is signed individually: the signature covers the request body,
    and ERS rejects timestamps more than 300s from its own clock.
    """

    def __init__(self, base_url: str, key_id: str, private_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._key_id = key_id
        self._private_key = load_private_key(private_key)

    @retry_builder(
        tries=_NUM_RETRIES,
        delay=1,
        exceptions=(requests.ConnectionError, requests.Timeout, ErsTransientError),
    )
    def _post(self, body: bytes) -> requests.Response:
        response = requests.post(
            f"{self._base_url}{GRAPHQL_PATH}",
            data=body,
            headers={
                "Content-Type": "application/json",
                **signed_headers(
                    self._private_key,
                    self._key_id,
                    "POST",
                    GRAPHQL_PATH,
                    body,
                ),
            },
            timeout=_TIMEOUT,
        )
        if response.status_code in (500, 502, 503, 504):
            raise ErsTransientError(f"ERS API returned {response.status_code}")
        return response

    def execute(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        # Signed over the exact bytes sent, so serialize once and reuse.
        body = json.dumps(
            {"query": query, "variables": variables or {}},
            separators=(",", ":"),
        ).encode("utf-8")

        response = self._post(body)

        if response.status_code == 401:
            raise CredentialInvalidError(
                "ERS rejected the request signature. Check that the key id is "
                "registered and enabled in request_signing_principals, that the "
                "private key matches the registered public key, and that this "
                "host's clock is within 300s of the server's."
            )
        if response.status_code == 403:
            raise CredentialInvalidError(
                "ERS accepted the signature but the principal lacks the scopes "
                "needed for this query."
            )
        response.raise_for_status()

        payload = response.json()
        if errors := payload.get("errors"):
            raise ErsGraphQLError("; ".join(e.get("message", str(e)) for e in errors))

        data = payload.get("data")
        if data is None:
            raise ErsGraphQLError("ERS returned no data for the query")
        return data

    def validate(self) -> None:
        """Confirm the credential signs a request ERS will accept."""
        try:
            self.execute("query OnyxConnectorValidate { __typename }")
        except CredentialInvalidError:
            raise
        except (ErsGraphQLError, requests.RequestException) as e:
            raise ConnectorValidationError(f"Failed to reach the ERS API: {e}") from e
