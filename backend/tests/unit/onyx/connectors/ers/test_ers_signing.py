"""Locks the ERS request-signing wire format to the server-side verifier.

The expected values are produced by `ers-auth/src/signing.rs` for the same
fixed inputs (seed `[7u8; 32]`, the seed used by its `TestSigningKey`). If a
change here breaks these, ERS will reject every signed request.
"""

import base64

import pytest

from onyx.connectors.ers import signing

# base64url of [7u8; 32] — the seed in ers-auth's TestSigningKey::generate_admin.
_SEED_B64 = base64.urlsafe_b64encode(bytes([7] * 32)).decode().rstrip("=")
_BODY = b'{"query":"{ __typename }"}'
_TIMESTAMP = 1700000000

# Public half of the fixed test seed above — published in ers-auth's own test
# support, and a public key regardless. Not a credential.
_EXPECTED_PUBLIC_KEY = (
    "6kpsY-KcUgq-9VB7Ey7F-ZVHdq6-vnuSQh7qaRRG0iw"  # pragma: allowlist secret
)
_EXPECTED_CONTENT_SHA256 = "kQdqlhasDNntntftKLr-cg9HwM2EBuaLRbbduh_ouJc"
_EXPECTED_CANONICAL = f"v1\nPOST\n/graphql\n{_TIMESTAMP}\n{_EXPECTED_CONTENT_SHA256}"
_EXPECTED_SIGNATURE = "ZKzfRlkuT6xAwdb2Sr1ktSg67bWVE9X-ieoCs0Egk9wJG9Jinn1nSZOG32pCjn2SRSZkTL-4DI-4uwzoMSghCQ"


def test_public_key_matches_rust_encoding() -> None:
    key = signing.load_private_key(_SEED_B64)
    assert signing.public_key_b64(key) == _EXPECTED_PUBLIC_KEY


def test_body_hash_is_unpadded_base64url_sha256() -> None:
    assert signing.body_sha256(_BODY) == _EXPECTED_CONTENT_SHA256


def test_canonical_request_matches_rust_format() -> None:
    canonical = signing.canonical_request(
        "POST", "/graphql", _TIMESTAMP, _EXPECTED_CONTENT_SHA256
    )
    assert canonical == _EXPECTED_CANONICAL


def test_signed_headers_match_rust_signature() -> None:
    key = signing.load_private_key(_SEED_B64)
    headers = signing.signed_headers(
        key, "test-admin", "POST", "/graphql", _BODY, timestamp=_TIMESTAMP
    )
    assert headers == {
        signing.HEADER_KEY_ID: "test-admin",
        signing.HEADER_TIMESTAMP: str(_TIMESTAMP),
        signing.HEADER_CONTENT_SHA256: _EXPECTED_CONTENT_SHA256,
        signing.HEADER_SIGNATURE: _EXPECTED_SIGNATURE,
    }


def test_signature_covers_the_body() -> None:
    key = signing.load_private_key(_SEED_B64)
    original = signing.signed_headers(
        key, "k", "POST", "/graphql", b'{"query":"a"}', timestamp=_TIMESTAMP
    )
    tampered = signing.signed_headers(
        key, "k", "POST", "/graphql", b'{"query":"b"}', timestamp=_TIMESTAMP
    )
    assert original[signing.HEADER_SIGNATURE] != tampered[signing.HEADER_SIGNATURE]


def test_signature_covers_the_path() -> None:
    key = signing.load_private_key(_SEED_B64)
    graphql = signing.signed_headers(
        key, "k", "POST", "/graphql", _BODY, timestamp=_TIMESTAMP
    )
    other = signing.signed_headers(
        key, "k", "POST", "/admin", _BODY, timestamp=_TIMESTAMP
    )
    assert graphql[signing.HEADER_SIGNATURE] != other[signing.HEADER_SIGNATURE]


@pytest.mark.parametrize(
    "bad_key",
    [
        "not-base64url!!",
        base64.urlsafe_b64encode(b"too-short").decode().rstrip("="),
    ],
)
def test_rejects_malformed_private_keys(bad_key: str) -> None:
    with pytest.raises(ValueError):
        signing.load_private_key(bad_key)
