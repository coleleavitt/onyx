from collections.abc import Generator
from datetime import datetime
from datetime import timezone
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from onyx.access.access import get_acl_for_user
from onyx.auth.schemas import UserRole
from onyx.access.utils import prefix_user_email
from onyx.chat.models import SearchParams
from onyx.chat.process_message import apply_project_connected_knowledge_to_search_params
from onyx.configs.constants import DocumentSource
from onyx.configs.constants import PUBLIC_DOC_PAT
from onyx.context.search.models import IndexFilters
from onyx.context.search.models import InferenceChunk
from onyx.context.search.models import PersonaSearchInfo
from onyx.db.connected_source_governance import create_connected_knowledge_preset
from onyx.db.connected_source_governance import filter_governed_hierarchy_node_ids
from onyx.db.connected_source_governance import get_governed_hierarchy_nodes_for_source
from onyx.db.connected_source_governance import get_visible_presets_for_user
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
from onyx.error_handling.exceptions import OnyxError
from onyx.server.features.projects.api import create_project as create_project_api
from onyx.server.features.projects.api import get_project_connected_knowledge
from onyx.server.features.projects.api import update_project_connected_knowledge
from onyx.server.features.projects.models import ProjectConnectedKnowledgeRequest
from onyx.tools.models import SearchToolUsage
from onyx.tools.tool_implementations.search.search_tool import SearchTool
from tests.external_dependency_unit.conftest import create_test_user
from tests.external_dependency_unit.indexing_helpers import make_cc_pair


@pytest.fixture(autouse=True)
def _clear_connected_source_governance(
    db_session: Session,
) -> Generator[None, None, None]:
    db_session.query(ConnectedSourceScope).delete()
    db_session.commit()
    yield
    db_session.query(ConnectedSourceScope).delete()
    db_session.commit()


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
) -> HierarchyNode:
    node = HierarchyNode(
        raw_node_id=raw_id,
        display_name=name,
        source=source,
        node_type=HierarchyNodeType.FOLDER,
        is_public=is_public,
        parent_id=parent_id,
    )
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)
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
        emitter=None,  # type: ignore[arg-type]
        user=viewer,
        persona_search_info=PersonaSearchInfo(
            document_set_names=[],
            search_start_date=None,
            attached_document_ids=params.project_attached_document_ids,
            hierarchy_node_ids=params.project_hierarchy_node_ids,
        ),
        llm=None,  # type: ignore[arg-type]
        document_index=fake_index,  # type: ignore[arg-type]
        user_selected_filters=None,
        project_id_filter=params.project_id_filter,
        persona_id_filter=params.persona_id_filter,
    )

    chunks = search_tool._run_search_for_query(
        query="policy",
        hybrid_alpha=0.0,
        num_hits=10,
        acl_filters=list(get_acl_for_user(viewer, db_session)),
        embedding_model=None,  # type: ignore[arg-type]
        federated_retrieval_infos=[],
        effective_filters=None,
    )

    assert {chunk.document_id for chunk in chunks} == {
        public_exact.id,
        public_folder_doc.id,
    }
    assert fake_index.last_filters is not None
    assert private_owner_exact.id in fake_index.last_filters.attached_document_ids
    assert folder.id in fake_index.last_filters.hierarchy_node_ids
    assert (
        prefix_user_email(viewer.email) in fake_index.last_filters.access_control_list
    )


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
        emitter=None,  # type: ignore[arg-type]
        user=user,
        persona_search_info=PersonaSearchInfo(
            document_set_names=[],
            search_start_date=None,
            attached_document_ids=params.project_attached_document_ids,
            hierarchy_node_ids=params.project_hierarchy_node_ids,
            excluded_hierarchy_node_ids=params.project_excluded_hierarchy_node_ids,
        ),
        llm=None,  # type: ignore[arg-type]
        document_index=fake_index,  # type: ignore[arg-type]
        user_selected_filters=None,
        project_id_filter=params.project_id_filter,
        persona_id_filter=params.persona_id_filter,
    )

    chunks = search_tool._run_search_for_query(
        query="transition",
        hybrid_alpha=0.0,
        num_hits=10,
        acl_filters=list(get_acl_for_user(user, db_session)),
        embedding_model=None,  # type: ignore[arg-type]
        federated_retrieval_infos=[],
        effective_filters=None,
    )

    assert {chunk.document_id for chunk in chunks} == {active_doc.id}
    assert fake_index.last_filters is not None
    assert fake_index.last_filters.excluded_hierarchy_node_ids == [archive.id]


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
