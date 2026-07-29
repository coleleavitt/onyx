"""Ed25519 HTTP request signing for the ERS API.

Mirrors the server-side verifier in `ers-auth/src/signing.rs`. The canonical
string and every encoded field must match it byte for byte, so treat the
format below as a wire contract rather than an implementation detail:

    content_sha256 = base64url_nopad(SHA256(body))
    canonical      = "v1\\n{METHOD}\\n{PATH_AND_QUERY}\\n{timestamp}\\n{content_sha256}"
    signature      = base64url_nopad(Ed25519_sign(canonical))

The server rejects a timestamp more than 300s from its own clock, so the
signature is computed per request rather than cached.
"""

import base64
import binascii
import hashlib
import time

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

HEADER_KEY_ID = "X-ERS-Key-Id"
HEADER_TIMESTAMP = "X-ERS-Timestamp"
HEADER_CONTENT_SHA256 = "X-ERS-Content-SHA256"
HEADER_SIGNATURE = "X-ERS-Signature"

_CANONICAL_VERSION = "v1"
_ED25519_SEED_BYTES = 32


def _b64url_nopad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def load_private_key(encoded_seed: str) -> Ed25519PrivateKey:
    """Decode a base64url-encoded 32-byte Ed25519 seed.

    Matches the encoding ERS uses for the paired public key in its
    `request_signing_principals` registry.
    """
    try:
        seed = _b64url_decode(encoded_seed.strip())
    except (ValueError, binascii.Error) as e:
        raise ValueError(f"ERS private key is not valid base64url: {e}") from e

    if len(seed) != _ED25519_SEED_BYTES:
        raise ValueError(
            f"ERS private key must decode to {_ED25519_SEED_BYTES} bytes, got {len(seed)}"
        )

    try:
        return Ed25519PrivateKey.from_private_bytes(seed)
    except (InvalidKey, ValueError) as e:
        raise ValueError(f"ERS private key is not a valid Ed25519 seed: {e}") from e


def public_key_b64(private_key: Ed25519PrivateKey) -> str:
    """base64url-encoded public key, as registered under a `key_id` in ERS."""
    from cryptography.hazmat.primitives.serialization import Encoding
    from cryptography.hazmat.primitives.serialization import PublicFormat

    return _b64url_nopad(
        private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    )


def body_sha256(body: bytes) -> str:
    return _b64url_nopad(hashlib.sha256(body).digest())


def canonical_request(
    method: str, path_and_query: str, timestamp: int, content_sha256: str
) -> str:
    return "\n".join(
        [
            _CANONICAL_VERSION,
            method,
            path_and_query,
            str(timestamp),
            content_sha256,
        ]
    )


def signed_headers(
    private_key: Ed25519PrivateKey,
    key_id: str,
    method: str,
    path_and_query: str,
    body: bytes,
    timestamp: int | None = None,
) -> dict[str, str]:
    """Build the four `X-ERS-*` headers authenticating a single request."""
    ts = int(time.time()) if timestamp is None else timestamp
    content_hash = body_sha256(body)
    canonical = canonical_request(method, path_and_query, ts, content_hash)
    return {
        HEADER_KEY_ID: key_id,
        HEADER_TIMESTAMP: str(ts),
        HEADER_CONTENT_SHA256: content_hash,
        HEADER_SIGNATURE: _b64url_nopad(private_key.sign(canonical.encode("utf-8"))),
    }
