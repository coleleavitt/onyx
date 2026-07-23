import datetime
import uuid
from enum import Enum
from typing import List
from typing import Mapping
from typing import TypeVar
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from sqlalchemy import ColumnElement
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session
from starlette.background import BackgroundTasks

from onyx.access.hierarchy_access import get_user_external_group_ids
from onyx.configs.app_configs import DISABLE_VECTOR_DB
from onyx.configs.constants import CELERY_USER_FILE_PROCESSING_TASK_EXPIRES
from onyx.configs.constants import FileOrigin
from onyx.configs.constants import OnyxCeleryPriority
from onyx.configs.constants import OnyxCeleryQueues
from onyx.configs.constants import OnyxCeleryTask
from onyx.db.document_access import get_accessible_documents_by_ids
from onyx.db.enums import ProjectAccessLevel
from onyx.db.enums import ProjectJoinRequestStatus
from onyx.db.enums import ProjectSharePermission
from onyx.db.enums import UserFileStatus
from onyx.db.hierarchy import filter_accessible_hierarchy_node_ids
from onyx.db.models import Document
from onyx.db.models import HierarchyNode
from onyx.db.models import Project__Document
from onyx.db.models import Project__HierarchyNode
from onyx.db.models import Project__User
from onyx.db.models import Project__UserFile
from onyx.db.models import Project__UserGroup
from onyx.db.models import ProjectJoinRequest
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.models import UserFile
from onyx.db.models import UserProject
from onyx.db.models import UserProject__UserState
from onyx.db.utils import is_fk_violation
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.documents.connector import upload_files
from onyx.server.features.projects.projects_file_utils import categorize_uploaded_files
from onyx.server.features.projects.projects_file_utils import RejectedFile
from onyx.utils.logger import setup_logger
from shared_configs.contextvars import get_current_tenant_id

logger = setup_logger()

T = TypeVar("T")


class ProjectAccessPolicy(str, Enum):
    VIEW = "view"
    EDIT = "edit"
    OWN = "own"


def _is_project_shared_with_user(
    user: User,
    permission: ProjectSharePermission | None = None,
) -> ColumnElement[bool]:
    stmt = (
        select(Project__User.project_id)
        .where(Project__User.project_id == UserProject.id)
        .where(Project__User.user_id == user.id)
    )
    if permission is not None:
        stmt = stmt.where(Project__User.permission == permission)
    return stmt.exists()


def _is_project_shared_with_user_group(
    user: User,
    permission: ProjectSharePermission | None = None,
) -> ColumnElement[bool]:
    stmt = (
        select(Project__UserGroup.project_id)
        .join(
            User__UserGroup,
            User__UserGroup.user_group_id == Project__UserGroup.user_group_id,
        )
        .where(Project__UserGroup.project_id == UserProject.id)
        .where(User__UserGroup.user_id == user.id)
    )
    if permission is not None:
        stmt = stmt.where(Project__UserGroup.permission == permission)
    return stmt.exists()


def _project_base_select() -> Select[tuple[UserProject]]:
    return select(UserProject).options(
        selectinload(UserProject.user),
        selectinload(UserProject.user_shares).selectinload(Project__User.user),
        selectinload(UserProject.group_shares).selectinload(
            Project__UserGroup.user_group
        ),
        selectinload(UserProject.join_requests).selectinload(
            ProjectJoinRequest.requester
        ),
        selectinload(UserProject.chat_sessions),
        selectinload(UserProject.hierarchy_nodes),
        selectinload(UserProject.attached_documents).selectinload(
            Document.parent_hierarchy_node
        ),
    )


def _project_select_for_user(
    *, user: User, policy: ProjectAccessPolicy
) -> Select[tuple[UserProject]]:
    stmt = _project_base_select()
    if user.id is None:
        return stmt

    owned = UserProject.user_id == user.id
    if policy == ProjectAccessPolicy.OWN:
        return stmt.where(owned)

    shared_with_user = _is_project_shared_with_user(user)
    shared_with_group = _is_project_shared_with_user_group(user)
    if policy == ProjectAccessPolicy.VIEW:
        return stmt.where(
            or_(
                owned,
                UserProject.organization_permission.isnot(None),
                shared_with_user,
                shared_with_group,
            )
        )

    if policy == ProjectAccessPolicy.EDIT:
        return stmt.where(
            or_(
                owned,
                UserProject.organization_permission == ProjectSharePermission.EDITOR,
                _is_project_shared_with_user(user, ProjectSharePermission.EDITOR),
                _is_project_shared_with_user_group(user, ProjectSharePermission.EDITOR),
            )
        )

    raise ValueError(f"Unknown project access policy: {policy}")


def list_projects_for_user(*, user: User, db_session: Session) -> list[UserProject]:
    stmt = _project_select_for_user(
        user=user, policy=ProjectAccessPolicy.VIEW
    ).order_by(UserProject.created_at.desc())
    return list(db_session.scalars(stmt).unique())


def compute_project_last_activity(project: UserProject) -> datetime.datetime | None:
    """Most recent non-deleted chat activity for the project, or None.

    Read from the eagerly-loaded chat_sessions relationship so it costs no extra
    query. UserProject has no updated_at column; the API surfaces this as the
    project's last-activity time and the client falls back to created_at on None.
    """
    return max(
        (chat.time_updated for chat in project.chat_sessions if not chat.deleted),
        default=None,
    )


def get_pinned_project_ids(*, user: User, db_session: Session) -> set[int]:
    if user.id is None:
        return set()
    rows = db_session.scalars(
        select(UserProject__UserState.project_id).where(
            UserProject__UserState.user_id == user.id,
            UserProject__UserState.is_pinned.is_(True),
        )
    ).all()
    return set(rows)


def set_project_pinned(
    *, project_id: int, user: User, pinned: bool, db_session: Session
) -> None:
    if user.id is None:
        return
    state = db_session.get(UserProject__UserState, (project_id, user.id))
    if state is None:
        state = UserProject__UserState(
            project_id=project_id, user_id=user.id, is_pinned=pinned
        )
        db_session.add(state)
    else:
        state.is_pinned = pinned


def fetch_project_for_user(
    project_id: int,
    *,
    user: User,
    db_session: Session,
    policy: ProjectAccessPolicy,
) -> UserProject | None:
    stmt = _project_select_for_user(user=user, policy=policy).where(
        UserProject.id == project_id
    )
    return db_session.scalars(stmt).unique().one_or_none()


def fetch_project_by_id(
    project_id: int,
    *,
    db_session: Session,
) -> UserProject | None:
    stmt = _project_base_select().where(UserProject.id == project_id)
    return db_session.scalars(stmt).unique().one_or_none()


def project_exists(
    project_id: int,
    *,
    db_session: Session,
) -> bool:
    return (
        db_session.scalar(select(UserProject.id).where(UserProject.id == project_id))
        is not None
    )


def user_has_project_access(
    project_id: int,
    *,
    user: User,
    db_session: Session,
    policy: ProjectAccessPolicy,
) -> bool:
    if user.id is None:
        return project_exists(project_id, db_session=db_session)

    owned = UserProject.user_id == user.id
    stmt = select(UserProject.id).where(UserProject.id == project_id)
    if policy == ProjectAccessPolicy.OWN:
        stmt = stmt.where(owned)
    elif policy == ProjectAccessPolicy.VIEW:
        stmt = stmt.where(
            or_(
                owned,
                UserProject.organization_permission.isnot(None),
                _is_project_shared_with_user(user),
                _is_project_shared_with_user_group(user),
            )
        )
    elif policy == ProjectAccessPolicy.EDIT:
        stmt = stmt.where(
            or_(
                owned,
                UserProject.organization_permission == ProjectSharePermission.EDITOR,
                _is_project_shared_with_user(user, ProjectSharePermission.EDITOR),
                _is_project_shared_with_user_group(user, ProjectSharePermission.EDITOR),
            )
        )
    else:
        raise ValueError(f"Unknown project access policy: {policy}")

    return db_session.scalar(stmt.limit(1)) is not None


def fetch_pending_project_join_request_for_user(
    project_id: int,
    *,
    requester: User,
    db_session: Session,
) -> ProjectJoinRequest | None:
    if requester.id is None:
        return None
    return db_session.scalar(
        select(ProjectJoinRequest).where(
            ProjectJoinRequest.project_id == project_id,
            ProjectJoinRequest.requester_user_id == requester.id,
            ProjectJoinRequest.status == ProjectJoinRequestStatus.PENDING,
        )
    )


def fetch_latest_project_join_request_for_user(
    project_id: int,
    *,
    requester: User,
    db_session: Session,
) -> ProjectJoinRequest | None:
    if requester.id is None:
        return None
    return db_session.scalar(
        select(ProjectJoinRequest)
        .where(
            ProjectJoinRequest.project_id == project_id,
            ProjectJoinRequest.requester_user_id == requester.id,
        )
        .order_by(ProjectJoinRequest.created_at.desc(), ProjectJoinRequest.id.desc())
        .limit(1)
    )


def get_project_access_level(
    project: UserProject,
    *,
    user: User,
    db_session: Session,
) -> ProjectAccessLevel:
    if user.id is None or project.user_id == user.id:
        return ProjectAccessLevel.OWNER

    editable = fetch_project_for_user(
        project.id,
        user=user,
        db_session=db_session,
        policy=ProjectAccessPolicy.EDIT,
    )
    return (
        ProjectAccessLevel.EDITOR if editable is not None else ProjectAccessLevel.VIEWER
    )


def _dedupe_preserving_order(values: list[T]) -> list[T]:
    seen: set[T] = set()
    result: list[T] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def fetch_project_connected_knowledge(
    *,
    project_id: int,
    db_session: Session,
) -> tuple[list[Document], list[HierarchyNode]]:
    project = fetch_project_by_id(project_id, db_session=db_session)
    if project is None:
        return [], []
    documents = sorted(project.attached_documents, key=lambda doc: doc.semantic_id)
    hierarchy_nodes = sorted(project.hierarchy_nodes, key=lambda node: node.display_name)
    return documents, hierarchy_nodes


def replace_project_connected_knowledge(
    *,
    project: UserProject,
    document_ids: list[str],
    hierarchy_node_ids: list[int],
    user: User,
    db_session: Session,
) -> UserProject:
    requested_document_ids = _dedupe_preserving_order(document_ids)
    requested_node_ids = _dedupe_preserving_order(hierarchy_node_ids)

    external_group_ids = get_user_external_group_ids(db_session, user)

    documents: list[Document] = []
    if requested_document_ids:
        documents = get_accessible_documents_by_ids(
            db_session=db_session,
            document_ids=requested_document_ids,
            user_email=user.email,
            external_group_ids=external_group_ids,
        )
        accessible_document_ids = {document.id for document in documents}
        if set(requested_document_ids) - accessible_document_ids:
            raise OnyxError(
                OnyxErrorCode.INSUFFICIENT_PERMISSIONS,
                "Cannot attach documents you do not have access to.",
            )

    hierarchy_nodes: list[HierarchyNode] = []
    if requested_node_ids:
        hierarchy_nodes = (
            db_session.query(HierarchyNode)
            .filter(HierarchyNode.id.in_(requested_node_ids))
            .all()
        )
        existing_node_ids = {node.id for node in hierarchy_nodes}
        if set(requested_node_ids) - existing_node_ids:
            raise OnyxError(OnyxErrorCode.NOT_FOUND, "Hierarchy node not found.")
        accessible_node_ids = filter_accessible_hierarchy_node_ids(
            db_session,
            requested_node_ids,
            user.email,
            external_group_ids,
        )
        if set(requested_node_ids) - accessible_node_ids:
            raise OnyxError(
                OnyxErrorCode.INSUFFICIENT_PERMISSIONS,
                "Cannot attach hierarchy nodes you do not have access to.",
            )

    project.attached_documents.clear()
    project.attached_documents = documents
    project.hierarchy_nodes.clear()
    project.hierarchy_nodes = hierarchy_nodes
    db_session.commit()
    db_session.refresh(project)
    return project


def get_project_connected_document_ids(
    *,
    project_id: int,
    db_session: Session,
) -> list[str]:
    return list(
        db_session.scalars(
            select(Project__Document.document_id).where(
                Project__Document.project_id == project_id
            )
        ).all()
    )


def get_project_connected_hierarchy_node_ids(
    *,
    project_id: int,
    db_session: Session,
) -> list[int]:
    return list(
        db_session.scalars(
            select(Project__HierarchyNode.hierarchy_node_id).where(
                Project__HierarchyNode.project_id == project_id
            )
        ).all()
    )


def replace_project_shares(
    *,
    project: UserProject,
    organization_permission: ProjectSharePermission | None,
    user_shares: Mapping[UUID, ProjectSharePermission],
    group_shares: Mapping[int, ProjectSharePermission],
    db_session: Session,
) -> UserProject:
    requested_user_shares = dict(user_shares)
    if project.user_id is not None:
        requested_user_shares.pop(project.user_id, None)

    project.organization_permission = organization_permission
    project.user_shares = [
        Project__User(user_id=user_id, permission=permission)
        for user_id, permission in requested_user_shares.items()
    ]
    project.group_shares = [
        Project__UserGroup(user_group_id=group_id, permission=permission)
        for group_id, permission in group_shares.items()
    ]
    try:
        db_session.flush()
    except IntegrityError as e:
        if is_fk_violation(e):
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT,
                "One or more project share targets are unavailable.",
            ) from e
        raise
    return project


def create_or_reset_project_join_request(
    *,
    project: UserProject,
    requester: User,
    requested_permission: ProjectSharePermission,
    db_session: Session,
) -> ProjectJoinRequest:
    if requester.id is None:
        raise OnyxError(OnyxErrorCode.UNAUTHENTICATED)
    if project.user_id == requester.id:
        raise OnyxError(OnyxErrorCode.CONFLICT, "Project owners already have access.")

    existing = db_session.scalar(
        select(ProjectJoinRequest).where(
            ProjectJoinRequest.project_id == project.id,
            ProjectJoinRequest.requester_user_id == requester.id,
        )
    )
    if existing is None:
        existing = ProjectJoinRequest(
            project_id=project.id,
            requester_user_id=requester.id,
            requested_permission=requested_permission,
        )
        db_session.add(existing)
    else:
        existing.requested_permission = requested_permission
        existing.status = ProjectJoinRequestStatus.PENDING
        existing.resolution_comment = None
        existing.resolved_at = None
    db_session.flush()
    return existing


def resolve_project_join_request(
    *,
    project: UserProject,
    request_id: int,
    approve: bool,
    resolution_comment: str | None,
    db_session: Session,
) -> ProjectJoinRequest:
    join_request = db_session.scalar(
        select(ProjectJoinRequest).where(
            ProjectJoinRequest.id == request_id,
            ProjectJoinRequest.project_id == project.id,
        )
    )
    if join_request is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Project access request not found.")
    if join_request.status != ProjectJoinRequestStatus.PENDING:
        raise OnyxError(
            OnyxErrorCode.CONFLICT, "Project access request has already been resolved."
        )

    join_request.status = (
        ProjectJoinRequestStatus.APPROVED
        if approve
        else ProjectJoinRequestStatus.DENIED
    )
    join_request.resolution_comment = resolution_comment
    join_request.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    if approve:
        existing_share = db_session.scalar(
            select(Project__User).where(
                Project__User.project_id == project.id,
                Project__User.user_id == join_request.requester_user_id,
            )
        )
        if existing_share is None:
            db_session.add(
                Project__User(
                    project_id=project.id,
                    user_id=join_request.requester_user_id,
                    permission=join_request.requested_permission,
                )
            )
        else:
            existing_share.permission = join_request.requested_permission
    db_session.flush()
    return join_request


def cancel_project_join_request(
    *,
    project: UserProject,
    requester: User,
    db_session: Session,
) -> None:
    if requester.id is None:
        raise OnyxError(OnyxErrorCode.UNAUTHENTICATED)
    join_request = db_session.scalar(
        select(ProjectJoinRequest).where(
            ProjectJoinRequest.project_id == project.id,
            ProjectJoinRequest.requester_user_id == requester.id,
            ProjectJoinRequest.status == ProjectJoinRequestStatus.PENDING,
        )
    )
    if join_request is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Project access request not found.")
    db_session.delete(join_request)
    db_session.flush()


class CategorizedFilesResult(BaseModel):
    user_files: list[UserFile]
    rejected_files: list[RejectedFile]
    id_to_temp_id: dict[str, str]
    # Filenames that should be stored but not indexed.
    skip_indexing_filenames: set[str] = Field(default_factory=set)
    # Allow SQLAlchemy ORM models inside this result container
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def indexable_files(self) -> list[UserFile]:
        return [
            uf
            for uf in self.user_files
            if (uf.name or "") not in self.skip_indexing_filenames
        ]


def build_hashed_file_key(file: UploadFile) -> str:
    name_prefix = (file.filename or "")[:50]
    return f"{file.size}|{name_prefix}"


def create_user_files(
    files: List[UploadFile],
    project_id: int | None,
    user: User,
    db_session: Session,
    link_url: str | None = None,
    temp_id_map: dict[str, str] | None = None,
) -> CategorizedFilesResult:
    # Categorize the files
    categorized_files = categorize_uploaded_files(files, db_session)
    # NOTE: At the moment, zip metadata is not used for user files.
    # Should revisit to decide whether this should be a feature.
    upload_response = upload_files(categorized_files.acceptable, FileOrigin.USER_FILE)
    user_files = []
    rejected_files = categorized_files.rejected
    id_to_temp_id: dict[str, str] = {}
    # Pair returned storage paths with the same set of acceptable files we uploaded
    for file_path, file in zip(
        upload_response.file_paths, categorized_files.acceptable
    ):
        new_id = uuid.uuid4()
        new_temp_id = (
            temp_id_map.get(build_hashed_file_key(file)) if temp_id_map else None
        )
        if new_temp_id is not None:
            id_to_temp_id[str(new_id)] = new_temp_id
        should_skip = (file.filename or "") in categorized_files.skip_indexing
        new_file = UserFile(
            id=new_id,
            user_id=user.id,
            file_id=file_path,
            name=file.filename,
            token_count=categorized_files.acceptable_file_to_token_count[
                file.filename or ""
            ],
            link_url=link_url,
            content_type=file.content_type,
            file_type=file.content_type,
            status=UserFileStatus.SKIPPED if should_skip else UserFileStatus.PROCESSING,
            last_accessed_at=datetime.datetime.now(datetime.timezone.utc),
        )
        # Persist the UserFile first to satisfy FK constraints for association table
        db_session.add(new_file)
        db_session.flush()
        if project_id:
            project_to_user_file = Project__UserFile(
                project_id=project_id,
                user_file_id=new_file.id,
            )
            db_session.add(project_to_user_file)
        user_files.append(new_file)
    db_session.commit()
    return CategorizedFilesResult(
        user_files=user_files,
        rejected_files=rejected_files,
        id_to_temp_id=id_to_temp_id,
        skip_indexing_filenames=categorized_files.skip_indexing,
    )


def upload_files_to_user_files_with_indexing(
    files: List[UploadFile],
    project_id: int | None,
    user: User,
    temp_id_map: dict[str, str] | None,
    db_session: Session,
    background_tasks: BackgroundTasks | None = None,
) -> CategorizedFilesResult:
    if project_id is not None and user is not None:
        if not check_project_access(
            project_id,
            user.id,
            db_session,
            policy=ProjectAccessPolicy.EDIT,
        ):
            raise OnyxError(OnyxErrorCode.NOT_FOUND, "Project not found.")

    categorized_files_result = create_user_files(
        files,
        project_id,
        user,
        db_session,
        temp_id_map=temp_id_map,
    )
    user_files = categorized_files_result.user_files
    rejected_files = categorized_files_result.rejected_files
    id_to_temp_id = categorized_files_result.id_to_temp_id
    indexable_files = categorized_files_result.indexable_files
    # Trigger per-file processing immediately for the current tenant
    tenant_id = get_current_tenant_id()
    for rejected_file in rejected_files:
        logger.warning(
            "File %s rejected for %s", rejected_file.filename, rejected_file.reason
        )

    if DISABLE_VECTOR_DB and background_tasks is not None:
        from onyx.background.task_utils import drain_processing_loop

        background_tasks.add_task(drain_processing_loop, tenant_id)
        for user_file in indexable_files:
            logger.info(
                "Queued in-process processing for user_file_id=%s", user_file.id
            )
    else:
        from onyx.background.celery.versioned_apps.client import app as client_app

        for user_file in indexable_files:
            task = client_app.send_task(
                OnyxCeleryTask.PROCESS_SINGLE_USER_FILE,
                kwargs={"user_file_id": user_file.id, "tenant_id": tenant_id},
                queue=OnyxCeleryQueues.USER_FILE_PROCESSING,
                priority=OnyxCeleryPriority.HIGH,
                expires=CELERY_USER_FILE_PROCESSING_TASK_EXPIRES,
            )
            logger.info(
                "Triggered indexing for user_file_id=%s with task_id=%s",
                user_file.id,
                task.id,
            )

    return CategorizedFilesResult(
        user_files=user_files,
        rejected_files=rejected_files,
        id_to_temp_id=id_to_temp_id,
        skip_indexing_filenames=categorized_files_result.skip_indexing_filenames,
    )


def check_project_ownership(
    project_id: int, user_id: UUID | None, db_session: Session
) -> bool:
    # In no-auth mode, all projects are accessible
    if user_id is None:
        # Verify project exists
        return (
            db_session.query(UserProject).filter(UserProject.id == project_id).first()
            is not None
        )

    return (
        db_session.query(UserProject)
        .filter(UserProject.id == project_id, UserProject.user_id == user_id)
        .first()
        is not None
    )


def check_project_access(
    project_id: int,
    user_id: UUID | None,
    db_session: Session,
    *,
    policy: ProjectAccessPolicy = ProjectAccessPolicy.VIEW,
) -> bool:
    if user_id is None:
        return db_session.get(UserProject, project_id) is not None
    user = db_session.get(User, user_id)
    if user is None:
        return False
    return user_has_project_access(
        project_id,
        user=user,
        db_session=db_session,
        policy=policy,
    )


def get_user_files_from_project(
    project_id: int, user_id: UUID | None, db_session: Session
) -> list[UserFile]:
    if not check_project_access(project_id, user_id, db_session):
        return []

    return (
        db_session.query(UserFile)
        .join(Project__UserFile)
        .filter(Project__UserFile.project_id == project_id)
        .all()
    )


def get_project_instructions(db_session: Session, project_id: int | None) -> str | None:
    """Return the project's instruction text from the project, else None.

    Safe helper that swallows DB errors and returns None on any failure.
    """
    if not project_id:
        return None
    try:
        project = (
            db_session.query(UserProject)
            .filter(UserProject.id == project_id)
            .one_or_none()
        )
        if not project or not project.instructions:
            return None
        instructions = project.instructions.strip()
        return instructions or None
    except Exception:
        return None


def get_project_token_count(
    project_id: int | None,
    user_id: UUID | None,
    db_session: Session,
) -> int:
    """Return sum of token_count for all user files in the given project.

    If project_id is None, returns 0.
    """
    if project_id is None:
        return 0
    if not check_project_access(project_id, user_id, db_session):
        return 0

    total_tokens = (
        db_session.query(func.coalesce(func.sum(UserFile.token_count), 0))
        .filter(
            UserFile.projects.any(id=project_id),
        )
        .scalar()
        or 0
    )

    return int(total_tokens)
