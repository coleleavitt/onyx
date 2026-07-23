from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from onyx.access.hierarchy_access import get_user_external_group_ids
from onyx.auth.schemas import UserRole
from onyx.configs.constants import DocumentSource
from onyx.db.document_access import get_accessible_documents_by_ids
from onyx.db.enums import ConnectedSourceAccessType
from onyx.db.enums import ConnectedSourceCurationStatus
from onyx.db.enums import ConnectorCredentialPairStatus
from onyx.db.models import ConnectedSourceScope
from onyx.db.models import ConnectedSourceScope__UserGroup
from onyx.db.models import ConnectedSourceScopeExclusion
from onyx.db.models import ConnectorCredentialPair
from onyx.db.models import Document
from onyx.db.models import HierarchyNode
from onyx.db.models import HierarchyNodeByConnectorCredentialPair
from onyx.db.models import IndexAttempt
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
    connector_statuses: tuple[str, ...] = ()

    @property
    def has_connector_backing(self) -> bool:
        return bool(self.connector_statuses)

    @property
    def has_active_connector(self) -> bool:
        active_statuses = {
            ConnectorCredentialPairStatus.SCHEDULED.value,
            ConnectorCredentialPairStatus.INITIAL_INDEXING.value,
            ConnectorCredentialPairStatus.ACTIVE.value,
        }
        return any(status in active_statuses for status in self.connector_statuses)


@dataclass(frozen=True)
class ConnectedSourceScopeMetadata:
    hierarchy_node_id: int
    access_type: ConnectedSourceAccessType
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


def user_bypasses_connected_source_group_policy(user: User | None) -> bool:
    """Admins can manage/use restricted source scopes without group grants.

    Group grants are still meaningful for non-admin users; this bypass only
    skips the `RESTRICTED` scope membership gate. Curation status, exclusions,
    and paused-connector hiding continue to apply normally.
    """
    return user is not None and user.role == UserRole.ADMIN


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
    if scope.access_type == ConnectedSourceAccessType.PUBLIC:
        return True
    allowed_group_ids = {link.user_group_id for link in scope.group_links}
    return bool(allowed_group_ids & user_group_ids)


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


def _status_value(status: object) -> str:
    return getattr(status, "value", str(status))


def _aggregate_index_status(statuses: list[object]) -> str | None:
    if not statuses:
        return None
    priority = {
        "IN_PROGRESS": 0,
        "in_progress": 0,
        "NOT_STARTED": 1,
        "not_started": 1,
        "COMPLETED_WITH_ERRORS": 2,
        "completed_with_errors": 2,
        "FAILED": 3,
        "failed": 3,
        "CANCELED": 4,
        "canceled": 4,
        "INTERRUPTED": 4,
        "interrupted": 4,
        "SUCCESS": 5,
        "success": 5,
    }
    return min(
        (_status_value(status) for status in statuses),
        key=lambda value: priority.get(value, 99),
    )


def _build_metrics_by_node_id(
    db_session: Session,
    nodes: list[HierarchyNode],
) -> dict[int, ConnectedSourceScopeMetrics]:
    if not nodes:
        return {}

    descendants = _descendants_by_node_id(nodes)
    node_ids = [node.id for node in nodes]
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
            .where(Document.parent_hierarchy_node_id.in_(node_ids))
            .group_by(Document.parent_hierarchy_node_id)
        )
    }

    cc_pair_ids_by_node: dict[int, set[int]] = defaultdict(set)
    last_successful_sync_by_cc_pair: dict[int, datetime] = {}
    association_rows = db_session.execute(
        select(
            HierarchyNodeByConnectorCredentialPair.hierarchy_node_id,
            ConnectorCredentialPair.id,
            ConnectorCredentialPair.status,
            ConnectorCredentialPair.last_successful_index_time,
        )
        .join(
            ConnectorCredentialPair,
            (
                ConnectorCredentialPair.connector_id
                == HierarchyNodeByConnectorCredentialPair.connector_id
            )
            & (
                ConnectorCredentialPair.credential_id
                == HierarchyNodeByConnectorCredentialPair.credential_id
            ),
        )
        .where(HierarchyNodeByConnectorCredentialPair.hierarchy_node_id.in_(node_ids))
    ).all()
    cc_pair_status_by_id: dict[int, str] = {}
    for (
        node_id,
        cc_pair_id,
        cc_pair_status,
        last_successful_index_time,
    ) in association_rows:
        cc_pair_ids_by_node[node_id].add(cc_pair_id)
        cc_pair_status_by_id[cc_pair_id] = _status_value(cc_pair_status)
        if last_successful_index_time is not None:
            current = last_successful_sync_by_cc_pair.get(cc_pair_id)
            if current is None or last_successful_index_time > current:
                last_successful_sync_by_cc_pair[cc_pair_id] = last_successful_index_time

    cc_pair_ids = {
        cc_pair_id for ids in cc_pair_ids_by_node.values() for cc_pair_id in ids
    }
    latest_attempt_by_cc_pair: dict[int, IndexAttempt] = {}
    if cc_pair_ids:
        attempts = db_session.scalars(
            select(IndexAttempt)
            .where(IndexAttempt.connector_credential_pair_id.in_(cc_pair_ids))
            .order_by(
                IndexAttempt.connector_credential_pair_id,
                IndexAttempt.time_created.desc(),
                IndexAttempt.id.desc(),
            )
        ).all()
        for attempt in attempts:
            latest_attempt_by_cc_pair.setdefault(
                attempt.connector_credential_pair_id,
                attempt,
            )

    raw_metrics: dict[int, ConnectedSourceScopeMetrics] = {}
    for node in nodes:
        document_count = 0
        chunk_count = 0
        effective_cc_pair_ids: set[int] = set()
        for descendant_id in descendants[node.id]:
            direct_document_count, direct_chunk_count = direct_counts.get(
                descendant_id, (0, 0)
            )
            document_count += direct_document_count
            chunk_count += direct_chunk_count
            effective_cc_pair_ids.update(cc_pair_ids_by_node.get(descendant_id, set()))
        status = _aggregate_index_status(
            [
                latest_attempt_by_cc_pair[cc_pair_id].status
                for cc_pair_id in effective_cc_pair_ids
                if cc_pair_id in latest_attempt_by_cc_pair
            ]
        )
        last_successful_index_time = max(
            (
                last_successful_sync_by_cc_pair[cc_pair_id]
                for cc_pair_id in effective_cc_pair_ids
                if cc_pair_id in last_successful_sync_by_cc_pair
            ),
            default=None,
        )
        raw_metrics[node.id] = ConnectedSourceScopeMetrics(
            document_count=document_count,
            chunk_count=chunk_count,
            latest_index_status=status,
            last_successful_index_time=last_successful_index_time,
            connector_statuses=tuple(
                sorted(
                    {
                        cc_pair_status_by_id[cc_pair_id]
                        for cc_pair_id in effective_cc_pair_ids
                        if cc_pair_id in cc_pair_status_by_id
                    }
                )
            ),
        )

    return raw_metrics


def _evaluate_source_partition(
    *,
    nodes: list[HierarchyNode],
    scopes_by_node_id: dict[int, ConnectedSourceScope],
    metrics_by_node_id: dict[int, ConnectedSourceScopeMetrics],
    user_group_ids: set[int],
    bypass_group_policy: bool,
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
        node_metrics = metrics_by_node_id.get(node.id, ConnectedSourceScopeMetrics())
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

        if (
            node_metrics.has_connector_backing
            and not node_metrics.has_active_connector
            and not include_hidden
        ):
            visible = False
            selectable = False
            denial_reason = "connector_not_active"

        for scope in path_scopes:
            if (
                not bypass_group_policy
                and not _scope_is_allowed_for_groups(scope, user_group_ids)
            ):
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
            scope_metrics = metrics_by_node_id.get(
                scope.hierarchy_node_id,
                ConnectedSourceScopeMetrics(),
            )
            if (
                scope_metrics.has_connector_backing
                and not scope_metrics.has_active_connector
                and not include_hidden
            ):
                visible = False
                selectable = False
                denial_reason = "connector_not_active"
            excluded_ids = {
                link.excluded_hierarchy_node_id for link in scope.excluded_links
            }
            if excluded_ids & path_node_ids:
                visible = False
                selectable = False
                denial_reason = "excluded_by_parent_scope"

        access_type = (
            own_scope.access_type if own_scope else ConnectedSourceAccessType.PUBLIC
        )
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
            access_type=access_type,
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
            metrics=node_metrics,
        )
    return metadata


def build_metadata_for_nodes(
    *,
    db_session: Session,
    nodes: list[HierarchyNode],
    user_group_ids: set[int],
    include_archived: bool,
    include_hidden: bool,
    bypass_group_policy: bool = False,
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
                bypass_group_policy=bypass_group_policy,
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
        bypass_group_policy=user_bypasses_connected_source_group_policy(user),
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
        bypass_group_policy=user_bypasses_connected_source_group_policy(user),
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


def _effective_exclusions_for_selected_node_ids(
    *,
    db_session: Session,
    selected_node_ids: list[int],
) -> set[int]:
    if not selected_node_ids:
        return set()

    source_rows = db_session.execute(
        select(HierarchyNode.id, HierarchyNode.source).where(
            HierarchyNode.id.in_(selected_node_ids)
        )
    ).all()
    selected_ids_by_source: dict[DocumentSource, set[int]] = defaultdict(set)
    for node_id, source in source_rows:
        selected_ids_by_source[source].add(node_id)

    if not selected_ids_by_source:
        return set()

    nodes_by_source: dict[DocumentSource, list[HierarchyNode]] = defaultdict(list)
    all_source_nodes = list(
        db_session.scalars(
            select(HierarchyNode).where(
                HierarchyNode.source.in_(set(selected_ids_by_source))
            )
        ).all()
    )
    for node in all_source_nodes:
        nodes_by_source[node.source].append(node)

    scopes_by_source = _load_scopes_by_source(db_session, set(selected_ids_by_source))
    exclusions: set[int] = set()
    for source, selected_ids in selected_ids_by_source.items():
        paths_by_node_id = _node_paths(nodes_by_source[source])
        source_scopes = scopes_by_source.get(source, {})
        for selected_id in selected_ids:
            for ancestor_id in paths_by_node_id.get(selected_id, []):
                scope = source_scopes.get(ancestor_id)
                if not scope:
                    continue
                exclusions.update(
                    link.excluded_hierarchy_node_id for link in scope.excluded_links
                )
    return exclusions


def get_project_connected_excluded_hierarchy_node_ids(
    *,
    project_id: int,
    db_session: Session,
) -> list[int]:
    selected_node_ids = list(
        db_session.scalars(
            select(Project__HierarchyNode.hierarchy_node_id).where(
                Project__HierarchyNode.project_id == project_id
            )
        ).all()
    )
    return sorted(
        _effective_exclusions_for_selected_node_ids(
            db_session=db_session,
            selected_node_ids=selected_node_ids,
        )
    )


def upsert_connected_source_scope(
    *,
    db_session: Session,
    hierarchy_node_id: int,
    curation_status: ConnectedSourceCurationStatus,
    group_ids: list[int],
    access_type: ConnectedSourceAccessType | None = None,
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
    scope.access_type = (
        access_type
        if access_type is not None
        else (
            ConnectedSourceAccessType.RESTRICTED
            if group_ids
            else ConnectedSourceAccessType.PUBLIC
        )
    )
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
        if set(selected_node_ids) != allowed_node_ids:
            continue

        selected_document_ids = [document.id for document in preset.attached_documents]
        if selected_document_ids:
            external_group_ids = get_user_external_group_ids(db_session, user)
            accessible_documents = get_accessible_documents_by_ids(
                db_session=db_session,
                document_ids=selected_document_ids,
                user_email=user.email,
                external_group_ids=external_group_ids,
            )
            accessible_document_ids = {document.id for document in accessible_documents}
            governed_document_ids = filter_governed_document_ids(
                db_session=db_session,
                document_ids=selected_document_ids,
                user=user,
            )
            if set(selected_document_ids) != accessible_document_ids:
                continue
            if set(selected_document_ids) != governed_document_ids:
                continue

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
