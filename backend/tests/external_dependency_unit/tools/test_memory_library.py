from sqlalchemy.orm import Session

from onyx.db.enums import MemoryCategory
from onyx.db.memory import create_memory_item
from onyx.db.memory import get_memories
from onyx.db.memory import get_memory_item_for_user
from onyx.db.memory import list_memory_items_for_user
from onyx.db.memory import list_memory_revisions
from onyx.db.memory import MAX_CONTEXT_MEMORIES
from onyx.db.memory import MAX_CONTEXT_MEMORY_CHARACTERS
from onyx.db.memory import restore_memory_revision
from onyx.db.memory import update_memory_item
from onyx.db.models import User
from tests.external_dependency_unit.conftest import create_test_user


def test_typed_memory_tracks_and_restores_revisions(
    db_session: Session,
) -> None:
    test_user: User = create_test_user(db_session, "typed_memory")
    memory = create_memory_item(
        user_id=test_user.id,
        title="Quarterly planning",
        category=MemoryCategory.WORKSTREAMS,
        memory_text="Prepare the quarterly plan with Finance.",
        source="manual",
        db_session=db_session,
    )
    assert memory is not None

    db_session.expire_all()
    persisted = get_memory_item_for_user(
        memory.id,
        test_user.id,
        db_session=db_session,
    )
    assert persisted is not None
    assert persisted.category is MemoryCategory.WORKSTREAMS
    memory = persisted

    updated = update_memory_item(
        memory,
        title="Quarterly planning",
        category=MemoryCategory.WORKSTREAMS,
        memory_text="Prepare the quarterly plan with Finance and Operations.",
        source="manual",
        db_session=db_session,
    )
    assert updated is not None

    revisions = list_memory_revisions(memory.id, db_session=db_session)
    assert [revision.memory_text for revision in revisions] == [
        "Prepare the quarterly plan with Finance and Operations.",
        "Prepare the quarterly plan with Finance.",
    ]

    restored = restore_memory_revision(
        memory,
        revisions[-1],
        db_session=db_session,
    )
    assert restored is not None
    assert restored.memory_text == "Prepare the quarterly plan with Finance."
    assert len(list_memory_revisions(memory.id, db_session=db_session)) == 3

    listed = list_memory_items_for_user(
        test_user.id,
        db_session=db_session,
        category=MemoryCategory.WORKSTREAMS,
        query="quarterly",
    )
    assert [item.id for item in listed] == [memory.id]


def test_memory_context_is_bounded_and_prefers_recent_items(
    db_session: Session,
) -> None:
    test_user: User = create_test_user(db_session, "bounded_memory_context")
    for index in range(MAX_CONTEXT_MEMORIES + 2):
        memory = create_memory_item(
            user_id=test_user.id,
            title=f"Memory {index}",
            category=MemoryCategory.NOTES,
            memory_text=f"remember-{index}",
            source="manual",
            db_session=db_session,
        )
        assert memory is not None

    context = get_memories(test_user, db_session)

    assert len(context.memories) == MAX_CONTEXT_MEMORIES
    assert context.memories[0] == f"remember-{MAX_CONTEXT_MEMORIES + 1}"
    assert "remember-0" not in context.memories

    newest = create_memory_item(
        user_id=test_user.id,
        title="Bounded long memory",
        category=MemoryCategory.NOTES,
        memory_text="x" * (MAX_CONTEXT_MEMORY_CHARACTERS + 100),
        source="manual",
        db_session=db_session,
    )
    assert newest is not None

    bounded_context = get_memories(test_user, db_session)
    assert len(bounded_context.memories) == 1
    assert len(bounded_context.memories[0]) == MAX_CONTEXT_MEMORY_CHARACTERS
