from typing import Any

from onyx.document_index.interfaces_new import TenantState
from onyx.document_index.opensearch.schema import DOCUMENT_ID_FIELD_NAME
from onyx.document_index.opensearch.search import DocumentQuery
from shared_configs.configs import POSTGRES_DEFAULT_SCHEMA


def _filters(
    selected_document_ids: list[str],
    attached_document_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    return DocumentQuery._get_search_filters(
        tenant_state=TenantState(tenant_id=POSTGRES_DEFAULT_SCHEMA, multitenant=False),
        include_hidden=True,
        access_control_list=["user_email:test@example.com"],
        source_types=[],
        tags=[],
        document_sets=["assistant knowledge"],
        project_id_filter=None,
        persona_id_filter=7,
        time_cutoff=None,
        time_cutoff_upper=None,
        min_chunk_index=None,
        max_chunk_index=None,
        selected_document_ids=selected_document_ids,
        attached_document_ids=attached_document_ids,
        hierarchy_node_ids=[42],
    )


def test_selected_documents_are_a_standalone_and_filter() -> None:
    clauses = _filters(["doc-a", "doc-b"], attached_document_ids=["persona-doc"])

    assert {"terms": {DOCUMENT_ID_FIELD_NAME: ["doc-a", "doc-b"]}} in clauses
    assert not any(
        clause.get("bool", {}).get("should")
        and any(
            DOCUMENT_ID_FIELD_NAME in candidate.get("terms", {})
            for candidate in clause["bool"]["should"]
        )
        for clause in clauses
    )
