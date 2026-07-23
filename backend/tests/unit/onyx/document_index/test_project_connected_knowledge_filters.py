from unittest.mock import MagicMock

from onyx.context.search.pipeline import _build_index_filters
from onyx.document_index.interfaces_new import TenantState
from onyx.document_index.opensearch.schema import ACCESS_CONTROL_LIST_FIELD_NAME
from onyx.document_index.opensearch.schema import ANCESTOR_HIERARCHY_NODE_IDS_FIELD_NAME
from onyx.document_index.opensearch.schema import DOCUMENT_ID_FIELD_NAME
from onyx.document_index.opensearch.search import DocumentQuery


def test_project_connected_scope_is_carried_into_index_filters_with_acl() -> None:
    filters = _build_index_filters(
        user_provided_filters=None,
        user=MagicMock(),
        project_id_filter=None,
        persona_id_filter=None,
        persona_document_sets=None,
        persona_time_cutoff=None,
        db_session=None,
        attached_document_ids=["doc-allowed-by-space"],
        hierarchy_node_ids=[42],
        excluded_hierarchy_node_ids=[99],
        acl_filters=["user@example.com"],
    )

    assert filters.attached_document_ids == ["doc-allowed-by-space"]
    assert filters.hierarchy_node_ids == [42]
    assert filters.excluded_hierarchy_node_ids == [99]
    assert filters.access_control_list == ["user@example.com"]


def test_attached_document_and_hierarchy_scope_is_acl_intersected_in_search_query() -> (
    None
):
    filters = DocumentQuery._get_search_filters(
        tenant_state=TenantState(tenant_id="", multitenant=False),
        include_hidden=False,
        access_control_list=["user@example.com"],
        source_types=[],
        document_sets=[],
        project_id_filter=None,
        persona_id_filter=None,
        tags=[],
        created_at_range=None,
        updated_at_range=None,
        min_chunk_index=None,
        max_chunk_index=None,
        attached_document_ids=["doc-allowed-by-space"],
        hierarchy_node_ids=[42],
        excluded_hierarchy_node_ids=[99],
    )

    assert any(ACCESS_CONTROL_LIST_FIELD_NAME in str(clause) for clause in filters)
    knowledge_filters = [
        clause
        for clause in filters
        if {"terms": {DOCUMENT_ID_FIELD_NAME: ["doc-allowed-by-space"]}}
        in clause.get("bool", {}).get("should", [])
    ]
    assert len(knowledge_filters) == 1
    should_clauses = knowledge_filters[0]["bool"]["should"]
    assert {
        "terms": {DOCUMENT_ID_FIELD_NAME: ["doc-allowed-by-space"]}
    } in should_clauses
    assert {"terms": {ANCESTOR_HIERARCHY_NODE_IDS_FIELD_NAME: [42]}} in should_clauses
    assert any(
        clause.get("bool", {}).get("must_not")
        == [{"terms": {ANCESTOR_HIERARCHY_NODE_IDS_FIELD_NAME: [99]}}]
        for clause in filters
    )
