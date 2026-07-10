import datetime
from collections.abc import Generator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.db.enums import MemoryGovernanceAuditAction
from onyx.db.memory import add_memory
from onyx.db.memory import delete_expired_memories
from onyx.db.memory import get_memories
from onyx.db.memory import get_memory_governance_audit_events
from onyx.db.memory import get_memory_governance_policy
from onyx.db.memory import update_memory_governance_policy
from onyx.db.models import Memory
from onyx.db.models import MemoryGovernancePolicy
from onyx.db.models import User
from tests.external_dependency_unit.conftest import create_test_user


@pytest.fixture()
def memory_policy(
    db_session: Session,
) -> Generator[MemoryGovernancePolicy, None, None]:
    policy = get_memory_governance_policy(db_session)
    if policy not in db_session:
        db_session.add(policy)
    policy.memories_enabled = True
    policy.memory_creation_enabled = True
    policy.retention_days = None
    db_session.commit()
    yield policy
    policy.memories_enabled = True
    policy.memory_creation_enabled = True
    policy.retention_days = None
    db_session.commit()


def test_disabled_policy_hides_and_blocks_memory(
    db_session: Session,
    memory_policy: MemoryGovernancePolicy,  # noqa: ARG001
) -> None:
    user = create_test_user(db_session, "memory_governance_disabled")
    memory_id = add_memory(user.id, "Visible before policy change", db_session)
    assert memory_id is not None

    update_memory_governance_policy(
        db_session=db_session,
        memories_enabled=False,
        memory_creation_enabled=False,
        retention_days=None,
        actor_user_id=user.id,
    )

    assert get_memories(user, db_session).memories == ()
    assert add_memory(user.id, "Blocked", db_session) is None
    assert db_session.get(Memory, memory_id) is not None


def test_retention_cleanup_deletes_only_expired_rows_and_audits(
    db_session: Session,
    memory_policy: MemoryGovernancePolicy,  # noqa: ARG001
) -> None:
    user = create_test_user(db_session, "memory_governance_retention")
    now = datetime.datetime.now(datetime.timezone.utc)
    old_memory = Memory(
        user_id=user.id,
        memory_text="Expired",
        created_at=now - datetime.timedelta(days=31),
        updated_at=now - datetime.timedelta(days=31),
    )
    current_memory = Memory(
        user_id=user.id,
        memory_text="Current",
        created_at=now - datetime.timedelta(days=29),
        updated_at=now - datetime.timedelta(days=29),
    )
    db_session.add_all([old_memory, current_memory])
    db_session.commit()

    update_memory_governance_policy(
        db_session=db_session,
        memories_enabled=True,
        memory_creation_enabled=True,
        retention_days=30,
        actor_user_id=user.id,
    )
    affected_count = delete_expired_memories(
        db_session=db_session, actor_user_id=user.id
    )

    remaining = db_session.scalars(
        select(Memory).where(Memory.user_id == user.id)
    ).all()
    assert affected_count == 1
    assert [memory.memory_text for memory in remaining] == ["Current"]
    audit_events = get_memory_governance_audit_events(db_session)
    assert audit_events[0][0].action == MemoryGovernanceAuditAction.RETENTION_CLEANUP
    assert audit_events[0][0].affected_count == 1


def test_policy_update_is_audited(
    db_session: Session,
    memory_policy: MemoryGovernancePolicy,  # noqa: ARG001
) -> None:
    actor: User = create_test_user(db_session, "memory_governance_actor")
    update_memory_governance_policy(
        db_session=db_session,
        memories_enabled=True,
        memory_creation_enabled=False,
        retention_days=90,
        actor_user_id=actor.id,
    )

    audit, actor_email = get_memory_governance_audit_events(db_session)[0]
    assert audit.action == MemoryGovernanceAuditAction.POLICY_UPDATED
    assert audit.details["after"]["retention_days"] == 90
    assert actor_email == actor.email
