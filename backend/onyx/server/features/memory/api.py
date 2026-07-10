from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import MemoryCategory
from onyx.db.enums import Permission
from onyx.db.memory import create_memory_item
from onyx.db.memory import delete_memory_item
from onyx.db.memory import get_memory_item_for_user
from onyx.db.memory import get_memory_revision
from onyx.db.memory import list_memory_items_for_user
from onyx.db.memory import list_memory_revisions
from onyx.db.memory import restore_memory_revision
from onyx.db.memory import update_memory_item
from onyx.db.models import Memory
from onyx.db.models import User
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.features.memory.models import MemoryCreateRequest
from onyx.server.features.memory.models import MemoryListResponse
from onyx.server.features.memory.models import MemoryRevisionSnapshot
from onyx.server.features.memory.models import MemorySnapshot
from onyx.server.features.memory.models import MemoryUpdateRequest

router = APIRouter(prefix="/memory")


def _user_id(user: User) -> UUID:
    if user.id is None:
        raise OnyxError(OnyxErrorCode.UNAUTHENTICATED)
    return user.id


def _memory_or_404(
    memory_id: int,
    *,
    user: User,
    db_session: Session,
) -> Memory:
    memory = get_memory_item_for_user(
        memory_id,
        _user_id(user),
        db_session=db_session,
    )
    if memory is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Memory not found")
    return memory


@router.get("")
def list_current_user_memories(
    category: MemoryCategory | None = None,
    query: str | None = Query(default=None, max_length=200),
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemoryListResponse:
    all_items = list_memory_items_for_user(_user_id(user), db_session=db_session)
    category_counts = {
        item_category: sum(item.category == item_category for item in all_items)
        for item_category in MemoryCategory
    }
    items = list_memory_items_for_user(
        _user_id(user),
        db_session=db_session,
        category=category,
        query=query,
    )
    return MemoryListResponse(
        items=[MemorySnapshot.from_model(item) for item in items],
        total=len(all_items),
        category_counts=category_counts,
    )


@router.post("")
def create_current_user_memory(
    body: MemoryCreateRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemorySnapshot:
    memory = create_memory_item(
        user_id=_user_id(user),
        memory_text=body.content.strip(),
        title=body.title,
        category=body.category,
        source="manual",
        db_session=db_session,
    )
    if memory is None:
        raise OnyxError(
            OnyxErrorCode.INSUFFICIENT_PERMISSIONS,
            "Memory creation is disabled for this organization",
        )
    return MemorySnapshot.from_model(memory)


@router.get("/{memory_id}")
def get_current_user_memory(
    memory_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemorySnapshot:
    return MemorySnapshot.from_model(
        _memory_or_404(memory_id, user=user, db_session=db_session)
    )


@router.patch("/{memory_id}")
def update_current_user_memory(
    memory_id: int,
    body: MemoryUpdateRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemorySnapshot:
    memory = _memory_or_404(memory_id, user=user, db_session=db_session)
    title = body.title if "title" in body.model_fields_set else memory.title
    category = body.category or memory.category
    content = body.content.strip() if body.content is not None else memory.memory_text
    updated = update_memory_item(
        memory,
        memory_text=content,
        title=title,
        category=category,
        source="manual",
        db_session=db_session,
    )
    if updated is None:
        raise OnyxError(
            OnyxErrorCode.INSUFFICIENT_PERMISSIONS,
            "Memory updates are disabled for this organization",
        )
    return MemorySnapshot.from_model(updated)


@router.delete("/{memory_id}")
def delete_current_user_memory(
    memory_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    delete_memory_item(
        _memory_or_404(memory_id, user=user, db_session=db_session),
        db_session=db_session,
    )


@router.get("/{memory_id}/history")
def get_current_user_memory_history(
    memory_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[MemoryRevisionSnapshot]:
    memory = _memory_or_404(memory_id, user=user, db_session=db_session)
    return [
        MemoryRevisionSnapshot.from_model(revision)
        for revision in list_memory_revisions(memory.id, db_session=db_session)
    ]


@router.post("/{memory_id}/history/{revision_id}/restore")
def restore_current_user_memory_revision(
    memory_id: int,
    revision_id: UUID,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemorySnapshot:
    memory = _memory_or_404(memory_id, user=user, db_session=db_session)
    revision = get_memory_revision(
        revision_id,
        memory.id,
        db_session=db_session,
    )
    if revision is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Memory revision not found")
    restored = restore_memory_revision(memory, revision, db_session=db_session)
    if restored is None:
        raise OnyxError(
            OnyxErrorCode.INSUFFICIENT_PERMISSIONS,
            "Memory updates are disabled for this organization",
        )
    return MemorySnapshot.from_model(restored)
