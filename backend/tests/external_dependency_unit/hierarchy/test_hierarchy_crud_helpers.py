"""Focused CRUD and helper coverage for hierarchy node DB utilities."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.configs.constants import DocumentSource
from onyx.connectors.models import InputType
from onyx.db.enums import AccessType
from onyx.db.enums import ConnectorCredentialPairStatus
from onyx.db.enums import HierarchyNodeType
from onyx.db.hierarchy import delete_orphaned_hierarchy_nodes
from onyx.db.hierarchy import filter_accessible_hierarchy_node_ids
from onyx.db.hierarchy import get_accessible_hierarchy_nodes_for_source
from onyx.db.hierarchy import get_all_hierarchy_nodes_for_source
from onyx.db.hierarchy import get_document_parent_hierarchy_node_ids
from onyx.db.hierarchy import get_hierarchy_node_by_id
from onyx.db.hierarchy import get_hierarchy_node_by_raw_id
from onyx.db.hierarchy import get_hierarchy_node_children
from onyx.db.hierarchy import get_root_hierarchy_nodes_for_source
from onyx.db.hierarchy import get_source_hierarchy_node
from onyx.db.hierarchy import link_hierarchy_nodes_to_documents
from onyx.db.hierarchy import remove_stale_hierarchy_node_cc_pair_entries
from onyx.db.hierarchy import reparent_orphaned_hierarchy_nodes
from onyx.db.hierarchy import search_accessible_hierarchy_nodes
from onyx.db.hierarchy import update_document_parent_hierarchy_nodes
from onyx.db.hierarchy import update_hierarchy_node_permissions
from onyx.db.hierarchy import upsert_hierarchy_node_cc_pair_entries
from onyx.db.models import Connector
from onyx.db.models import ConnectorCredentialPair
from onyx.db.models import Credential
from onyx.db.models import Document
from onyx.db.models import HierarchyNode
from onyx.db.models import HierarchyNodeByConnectorCredentialPair
from onyx.kg.models import KGStage


@pytest.fixture()
def tag() -> str:
    return uuid4().hex[:8]


@pytest.fixture()
def cleanup_nodes(db_session: Session, tag: str) -> Iterator[None]:
    yield
    nodes = (
        db_session.query(HierarchyNode)
        .filter(HierarchyNode.raw_node_id.like(f"%_{tag}"))
        .all()
    )
    for node in nodes:
        db_session.delete(node)
    db_session.commit()


@pytest.fixture()
def cleanup_documents(db_session: Session, tag: str) -> Iterator[None]:
    yield
    docs = db_session.query(Document).filter(Document.id.like(f"%_{tag}")).all()
    for doc in docs:
        db_session.delete(doc)
    db_session.commit()


def _node(
    raw_node_id: str,
    display_name: str,
    source: DocumentSource = DocumentSource.GOOGLE_DRIVE,
    node_type: HierarchyNodeType = HierarchyNodeType.FOLDER,
    parent_id: int | None = None,
    *,
    is_public: bool = True,
) -> HierarchyNode:
    return HierarchyNode(
        raw_node_id=raw_node_id,
        display_name=display_name,
        link=f"https://example.com/{raw_node_id}",
        source=source,
        node_type=node_type,
        parent_id=parent_id,
        is_public=is_public,
    )


def _document(document_id: str, parent_id: int | None = None) -> Document:
    return Document(
        id=document_id,
        semantic_id=document_id,
        kg_stage=KGStage.NOT_STARTED,
        parent_hierarchy_node_id=parent_id,
    )


@pytest.mark.usefixtures("cleanup_nodes")
def test_source_node_helpers_and_wrappers(db_session: Session, tag: str) -> None:
    source_node = get_source_hierarchy_node(db_session, DocumentSource.GOOGLE_DRIVE)
    assert source_node is not None
    original_is_public = source_node.is_public

    child_a = _node(f"alpha_{tag}", f"Alpha {tag}", parent_id=source_node.id)
    child_b = _node(f"beta_{tag}", f"Beta {tag}", parent_id=source_node.id)
    stub = _node(
        f"stub_{tag}",
        f"Stub {tag}",
        node_type=HierarchyNodeType.STUB,
        parent_id=source_node.id,
    )
    db_session.add_all([child_a, child_b, stub])
    db_session.flush()

    try:
        source_node.is_public = False
        db_session.flush()
        refreshed_source_node = get_source_hierarchy_node(
            db_session, DocumentSource.GOOGLE_DRIVE
        )
        assert refreshed_source_node is not None
        assert refreshed_source_node.is_public is False

        assert get_hierarchy_node_by_id(db_session, child_a.id) == child_a
        assert (
            get_hierarchy_node_by_raw_id(
                db_session, child_a.raw_node_id, DocumentSource.GOOGLE_DRIVE
            )
            == child_a
        )

        children = get_hierarchy_node_children(db_session, source_node.id, limit=1)
        assert children[0].display_name <= child_b.display_name
        offset_children = get_hierarchy_node_children(
            db_session, source_node.id, limit=10, offset=1
        )
        assert len(offset_children) >= 1

        root_ids = {
            node.raw_node_id
            for node in get_root_hierarchy_nodes_for_source(
                db_session, DocumentSource.GOOGLE_DRIVE
            )
        }
        assert child_a.raw_node_id in root_ids
        assert child_b.raw_node_id in root_ids

        all_ids = {
            node.raw_node_id
            for node in get_all_hierarchy_nodes_for_source(
                db_session, DocumentSource.GOOGLE_DRIVE
            )
        }
        assert source_node.raw_node_id in all_ids
        assert child_a.raw_node_id in all_ids

        accessible_ids = {
            node.raw_node_id
            for node in get_accessible_hierarchy_nodes_for_source(
                db_session, DocumentSource.GOOGLE_DRIVE, "user@example.com", []
            )
        }
        assert child_a.raw_node_id in accessible_ids
        assert stub.raw_node_id not in accessible_ids

        search_ids = {
            node.raw_node_id
            for node in search_accessible_hierarchy_nodes(
                db_session, tag, [DocumentSource.GOOGLE_DRIVE], "user@example.com", []
            )
        }
        assert child_a.raw_node_id in search_ids
        assert child_b.raw_node_id in search_ids
        assert stub.raw_node_id not in search_ids

        assert filter_accessible_hierarchy_node_ids(db_session, [], "", []) == set()
        assert filter_accessible_hierarchy_node_ids(
            db_session, [child_a.id, child_b.id], "", []
        ) == {child_a.id, child_b.id}
    finally:
        source_node.is_public = original_is_public
        db_session.commit()


@pytest.mark.usefixtures("cleanup_nodes", "cleanup_documents")
def test_document_parent_helpers_update_only_changed_existing_documents(
    db_session: Session, tag: str
) -> None:
    parent = _node(f"parent_{tag}", f"Parent {tag}")
    db_session.add(parent)
    db_session.flush()

    doc_without_parent = _document(f"doc_without_parent_{tag}")
    doc_with_parent = _document(f"doc_with_parent_{tag}", parent.id)
    db_session.add_all([doc_without_parent, doc_with_parent])
    db_session.commit()

    assert get_document_parent_hierarchy_node_ids(db_session, []) == {}
    parent_map = get_document_parent_hierarchy_node_ids(
        db_session, [doc_without_parent.id, doc_with_parent.id, f"missing_{tag}"]
    )
    assert parent_map == {
        doc_without_parent.id: None,
        doc_with_parent.id: parent.id,
    }

    updated = update_document_parent_hierarchy_nodes(
        db_session,
        {
            doc_without_parent.id: parent.id,
            doc_with_parent.id: parent.id,
            f"missing_{tag}": parent.id,
        },
    )
    assert updated == 1
    db_session.refresh(doc_without_parent)
    assert doc_without_parent.parent_hierarchy_node_id == parent.id

    assert (
        update_document_parent_hierarchy_nodes(
            db_session,
            {doc_without_parent.id: parent.id, doc_with_parent.id: parent.id},
        )
        == 0
    )
    assert update_document_parent_hierarchy_nodes(db_session, {}) == 0

    updated_without_commit = update_document_parent_hierarchy_nodes(
        db_session, {doc_without_parent.id: None}, commit=False
    )
    assert updated_without_commit == 1
    db_session.refresh(doc_without_parent)
    assert doc_without_parent.parent_hierarchy_node_id is None
    db_session.commit()


@pytest.mark.usefixtures("cleanup_nodes", "cleanup_documents")
def test_permission_update_and_document_linking_helpers(
    db_session: Session, tag: str
) -> None:
    assert (
        update_hierarchy_node_permissions(
            db_session,
            f"missing_{tag}",
            DocumentSource.NOTION,
            is_public=True,
            external_user_emails=None,
            external_user_group_ids=None,
        )
        is False
    )

    notion_doc_id = f"notion_page_{tag}"
    notion_node = _node(
        notion_doc_id,
        f"Notion Page {tag}",
        source=DocumentSource.NOTION,
        node_type=HierarchyNodeType.FOLDER,
        is_public=False,
    )
    db_session.add(notion_node)
    db_session.add(_document(notion_doc_id))
    db_session.commit()

    assert update_hierarchy_node_permissions(
        db_session,
        notion_node.raw_node_id,
        DocumentSource.NOTION,
        is_public=True,
        external_user_emails=["alice@example.com"],
        external_user_group_ids=["group-eng"],
        commit=False,
    )
    assert notion_node.is_public is True
    assert notion_node.external_user_emails == ["alice@example.com"]
    assert notion_node.external_user_group_ids == ["group-eng"]
    db_session.commit()

    assert link_hierarchy_nodes_to_documents(db_session, [], DocumentSource.NOTION) == 0
    assert (
        link_hierarchy_nodes_to_documents(
            db_session, [notion_doc_id], DocumentSource.GOOGLE_DRIVE
        )
        == 0
    )
    assert (
        link_hierarchy_nodes_to_documents(
            db_session, [notion_doc_id], DocumentSource.NOTION
        )
        == 1
    )
    assert notion_node.document_id == notion_doc_id
    assert (
        link_hierarchy_nodes_to_documents(
            db_session, [notion_doc_id], DocumentSource.NOTION
        )
        == 0
    )


@pytest.mark.usefixtures("cleanup_nodes")
def test_hierarchy_cc_pair_pruning_and_orphan_repair(
    db_session: Session, tag: str
) -> None:
    connector: Connector | None = None
    credential: Credential | None = None
    try:
        connector = Connector(
            name=f"hierarchy-helper-connector-{tag}",
            source=DocumentSource.CONFLUENCE,
            input_type=InputType.POLL,
            connector_specific_config={},
            refresh_freq=None,
            prune_freq=None,
            indexing_start=None,
        )
        credential = Credential(
            source=DocumentSource.CONFLUENCE,
            credential_json={"token": tag},
            admin_public=True,
        )
        db_session.add_all([connector, credential])
        db_session.flush()

        cc_pair = ConnectorCredentialPair(
            connector_id=connector.id,
            credential_id=credential.id,
            name=f"hierarchy-helper-cc-pair-{tag}",
            status=ConnectorCredentialPairStatus.ACTIVE,
            access_type=AccessType.PUBLIC,
            auto_sync_options=None,
        )
        db_session.add(cc_pair)
        db_session.flush()

        source_node = get_source_hierarchy_node(db_session, DocumentSource.CONFLUENCE)
        assert source_node is not None

        kept = _node(
            f"kept_{tag}",
            f"Kept {tag}",
            source=DocumentSource.CONFLUENCE,
            parent_id=source_node.id,
        )
        stale = _node(
            f"stale_{tag}",
            f"Stale {tag}",
            source=DocumentSource.CONFLUENCE,
            parent_id=source_node.id,
        )
        no_join = _node(
            f"no_join_{tag}",
            f"No Join {tag}",
            source=DocumentSource.CONFLUENCE,
            parent_id=source_node.id,
        )
        needs_parent = _node(
            f"needs_parent_{tag}",
            f"Needs Parent {tag}",
            source=DocumentSource.CONFLUENCE,
            parent_id=None,
        )
        db_session.add_all([kept, stale, no_join, needs_parent])
        db_session.flush()

        reparented = reparent_orphaned_hierarchy_nodes(
            db_session, DocumentSource.CONFLUENCE, commit=False
        )
        assert [node.raw_node_id for node in reparented] == [needs_parent.raw_node_id]
        assert needs_parent.parent_id == source_node.id

        upsert_hierarchy_node_cc_pair_entries(
            db_session, [], connector.id, credential.id
        )
        upsert_hierarchy_node_cc_pair_entries(
            db_session,
            [kept.id, stale.id, needs_parent.id, kept.id],
            connector.id,
            credential.id,
            commit=False,
        )
        rows = db_session.execute(
            select(HierarchyNodeByConnectorCredentialPair).where(
                HierarchyNodeByConnectorCredentialPair.connector_id == connector.id,
                HierarchyNodeByConnectorCredentialPair.credential_id == credential.id,
            )
        ).scalars()
        assert {row.hierarchy_node_id for row in rows} == {
            kept.id,
            stale.id,
            needs_parent.id,
        }

        deleted_stale_rows = remove_stale_hierarchy_node_cc_pair_entries(
            db_session,
            connector.id,
            credential.id,
            {kept.id, needs_parent.id},
            commit=False,
        )
        assert deleted_stale_rows == 1

        deleted_raw_ids = delete_orphaned_hierarchy_nodes(
            db_session, DocumentSource.CONFLUENCE, commit=False
        )
        assert deleted_raw_ids == [stale.raw_node_id, no_join.raw_node_id]

        deleted_remaining_rows = remove_stale_hierarchy_node_cc_pair_entries(
            db_session,
            connector.id,
            credential.id,
            set(),
        )
        assert deleted_remaining_rows == 2
    finally:
        db_session.rollback()
        if connector is not None:
            db_session.query(ConnectorCredentialPair).filter(
                ConnectorCredentialPair.connector_id == connector.id
            ).delete(synchronize_session=False)
        if credential is not None:
            db_session.delete(credential)
        if connector is not None:
            db_session.delete(connector)
        db_session.commit()
