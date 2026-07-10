import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql import Select

from onyx.db.enums import ArtifactType
from onyx.db.models import Artifact
from onyx.db.models import ArtifactLibraryItem
from onyx.db.models import ArtifactLibraryItem__User
from onyx.db.models import ArtifactLibraryItem__UserGroup
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.utils import is_fk_violation
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError


class ArtifactLibraryAccess(str, Enum):
    VIEW = "view"
    OWN = "own"


class ArtifactLibraryScope(str, Enum):
    ALL = "all"
    CREATED = "created"
    SHARED = "shared"


def _shared_with_user(user: User) -> ColumnElement[bool]:
    direct = (
        select(ArtifactLibraryItem__User.artifact_library_item_id)
        .where(
            ArtifactLibraryItem__User.artifact_library_item_id
            == ArtifactLibraryItem.id,
            ArtifactLibraryItem__User.user_id == user.id,
        )
        .exists()
    )
    group = (
        select(ArtifactLibraryItem__UserGroup.artifact_library_item_id)
        .join(
            User__UserGroup,
            User__UserGroup.user_group_id
            == ArtifactLibraryItem__UserGroup.user_group_id,
        )
        .where(
            ArtifactLibraryItem__UserGroup.artifact_library_item_id
            == ArtifactLibraryItem.id,
            User__UserGroup.user_id == user.id,
        )
        .exists()
    )
    return or_(ArtifactLibraryItem.published_at.isnot(None), direct, group)


def _base_select() -> Select[tuple[ArtifactLibraryItem]]:
    return select(ArtifactLibraryItem).options(
        selectinload(ArtifactLibraryItem.owner),
        selectinload(ArtifactLibraryItem.versions),
        selectinload(ArtifactLibraryItem.user_shares).selectinload(
            ArtifactLibraryItem__User.user
        ),
        selectinload(ArtifactLibraryItem.group_shares).selectinload(
            ArtifactLibraryItem__UserGroup.user_group
        ),
    )


def list_artifact_library_items(
    *,
    user: User,
    db_session: Session,
    scope: ArtifactLibraryScope = ArtifactLibraryScope.ALL,
    query: str | None = None,
    artifact_type: ArtifactType | None = None,
    pinned: bool | None = None,
    published: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ArtifactLibraryItem]:
    owned = ArtifactLibraryItem.owner_user_id == user.id
    shared = _shared_with_user(user)
    stmt = _base_select()
    if scope == ArtifactLibraryScope.CREATED:
        stmt = stmt.where(owned)
    elif scope == ArtifactLibraryScope.SHARED:
        stmt = stmt.where(~owned, shared)
    else:
        stmt = stmt.where(or_(owned, shared))

    normalized_query = query.strip() if query else ""
    if normalized_query:
        stmt = stmt.where(
            ArtifactLibraryItem.name.icontains(normalized_query, autoescape=True)
        )
    if artifact_type is not None:
        stmt = stmt.where(ArtifactLibraryItem.type == artifact_type)
    if pinned is not None:
        stmt = stmt.where(ArtifactLibraryItem.is_pinned.is_(pinned))
    if published is not None:
        stmt = stmt.where(
            ArtifactLibraryItem.published_at.isnot(None)
            if published
            else ArtifactLibraryItem.published_at.is_(None)
        )

    stmt = (
        stmt.order_by(
            ArtifactLibraryItem.is_pinned.desc(), ArtifactLibraryItem.updated_at.desc()
        )
        .offset(offset)
        .limit(limit)
    )
    return list(db_session.scalars(stmt).unique())


def fetch_artifact_library_item(
    item_id: UUID,
    *,
    user: User,
    db_session: Session,
    access: ArtifactLibraryAccess = ArtifactLibraryAccess.VIEW,
    lock: bool = False,
) -> ArtifactLibraryItem | None:
    stmt = _base_select().where(ArtifactLibraryItem.id == item_id)
    if access == ArtifactLibraryAccess.OWN:
        stmt = stmt.where(ArtifactLibraryItem.owner_user_id == user.id)
    else:
        stmt = stmt.where(
            or_(
                ArtifactLibraryItem.owner_user_id == user.id,
                _shared_with_user(user),
            )
        )
    if lock:
        stmt = stmt.with_for_update()
    return db_session.scalars(stmt).unique().one_or_none()


def create_artifact_library_item(
    *,
    owner_user_id: UUID,
    name: str,
    artifact_type: ArtifactType,
    storage_file_id: str,
    source_path: str,
    mime_type: str,
    size_bytes: int,
    db_session: Session,
) -> ArtifactLibraryItem:
    item = ArtifactLibraryItem(
        owner_user_id=owner_user_id,
        name=name,
        type=artifact_type,
    )
    item.versions.append(
        Artifact(
            session_id=None,
            type=artifact_type,
            path=source_path,
            name=name,
            version_number=1,
            storage_file_id=storage_file_id,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
    )
    db_session.add(item)
    db_session.flush()
    return item


def add_artifact_library_version(
    *,
    item: ArtifactLibraryItem,
    storage_file_id: str,
    source_path: str,
    mime_type: str,
    size_bytes: int,
    db_session: Session,
) -> Artifact:
    latest_version = db_session.scalar(
        select(func.max(Artifact.version_number)).where(
            Artifact.library_item_id == item.id
        )
    )
    version = Artifact(
        session_id=None,
        library_item_id=item.id,
        type=item.type,
        path=source_path,
        name=item.name,
        version_number=(latest_version or 0) + 1,
        storage_file_id=storage_file_id,
        mime_type=mime_type,
        size_bytes=size_bytes,
    )
    db_session.add(version)
    item.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.flush()
    db_session.refresh(item)
    return version


def replace_artifact_library_shares(
    *,
    item: ArtifactLibraryItem,
    user_ids: set[UUID],
    group_ids: set[int],
    db_session: Session,
) -> ArtifactLibraryItem:
    requested_user_ids = user_ids - {item.owner_user_id}
    item.user_shares = [
        ArtifactLibraryItem__User(user_id=value) for value in requested_user_ids
    ]
    item.group_shares = [
        ArtifactLibraryItem__UserGroup(user_group_id=value) for value in group_ids
    ]
    try:
        db_session.flush()
    except IntegrityError as error:
        if is_fk_violation(error):
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT,
                "One or more artifact share targets are unavailable.",
            ) from error
        raise
    return item


def update_artifact_library_item(
    *,
    item: ArtifactLibraryItem,
    name: str | None = None,
    is_pinned: bool | None = None,
    published: bool | None = None,
    db_session: Session,
) -> ArtifactLibraryItem:
    if name is not None:
        item.name = name
    if is_pinned is not None:
        item.is_pinned = is_pinned
    if published is not None:
        item.published_at = (
            datetime.datetime.now(datetime.timezone.utc) if published else None
        )
    item.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.flush()
    return item


def delete_artifact_library_item(
    *, item: ArtifactLibraryItem, db_session: Session
) -> list[str]:
    file_ids = [
        version.storage_file_id
        for version in item.versions
        if version.storage_file_id is not None
    ]
    db_session.delete(item)
    db_session.flush()
    return file_ids
