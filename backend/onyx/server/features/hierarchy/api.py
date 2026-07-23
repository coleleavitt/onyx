from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from sqlalchemy.orm import Session

from onyx.access.hierarchy_access import get_user_external_group_ids
from onyx.auth.permissions import require_permission
from onyx.configs.app_configs import ENABLE_OPENSEARCH_INDEXING_FOR_ONYX
from onyx.configs.constants import DocumentSource
from onyx.db.connected_source_governance import ConnectedSourceScopeMetadata
from onyx.db.connected_source_governance import filter_governed_hierarchy_node_ids
from onyx.db.connected_source_governance import get_governed_hierarchy_nodes_for_source
from onyx.db.document import get_accessible_documents_for_hierarchy_node_paginated
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import Permission
from onyx.db.hierarchy import get_accessible_hierarchy_nodes_for_source
from onyx.db.hierarchy import search_accessible_hierarchy_nodes
from onyx.db.models import User
from onyx.db.opensearch_migration import get_opensearch_retrieval_state
from onyx.server.features.hierarchy.constants import DOCUMENT_PAGE_SIZE
from onyx.server.features.hierarchy.constants import HIERARCHY_NODE_DOCUMENTS_PATH
from onyx.server.features.hierarchy.constants import HIERARCHY_NODE_SEARCH_LIMIT
from onyx.server.features.hierarchy.constants import HIERARCHY_NODES_LIST_PATH
from onyx.server.features.hierarchy.constants import HIERARCHY_NODES_PREFIX
from onyx.server.features.hierarchy.constants import HIERARCHY_NODES_SEARCH_PATH
from onyx.server.features.hierarchy.models import DocumentPageCursor
from onyx.server.features.hierarchy.models import DocumentSortDirection
from onyx.server.features.hierarchy.models import DocumentSortField
from onyx.server.features.hierarchy.models import DocumentSummary
from onyx.server.features.hierarchy.models import HierarchyNodeDocumentsRequest
from onyx.server.features.hierarchy.models import HierarchyNodeDocumentsResponse
from onyx.server.features.hierarchy.models import HierarchyNodeGovernanceSnapshot
from onyx.server.features.hierarchy.models import HierarchyNodeSearchResponse
from onyx.server.features.hierarchy.models import HierarchyNodeSearchSummary
from onyx.server.features.hierarchy.models import HierarchyNodesResponse
from onyx.server.features.hierarchy.models import HierarchyNodeSummary

OPENSEARCH_NOT_ENABLED_MESSAGE = "Per-source knowledge selection is coming soon in v3.0! OpenSearch indexing must be enabled to use this feature."

MIGRATION_STATUS_MESSAGE = (
    "Our records indicate that the transition to OpenSearch is still in progress. "
    "OpenSearch retrieval is necessary to use this feature. "
    "You can still use Document Sets, though! "
    "If you would like to manually switch to OpenSearch, "
    'Go to the "Document Index Migration" section in the Admin panel.'
)

router = APIRouter(prefix=HIERARCHY_NODES_PREFIX)


def _require_opensearch(db_session: Session) -> None:
    if not ENABLE_OPENSEARCH_INDEXING_FOR_ONYX:
        raise HTTPException(
            status_code=403,
            detail=OPENSEARCH_NOT_ENABLED_MESSAGE,
        )
    if not get_opensearch_retrieval_state(db_session):
        raise HTTPException(
            status_code=403,
            detail=MIGRATION_STATUS_MESSAGE,
        )


def _get_user_access_info(user: User, db_session: Session) -> tuple[str, list[str]]:
    return user.email, get_user_external_group_ids(db_session, user)


def _governance_snapshot(
    metadata: ConnectedSourceScopeMetadata,
) -> HierarchyNodeGovernanceSnapshot:
    return HierarchyNodeGovernanceSnapshot(
        curation_status=metadata.curation_status,
        is_default=metadata.is_default,
        is_archived=metadata.is_archived,
        is_hidden=metadata.is_hidden,
        is_diagnostic=metadata.is_diagnostic,
        is_selectable=metadata.is_selectable,
        denial_reason=metadata.denial_reason,
        display_label=metadata.display_label,
        tenant_label=metadata.tenant_label,
        department_label=metadata.department_label,
        sort_order=metadata.sort_order,
        size_bytes=metadata.size_bytes,
        document_count_estimate=metadata.document_count_estimate,
        indexed_document_count=metadata.metrics.document_count,
        indexed_chunk_count=metadata.metrics.chunk_count,
        indexing_status=metadata.metrics.latest_index_status,
        last_synced_at=metadata.metrics.last_successful_index_time,
        warning=metadata.warning,
        allowed_group_ids=list(metadata.allowed_group_ids),
        excluded_hierarchy_node_ids=list(metadata.excluded_hierarchy_node_ids),
    )


@router.get(HIERARCHY_NODES_LIST_PATH)
def list_accessible_hierarchy_nodes(
    source: DocumentSource,
    include_archived: bool = Query(default=False),
    include_hidden: bool = Query(default=False),
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> HierarchyNodesResponse:
    _require_opensearch(db_session)
    user_email, external_group_ids = _get_user_access_info(user, db_session)
    acl_nodes = get_accessible_hierarchy_nodes_for_source(
        db_session=db_session,
        source=source,
        user_email=user_email,
        external_group_ids=external_group_ids,
    )
    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=acl_nodes,
        user=user,
        include_archived=include_archived,
        include_hidden=include_hidden,
    )
    return HierarchyNodesResponse(
        nodes=[
            HierarchyNodeSummary(
                id=node.id,
                title=node.display_name,
                link=node.link,
                parent_id=node.parent_id,
                governance=_governance_snapshot(governed.metadata_by_node_id[node.id]),
            )
            for node in governed.nodes
        ]
    )


@router.post(HIERARCHY_NODE_DOCUMENTS_PATH)
def list_accessible_hierarchy_node_documents(
    documents_request: HierarchyNodeDocumentsRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> HierarchyNodeDocumentsResponse:
    _require_opensearch(db_session)
    user_email, external_group_ids = _get_user_access_info(user, db_session)
    cursor = documents_request.cursor
    sort_field = documents_request.sort_field
    sort_direction = documents_request.sort_direction

    sort_by_name = sort_field == DocumentSortField.NAME
    sort_ascending = sort_direction == DocumentSortDirection.ASC

    allowed_node_ids = filter_governed_hierarchy_node_ids(
        db_session=db_session,
        node_ids=[documents_request.parent_hierarchy_node_id],
        user=user,
        include_archived=True,
    )
    if documents_request.parent_hierarchy_node_id not in allowed_node_ids:
        raise HTTPException(status_code=403, detail="Hierarchy node is not available")

    documents = get_accessible_documents_for_hierarchy_node_paginated(
        db_session=db_session,
        parent_hierarchy_node_id=documents_request.parent_hierarchy_node_id,
        user_email=user_email,
        external_group_ids=external_group_ids,
        limit=DOCUMENT_PAGE_SIZE + 1,
        sort_by_name=sort_by_name,
        sort_ascending=sort_ascending,
        cursor_last_modified=cursor.last_modified if cursor else None,
        cursor_last_synced=cursor.last_synced if cursor else None,
        cursor_name=cursor.name if cursor else None,
        cursor_document_id=cursor.document_id if cursor else None,
    )
    document_summaries = [
        DocumentSummary(
            id=document.id,
            title=document.semantic_id,
            link=document.link,
            parent_id=document.parent_hierarchy_node_id,
            last_modified=document.last_modified,
            last_synced=document.last_synced,
        )
        for document in documents[:DOCUMENT_PAGE_SIZE]
    ]
    next_cursor = None
    if len(documents) > DOCUMENT_PAGE_SIZE and document_summaries:
        last_document = document_summaries[-1]
        # For name sorting, we always have a title; for last_updated, we need last_modified
        can_create_cursor = sort_by_name or last_document.last_modified is not None
        if can_create_cursor:
            next_cursor = DocumentPageCursor.from_document(last_document, sort_field)
    return HierarchyNodeDocumentsResponse(
        documents=document_summaries,
        next_cursor=next_cursor,
        sort_field=sort_field,
        sort_direction=sort_direction,
        folder_position=documents_request.folder_position,
    )


@router.get(HIERARCHY_NODES_SEARCH_PATH)
def search_hierarchy_nodes(
    query: str = Query(min_length=1),
    source: list[DocumentSource] | None = Query(default=None),
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> HierarchyNodeSearchResponse:
    _require_opensearch(db_session)
    user_email, external_group_ids = _get_user_access_info(user, db_session)
    nodes = search_accessible_hierarchy_nodes(
        db_session=db_session,
        query=query,
        sources=source,
        user_email=user_email,
        external_group_ids=external_group_ids,
        limit=HIERARCHY_NODE_SEARCH_LIMIT,
    )
    visible_ids: set[int] = set()
    for node_source in {node.source for node in nodes}:
        source_nodes = get_accessible_hierarchy_nodes_for_source(
            db_session=db_session,
            source=node_source,
            user_email=user_email,
            external_group_ids=external_group_ids,
        )
        governed = get_governed_hierarchy_nodes_for_source(
            db_session=db_session,
            nodes=source_nodes,
            user=user,
        )
        visible_ids.update(node.id for node in governed.nodes)
    return HierarchyNodeSearchResponse(
        nodes=[
            HierarchyNodeSearchSummary(
                id=node.id,
                title=node.display_name,
                link=node.link,
                parent_id=node.parent_id,
                source=node.source,
            )
            for node in nodes
            if node.id in visible_ids
        ]
    )
