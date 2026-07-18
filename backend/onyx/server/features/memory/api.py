from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.configs.constants import OnyxCeleryPriority
from onyx.configs.constants import OnyxCeleryQueues
from onyx.configs.constants import OnyxCeleryTask
from onyx.db.brain import BrainSettings
from onyx.db.brain import get_memory_graph
from onyx.db.brain import get_memory_sources
from onyx.db.brain import get_related_memories
from onyx.db.brain import MemoryGraph
from onyx.db.brain import update_brain_settings
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import MemoryCategory
from onyx.db.enums import Permission
from onyx.db.memory import create_memory_item
from onyx.db.memory import delete_memory_item
from onyx.db.memory import get_memory_item_for_user
from onyx.db.memory import get_memory_revision
from onyx.db.memory import is_memory_creation_allowed
from onyx.db.memory import list_memory_items_for_user
from onyx.db.memory import list_memory_revisions
from onyx.db.memory import restore_memory_revision
from onyx.db.memory import update_memory_item
from onyx.db.models import Memory
from onyx.db.models import User
from onyx.db.projects import ProjectAccessPolicy
from onyx.db.projects import user_has_project_access
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.redis.redis_pool import get_redis_client
from onyx.server.features.memory.models import BrainRunTriggerResponse
from onyx.server.features.memory.models import BrainSettingsUpdateRequest
from onyx.server.features.memory.models import MemoryCreateRequest
from onyx.server.features.memory.models import MemoryListResponse
from onyx.server.features.memory.models import MemoryRevisionSnapshot
from onyx.server.features.memory.models import MemorySnapshot
from onyx.server.features.memory.models import MemorySourceSnapshot
from onyx.server.features.memory.models import MemoryUpdateRequest
from onyx.server.features.memory.models import RelatedMemoriesResponse
from onyx.server.features.memory.models import RelatedMemory
from shared_configs.contextvars import get_current_tenant_id

router = APIRouter(prefix="/memory")

# A manual brain refresh is expensive (LLM extraction over recent sessions), so
# repeat requests inside the cooldown are rejected instead of queued.
BRAIN_MANUAL_RUN_COOLDOWN_SECONDS = 5 * 60
BRAIN_MANUAL_RUN_TASK_EXPIRES_SECONDS = 60 * 60


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


def _validate_project_scope(
    project_id: int | None,
    *,
    user: User,
    db_session: Session,
) -> None:
    if project_id is None:
        return
    if not user_has_project_access(
        project_id,
        user=user,
        db_session=db_session,
        policy=ProjectAccessPolicy.VIEW,
    ):
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Space not found")


@router.get("")
def list_current_user_memories(
    category: MemoryCategory | None = None,
    query: str | None = Query(default=None, max_length=200),
    project_id: int | None = Query(default=None),
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemoryListResponse:
    _validate_project_scope(project_id, user=user, db_session=db_session)
    all_items = list_memory_items_for_user(
        _user_id(user), db_session=db_session, project_id=project_id
    )
    category_counts = {
        item_category: sum(item.category == item_category for item in all_items)
        for item_category in MemoryCategory
    }
    items = list_memory_items_for_user(
        _user_id(user),
        db_session=db_session,
        category=category,
        query=query,
        project_id=project_id,
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
    _validate_project_scope(body.project_id, user=user, db_session=db_session)
    memory = create_memory_item(
        user_id=_user_id(user),
        memory_text=body.content.strip(),
        title=body.title,
        category=body.category,
        source="manual",
        db_session=db_session,
        project_id=body.project_id,
    )
    if memory is None:
        raise OnyxError(
            OnyxErrorCode.INSUFFICIENT_PERMISSIONS,
            "Memory creation is disabled for this organization",
        )
    return MemorySnapshot.from_model(memory)


@router.get("/graph")
def get_current_user_memory_graph(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemoryGraph:
    return get_memory_graph(db_session, _user_id(user))


@router.get("/brain/settings")
def get_current_user_brain_settings(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
) -> BrainSettings:
    return BrainSettings.from_user(user)


@router.put("/brain/settings")
def update_current_user_brain_settings(
    request: BrainSettingsUpdateRequest,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> BrainSettings:
    settings = update_brain_settings(
        db_session,
        _user_id(user),
        brain_enabled=request.brain_enabled,
        brain_use_connectors=request.brain_use_connectors,
        brain_focus_instructions=request.brain_focus_instructions,
    )
    if settings is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "User not found")
    return settings


@router.post("/brain/run")
def trigger_current_user_brain_run(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
) -> BrainRunTriggerResponse:
    """Queue an on-demand brain run for the current user (the scheduled nightly
    sweep still happens); a Redis guard rate-limits repeat requests."""
    if not user.brain_enabled:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "Enable Brain before requesting a refresh",
        )
    if not is_memory_creation_allowed(db_session):
        raise OnyxError(
            OnyxErrorCode.INSUFFICIENT_PERMISSIONS,
            "Memory creation is disabled for this organization",
        )

    # NX+EX = atomic dedupe (a queued-but-unstarted run can't be double-queued)
    # and cooldown in one call.
    redis_client = get_redis_client(tenant_id=tenant_id)
    guard_set = redis_client.set(
        f"brain_manual_run:{_user_id(user)}",
        1,
        nx=True,
        ex=BRAIN_MANUAL_RUN_COOLDOWN_SECONDS,
    )
    if not guard_set:
        raise OnyxError(
            OnyxErrorCode.RATE_LIMITED,
            "A brain refresh was requested recently — try again in a few minutes",
        )

    from onyx.background.celery.versioned_apps.client import app as client_app

    client_app.send_task(
        OnyxCeleryTask.BRAIN_SELF_IMPROVEMENT_USER,
        kwargs={"user_id": str(_user_id(user)), "tenant_id": tenant_id},
        queue=OnyxCeleryQueues.PRIMARY,
        priority=OnyxCeleryPriority.HIGH,
        expires=BRAIN_MANUAL_RUN_TASK_EXPIRES_SECONDS,
    )
    return BrainRunTriggerResponse(
        queued=True,
        cooldown_seconds=BRAIN_MANUAL_RUN_COOLDOWN_SECONDS,
    )


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


@router.get("/{memory_id}/related")
def get_current_user_memory_related(
    memory_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> RelatedMemoriesResponse:
    _memory_or_404(memory_id, user=user, db_session=db_session)
    related = get_related_memories(db_session, _user_id(user), memory_id)
    groups: dict[MemoryCategory, list[RelatedMemory]] = {
        category: [] for category in MemoryCategory
    }
    for memory in related:
        groups[memory.category].append(
            RelatedMemory(
                id=memory.id,
                title=memory.title or "Untitled memory",
                category=memory.category,
            )
        )
    return RelatedMemoriesResponse(groups=groups)


@router.get("/{memory_id}/sources")
def get_current_user_memory_sources(
    memory_id: int,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[MemorySourceSnapshot]:
    _memory_or_404(memory_id, user=user, db_session=db_session)
    return [
        MemorySourceSnapshot.from_model(source)
        for source in get_memory_sources(db_session, memory_id)
    ]
