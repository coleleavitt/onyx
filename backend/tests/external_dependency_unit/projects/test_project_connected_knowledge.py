from collections.abc import Generator
from collections.abc import Mapping
from collections.abc import Sequence
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.orm import Session

from onyx.access.access import get_acl_for_user
from onyx.access.utils import prefix_user_email
from onyx.auth.schemas import UserRole
from onyx.chat.emitter import Emitter
from onyx.chat.models import SearchParams
from onyx.chat.process_message import apply_project_connected_knowledge_to_search_params
from onyx.configs.constants import DocumentSource
from onyx.configs.constants import PUBLIC_DOC_PAT
from onyx.context.search.models import IndexFilters
from onyx.context.search.models import InferenceChunk
from onyx.context.search.models import PersonaSearchInfo
from onyx.db.connected_source_governance import _build_metrics_by_node_id
from onyx.db.connected_source_governance import (
    _effective_exclusions_for_selected_node_ids,
)
from onyx.db.connected_source_governance import _load_scopes_by_source
from onyx.db.connected_source_governance import _sharepoint_folder_path_from_url
from onyx.db.connected_source_governance import build_metadata_for_nodes
from onyx.db.connected_source_governance import create_connected_knowledge_preset
from onyx.db.connected_source_governance import filter_governed_document_ids
from onyx.db.connected_source_governance import filter_governed_hierarchy_node_ids
from onyx.db.connected_source_governance import get_governed_hierarchy_nodes_for_source
from onyx.db.connected_source_governance import get_user_group_ids
from onyx.db.connected_source_governance import get_visible_presets_for_user
from onyx.db.connected_source_governance import list_connected_source_scopes
from onyx.db.connected_source_governance import provision_sharepoint_scope_to_connectors
from onyx.db.connected_source_governance import upsert_connected_source_scope
from onyx.db.enums import AccessType
from onyx.db.enums import ConnectedSourceAccessType
from onyx.db.enums import ConnectedSourceCurationStatus
from onyx.db.enums import ConnectorCredentialPairStatus
from onyx.db.enums import HierarchyNodeType
from onyx.db.enums import IndexingStatus
from onyx.db.enums import ProjectSharePermission
from onyx.db.models import ConnectedSourceScope
from onyx.db.models import Document
from onyx.db.models import DocumentByConnectorCredentialPair
from onyx.db.models import HierarchyNode
from onyx.db.models import HierarchyNodeByConnectorCredentialPair
from onyx.db.models import IndexAttempt
from onyx.db.models import KGStage
from onyx.db.models import Project__User
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.models import UserGroup
from onyx.db.models import UserProject
from onyx.db.projects import fetch_project_by_id
from onyx.db.projects import replace_project_connected_knowledge
from onyx.db.search_settings import get_current_search_settings
from onyx.document_index.interfaces_new import DocumentIndex
from onyx.error_handling.exceptions import OnyxError
from onyx.llm.interfaces import LLM
from onyx.natural_language_processing.search_nlp_models import EmbeddingModel
from onyx.server.features.projects.api import create_project as create_project_api
from onyx.server.features.projects.api import get_project_connected_knowledge
from onyx.server.features.projects.api import update_project_connected_knowledge
from onyx.server.features.projects.models import ProjectConnectedKnowledgeRequest
from onyx.tools.models import SearchToolUsage
from onyx.tools.tool_implementations.search.search_tool import SearchTool
from tests.external_dependency_unit.conftest import create_test_user
from tests.external_dependency_unit.indexing_helpers import make_cc_pair

# Per-worker registries of the rows the helpers create, so teardown drops exactly
# those. xdist runs each worker in its own process, so this module-level state is
# isolated per worker and tests within a worker run sequentially — no cross-test
# or cross-worker interference.
_CREATED_HIERARCHY_NODE_IDS: list[int] = []
_CREATED_DOCUMENT_IDS: list[str] = []


def _restore_rows(
    db_session: Session, table: str, rows: Sequence[Mapping[str, Any] | RowMapping]
) -> None:
    """Re-insert rows verbatim, preserving their original ids."""
    for row in rows:
        columns = list(row.keys())
        db_session.execute(
            text(
                f"INSERT INTO {table} ({', '.join(columns)}) "
                f"VALUES ({', '.join(':' + column for column in columns)})"
            ),
            dict(row),
        )


@pytest.fixture(autouse=True)
def _clear_connected_source_governance(
    db_session: Session,
) -> Generator[None, None, None]:
    # These tests need a policy-free environment: any real governance scope
    # would put the deployment in policy mode and reject their fixture
    # documents. A deployment's scopes are real configuration though, so they
    # are set aside and restored afterwards rather than destroyed.
    saved_scopes = (
        db_session.execute(text("SELECT * FROM connected_source_scope"))
        .mappings()
        .all()
    )
    saved_scope_groups = (
        db_session.execute(text("SELECT * FROM connected_source_scope__user_group"))
        .mappings()
        .all()
    )
    db_session.query(ConnectedSourceScope).delete()
    db_session.commit()
    _CREATED_HIERARCHY_NODE_IDS.clear()
    _CREATED_DOCUMENT_IDS.clear()
    yield
    db_session.query(ConnectedSourceScope).delete()
    if _CREATED_DOCUMENT_IDS:
        db_session.query(DocumentByConnectorCredentialPair).filter(
            DocumentByConnectorCredentialPair.id.in_(_CREATED_DOCUMENT_IDS)
        ).delete(synchronize_session=False)
        db_session.query(Document).filter(
            Document.id.in_(_CREATED_DOCUMENT_IDS)
        ).delete(synchronize_session=False)
    if _CREATED_HIERARCHY_NODE_IDS:
        db_session.query(HierarchyNode).filter(
            HierarchyNode.id.in_(_CREATED_HIERARCHY_NODE_IDS)
        ).delete(synchronize_session=False)
    db_session.commit()
    _restore_rows(db_session, "connected_source_scope", saved_scopes)
    _restore_rows(db_session, "connected_source_scope__user_group", saved_scope_groups)
    db_session.execute(
        text(
            "SELECT setval(pg_get_serial_sequence('connected_source_scope', 'id'), "
            "GREATEST(COALESCE((SELECT MAX(id) FROM connected_source_scope), 1), 1))"
        )
    )
    db_session.commit()
    _CREATED_HIERARCHY_NODE_IDS.clear()
    _CREATED_DOCUMENT_IDS.clear()


class _FilteringDocumentIndex:
    def __init__(self, chunks: list[InferenceChunk]) -> None:
        self.chunks = chunks
        self.last_filters: IndexFilters | None = None

    def keyword_retrieval(
        self,
        query: str,  # noqa: ARG002
        filters: IndexFilters,
        num_to_retrieve: int,
        include_hidden: bool = False,  # noqa: ARG002
    ) -> list[InferenceChunk]:
        self.last_filters = filters
        selected_doc_ids = set(filters.attached_document_ids or [])
        selected_node_ids = {
            str(node_id) for node_id in (filters.hierarchy_node_ids or [])
        }
        excluded_node_ids = {
            str(node_id) for node_id in (filters.excluded_hierarchy_node_ids or [])
        }
        acl_entries = set(filters.access_control_list or [])
        results: list[InferenceChunk] = []
        for chunk in self.chunks:
            chunk_nodes = set(chunk.metadata.get("ancestor_hierarchy_node_ids", []))
            if chunk_nodes & excluded_node_ids:
                continue
            in_scope = chunk.document_id in selected_doc_ids or bool(
                chunk_nodes & selected_node_ids
            )
            if not in_scope:
                continue
            chunk_acl = set(chunk.metadata.get("acl", []))
            if acl_entries and not (chunk_acl & acl_entries):
                continue
            results.append(chunk)
        return results[:num_to_retrieve]


def _chunk(
    document_id: str,
    *,
    title: str,
    acl: list[str],
    ancestor_node_ids: list[int],
) -> InferenceChunk:
    return InferenceChunk(
        chunk_id=0,
        blurb=title,
        content=f"content for {title}",
        source_links=None,
        image_file_id=None,
        section_continuation=False,
        document_id=document_id,
        source_type=DocumentSource.SHAREPOINT,
        semantic_identifier=title,
        title=title,
        boost=0,
        score=1.0,
        hidden=False,
        metadata={
            "acl": acl,
            "ancestor_hierarchy_node_ids": [
                str(node_id) for node_id in ancestor_node_ids
            ],
        },
        match_highlights=[],
        doc_summary="",
        chunk_context="",
        updated_at=None,
    )


def _create_project(db_session: Session, user: User, name: str) -> UserProject:
    project = UserProject(user_id=user.id, name=name, instructions="")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _create_group_for_user(
    db_session: Session,
    user: User,
    name: str,
) -> UserGroup:
    group = UserGroup(name=f"{name}-{uuid4().hex}")
    db_session.add(group)
    db_session.flush()
    db_session.add(User__UserGroup(user_group_id=group.id, user_id=user.id))
    db_session.commit()
    db_session.refresh(group)
    return group


def _create_hierarchy_node(
    db_session: Session,
    *,
    raw_id: str,
    name: str,
    source: DocumentSource = DocumentSource.SHAREPOINT,
    is_public: bool = True,
    parent_id: int | None = None,
    link: str | None = None,
) -> HierarchyNode:
    node = HierarchyNode(
        raw_node_id=raw_id,
        display_name=name,
        link=link,
        source=source,
        node_type=HierarchyNodeType.FOLDER,
        is_public=is_public,
        parent_id=parent_id,
    )
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)
    _CREATED_HIERARCHY_NODE_IDS.append(node.id)
    return node


def _create_indexed_document(
    db_session: Session,
    *,
    document_id: str,
    title: str,
    parent: HierarchyNode,
    is_public: bool = True,
    external_user_emails: list[str] | None = None,
) -> Document:
    pair = make_cc_pair(db_session, source=parent.source, commit=False)
    pair.access_type = AccessType.PUBLIC if is_public else AccessType.PRIVATE
    document = Document(
        id=document_id,
        semantic_id=title,
        link=f"https://example.com/{document_id}",
        parent_hierarchy_node_id=parent.id,
        is_public=is_public,
        external_user_emails=external_user_emails,
        kg_stage=KGStage.NOT_STARTED,
    )
    db_session.add(document)
    db_session.flush()
    from onyx.db.models import DocumentByConnectorCredentialPair

    db_session.add(
        DocumentByConnectorCredentialPair(
            id=document.id,
            connector_id=pair.connector_id,
            credential_id=pair.credential_id,
            has_been_indexed=True,
        )
    )
    db_session.commit()
    db_session.refresh(document)
    _CREATED_DOCUMENT_IDS.append(document.id)
    return document


def test_project_connected_knowledge_persists_and_reloads(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_knowledge_owner")
    project = _create_project(db_session, user, "Connected Knowledge Space")
    folder = _create_hierarchy_node(
        db_session,
        raw_id=f"folder-{uuid4().hex}",
        name="SharePoint Policies",
    )
    document = _create_indexed_document(
        db_session,
        document_id=f"doc-{uuid4().hex}",
        title="Employee Handbook",
        parent=folder,
    )

    replace_project_connected_knowledge(
        project=project,
        document_ids=[document.id],
        hierarchy_node_ids=[folder.id],
        user=user,
        db_session=db_session,
    )

    reloaded = fetch_project_by_id(project.id, db_session=db_session)
    assert reloaded is not None
    assert [doc.id for doc in reloaded.attached_documents] == [document.id]
    assert [node.id for node in reloaded.hierarchy_nodes] == [folder.id]

    snapshot = get_project_connected_knowledge(project.id, user, db_session)
    assert [doc.id for doc in snapshot.documents] == [document.id]
    assert [node.id for node in snapshot.hierarchy_nodes] == [folder.id]

    updated = update_project_connected_knowledge(
        project.id,
        ProjectConnectedKnowledgeRequest(document_ids=[], hierarchy_node_ids=[]),
        user,
        db_session,
    )
    assert updated.documents == []
    assert updated.hierarchy_nodes == []


def test_project_connected_knowledge_enables_search_params(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_knowledge_search")
    project = _create_project(db_session, user, "Searchable Connected Knowledge")
    folder = _create_hierarchy_node(
        db_session,
        raw_id=f"search-folder-{uuid4().hex}",
        name="Search Folder",
    )
    document = _create_indexed_document(
        db_session,
        document_id=f"search-doc-{uuid4().hex}",
        title="Search Doc",
        parent=folder,
    )
    replace_project_connected_knowledge(
        project=project,
        document_ids=[document.id],
        hierarchy_node_ids=[folder.id],
        user=user,
        db_session=db_session,
    )

    params = apply_project_connected_knowledge_to_search_params(
        SearchParams(
            project_id_filter=None,
            persona_id_filter=None,
            search_usage=SearchToolUsage.DISABLED,
        ),
        project.id,
        db_session,
    )

    assert params.search_usage == SearchToolUsage.ENABLED
    assert params.project_attached_document_ids == [document.id]
    assert params.project_hierarchy_node_ids == [folder.id]


def test_search_tool_project_connected_knowledge_excludes_unauthorized_selected_docs(
    db_session: Session,
) -> None:
    owner = create_test_user(db_session, "project_knowledge_owner_search")
    viewer = create_test_user(db_session, "project_knowledge_viewer_search")
    project = _create_project(db_session, owner, "Shared Search Space")
    db_session.add(
        Project__User(
            project_id=project.id,
            user_id=viewer.id,
            permission=ProjectSharePermission.VIEWER,
        )
    )
    folder = _create_hierarchy_node(
        db_session,
        raw_id=f"retrieval-folder-{uuid4().hex}",
        name="Retrieval Folder",
    )
    public_exact = _create_indexed_document(
        db_session,
        document_id=f"public-exact-{uuid4().hex}",
        title="Public exact selected document",
        parent=folder,
        is_public=True,
    )
    public_folder_doc = _create_indexed_document(
        db_session,
        document_id=f"public-folder-{uuid4().hex}",
        title="Public document inherited from selected folder",
        parent=folder,
        is_public=True,
    )
    private_owner_exact = _create_indexed_document(
        db_session,
        document_id=f"owner-private-{uuid4().hex}",
        title="Owner private selected document",
        parent=folder,
        is_public=False,
        external_user_emails=[owner.email],
    )
    db_session.commit()

    replace_project_connected_knowledge(
        project=project,
        document_ids=[public_exact.id, private_owner_exact.id],
        hierarchy_node_ids=[folder.id],
        user=owner,
        db_session=db_session,
    )
    params = apply_project_connected_knowledge_to_search_params(
        SearchParams(
            project_id_filter=None,
            persona_id_filter=None,
            search_usage=SearchToolUsage.DISABLED,
        ),
        project.id,
        db_session,
    )
    fake_index = _FilteringDocumentIndex(
        [
            _chunk(
                public_exact.id,
                title="Public exact selected document",
                acl=[PUBLIC_DOC_PAT],
                ancestor_node_ids=[folder.id],
            ),
            _chunk(
                public_folder_doc.id,
                title="Public folder document",
                acl=[PUBLIC_DOC_PAT],
                ancestor_node_ids=[folder.id],
            ),
            _chunk(
                private_owner_exact.id,
                title="Owner private selected document",
                acl=[prefix_user_email(owner.email)],
                ancestor_node_ids=[folder.id],
            ),
        ]
    )
    search_tool = SearchTool(
        tool_id=1,
        emitter=cast(Emitter, None),
        user=viewer,
        persona_search_info=PersonaSearchInfo(
            document_set_names=[],
            search_start_date=None,
            attached_document_ids=params.project_attached_document_ids,
            hierarchy_node_ids=params.project_hierarchy_node_ids,
        ),
        llm=cast(LLM, None),
        document_index=cast(DocumentIndex, fake_index),
        user_selected_filters=None,
        project_id_filter=params.project_id_filter,
        persona_id_filter=params.persona_id_filter,
    )

    chunks = search_tool._run_search_for_query(
        query="policy",
        hybrid_alpha=0.0,
        num_hits=10,
        acl_filters=list(get_acl_for_user(viewer, db_session)),
        embedding_model=cast(EmbeddingModel, None),
        federated_retrieval_infos=[],
        effective_filters=None,
    )

    assert {chunk.document_id for chunk in chunks} == {
        public_exact.id,
        public_folder_doc.id,
    }
    filters = fake_index.last_filters
    assert filters is not None
    assert filters.attached_document_ids is not None
    assert filters.hierarchy_node_ids is not None
    assert filters.access_control_list is not None
    assert private_owner_exact.id in filters.attached_document_ids
    assert folder.id in filters.hierarchy_node_ids
    assert prefix_user_email(viewer.email) in filters.access_control_list


def test_project_connected_knowledge_requires_edit_access(
    db_session: Session,
) -> None:
    owner = create_test_user(db_session, "project_knowledge_owner_edit")
    viewer = create_test_user(db_session, "project_knowledge_viewer")
    project = _create_project(db_session, owner, "Viewer Shared Space")
    db_session.add(
        Project__User(
            project_id=project.id,
            user_id=viewer.id,
            permission=ProjectSharePermission.VIEWER,
        )
    )
    db_session.commit()

    with pytest.raises(OnyxError):
        update_project_connected_knowledge(
            project.id,
            ProjectConnectedKnowledgeRequest(document_ids=[], hierarchy_node_ids=[]),
            viewer,
            db_session,
        )


@pytest.mark.parametrize("field", ["document", "hierarchy_node"])
def test_project_connected_knowledge_rejects_inaccessible_selection(
    db_session: Session,
    field: str,
) -> None:
    user = create_test_user(db_session, f"project_knowledge_inaccessible_{field}")
    project = _create_project(db_session, user, "Permissioned Space")
    private_folder = _create_hierarchy_node(
        db_session,
        raw_id=f"private-folder-{uuid4().hex}",
        name="Private Folder",
        is_public=False,
    )
    private_document = _create_indexed_document(
        db_session,
        document_id=f"private-doc-{uuid4().hex}",
        title="Private Doc",
        parent=private_folder,
        is_public=False,
    )

    with pytest.raises(OnyxError):
        replace_project_connected_knowledge(
            project=project,
            document_ids=[private_document.id] if field == "document" else [],
            hierarchy_node_ids=[private_folder.id] if field == "hierarchy_node" else [],
            user=user,
            db_session=db_session,
        )


def test_project_connected_knowledge_rejects_scope_outside_group_policy(
    db_session: Session,
) -> None:
    allowed_user = create_test_user(db_session, "project_policy_allowed")
    denied_user = create_test_user(db_session, "project_policy_denied")
    allowed_group = _create_group_for_user(
        db_session, allowed_user, "advisor-services-policy"
    )
    governed_folder = _create_hierarchy_node(
        db_session,
        raw_id=f"governed-folder-{uuid4().hex}",
        name="Advisor Services Intranet",
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=governed_folder.id,
        curation_status=ConnectedSourceCurationStatus.DEFAULT_SAFE,
        group_ids=[allowed_group.id],
        excluded_hierarchy_node_ids=[],
        tenant_label="Foundations",
        department_label="Advisor Services",
    )

    denied_project = _create_project(db_session, denied_user, "Denied Policy Space")
    with pytest.raises(OnyxError):
        replace_project_connected_knowledge(
            project=denied_project,
            document_ids=[],
            hierarchy_node_ids=[governed_folder.id],
            user=denied_user,
            db_session=db_session,
        )

    allowed_project = _create_project(db_session, allowed_user, "Allowed Policy Space")
    replace_project_connected_knowledge(
        project=allowed_project,
        document_ids=[],
        hierarchy_node_ids=[governed_folder.id],
        user=allowed_user,
        db_session=db_session,
    )
    assert [node.id for node in allowed_project.hierarchy_nodes] == [governed_folder.id]

    admin_user = create_test_user(
        db_session,
        "project_policy_admin_bypass",
        role=UserRole.ADMIN,
    )
    governed_nodes = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[governed_folder],
        user=admin_user,
    )
    assert [node.id for node in governed_nodes.nodes] == [governed_folder.id]
    admin_project = _create_project(db_session, admin_user, "Admin Policy Space")
    replace_project_connected_knowledge(
        project=admin_project,
        document_ids=[],
        hierarchy_node_ids=[governed_folder.id],
        user=admin_user,
        db_session=db_session,
    )
    assert [node.id for node in admin_project.hierarchy_nodes] == [governed_folder.id]


def test_project_connected_knowledge_applies_configured_excluded_child_scope(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_exclusion")
    project = _create_project(db_session, user, "Excluded Archive Space")
    parent = _create_hierarchy_node(
        db_session,
        raw_id=f"parent-scope-{uuid4().hex}",
        name="Business Development Intranet",
    )
    archive = _create_hierarchy_node(
        db_session,
        raw_id=f"archive-scope-{uuid4().hex}",
        name="z.Completed Transitions",
        parent_id=parent.id,
    )
    active_doc = _create_indexed_document(
        db_session,
        document_id=f"active-doc-{uuid4().hex}",
        title="Current transition template",
        parent=parent,
    )
    archived_doc = _create_indexed_document(
        db_session,
        document_id=f"archived-doc-{uuid4().hex}",
        title="Completed transition archive",
        parent=archive,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=parent.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[archive.id],
        warning="Excludes completed transition archive.",
    )

    replace_project_connected_knowledge(
        project=project,
        document_ids=[],
        hierarchy_node_ids=[parent.id],
        user=user,
        db_session=db_session,
    )
    params = apply_project_connected_knowledge_to_search_params(
        SearchParams(
            project_id_filter=None,
            persona_id_filter=None,
            search_usage=SearchToolUsage.DISABLED,
        ),
        project.id,
        db_session,
    )
    assert params.project_hierarchy_node_ids == [parent.id]
    assert params.project_excluded_hierarchy_node_ids == [archive.id]

    fake_index = _FilteringDocumentIndex(
        [
            _chunk(
                active_doc.id,
                title="Current transition template",
                acl=[PUBLIC_DOC_PAT],
                ancestor_node_ids=[parent.id],
            ),
            _chunk(
                archived_doc.id,
                title="Completed transition archive",
                acl=[PUBLIC_DOC_PAT],
                ancestor_node_ids=[parent.id, archive.id],
            ),
        ]
    )
    search_tool = SearchTool(
        tool_id=1,
        emitter=cast(Emitter, None),
        user=user,
        persona_search_info=PersonaSearchInfo(
            document_set_names=[],
            search_start_date=None,
            attached_document_ids=params.project_attached_document_ids,
            hierarchy_node_ids=params.project_hierarchy_node_ids,
            excluded_hierarchy_node_ids=params.project_excluded_hierarchy_node_ids,
        ),
        llm=cast(LLM, None),
        document_index=cast(DocumentIndex, fake_index),
        user_selected_filters=None,
        project_id_filter=params.project_id_filter,
        persona_id_filter=params.persona_id_filter,
    )

    chunks = search_tool._run_search_for_query(
        query="transition",
        hybrid_alpha=0.0,
        num_hits=10,
        acl_filters=list(get_acl_for_user(user, db_session)),
        embedding_model=cast(EmbeddingModel, None),
        federated_retrieval_infos=[],
        effective_filters=None,
    )

    assert {chunk.document_id for chunk in chunks} == {active_doc.id}
    assert fake_index.last_filters is not None
    assert fake_index.last_filters.excluded_hierarchy_node_ids == [archive.id]


def test_sharepoint_scope_provisioning_updates_associated_connector_config(
    db_session: Session,
) -> None:
    scope_node = _create_hierarchy_node(
        db_session,
        raw_id=f"sharepoint-scope-{uuid4().hex}",
        name="Advisor Services",
        link="https://contoso.sharepoint.com/sites/advisor/Shared%20Documents/Advisor%20Services",
    )
    excluded_node = _create_hierarchy_node(
        db_session,
        raw_id=f"sharepoint-excluded-{uuid4().hex}",
        name="Completed Transitions",
        parent_id=scope_node.id,
        link="https://contoso.sharepoint.com/sites/advisor/Shared%20Documents/Advisor%20Services/Completed%20Transitions",
    )
    pair = make_cc_pair(db_session, source=DocumentSource.SHAREPOINT, commit=False)
    pair.connector.connector_specific_config = {
        "sites": ["https://contoso.sharepoint.com/sites/advisor"],
        "excluded_paths": ["*.tmp"],
    }
    db_session.add(
        HierarchyNodeByConnectorCredentialPair(
            hierarchy_node_id=scope_node.id,
            connector_id=pair.connector_id,
            credential_id=pair.credential_id,
        )
    )
    db_session.commit()

    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=scope_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[excluded_node.id],
    )

    dry_run_results = provision_sharepoint_scope_to_connectors(
        db_session=db_session,
        hierarchy_node_id=scope_node.id,
        dry_run=True,
    )

    assert len(dry_run_results) == 1
    assert dry_run_results[0].dry_run is True
    assert dry_run_results[0].added_sites == (
        "https://contoso.sharepoint.com/sites/advisor/Shared%20Documents/Advisor%20Services",
    )
    assert (
        "Advisor Services/Completed Transitions/**"
        in dry_run_results[0].added_excluded_paths
    )
    assert pair.connector.connector_specific_config["sites"] == [
        "https://contoso.sharepoint.com/sites/advisor"
    ]

    results = provision_sharepoint_scope_to_connectors(
        db_session=db_session,
        hierarchy_node_id=scope_node.id,
        dry_run=False,
    )

    config = pair.connector.connector_specific_config
    assert len(results) == 1
    assert results[0].dry_run is False
    assert config["sites"] == [
        "https://contoso.sharepoint.com/sites/advisor",
        "https://contoso.sharepoint.com/sites/advisor/Shared%20Documents/Advisor%20Services",
    ]
    assert config["excluded_paths"] == [
        "*.tmp",
        "Advisor Services/Completed Transitions",
        "Advisor Services/Completed Transitions/**",
    ]


def test_sharepoint_scope_provisioning_rejects_unassociated_connector(
    db_session: Session,
) -> None:
    scope_node = _create_hierarchy_node(
        db_session,
        raw_id=f"sharepoint-scope-unassociated-{uuid4().hex}",
        name="Billing",
        link="https://contoso.sharepoint.com/sites/billing/Shared%20Documents/Billing",
    )
    associated_pair = make_cc_pair(
        db_session, source=DocumentSource.SHAREPOINT, commit=False
    )
    unassociated_pair = make_cc_pair(
        db_session, source=DocumentSource.SHAREPOINT, commit=False
    )
    db_session.add(
        HierarchyNodeByConnectorCredentialPair(
            hierarchy_node_id=scope_node.id,
            connector_id=associated_pair.connector_id,
            credential_id=associated_pair.credential_id,
        )
    )
    db_session.commit()
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=scope_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )

    with pytest.raises(ValueError):
        provision_sharepoint_scope_to_connectors(
            db_session=db_session,
            hierarchy_node_id=scope_node.id,
            connector_ids=[unassociated_pair.connector_id],
            dry_run=True,
        )


def test_empty_governance_helpers_return_empty_results(db_session: Session) -> None:
    user = create_test_user(db_session, "project_policy_empty_helpers")

    assert _build_metrics_by_node_id(db_session, []) == {}
    assert _load_scopes_by_source(db_session, set()) == {}
    assert get_user_group_ids(db_session, None) == set()
    assert (
        build_metadata_for_nodes(
            db_session=db_session,
            nodes=[],
            user_group_ids=set(),
            include_archived=False,
            include_hidden=False,
        )
        == {}
    )
    assert (
        filter_governed_hierarchy_node_ids(
            db_session=db_session,
            node_ids=[],
            user=user,
        )
        == set()
    )
    assert (
        filter_governed_document_ids(
            db_session=db_session,
            document_ids=[],
            user=user,
        )
        == set()
    )
    assert (
        _effective_exclusions_for_selected_node_ids(
            db_session=db_session,
            selected_node_ids=[],
        )
        == set()
    )
    assert (
        _effective_exclusions_for_selected_node_ids(
            db_session=db_session,
            selected_node_ids=[-1],
        )
        == set()
    )


def test_hidden_connected_source_scope_requires_include_hidden(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_hidden_scope")
    hidden_node = _create_hierarchy_node(
        db_session,
        raw_id=f"hidden-scope-{uuid4().hex}",
        name="Hidden Scope",
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=hidden_node.id,
        curation_status=ConnectedSourceCurationStatus.HIDDEN,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )

    hidden_result = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[hidden_node],
        user=user,
        include_hidden=False,
    )
    visible_result = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[hidden_node],
        user=user,
        include_hidden=True,
    )

    assert hidden_result.nodes == []
    assert visible_result.nodes == [hidden_node]


def test_visible_presets_exclude_document_blocked_by_source_governance(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_preset_doc_governance")
    public_node = _create_hierarchy_node(
        db_session,
        raw_id=f"preset-public-node-{uuid4().hex}",
        name="Public Scope",
    )
    restricted_node = _create_hierarchy_node(
        db_session,
        raw_id=f"preset-restricted-node-{uuid4().hex}",
        name="Restricted Scope",
    )
    document = _create_indexed_document(
        db_session,
        document_id=f"preset-restricted-doc-{uuid4().hex}",
        title="Restricted Preset Document",
        parent=restricted_node,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=public_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )
    restricted_group = UserGroup(name=f"preset-denied-{uuid4().hex}")
    db_session.add(restricted_group)
    db_session.commit()
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=restricted_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[restricted_group.id],
        excluded_hierarchy_node_ids=[],
    )
    preset = create_connected_knowledge_preset(
        db_session=db_session,
        name=f"Preset Governed Document {uuid4().hex}",
        hierarchy_node_ids=[public_node.id],
        document_ids=[document.id],
    )

    visible_presets = get_visible_presets_for_user(db_session=db_session, user=user)

    assert all(
        document.id not in {doc.id for doc in preset.attached_documents}
        for preset in visible_presets
    )

    db_session.delete(preset)
    db_session.commit()


def test_sharepoint_folder_path_parser_edge_cases() -> None:
    assert _sharepoint_folder_path_from_url(None) is None
    assert (
        _sharepoint_folder_path_from_url("https://contoso.sharepoint.com/root") is None
    )
    assert (
        _sharepoint_folder_path_from_url(
            "https://contoso.sharepoint.com/sites/advisor/Shared%20Documents"
        )
        is None
    )
    assert (
        _sharepoint_folder_path_from_url(
            "https://contoso.sharepoint.com/teams/advisor/Shared%20Documents/Folder%20A"
        )
        == "Folder A"
    )


def test_sharepoint_scope_provisioning_rejects_missing_or_invalid_scope(
    db_session: Session,
) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        provision_sharepoint_scope_to_connectors(
            db_session=db_session,
            hierarchy_node_id=-1,
            dry_run=True,
        )

    non_sharepoint_node = _create_hierarchy_node(
        db_session,
        raw_id=f"drive-scope-{uuid4().hex}",
        name="Drive Scope",
        source=DocumentSource.GOOGLE_DRIVE,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=non_sharepoint_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )
    with pytest.raises(ValueError, match="Only SharePoint"):
        provision_sharepoint_scope_to_connectors(
            db_session=db_session,
            hierarchy_node_id=non_sharepoint_node.id,
            dry_run=True,
        )

    missing_link_node = _create_hierarchy_node(
        db_session,
        raw_id=f"sharepoint-missing-link-{uuid4().hex}",
        name="Missing Link",
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=missing_link_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )
    with pytest.raises(ValueError, match="source link"):
        provision_sharepoint_scope_to_connectors(
            db_session=db_session,
            hierarchy_node_id=missing_link_node.id,
            dry_run=True,
        )


def test_sharepoint_scope_provisioning_ignores_invalid_exclusion_links(
    db_session: Session,
) -> None:
    scope_node = _create_hierarchy_node(
        db_session,
        raw_id=f"sharepoint-invalid-exclusion-{uuid4().hex}",
        name="Advisor Services",
        link="https://contoso.sharepoint.com/sites/advisor/Shared%20Documents/Advisor%20Services",
    )
    invalid_excluded_node = _create_hierarchy_node(
        db_session,
        raw_id=f"sharepoint-invalid-excluded-{uuid4().hex}",
        name="Invalid Exclusion",
        parent_id=scope_node.id,
        link="https://contoso.sharepoint.com/root-only",
    )
    pair = make_cc_pair(db_session, source=DocumentSource.SHAREPOINT, commit=False)
    pair.connector.connector_specific_config = {
        "sites": [
            "https://CONTOSO.sharepoint.com/sites/advisor/Shared%20Documents/Advisor%20Services/"
        ],
        "excluded_paths": [],
    }
    db_session.add(
        HierarchyNodeByConnectorCredentialPair(
            hierarchy_node_id=scope_node.id,
            connector_id=pair.connector_id,
            credential_id=pair.credential_id,
        )
    )
    db_session.commit()
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=scope_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[invalid_excluded_node.id],
    )

    results = provision_sharepoint_scope_to_connectors(
        db_session=db_session,
        hierarchy_node_id=scope_node.id,
        dry_run=False,
    )

    assert len(results) == 1
    assert results[0].added_sites == ()
    assert results[0].added_excluded_paths == ()
    assert pair.connector.connector_specific_config["excluded_paths"] == []


def test_list_connected_source_scopes_orders_by_sort_order_then_id(
    db_session: Session,
) -> None:
    later_node = _create_hierarchy_node(
        db_session,
        raw_id=f"scope-list-later-{uuid4().hex}",
        name="Later",
    )
    earlier_node = _create_hierarchy_node(
        db_session,
        raw_id=f"scope-list-earlier-{uuid4().hex}",
        name="Earlier",
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=later_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
        sort_order=20,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=earlier_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
        sort_order=10,
    )

    scopes = list_connected_source_scopes(db_session)
    scope_node_ids = [scope.hierarchy_node_id for scope in scopes]

    assert scope_node_ids.index(earlier_node.id) < scope_node_ids.index(later_node.id)


def test_governed_source_root_is_browsable_but_not_selectable(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_root_bypass")
    group = _create_group_for_user(db_session, user, "root-bypass-group")
    project = _create_project(db_session, user, "Root Bypass Space")
    source_root = _create_hierarchy_node(
        db_session,
        raw_id=f"sharepoint-root-{uuid4().hex}",
        name="SharePoint",
    )
    department = _create_hierarchy_node(
        db_session,
        raw_id=f"advisor-services-root-bypass-{uuid4().hex}",
        name="Advisor Services Intranet",
        parent_id=source_root.id,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=department.id,
        curation_status=ConnectedSourceCurationStatus.DEFAULT_SAFE,
        group_ids=[group.id],
        excluded_hierarchy_node_ids=[],
    )

    # The broad root is visible for navigation but cannot be attached to bypass
    # department-level governance.
    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[source_root, department],
        user=user,
    )
    assert {node.id for node in governed.nodes} == {source_root.id, department.id}
    assert governed.metadata_by_node_id[source_root.id].is_visible is True
    assert governed.metadata_by_node_id[source_root.id].is_selectable is False
    assert governed.metadata_by_node_id[department.id].is_selectable is True

    with pytest.raises(OnyxError):
        replace_project_connected_knowledge(
            project=project,
            document_ids=[],
            hierarchy_node_ids=[source_root.id],
            user=user,
            db_session=db_session,
        )

    replace_project_connected_knowledge(
        project=project,
        document_ids=[],
        hierarchy_node_ids=[department.id],
        user=user,
        db_session=db_session,
    )
    assert [node.id for node in project.hierarchy_nodes] == [department.id]


@pytest.mark.parametrize("denied_first", [False, True])
def test_governance_evaluation_is_source_partitioned_for_mixed_source_selections(
    db_session: Session,
    denied_first: bool,
) -> None:
    user = create_test_user(
        db_session,
        f"project_policy_mixed_source_{'denied_first' if denied_first else 'allowed_first'}",
    )
    allowed_group = _create_group_for_user(db_session, user, "mixed-source-allowed")
    denied_group = UserGroup(name=f"mixed-source-denied-{uuid4().hex}")
    db_session.add(denied_group)
    db_session.commit()
    db_session.refresh(denied_group)

    sharepoint_node = _create_hierarchy_node(
        db_session,
        raw_id=f"sp-mixed-{uuid4().hex}",
        name="Advisor Services Intranet",
        source=DocumentSource.SHAREPOINT,
    )
    drive_node = _create_hierarchy_node(
        db_session,
        raw_id=f"drive-mixed-{uuid4().hex}",
        name="Restricted Drive Folder",
        source=DocumentSource.GOOGLE_DRIVE,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=sharepoint_node.id,
        curation_status=ConnectedSourceCurationStatus.DEFAULT_SAFE,
        group_ids=[allowed_group.id],
        excluded_hierarchy_node_ids=[],
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=drive_node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[denied_group.id],
        excluded_hierarchy_node_ids=[],
    )

    requested_ids = (
        [drive_node.id, sharepoint_node.id]
        if denied_first
        else [sharepoint_node.id, drive_node.id]
    )
    assert filter_governed_hierarchy_node_ids(
        db_session=db_session,
        node_ids=requested_ids,
        user=user,
        include_archived=True,
    ) == {sharepoint_node.id}

    project = _create_project(db_session, user, "Mixed Source Policy Space")
    with pytest.raises(OnyxError):
        replace_project_connected_knowledge(
            project=project,
            document_ids=[],
            hierarchy_node_ids=requested_ids,
            user=user,
            db_session=db_session,
        )

    replace_project_connected_knowledge(
        project=project,
        document_ids=[],
        hierarchy_node_ids=[sharepoint_node.id],
        user=user,
        db_session=db_session,
    )
    assert [node.id for node in project.hierarchy_nodes] == [sharepoint_node.id]


def test_selected_child_inherits_governed_parent_exclusions(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_child_exclusion")
    project = _create_project(db_session, user, "Child Exclusion Space")
    parent = _create_hierarchy_node(
        db_session,
        raw_id=f"bd-parent-{uuid4().hex}",
        name="Business Development Intranet",
    )
    transitions = _create_hierarchy_node(
        db_session,
        raw_id=f"bd-transitions-{uuid4().hex}",
        name="Transitions",
        parent_id=parent.id,
    )
    archive = _create_hierarchy_node(
        db_session,
        raw_id=f"bd-archive-{uuid4().hex}",
        name="z.Completed Transitions",
        parent_id=transitions.id,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=parent.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[archive.id],
    )

    replace_project_connected_knowledge(
        project=project,
        document_ids=[],
        hierarchy_node_ids=[transitions.id],
        user=user,
        db_session=db_session,
    )
    params = apply_project_connected_knowledge_to_search_params(
        SearchParams(
            project_id_filter=None,
            persona_id_filter=None,
            search_usage=SearchToolUsage.DISABLED,
        ),
        project.id,
        db_session,
    )

    assert params.project_hierarchy_node_ids == [transitions.id]
    assert params.project_excluded_hierarchy_node_ids == [archive.id]


def test_visible_presets_filter_inaccessible_attached_documents(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_preset_acl_user")
    other_user = create_test_user(db_session, "project_preset_acl_other")
    governed_folder = _create_hierarchy_node(
        db_session,
        raw_id=f"preset-folder-{uuid4().hex}",
        name="Advisor Services Intranet",
    )
    private_document = _create_indexed_document(
        db_session,
        document_id=f"preset-private-doc-{uuid4().hex}",
        title="Private preset document",
        parent=governed_folder,
        is_public=False,
        external_user_emails=[other_user.email],
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=governed_folder.id,
        curation_status=ConnectedSourceCurationStatus.DEFAULT_SAFE,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )
    preset = create_connected_knowledge_preset(
        db_session=db_session,
        name=f"Preset With Private Doc {uuid4().hex}",
        hierarchy_node_ids=[governed_folder.id],
        document_ids=[private_document.id],
    )

    visible_presets = get_visible_presets_for_user(
        db_session=db_session,
        user=user,
    )

    assert preset.id not in {visible.id for visible in visible_presets}


def test_create_project_with_unavailable_preset_is_atomic(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_preset_atomic_user")
    before_count = (
        db_session.query(UserProject).filter(UserProject.user_id == user.id).count()
    )

    with pytest.raises(OnyxError):
        create_project_api(
            name="Should Not Persist",
            connected_knowledge_preset_id=987654321,
            user=user,
            db_session=db_session,
        )

    after_count = (
        db_session.query(UserProject).filter(UserProject.user_id == user.id).count()
    )
    assert after_count == before_count


def test_governance_metrics_include_indexing_status_and_last_sync(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_status_metrics")
    node = _create_hierarchy_node(
        db_session,
        raw_id=f"status-metrics-node-{uuid4().hex}",
        name="Human Resources Intranet",
    )
    cc_pair = make_cc_pair(db_session, source=node.source, commit=False)
    last_successful_sync = datetime(2026, 7, 23, 16, 0, tzinfo=timezone.utc)
    cc_pair.last_successful_index_time = last_successful_sync
    db_session.add(
        HierarchyNodeByConnectorCredentialPair(
            hierarchy_node_id=node.id,
            connector_id=cc_pair.connector_id,
            credential_id=cc_pair.credential_id,
        )
    )
    search_settings = get_current_search_settings(db_session)
    db_session.add(
        IndexAttempt(
            connector_credential_pair_id=cc_pair.id,
            search_settings_id=search_settings.id,
            from_beginning=True,
            status=IndexingStatus.IN_PROGRESS,
            time_created=last_successful_sync,
            time_started=last_successful_sync,
            time_updated=last_successful_sync,
            total_docs_indexed=10,
            total_chunks=40,
        )
    )
    db_session.commit()

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[node],
        user=user,
    )
    metrics = governed.metadata_by_node_id[node.id].metrics

    assert metrics.latest_index_status == IndexingStatus.IN_PROGRESS.value
    assert metrics.last_successful_index_time == last_successful_sync


def test_restricted_empty_scope_grants_no_access(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_restricted_empty")
    project = _create_project(db_session, user, "Restricted Empty Space")
    node = _create_hierarchy_node(
        db_session,
        raw_id=f"restricted-empty-{uuid4().hex}",
        name="Restricted Empty Intranet",
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        access_type=ConnectedSourceAccessType.RESTRICTED,
        excluded_hierarchy_node_ids=[],
    )

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[node],
        user=user,
    )
    assert governed.nodes == []
    assert governed.metadata_by_node_id[node.id].is_selectable is False
    assert governed.metadata_by_node_id[node.id].denial_reason == "group_not_allowed"
    assert (
        filter_governed_hierarchy_node_ids(
            db_session=db_session,
            node_ids=[node.id],
            user=user,
        )
        == set()
    )
    with pytest.raises(OnyxError):
        replace_project_connected_knowledge(
            project=project,
            document_ids=[],
            hierarchy_node_ids=[node.id],
            user=user,
            db_session=db_session,
        )


def test_paused_connector_backed_scope_is_hidden_by_default(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_paused_connector")
    node = _create_hierarchy_node(
        db_session,
        raw_id=f"paused-scope-{uuid4().hex}",
        name="Paused Intranet",
    )
    cc_pair = make_cc_pair(db_session, source=node.source, commit=False)
    cc_pair.status = ConnectorCredentialPairStatus.PAUSED
    db_session.add(
        HierarchyNodeByConnectorCredentialPair(
            hierarchy_node_id=node.id,
            connector_id=cc_pair.connector_id,
            credential_id=cc_pair.credential_id,
        )
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=node.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[node],
        user=user,
    )
    assert governed.nodes == []
    assert governed.metadata_by_node_id[node.id].denial_reason == "connector_not_active"

    governed_with_hidden = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[node],
        user=user,
        include_hidden=True,
    )
    assert [visible.id for visible in governed_with_hidden.nodes] == [node.id]
    assert governed_with_hidden.metadata_by_node_id[
        node.id
    ].metrics.connector_statuses == (ConnectorCredentialPairStatus.PAUSED.value,)


def test_uncurated_paused_connector_backed_scope_is_hidden_by_default(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "project_policy_uncurated_paused")
    node = _create_hierarchy_node(
        db_session,
        raw_id=f"uncurated-paused-{uuid4().hex}",
        name="Uncurated Paused Intranet",
    )
    cc_pair = make_cc_pair(db_session, source=node.source, commit=False)
    cc_pair.status = ConnectorCredentialPairStatus.PAUSED
    db_session.add(
        HierarchyNodeByConnectorCredentialPair(
            hierarchy_node_id=node.id,
            connector_id=cc_pair.connector_id,
            credential_id=cc_pair.credential_id,
        )
    )
    db_session.commit()

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[node],
        user=user,
    )

    assert governed.nodes == []
    assert governed.metadata_by_node_id[node.id].denial_reason == "connector_not_active"
    assert governed.metadata_by_node_id[node.id].is_selectable is False


def test_paused_connector_backed_scope_with_indexed_content_stays_visible(
    db_session: Session,
) -> None:
    # A paused connector still leaves its already-indexed corpus searchable, so
    # the space knowledge picker must keep it selectable for retrieval-scoping
    # even though no active connector is refreshing it.
    user = create_test_user(db_session, "project_policy_paused_indexed")
    node = _create_hierarchy_node(
        db_session,
        raw_id=f"paused-indexed-{uuid4().hex}",
        name="Paused But Indexed Intranet",
    )
    cc_pair = make_cc_pair(db_session, source=node.source, commit=False)
    cc_pair.status = ConnectorCredentialPairStatus.PAUSED
    db_session.add(
        HierarchyNodeByConnectorCredentialPair(
            hierarchy_node_id=node.id,
            connector_id=cc_pair.connector_id,
            credential_id=cc_pair.credential_id,
        )
    )
    db_session.commit()
    _create_indexed_document(
        db_session,
        document_id=f"doc-{uuid4().hex}",
        title="Already Indexed Handbook",
        parent=node,
    )

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[node],
        user=user,
    )

    assert [visible.id for visible in governed.nodes] == [node.id]
    metadata = governed.metadata_by_node_id[node.id]
    assert metadata.is_visible is True
    assert metadata.is_selectable is True
    assert metadata.denial_reason is None
    assert metadata.metrics.connector_statuses == (
        ConnectorCredentialPairStatus.PAUSED.value,
    )
    assert metadata.metrics.has_indexed_content is True
    assert metadata.metrics.retains_searchable_content is True


def test_deleting_connector_backed_scope_with_indexed_content_stays_hidden(
    db_session: Session,
) -> None:
    # A DELETING connector is actively removing its index, so even though its
    # documents still momentarily exist, its nodes must NOT be offered as
    # selectable knowledge (unlike a paused connector, which is retained).
    user = create_test_user(db_session, "project_policy_deleting_indexed")
    node = _create_hierarchy_node(
        db_session,
        raw_id=f"deleting-indexed-{uuid4().hex}",
        name="Deleting Intranet",
    )
    cc_pair = make_cc_pair(db_session, source=node.source, commit=False)
    cc_pair.status = ConnectorCredentialPairStatus.DELETING
    db_session.add(
        HierarchyNodeByConnectorCredentialPair(
            hierarchy_node_id=node.id,
            connector_id=cc_pair.connector_id,
            credential_id=cc_pair.credential_id,
        )
    )
    db_session.commit()
    _create_indexed_document(
        db_session,
        document_id=f"doc-{uuid4().hex}",
        title="Doomed Handbook",
        parent=node,
    )

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session,
        nodes=[node],
        user=user,
    )

    assert governed.nodes == []
    metadata = governed.metadata_by_node_id[node.id]
    assert metadata.is_visible is False
    assert metadata.denial_reason == "connector_not_active"
    assert metadata.metrics.has_indexed_content is True
    assert metadata.metrics.has_deleting_connector is True
    assert metadata.metrics.retains_searchable_content is False


def test_ungoverned_ancestor_of_scoped_node_is_navigation_only(
    db_session: Session,
) -> None:
    # Once any scope exists for a source, an ungoverned ancestor on the path to
    # a governed node stays browsable (visible) but is NOT selectable, so a user
    # cannot attach a broad parent as a shortcut around policy.
    user = create_test_user(db_session, "project_policy_navigation_only")
    parent = _create_hierarchy_node(
        db_session, raw_id=f"nav-parent-{uuid4().hex}", name="Nav Parent"
    )
    child = _create_hierarchy_node(
        db_session,
        raw_id=f"nav-child-{uuid4().hex}",
        name="Nav Child",
        parent_id=parent.id,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=child.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session, nodes=[parent, child], user=user
    )
    visible_ids = {node.id for node in governed.nodes}

    assert parent.id in visible_ids
    assert child.id in visible_ids
    parent_meta = governed.metadata_by_node_id[parent.id]
    assert parent_meta.is_visible is True
    assert parent_meta.is_selectable is False
    assert parent_meta.denial_reason == "navigation_only"
    assert governed.metadata_by_node_id[child.id].is_selectable is True


def test_ungoverned_node_outside_policy_is_hidden(
    db_session: Session,
) -> None:
    # A node with no scope that is not on the path to any governed node is hidden
    # entirely once a policy exists for the source ("outside_policy").
    user = create_test_user(db_session, "project_policy_outside")
    scoped = _create_hierarchy_node(
        db_session, raw_id=f"outside-scoped-{uuid4().hex}", name="Scoped Node"
    )
    unrelated = _create_hierarchy_node(
        db_session, raw_id=f"outside-unrelated-{uuid4().hex}", name="Unrelated Node"
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=scoped.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session, nodes=[scoped, unrelated], user=user
    )
    visible_ids = {node.id for node in governed.nodes}

    assert scoped.id in visible_ids
    assert unrelated.id not in visible_ids
    unrelated_meta = governed.metadata_by_node_id[unrelated.id]
    assert unrelated_meta.is_visible is False
    assert unrelated_meta.denial_reason == "outside_policy"


def test_child_excluded_by_parent_scope_is_hidden(
    db_session: Session,
) -> None:
    # A parent scope can carve a child out of its coverage; the excluded child is
    # hidden while the parent itself stays visible ("excluded_by_parent_scope").
    user = create_test_user(db_session, "project_policy_excluded")
    parent = _create_hierarchy_node(
        db_session, raw_id=f"excl-parent-{uuid4().hex}", name="Excl Parent"
    )
    child = _create_hierarchy_node(
        db_session,
        raw_id=f"excl-child-{uuid4().hex}",
        name="Excl Child",
        parent_id=parent.id,
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=parent.id,
        curation_status=ConnectedSourceCurationStatus.STANDARD,
        group_ids=[],
        excluded_hierarchy_node_ids=[child.id],
    )

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session, nodes=[parent, child], user=user
    )
    visible_ids = {node.id for node in governed.nodes}

    assert parent.id in visible_ids
    assert child.id not in visible_ids
    child_meta = governed.metadata_by_node_id[child.id]
    assert child_meta.is_visible is False
    assert child_meta.denial_reason == "excluded_by_parent_scope"


def test_archived_scope_hidden_by_default_and_shown_with_include_archived(
    db_session: Session,
) -> None:
    # A scope curated as ARCHIVE is hidden by default ("hidden_by_curation_status")
    # and only surfaces when include_archived is requested.
    user = create_test_user(db_session, "project_policy_archived")
    node = _create_hierarchy_node(
        db_session, raw_id=f"archived-scope-{uuid4().hex}", name="Archived Intranet"
    )
    upsert_connected_source_scope(
        db_session=db_session,
        hierarchy_node_id=node.id,
        curation_status=ConnectedSourceCurationStatus.ARCHIVE,
        group_ids=[],
        excluded_hierarchy_node_ids=[],
    )

    governed = get_governed_hierarchy_nodes_for_source(
        db_session=db_session, nodes=[node], user=user
    )
    assert governed.nodes == []
    hidden_meta = governed.metadata_by_node_id[node.id]
    assert hidden_meta.is_visible is False
    assert hidden_meta.denial_reason == "hidden_by_curation_status"

    governed_with_archived = get_governed_hierarchy_nodes_for_source(
        db_session=db_session, nodes=[node], user=user, include_archived=True
    )
    assert [visible.id for visible in governed_with_archived.nodes] == [node.id]
    assert governed_with_archived.metadata_by_node_id[node.id].is_archived is True
