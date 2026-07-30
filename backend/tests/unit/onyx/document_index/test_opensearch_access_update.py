"""The OpenSearch metadata update must write both halves of the access state.

``access_control_list`` and ``public`` are two separate index fields, and the
retrieval filter matches a document if *either* one matches. Writing only the
ACL on an access update leaves a revoked document permanently matching the
public clause.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

from onyx.access.models import DocumentAccess
from onyx.access.utils import prefix_user_email
from onyx.document_index.interfaces_new import MetadataUpdateRequest
from onyx.document_index.interfaces_new import TenantState
from onyx.document_index.opensearch.opensearch_document_index import (
    OpenSearchDocumentIndex,
)
from onyx.document_index.opensearch.schema import ACCESS_CONTROL_LIST_FIELD_NAME
from onyx.document_index.opensearch.schema import PUBLIC_FIELD_NAME

DOC_ID = "doc-1"
USER_EMAIL = "cole@unwrap.rs"


def _index_with_mock_client() -> tuple[OpenSearchDocumentIndex, MagicMock]:
    index = object.__new__(OpenSearchDocumentIndex)
    client = MagicMock()
    index._client = client
    index._index_name = "test_index"
    index._tenant_state = TenantState(tenant_id="public", multitenant=False)
    return index, client


def _access(*, is_public: bool) -> DocumentAccess:
    return DocumentAccess.build(
        user_emails=[],
        user_groups=[],
        is_public=is_public,
        external_user_emails=[USER_EMAIL],
        external_user_group_ids=[],
    )


def _sent_properties(client: MagicMock) -> dict[str, Any]:
    client.bulk_update_documents.assert_called_once()
    return client.bulk_update_documents.call_args.kwargs["properties_to_update"]


@pytest.mark.parametrize("is_public", [True, False])
def test_access_update_writes_the_public_field(is_public: bool) -> None:
    index, client = _index_with_mock_client()

    index.update(
        [
            MetadataUpdateRequest(
                document_ids=[DOC_ID],
                doc_id_to_chunk_cnt={DOC_ID: 2},
                access=_access(is_public=is_public),
            )
        ]
    )

    properties = _sent_properties(client)
    assert PUBLIC_FIELD_NAME in properties, (
        "an access update that omits the public field can never revoke a stale "
        "public marker, leaving private documents retrievable by every user"
    )
    assert properties[PUBLIC_FIELD_NAME] is is_public
    assert properties[ACCESS_CONTROL_LIST_FIELD_NAME] == [prefix_user_email(USER_EMAIL)]


def test_revoking_public_access_clears_the_flag() -> None:
    """The exact production repair: public=true -> public=false."""
    index, client = _index_with_mock_client()

    index.update(
        [
            MetadataUpdateRequest(
                document_ids=[DOC_ID],
                doc_id_to_chunk_cnt={DOC_ID: 1},
                access=_access(is_public=False),
            )
        ]
    )

    assert _sent_properties(client)[PUBLIC_FIELD_NAME] is False


def test_non_access_update_does_not_touch_the_public_field() -> None:
    """Boost-only updates must not rewrite access state."""
    index, client = _index_with_mock_client()

    index.update(
        [
            MetadataUpdateRequest(
                document_ids=[DOC_ID],
                doc_id_to_chunk_cnt={DOC_ID: 1},
                boost=2.0,
            )
        ]
    )

    properties = _sent_properties(client)
    assert PUBLIC_FIELD_NAME not in properties
    assert ACCESS_CONTROL_LIST_FIELD_NAME not in properties
