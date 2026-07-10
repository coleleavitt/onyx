import io
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from onyx.auth.permissions import require_permission
from onyx.configs.constants import FileOrigin
from onyx.db.artifact_library import add_artifact_library_version
from onyx.db.artifact_library import ArtifactLibraryAccess
from onyx.db.artifact_library import ArtifactLibraryScope
from onyx.db.artifact_library import create_artifact_library_item
from onyx.db.artifact_library import delete_artifact_library_item
from onyx.db.artifact_library import fetch_artifact_library_item
from onyx.db.artifact_library import list_artifact_library_items
from onyx.db.artifact_library import replace_artifact_library_shares
from onyx.db.artifact_library import update_artifact_library_item
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import ArtifactType
from onyx.db.enums import Permission
from onyx.db.models import ArtifactLibraryItem
from onyx.db.models import User
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.file_store.file_store import FileStore
from onyx.file_store.file_store import get_default_file_store
from onyx.server.features.build.artifact_library.models import ArtifactLibraryBulkAction
from onyx.server.features.build.artifact_library.models import (
    ArtifactLibraryBulkRequest,
)
from onyx.server.features.build.artifact_library.models import (
    ArtifactLibraryBulkResponse,
)
from onyx.server.features.build.artifact_library.models import (
    ArtifactLibraryImportRequest,
)
from onyx.server.features.build.artifact_library.models import (
    ArtifactLibraryItemSnapshot,
)
from onyx.server.features.build.artifact_library.models import (
    ArtifactLibraryShareRequest,
)
from onyx.server.features.build.artifact_library.models import (
    ArtifactLibraryUpdateRequest,
)
from onyx.server.features.build.artifact_library.service import (
    ARTIFACT_LIBRARY_MAX_BYTES,
)
from onyx.server.features.build.artifact_library.service import infer_artifact_type
from onyx.server.features.build.artifact_library.service import normalize_artifact_name
from onyx.server.features.build.session.manager import SessionManager
from onyx.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(prefix="/artifact-library")


def _user_id(user: User) -> UUID:
    if user.id is None:
        raise OnyxError(OnyxErrorCode.UNAUTHENTICATED)
    return user.id


def _snapshot(item: ArtifactLibraryItem, user: User) -> ArtifactLibraryItemSnapshot:
    return ArtifactLibraryItemSnapshot.from_model(
        item, requesting_user_id=_user_id(user)
    )


def _owned_item(
    item_id: UUID, *, user: User, db_session: Session, lock: bool = False
) -> ArtifactLibraryItem:
    item = fetch_artifact_library_item(
        item_id,
        user=user,
        db_session=db_session,
        access=ArtifactLibraryAccess.OWN,
        lock=lock,
    )
    if item is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Artifact not found.")
    return item


def _visible_item(
    item_id: UUID, *, user: User, db_session: Session
) -> ArtifactLibraryItem:
    item = fetch_artifact_library_item(
        item_id,
        user=user,
        db_session=db_session,
        access=ArtifactLibraryAccess.VIEW,
    )
    if item is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Artifact not found.")
    return item


def _read_source(
    request: ArtifactLibraryImportRequest,
    *,
    user: User,
    db_session: Session,
) -> tuple[bytes, str, str, bool]:
    try:
        result = SessionManager(db_session).export_artifact_source(
            request.session_id, _user_id(user), request.path
        )
    except ValueError as error:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(error)) from error
    if result is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Artifact source not found.")
    content, mime_type, filename, is_directory = result
    if len(content) > ARTIFACT_LIBRARY_MAX_BYTES:
        raise OnyxError(
            OnyxErrorCode.PAYLOAD_TOO_LARGE,
            "Artifacts saved to the library must be 100 MB or smaller.",
        )
    return content, mime_type, filename, is_directory


def _save_source_blob(
    *,
    content: bytes,
    filename: str,
    mime_type: str,
    request: ArtifactLibraryImportRequest,
    file_store: FileStore,
) -> str:
    return file_store.save_file(
        content=io.BytesIO(content),
        display_name=filename,
        file_origin=FileOrigin.OTHER,
        file_type=mime_type,
        file_metadata={
            "feature": "artifact_library",
            "source_session_id": str(request.session_id),
            "source_path": request.path,
        },
    )


def _delete_blobs(file_ids: list[str], file_store: FileStore) -> None:
    for file_id in file_ids:
        try:
            file_store.delete_file(file_id, error_on_missing=False)
        except Exception:
            logger.exception("Failed to delete artifact library blob %s", file_id)


@router.get("")
def list_library_items(
    scope: ArtifactLibraryScope = ArtifactLibraryScope.ALL,
    query: str | None = Query(default=None, max_length=255),
    artifact_type: ArtifactType | None = None,
    pinned: bool | None = None,
    published: bool | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[ArtifactLibraryItemSnapshot]:
    items = list_artifact_library_items(
        user=user,
        db_session=db_session,
        scope=scope,
        query=query,
        artifact_type=artifact_type,
        pinned=pinned,
        published=published,
        limit=limit,
        offset=offset,
    )
    return [_snapshot(item, user) for item in items]


@router.post("")
def save_library_item(
    request: ArtifactLibraryImportRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ArtifactLibraryItemSnapshot:
    content, mime_type, filename, is_directory = _read_source(
        request, user=user, db_session=db_session
    )
    try:
        name = normalize_artifact_name(request.name, filename)
    except ValueError as error:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(error)) from error
    artifact_type = infer_artifact_type(
        filename=filename,
        source_path=request.path,
        is_directory=is_directory,
    )
    file_store = get_default_file_store()
    storage_file_id = _save_source_blob(
        content=content,
        filename=filename,
        mime_type=mime_type,
        request=request,
        file_store=file_store,
    )
    try:
        item = create_artifact_library_item(
            owner_user_id=_user_id(user),
            name=name,
            artifact_type=artifact_type,
            storage_file_id=storage_file_id,
            source_path=request.path,
            mime_type=mime_type,
            size_bytes=len(content),
            db_session=db_session,
        )
        db_session.commit()
        refreshed = fetch_artifact_library_item(
            item.id, user=user, db_session=db_session
        )
        if refreshed is None:
            raise RuntimeError("Created artifact could not be loaded")
        return _snapshot(refreshed, user)
    except Exception:
        db_session.rollback()
        _delete_blobs([storage_file_id], file_store)
        raise


@router.post("/bulk")
def bulk_update_library_items(
    request: ArtifactLibraryBulkRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ArtifactLibraryBulkResponse:
    items = [
        _owned_item(item_id, user=user, db_session=db_session)
        for item_id in dict.fromkeys(request.item_ids)
    ]
    file_ids: list[str] = []
    for item in items:
        if request.action == ArtifactLibraryBulkAction.DELETE:
            file_ids.extend(
                delete_artifact_library_item(item=item, db_session=db_session)
            )
        elif request.action == ArtifactLibraryBulkAction.PIN:
            update_artifact_library_item(
                item=item, is_pinned=True, db_session=db_session
            )
        elif request.action == ArtifactLibraryBulkAction.UNPIN:
            update_artifact_library_item(
                item=item, is_pinned=False, db_session=db_session
            )
        elif request.action == ArtifactLibraryBulkAction.PUBLISH:
            update_artifact_library_item(
                item=item, published=True, db_session=db_session
            )
        else:
            update_artifact_library_item(
                item=item, published=False, db_session=db_session
            )
    db_session.commit()
    _delete_blobs(file_ids, get_default_file_store())
    return ArtifactLibraryBulkResponse(affected=len(items))


@router.get("/{item_id}")
def get_library_item(
    item_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ArtifactLibraryItemSnapshot:
    return _snapshot(_visible_item(item_id, user=user, db_session=db_session), user)


@router.patch("/{item_id}")
def update_library_item(
    item_id: UUID,
    request: ArtifactLibraryUpdateRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ArtifactLibraryItemSnapshot:
    item = _owned_item(item_id, user=user, db_session=db_session)
    name: str | None = None
    if request.name is not None:
        try:
            name = normalize_artifact_name(request.name, item.name)
        except ValueError as error:
            raise OnyxError(OnyxErrorCode.INVALID_INPUT, str(error)) from error
    update_artifact_library_item(
        item=item,
        name=name,
        is_pinned=request.is_pinned,
        published=request.published,
        db_session=db_session,
    )
    db_session.commit()
    refreshed = _owned_item(item_id, user=user, db_session=db_session)
    return _snapshot(refreshed, user)


@router.put("/{item_id}/shares")
def update_library_item_shares(
    item_id: UUID,
    request: ArtifactLibraryShareRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ArtifactLibraryItemSnapshot:
    item = _owned_item(item_id, user=user, db_session=db_session)
    replace_artifact_library_shares(
        item=item,
        user_ids=set(request.user_ids),
        group_ids=set(request.group_ids),
        db_session=db_session,
    )
    db_session.commit()
    return _snapshot(_owned_item(item_id, user=user, db_session=db_session), user)


@router.post("/{item_id}/versions")
def save_library_item_version(
    item_id: UUID,
    request: ArtifactLibraryImportRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> ArtifactLibraryItemSnapshot:
    item = _owned_item(item_id, user=user, db_session=db_session, lock=True)
    content, mime_type, filename, is_directory = _read_source(
        request, user=user, db_session=db_session
    )
    inferred_type = infer_artifact_type(
        filename=filename,
        source_path=request.path,
        is_directory=is_directory,
    )
    if inferred_type != item.type:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"This version is {inferred_type.value}; expected {item.type.value}.",
        )
    file_store = get_default_file_store()
    storage_file_id = _save_source_blob(
        content=content,
        filename=filename,
        mime_type=mime_type,
        request=request,
        file_store=file_store,
    )
    try:
        add_artifact_library_version(
            item=item,
            storage_file_id=storage_file_id,
            source_path=request.path,
            mime_type=mime_type,
            size_bytes=len(content),
            db_session=db_session,
        )
        db_session.commit()
        return _snapshot(_owned_item(item_id, user=user, db_session=db_session), user)
    except Exception:
        db_session.rollback()
        _delete_blobs([storage_file_id], file_store)
        raise


@router.get("/{item_id}/versions/{version_number}/download")
def download_library_item_version(
    item_id: UUID,
    version_number: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> StreamingResponse:
    item = _visible_item(item_id, user=user, db_session=db_session)
    version = next(
        (
            candidate
            for candidate in item.versions
            if candidate.version_number == version_number
        ),
        None,
    )
    if version is None or version.storage_file_id is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Artifact version not found.")
    file_io = get_default_file_store().read_file(
        version.storage_file_id, use_tempfile=True
    )
    encoded_name = quote(version.name, safe="")
    return StreamingResponse(
        file_io,
        media_type=version.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
        background=BackgroundTask(file_io.close),
    )


@router.delete("/{item_id}")
def delete_library_item(
    item_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    item = _owned_item(item_id, user=user, db_session=db_session)
    file_ids = delete_artifact_library_item(item=item, db_session=db_session)
    db_session.commit()
    _delete_blobs(file_ids, get_default_file_store())
