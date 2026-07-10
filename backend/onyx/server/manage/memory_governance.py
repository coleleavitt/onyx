import datetime
from typing import Any
from typing import Literal

from fastapi import APIRouter
from fastapi import Depends
from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import MemoryGovernanceAuditAction
from onyx.db.enums import Permission
from onyx.db.memory import delete_all_memories
from onyx.db.memory import delete_expired_memories
from onyx.db.memory import get_memory_governance_audit_events
from onyx.db.memory import get_memory_governance_policy
from onyx.db.memory import get_memory_governance_stats
from onyx.db.memory import update_memory_governance_policy
from onyx.db.models import MemoryGovernanceAudit
from onyx.db.models import MemoryGovernancePolicy
from onyx.db.models import User
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.utils.audit import actor_from_user
from onyx.utils.audit import AuditAction
from onyx.utils.audit import AuditOutcome
from onyx.utils.audit import emit_audit_event

admin_router = APIRouter(prefix="/admin/memory-governance")


class MemoryGovernancePolicyUpdate(BaseModel):
    memories_enabled: bool
    memory_creation_enabled: bool
    retention_days: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def validate_creation_requires_memory(self) -> "MemoryGovernancePolicyUpdate":
        if self.memory_creation_enabled and not self.memories_enabled:
            raise ValueError(
                "Memory creation cannot remain enabled when memory is disabled"
            )
        return self


class MemoryGovernancePolicySnapshot(BaseModel):
    memories_enabled: bool
    memory_creation_enabled: bool
    retention_days: int | None
    updated_at: datetime.datetime | None


class MemoryGovernanceStatsSnapshot(BaseModel):
    memory_count: int
    user_count: int
    oldest_memory_at: datetime.datetime | None


class MemoryGovernanceAuditSnapshot(BaseModel):
    id: int
    action: MemoryGovernanceAuditAction
    actor_email: str | None
    affected_count: int
    details: dict[str, Any]
    created_at: datetime.datetime


class MemoryGovernanceOverview(BaseModel):
    policy: MemoryGovernancePolicySnapshot
    stats: MemoryGovernanceStatsSnapshot
    audit_events: list[MemoryGovernanceAuditSnapshot]


class MemoryBulkDeleteRequest(BaseModel):
    scope: Literal["expired", "all"]
    confirmation: str | None = None


class MemoryBulkDeleteResponse(BaseModel):
    affected_count: int


def _policy_snapshot(
    policy: MemoryGovernancePolicy,
) -> MemoryGovernancePolicySnapshot:
    return MemoryGovernancePolicySnapshot(
        memories_enabled=policy.memories_enabled,
        memory_creation_enabled=policy.memory_creation_enabled,
        retention_days=policy.retention_days,
        updated_at=policy.updated_at,
    )


def _audit_snapshot(
    audit: MemoryGovernanceAudit, actor_email: str | None
) -> MemoryGovernanceAuditSnapshot:
    return MemoryGovernanceAuditSnapshot(
        id=audit.id,
        action=audit.action,
        actor_email=actor_email,
        affected_count=audit.affected_count,
        details=audit.details,
        created_at=audit.created_at,
    )


def _get_overview(db_session: Session) -> MemoryGovernanceOverview:
    policy = get_memory_governance_policy(db_session)
    stats = get_memory_governance_stats(db_session)
    audit_events = get_memory_governance_audit_events(db_session)
    return MemoryGovernanceOverview(
        policy=_policy_snapshot(policy),
        stats=MemoryGovernanceStatsSnapshot(
            memory_count=stats.memory_count,
            user_count=stats.user_count,
            oldest_memory_at=stats.oldest_memory_at,
        ),
        audit_events=[
            _audit_snapshot(audit, actor_email) for audit, actor_email in audit_events
        ],
    )


@admin_router.get("")
def get_memory_governance(
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> MemoryGovernanceOverview:
    return _get_overview(db_session)


@admin_router.put("")
def put_memory_governance(
    request: MemoryGovernancePolicyUpdate,
    current_user: User = Depends(
        require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)
    ),
    db_session: Session = Depends(get_session),
) -> MemoryGovernanceOverview:
    update_memory_governance_policy(
        db_session=db_session,
        memories_enabled=request.memories_enabled,
        memory_creation_enabled=request.memory_creation_enabled,
        retention_days=request.retention_days,
        actor_user_id=current_user.id,
    )
    emit_audit_event(
        AuditAction.MEMORY_POLICY_CHANGE,
        AuditOutcome.SUCCESS,
        actor=actor_from_user(current_user),
        resource_type="memory_governance_policy",
        resource_id=1,
        extra=request.model_dump(),
    )
    return _get_overview(db_session)


@admin_router.post("/bulk-delete")
def bulk_delete_memories(
    request: MemoryBulkDeleteRequest,
    current_user: User = Depends(
        require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)
    ),
    db_session: Session = Depends(get_session),
) -> MemoryBulkDeleteResponse:
    if request.scope == "all":
        if request.confirmation != "DELETE ALL MEMORIES":
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT,
                'Set confirmation to "DELETE ALL MEMORIES" to continue.',
            )
        affected_count = delete_all_memories(
            db_session=db_session, actor_user_id=current_user.id
        )
        action = AuditAction.MEMORY_BULK_DELETE
    else:
        policy = get_memory_governance_policy(db_session)
        if policy.retention_days is None:
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT,
                "Set a memory retention period before deleting expired memories.",
            )
        affected_count = delete_expired_memories(
            db_session=db_session, actor_user_id=current_user.id
        )
        action = AuditAction.MEMORY_RETENTION_CLEANUP

    emit_audit_event(
        action,
        AuditOutcome.SUCCESS,
        actor=actor_from_user(current_user),
        resource_type="memory",
        extra={"scope": request.scope, "affected_count": affected_count},
    )
    return MemoryBulkDeleteResponse(affected_count=affected_count)
