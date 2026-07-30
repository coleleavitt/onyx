"""Regression coverage for the SYNC-connector ACL failure modes.

These encode two invariants that a live deployment violated:

1. Documents from a permission-synced connector whose external permissions were
   never populated end up with an empty DB ACL, so the defensive post-filter in
   the search tool drops every retrieved chunk and the user sees "no results".
2. The OpenSearch ``public`` flag must be derived from the same
   ``DocumentAccess.is_public`` used to build the ACL list, otherwise the index
   can keep serving documents that Postgres considers private.
"""

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from onyx.access.models import DocumentAccess
from onyx.access.utils import prefix_user_email
from onyx.configs.constants import PUBLIC_DOC_PAT
from onyx.document_index.opensearch.opensearch_document_index import (
    generate_opensearch_filtered_access_control_list,
)
from onyx.tools.tool_implementations.search.search_tool import (
    _filter_chunks_by_current_db_access,
)

SEARCH_TOOL_MODULE = "onyx.tools.tool_implementations.search.search_tool"

USER_EMAIL = "cole@unwrap.rs"
DOC_ID = "sharepoint-orgchart"


def _access(
    *,
    is_public: bool = False,
    external_user_emails: list[str] | None = None,
) -> DocumentAccess:
    return DocumentAccess.build(
        user_emails=[],
        user_groups=[],
        is_public=is_public,
        external_user_emails=external_user_emails or [],
        external_user_group_ids=[],
    )


def _chunk(document_id: str = DOC_ID) -> Any:
    chunk = MagicMock()
    chunk.document_id = document_id
    return chunk


@contextmanager
def _patched_access(access_by_doc: dict[str, DocumentAccess]) -> Any:
    with (
        patch(f"{SEARCH_TOOL_MODULE}.get_session_with_current_tenant"),
        patch(
            f"{SEARCH_TOOL_MODULE}.get_access_for_documents",
            return_value=access_by_doc,
        ) as mocked,
    ):
        yield mocked


def test_sync_connector_without_perm_sync_drops_every_chunk() -> None:
    """A SYNC doc with no external permissions is unreachable by any user."""
    access = _access()
    assert access.to_acl() == set(), "no perm sync means no ACL entries at all"

    user = MagicMock(email=USER_EMAIL)
    ranked = [[_chunk()]]

    with _patched_access({DOC_ID: access}):
        filtered = _filter_chunks_by_current_db_access(
            ranked_results=ranked,
            user=user,
            acl_filters=[prefix_user_email(USER_EMAIL), PUBLIC_DOC_PAT],
        )

    assert filtered == [[]], (
        "documents whose external permissions were never synced must be dropped; "
        "this is the state that produced a silent 100% retrieval outage"
    )


def test_external_user_email_grant_restores_retrieval() -> None:
    """Adding the user's email to external_user_emails makes the doc retrievable."""
    access = _access(external_user_emails=[USER_EMAIL])
    assert prefix_user_email(USER_EMAIL) in access.to_acl()

    user = MagicMock(email=USER_EMAIL)
    chunk = _chunk()

    with _patched_access({DOC_ID: access}):
        filtered = _filter_chunks_by_current_db_access(
            ranked_results=[[chunk]],
            user=user,
            acl_filters=[prefix_user_email(USER_EMAIL), PUBLIC_DOC_PAT],
        )

    assert filtered == [[chunk]]


def test_unrelated_user_is_still_denied_after_targeted_grant() -> None:
    """A targeted grant must not widen access to other users."""
    access = _access(external_user_emails=[USER_EMAIL])
    other = MagicMock(email="someone.else@example.com")

    with _patched_access({DOC_ID: access}):
        filtered = _filter_chunks_by_current_db_access(
            ranked_results=[[_chunk()]],
            user=other,
            acl_filters=[prefix_user_email("someone.else@example.com"), PUBLIC_DOC_PAT],
        )

    assert filtered == [[]]


def test_none_acl_filters_bypasses_the_post_filter() -> None:
    """Admin/internal callers that pass no ACL filter are not silently filtered."""
    chunk = _chunk()
    filtered = _filter_chunks_by_current_db_access(
        ranked_results=[[chunk]],
        user=MagicMock(email=USER_EMAIL),
        acl_filters=None,
    )
    assert filtered == [[chunk]]


@pytest.mark.parametrize("is_public", [True, False])
def test_index_acl_list_never_carries_the_public_marker(is_public: bool) -> None:
    """PUBLIC_DOC_PAT lives in the ``public`` field, never in the ACL list.

    If the marker leaked into ``access_control_list`` the index would keep
    matching documents by ACL after Postgres flipped them to private.
    """
    access = _access(is_public=is_public, external_user_emails=[USER_EMAIL])
    acl_list = generate_opensearch_filtered_access_control_list(access)

    assert PUBLIC_DOC_PAT not in acl_list
    assert prefix_user_email(USER_EMAIL) in acl_list


def test_private_access_produces_no_index_acl_entries() -> None:
    """The exact indexed shape of an unsynced SYNC document."""
    access = _access()
    assert generate_opensearch_filtered_access_control_list(access) == []
    assert access.is_public is False, (
        "an unsynced SYNC document must never be indexed with public=true; "
        "a stale public flag serves private documents to every user"
    )
