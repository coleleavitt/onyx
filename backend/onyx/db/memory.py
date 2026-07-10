import datetime
from dataclasses import dataclass
from typing import Any
from typing import cast
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from sqlalchemy import delete
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from onyx.db.engine.sql_engine import get_session_with_current_tenant_if_none
from onyx.db.enums import MemoryGovernanceAuditAction
from onyx.db.models import Memory
from onyx.db.models import MemoryGovernanceAudit
from onyx.db.models import MemoryGovernancePolicy
from onyx.db.models import User

MAX_MEMORIES_PER_USER = 10
MEMORY_GOVERNANCE_POLICY_ID = 1


@dataclass(frozen=True)
class MemoryGovernanceStats:
    memory_count: int
    user_count: int
    oldest_memory_at: datetime.datetime | None


class UserInfo(BaseModel):
    name: str | None = None
    role: str | None = None
    email: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "email": self.email,
        }


class UserMemoryContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID | None = None
    user_info: UserInfo
    user_preferences: str | None = None
    memories: tuple[str, ...] = ()

    def without_memories(self) -> "UserMemoryContext":
        """Return a copy with memories cleared but user info/preferences intact."""
        return UserMemoryContext(
            user_id=self.user_id,
            user_info=self.user_info,
            user_preferences=self.user_preferences,
            memories=(),
        )

    def as_formatted_list(self) -> list[str]:
        """Returns combined list of user info, preferences, and memories."""
        result = []
        if self.user_info.name:
            result.append(f"User's name: {self.user_info.name}")
        if self.user_info.role:
            result.append(f"User's role: {self.user_info.role}")
        if self.user_info.email:
            result.append(f"User's email: {self.user_info.email}")
        if self.user_preferences:
            result.append(f"User preferences: {self.user_preferences}")
        result.extend(self.memories)
        return result


def get_memories(user: User, db_session: Session) -> UserMemoryContext:
    user_info = UserInfo(
        name=user.personal_name,
        role=user.personal_role,
        email=user.email,
    )

    user_preferences = None
    if user.user_preferences:
        user_preferences = user.user_preferences

    policy = get_memory_governance_policy(db_session)
    memory_rows = (
        db_session.scalars(
            select(Memory).where(Memory.user_id == user.id).order_by(Memory.id.asc())
        ).all()
        if policy.memories_enabled
        else []
    )
    memories = tuple(memory.memory_text for memory in memory_rows if memory.memory_text)

    return UserMemoryContext(
        user_id=user.id,
        user_info=user_info,
        user_preferences=user_preferences,
        memories=memories,
    )


def add_memory(
    user_id: UUID,
    memory_text: str,
    db_session: Session | None = None,
) -> int | None:
    """Insert a new Memory row for the given user.

    If the user already has MAX_MEMORIES_PER_USER memories, the oldest
    one (lowest id) is deleted before inserting the new one.

    Returns the id of the newly created Memory row.
    """
    with get_session_with_current_tenant_if_none(db_session) as db_session:
        if not is_memory_creation_allowed(db_session):
            return None

        existing = db_session.scalars(
            select(Memory).where(Memory.user_id == user_id).order_by(Memory.id.asc())
        ).all()

        if len(existing) >= MAX_MEMORIES_PER_USER:
            db_session.delete(existing[0])

        memory = Memory(
            user_id=user_id,
            memory_text=memory_text,
        )
        db_session.add(memory)
        db_session.commit()
        return memory.id


def update_memory_at_index(
    user_id: UUID,
    index: int,
    new_text: str,
    db_session: Session | None = None,
) -> int | None:
    """Update the memory at the given 0-based index (ordered by id ASC, matching get_memories()).

    Returns the id of the updated Memory row, or None if the index is out of range.
    """
    with get_session_with_current_tenant_if_none(db_session) as db_session:
        if not is_memory_creation_allowed(db_session):
            return None

        memory_rows = db_session.scalars(
            select(Memory).where(Memory.user_id == user_id).order_by(Memory.id.asc())
        ).all()

        if index < 0 or index >= len(memory_rows):
            return None

        memory = memory_rows[index]
        memory.memory_text = new_text
        db_session.commit()
        return memory.id


def get_memory_governance_policy(
    db_session: Session,
) -> MemoryGovernancePolicy:
    policy = db_session.get(MemoryGovernancePolicy, MEMORY_GOVERNANCE_POLICY_ID)
    if policy is not None:
        return policy
    return MemoryGovernancePolicy(
        id=MEMORY_GOVERNANCE_POLICY_ID,
        memories_enabled=True,
        memory_creation_enabled=True,
        retention_days=None,
    )


def is_memory_creation_allowed(db_session: Session) -> bool:
    policy = get_memory_governance_policy(db_session)
    return policy.memories_enabled and policy.memory_creation_enabled


def update_memory_governance_policy(
    *,
    db_session: Session,
    memories_enabled: bool,
    memory_creation_enabled: bool,
    retention_days: int | None,
    actor_user_id: UUID,
) -> MemoryGovernancePolicy:
    policy = db_session.get(MemoryGovernancePolicy, MEMORY_GOVERNANCE_POLICY_ID)
    if policy is None:
        policy = MemoryGovernancePolicy(
            id=MEMORY_GOVERNANCE_POLICY_ID,
            memories_enabled=True,
            memory_creation_enabled=True,
            retention_days=None,
        )
        db_session.add(policy)

    before = {
        "memories_enabled": policy.memories_enabled,
        "memory_creation_enabled": policy.memory_creation_enabled,
        "retention_days": policy.retention_days,
    }
    policy.memories_enabled = memories_enabled
    policy.memory_creation_enabled = memory_creation_enabled
    policy.retention_days = retention_days
    policy.updated_by_user_id = actor_user_id
    db_session.add(
        MemoryGovernanceAudit(
            action=MemoryGovernanceAuditAction.POLICY_UPDATED,
            actor_user_id=actor_user_id,
            details={
                "before": before,
                "after": {
                    "memories_enabled": memories_enabled,
                    "memory_creation_enabled": memory_creation_enabled,
                    "retention_days": retention_days,
                },
            },
        )
    )
    db_session.commit()
    db_session.refresh(policy)
    return policy


def get_memory_governance_stats(db_session: Session) -> MemoryGovernanceStats:
    memory_count, user_count, oldest_memory_at = db_session.execute(
        select(
            func.count(Memory.id),
            func.count(distinct(Memory.user_id)),
            func.min(Memory.created_at),
        )
    ).one()
    return MemoryGovernanceStats(
        memory_count=int(memory_count or 0),
        user_count=int(user_count or 0),
        oldest_memory_at=oldest_memory_at,
    )


def get_memory_governance_audit_events(
    db_session: Session, *, limit: int = 50
) -> list[tuple[MemoryGovernanceAudit, str | None]]:
    rows = db_session.execute(
        select(MemoryGovernanceAudit, cast(Any, User.email))
        .outerjoin(
            User,
            cast(Any, User.id) == MemoryGovernanceAudit.actor_user_id,
        )
        .order_by(MemoryGovernanceAudit.created_at.desc())
        .limit(limit)
    ).all()
    return [(row[0], row[1]) for row in rows]


def delete_expired_memories(
    *,
    db_session: Session,
    actor_user_id: UUID | None = None,
) -> int:
    policy = get_memory_governance_policy(db_session)
    if policy.retention_days is None:
        return 0

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=policy.retention_days
    )
    result = cast(
        CursorResult[Any],
        db_session.execute(delete(Memory).where(Memory.created_at < cutoff)),
    )
    affected_count = max(result.rowcount or 0, 0)
    if affected_count > 0:
        db_session.add(
            MemoryGovernanceAudit(
                action=MemoryGovernanceAuditAction.RETENTION_CLEANUP,
                actor_user_id=actor_user_id,
                affected_count=affected_count,
                details={
                    "retention_days": policy.retention_days,
                    "cutoff": cutoff.isoformat(),
                    "trigger": "manual" if actor_user_id else "scheduled",
                },
            )
        )
    db_session.commit()
    return affected_count


def delete_all_memories(
    *,
    db_session: Session,
    actor_user_id: UUID,
) -> int:
    result = cast(CursorResult[Any], db_session.execute(delete(Memory)))
    affected_count = max(result.rowcount or 0, 0)
    db_session.add(
        MemoryGovernanceAudit(
            action=MemoryGovernanceAuditAction.BULK_DELETE,
            actor_user_id=actor_user_id,
            affected_count=affected_count,
            details={"scope": "organization"},
        )
    )
    db_session.commit()
    return affected_count
