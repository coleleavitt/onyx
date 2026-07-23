from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from onyx.configs.constants import DocumentSource
from onyx.db.enums import ConnectedSourceCurationStatus
from onyx.db.models import ConnectedSourceScope
from onyx.db.models import ConnectedSourceScope__UserGroup
from onyx.db.models import ConnectedSourceScopeExclusion
from onyx.db.models import Document
from onyx.db.models import HierarchyNode
from onyx.db.models import Project__HierarchyNode
from onyx.db.models import ProjectConnectedKnowledgePreset
from onyx.db.models import User
from onyx.db.models import User__UserGroup


@dataclass(frozen=True)
class ConnectedSourceScopeMetrics:
    document_count: int = 0
    chunk_count: int = 0
    latest_index_status: str | None = None
    last_successful_index_time: datetime | None = None


@dataclass(frozen=True)
class ConnectedSourceScopeMetadata:
    hierarchy_node_id: int
    curation_status: ConnectedSourceCurationStatus | None
    is_default: bool
    is_archived: bool
    is_hidden: bool
    is_diagnostic: bool
    is_visible: bool
    is_selectable: bool
    denial_reason: str | None = None
    display_label: str | None = None
    tenant_label: str | None = None
    department_label: str | None = None
    sort_order: int = 0
    size_bytes: int | None = None
    document_count_estimate: int | None = None
    warning: str | None = None
    allowed_group_ids: tuple[int, ...] = ()
    excluded_hierarchy_node_ids: tuple[int, ...] = ()
    metrics: ConnectedSourceScopeMetrics = ConnectedSourceScopeMetrics()


@dataclass(frozen=True)
class GovernedHierarchyNodes:
    nodes: list[HierarchyNode]
    metadata_by_node_id: dict[int, ConnectedSourceScopeMetadata]


def get_user_group_ids(db_session: Session, user: User | None) -> set[int]:
    if user is None or user.id is None:
        return set()
    return set(
        db_session.scalars(
            select(User__UserGroup.user_group_id).where(
                User__UserGroup.user_id == user.id
            )
        ).all()
    )


def _node_paths(nodes: list[HierarchyNode]) -> dict[int, list[int]]:
    parent_by_id = {node.id: node.parent_id for node in nodes}
    paths: dict[int, list[int]] = {}

    def build(node_id: int) -> list[int]:
        if node_id in paths:
            return paths[node_id]
        parent_id = parent_by_id.get(node_id)
        if parent_id is None or parent_id not in parent_by_id:
            path = [node_id]
        else:
            path = [*build(parent_id), node_id]
        paths[node_id] = path
        return path

    for node in nodes:
        build(node.id)
    return paths


def _descendants_by_node_id(nodes: list[HierarchyNode]) -> dict[int, set[int]]:
    children_by_parent: dict[int | None, list[int]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node.id)

    descendants: dict[int, set[int]] = {}

    def collect(node_id: int) -> set[int]:
        if node_id in descendants:
            return descendants[node_id]
        values = {node_id}
        for child_id in children_by_parent.get(node_id, []):
            values.update(collect(child_id))
        descendants[node_id] = values
        return values

    for node in nodes:
        collect(node.id)
    return descendants


def _scope_status_flags(
    status: ConnectedSourceCurationStatus | None,
) -> tuple[bool, bool, bool, bool]:
    is_default = status == ConnectedSourceCurationStatus.DEFAULT_SAFE
    is_archived = status == ConnectedSourceCurationStatus.ARCHIVE
    is_hidden = status == ConnectedSourceCurationStatus.HIDDEN
    is_diagnostic = status == ConnectedSourceCurationStatus.DIAGNOSTIC
    return is_default, is_archived, is_hidden, is_diagnostic


def _scope_is_allowed_for_groups(
    scope: ConnectedSourceScope,
    user_group_ids: set[int],
) -> bool:
    allowed_group_ids = {link.user_group_id for link in scope.group_links}
    return not allowed_group_ids or bool(allowed_group_ids & user_group_ids)


def _scope_is_visible_by_status(
    scope: ConnectedSourceScope,
    *,
    include_archived: bool,
    include_hidden: bool,
) -> bool:
    if scope.curation_status == ConnectedSourceCurationStatus.ARCHIVE:
        return include_archived
    if scope.curation_status in {
        ConnectedSourceCurationStatus.HIDDEN,
        ConnectedSourceCurationStatus.DIAGNOSTIC,
    }:
        return include_hidden
    return True


def _load_scopes_by_source(
    db_session: Session,
    sources: set[DocumentSource],
) -> dict[DocumentSource, dict[int, ConnectedSourceScope]]:
    if not sources:
        return {}
    scopes = db_session.scalars(
        select(ConnectedSourceScope)
        .join(HierarchyNode, HierarchyNode.id == ConnectedSourceScope.hierarchy_node_id)
        .where(HierarchyNode.source.in_(sources))
        .options(
            selectinload(ConnectedSourceScope.group_links),
            selectinload(ConnectedSourceScope.excluded_links),
            selectinload(ConnectedSourceScope.hierarchy_node),
        )
    ).all()
    grouped: dict[DocumentSource, dict[int, ConnectedSourceScope]] = defaultdict(dict)
    for scope in scopes:
        grouped[scope.hierarchy_node.source][scope.hierarchy_node_id] = scope
    return grouped


def _build_metrics_by_node_id(
    db_session: Session,
    nodes: list[HierarchyNode],
) -> dict[int, ConnectedSourceScopeMetrics]:
    if not nodes:
        return {}

    descendants = _descendants_by_node_id(nodes)
    parent_ids = [node.id for node in nodes]
    direct_counts = {
        row.parent_hierarchy_node_id: (
            int(row.document_count),
            int(row.chunk_count or 0),
        )
        for row in db_session.execute(
            select(
                Document.parent_hierarchy_node_id,
                func.count(Document.id).label("document_count"),
                func.coalesce(func.sum(Document.chunk_count), 0).label("chunk_count"),
            )
            .where(Document.parent_hierarchy_node_id.in_(parent_ids))
            .group_by(Document.parent_hierarchy_node_id)
        )
    }

    raw_metrics: dict[int, ConnectedSourceScopeMetrics] = {}
    for node in nodes:
        document_count = 0
        chunk_count = 0
        for descendant_id in descendants[node.id]:
            direct_document_count, direct_chunk_count = direct_counts.get(
                descendant_id, (0, 0)
            )
            document_count += direct_document_count
            chunk_count += direct_chunk_count
        raw_metrics[node.id] = ConnectedSourceScopeMetrics(
            document_count=document_count,
            chunk_count=chunk_count,
        )

    return raw_metrics


def _evaluate_source_partition(
    *,
    nodes: list[HierarchyNode],
    scopes_by_node_id: dict[int, ConnectedSourceScope],
    metrics_by_node_id: dict[int, ConnectedSourceScopeMetrics],
    user_group_ids: set[int],
    include_archived: bool,
    include_hidden: bool,
) -> dict[int, ConnectedSourceScopeMetadata]:
    paths_by_node_id = _node_paths(nodes)
    any_policy = bool(scopes_by_node_id)
    governed_path_node_ids: set[int] = set()
    if any_policy:
        for scoped_node_id in scopes_by_node_id:
            governed_path_node_ids.update(paths_by_node_id.get(scoped_node_id, []))

    metadata: dict[int, ConnectedSourceScopeMetadata] = {}
    for node in nodes:
        path = paths_by_node_id[node.id]
        path_node_ids = set(path)
        path_scopes = [
            scopes_by_node_id[node_id]
            for node_id in path
            if node_id in scopes_by_node_id
        ]
        own_scope = scopes_by_node_id.get(node.id)
        visible = True
        selectable = True
        denial_reason: str | None = None

        if any_policy and not path_scopes:
            # Keep ungoverned ancestors of governed scopes visible so users can
            # browse from the source root to allowed departments, but never let
            # those broad ancestors be selected as a shortcut around policy.
            if node.id in governed_path_node_ids:
                selectable = False
                denial_reason = "navigation_only"
            else:
                visible = False
                selectable = False
                denial_reason = "outside_policy"

        for scope in path_scopes:
            if not _scope_is_allowed_for_groups(scope, user_group_ids):
                visible = False
                selectable = False
                denial_reason = "group_not_allowed"
            if not _scope_is_visible_by_status(
                scope,
                include_archived=include_archived,
                include_hidden=include_hidden,
            ):
                visible = False
                selectable = False
                denial_reason = "hidden_by_curation_status"
            excluded_ids = {
                link.excluded_hierarchy_node_id for link in scope.excluded_links
            }
            if excluded_ids & path_node_ids:
                visible = False
                selectable = False
                denial_reason = "excluded_by_parent_scope"

        status = own_scope.curation_status if own_scope else None
        is_default, is_archived, is_hidden, is_diagnostic = _scope_status_flags(status)
        allowed_group_ids = tuple(
            sorted(link.user_group_id for link in own_scope.group_links)
            if own_scope
            else ()
        )
        excluded_ids = tuple(
            sorted(link.excluded_hierarchy_node_id for link in own_scope.excluded_links)
            if own_scope
            else ()
        )
        metadata[node.id] = ConnectedSourceScopeMetadata(
            hierarchy_node_id=node.id,
            curation_status=status,
            is_default=is_default,
            is_archived=is_archived,
            is_hidden=is_hidden,
            is_diagnostic=is_diagnostic,
            is_visible=visible,
            is_selectable=selectable,
            denial_reason=denial_reason,
            display_label=own_scope.display_label if own_scope else None,
            tenant_label=own_scope.tenant_label if own_scope else None,
            department_label=own_scope.department_label if own_scope else None,
            sort_order=own_scope.sort_order if own_scope else 0,
            size_bytes=own_scope.size_bytes if own_scope else None,
            document_count_estimate=own_scope.document_count_estimate
            if own_scope
            else None,
            warning=own_scope.warning if own_scope else None,
            allowed_group_ids=allowed_group_ids,
            excluded_hierarchy_node_ids=excluded_ids,
            metrics=metrics_by_node_id.get(node.id, ConnectedSourceScopeMetrics()),
        )
    return metadata


def build_metadata_for_nodes(
    *,
    db_session: Session,
    nodes: list[HierarchyNode],
    user_group_ids: set[int],
    include_archived: bool,
    include_hidden: bool,
) -> dict[int, ConnectedSourceScopeMetadata]:
    if not nodes:
        return {}

    nodes_by_source: dict[DocumentSource, list[HierarchyNode]] = defaultdict(list)
    for node in nodes:
        nodes_by_source[node.source].append(node)

    scopes_by_source = _load_scopes_by_source(db_session, set(nodes_by_source))
    metrics_by_node_id = _build_metrics_by_node_id(db_session, nodes)
    metadata: dict[int, ConnectedSourceScopeMetadata] = {}
    for source, source_nodes in nodes_by_source.items():
        metadata.update(
            _evaluate_source_partition(
                nodes=source_nodes,
                scopes_by_node_id=scopes_by_source.get(source, {}),
                metrics_by_node_id=metrics_by_node_id,
                user_group_ids=user_group_ids,
                include_archived=include_archived,
                include_hidden=include_hidden,
            )
        )
    return metadata


def get_governed_hierarchy_nodes_for_source(
    *,
    db_session: Session,
    nodes: list[HierarchyNode],
    user: User,
    include_archived: bool = False,
    include_hidden: bool = False,
) -> GovernedHierarchyNodes:
    user_group_ids = get_user_group_ids(db_session, user)
    metadata = build_metadata_for_nodes(
        db_session=db_session,
        nodes=nodes,
        user_group_ids=user_group_ids,
        include_archived=include_archived,
        include_hidden=include_hidden,
    )
    visible_nodes = [node for node in nodes if metadata[node.id].is_visible]
    return GovernedHierarchyNodes(nodes=visible_nodes, metadata_by_node_id=metadata)


def filter_governed_hierarchy_node_ids(
    *,
    db_session: Session,
    node_ids: list[int],
    user: User,
    include_archived: bool = False,
    include_hidden: bool = False,
) -> set[int]:
    if not node_ids:
        return set()
    nodes = list(
        db_session.scalars(
            select(HierarchyNode).where(
                HierarchyNode.source.in_(
                    select(HierarchyNode.source).where(HierarchyNode.id.in_(node_ids))
                )
            )
        ).all()
    )
    metadata = build_metadata_for_nodes(
        db_session=db_session,
        nodes=nodes,
        user_group_ids=get_user_group_ids(db_session, user),
        include_archived=include_archived,
        include_hidden=include_hidden,
    )
    return {
        node_id
        for node_id in node_ids
        if metadata.get(node_id) and metadata[node_id].is_selectable
    }


def filter_governed_document_ids(
    *,
    db_session: Session,
    document_ids: list[str],
    user: User,
) -> set[str]:
    if not document_ids:
        return set()
    rows = db_session.execute(
        select(Document.id, Document.parent_hierarchy_node_id).where(
            Document.id.in_(document_ids)
        )
    ).all()
    parent_ids = [parent_id for _, parent_id in rows if parent_id is not None]
    allowed_parent_ids = filter_governed_hierarchy_node_ids(
        db_session=db_session,
        node_ids=parent_ids,
        user=user,
        include_archived=True,
    )
    return {
        document_id
        for document_id, parent_id in rows
        if parent_id is None or parent_id in allowed_parent_ids
    }


def get_project_connected_excluded_hierarchy_node_ids(
    *,
    project_id: int,
    db_session: Session,
) -> list[int]:
    rows = db_session.execute(
        select(ConnectedSourceScopeExclusion.excluded_hierarchy_node_id)
        .join(
            ConnectedSourceScope,
            ConnectedSourceScope.id == ConnectedSourceScopeExclusion.scope_id,
        )
        .join(
            Project__HierarchyNode,
            Project__HierarchyNode.hierarchy_node_id
            == ConnectedSourceScope.hierarchy_node_id,
        )
        .where(Project__HierarchyNode.project_id == project_id)
    ).all()
    return sorted({row[0] for row in rows})


def upsert_connected_source_scope(
    *,
    db_session: Session,
    hierarchy_node_id: int,
    curation_status: ConnectedSourceCurationStatus,
    group_ids: list[int],
    excluded_hierarchy_node_ids: list[int],
    display_label: str | None = None,
    tenant_label: str | None = None,
    department_label: str | None = None,
    sort_order: int = 0,
    size_bytes: int | None = None,
    document_count_estimate: int | None = None,
    warning: str | None = None,
) -> ConnectedSourceScope:
    scope = db_session.scalar(
        select(ConnectedSourceScope).where(
            ConnectedSourceScope.hierarchy_node_id == hierarchy_node_id
        )
    )
    if scope is None:
        scope = ConnectedSourceScope(hierarchy_node_id=hierarchy_node_id)
        db_session.add(scope)
        db_session.flush()
    scope.curation_status = curation_status
    scope.display_label = display_label
    scope.tenant_label = tenant_label
    scope.department_label = department_label
    scope.sort_order = sort_order
    scope.size_bytes = size_bytes
    scope.document_count_estimate = document_count_estimate
    scope.warning = warning
    scope.group_links = [
        ConnectedSourceScope__UserGroup(user_group_id=group_id)
        for group_id in group_ids
    ]
    scope.excluded_links = [
        ConnectedSourceScopeExclusion(excluded_hierarchy_node_id=node_id)
        for node_id in excluded_hierarchy_node_ids
    ]
    db_session.commit()
    db_session.refresh(scope)
    return scope


def list_connected_source_scopes(db_session: Session) -> list[ConnectedSourceScope]:
    return list(
        db_session.scalars(
            select(ConnectedSourceScope)
            .options(
                selectinload(ConnectedSourceScope.group_links),
                selectinload(ConnectedSourceScope.excluded_links),
                selectinload(ConnectedSourceScope.hierarchy_node),
            )
            .order_by(ConnectedSourceScope.sort_order, ConnectedSourceScope.id)
        ).all()
    )


def get_visible_presets_for_user(
    *,
    db_session: Session,
    user: User,
    include_archived: bool = False,
) -> list[ProjectConnectedKnowledgePreset]:
    stmt = select(ProjectConnectedKnowledgePreset).options(
        selectinload(ProjectConnectedKnowledgePreset.hierarchy_nodes),
        selectinload(ProjectConnectedKnowledgePreset.attached_documents),
    )
    if not include_archived:
        stmt = stmt.where(ProjectConnectedKnowledgePreset.is_archived.is_(False))
    presets = list(
        db_session.scalars(stmt.order_by(ProjectConnectedKnowledgePreset.name)).all()
    )
    visible: list[ProjectConnectedKnowledgePreset] = []
    for preset in presets:
        selected_node_ids = [node.id for node in preset.hierarchy_nodes]
        allowed_node_ids = filter_governed_hierarchy_node_ids(
            db_session=db_session,
            node_ids=selected_node_ids,
            user=user,
            include_archived=True,
        )
        if set(selected_node_ids) == allowed_node_ids:
            visible.append(preset)
    return visible


def create_connected_knowledge_preset(
    *,
    db_session: Session,
    name: str,
    hierarchy_node_ids: list[int],
    document_ids: list[str],
    description: str | None = None,
    emoji: str | None = None,
    instructions: str | None = None,
    is_default: bool = False,
    is_archived: bool = False,
) -> ProjectConnectedKnowledgePreset:
    preset = ProjectConnectedKnowledgePreset(
        name=name,
        description=description,
        emoji=emoji,
        instructions=instructions,
        is_default=is_default,
        is_archived=is_archived,
    )
    db_session.add(preset)
    db_session.flush()
    preset.hierarchy_nodes = list(
        db_session.scalars(
            select(HierarchyNode).where(HierarchyNode.id.in_(hierarchy_node_ids))
        ).all()
    )
    preset.attached_documents = list(
        db_session.scalars(select(Document).where(Document.id.in_(document_ids))).all()
    )
    db_session.commit()
    db_session.refresh(preset)
    return preset
