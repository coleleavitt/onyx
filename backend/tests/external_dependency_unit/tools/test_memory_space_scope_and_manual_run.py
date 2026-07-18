"""Space-scoped memory recall/writes and the on-demand ("refresh now") brain
run.

Scope semantics under test (mirrors per-space memory isolation):
- global memories (project_id NULL) are recalled everywhere;
- a space's memories are only recalled in that space's chats;
- memories written by the chat memory tool inherit the scope they were
  recalled with, so the LLM's replace-by-index stays aligned.

The manual-run test drives the real single-user Celery task body with a mocked
LLM (no network) and proves it creates pages, scopes them to the space every
cited session belongs to, and cites sessions with clickable in-app URLs.
"""

import json
from unittest.mock import MagicMock
from unittest.mock import patch

from sqlalchemy.orm import Session

from onyx.background.celery.tasks.brain.tasks import _page_project_id
from onyx.background.celery.tasks.brain.tasks import _SourceRef
from onyx.background.celery.tasks.brain.tasks import brain_self_improvement_user
from onyx.configs.constants import MessageType
from onyx.db.brain import get_memory_sources
from onyx.db.chat import create_chat_session
from onyx.db.chat import create_new_chat_message
from onyx.db.chat import get_or_create_root_message
from onyx.db.enums import MemoryCategory
from onyx.db.enums import MemorySourceType
from onyx.db.memory import add_memory
from onyx.db.memory import create_memory_item
from onyx.db.memory import get_memories
from onyx.db.memory import list_memory_items_for_user
from onyx.db.memory import update_memory_at_index
from onyx.db.models import ChatMessage
from onyx.db.models import Memory
from onyx.db.models import User
from onyx.db.models import UserProject
from tests.external_dependency_unit.conftest import create_test_user


def _create_project(db_session: Session, user: User, name: str) -> UserProject:
    project = UserProject(user_id=user.id, name=name, instructions="")
    db_session.add(project)
    db_session.commit()
    return project


def test_space_scoped_recall_isolation(db_session: Session) -> None:
    """Global memories apply everywhere; a space's memories only apply inside
    that space; sibling spaces never see each other's memories."""
    user: User = create_test_user(db_session, "memory_scope")
    space_a = _create_project(db_session, user, "Space A")
    space_b = _create_project(db_session, user, "Space B")

    global_memory = create_memory_item(
        user_id=user.id,
        memory_text="The user's favorite color is teal.",
        title="Favorite color",
        category=MemoryCategory.NOTES,
        source="manual",
        db_session=db_session,
    )
    assert global_memory is not None
    scoped_memory = create_memory_item(
        user_id=user.id,
        memory_text="Space A ships the Q3 launch.",
        title="Q3 launch",
        category=MemoryCategory.WORKSTREAMS,
        source="manual",
        db_session=db_session,
        project_id=space_a.id,
    )
    assert scoped_memory is not None
    assert scoped_memory.project_id == space_a.id

    # Outside any space: only the global memory.
    global_context = get_memories(user, db_session)
    assert "The user's favorite color is teal." in global_context.memories
    assert "Space A ships the Q3 launch." not in global_context.memories
    assert global_context.project_id is None

    # Inside space A: global + space A's memory.
    space_a_context = get_memories(user, db_session, project_id=space_a.id)
    assert "The user's favorite color is teal." in space_a_context.memories
    assert "Space A ships the Q3 launch." in space_a_context.memories
    assert space_a_context.project_id == space_a.id

    # Inside space B: space A's memory is invisible.
    space_b_context = get_memories(user, db_session, project_id=space_b.id)
    assert "The user's favorite color is teal." in space_b_context.memories
    assert "Space A ships the Q3 launch." not in space_b_context.memories

    # The library API filter follows the same scope rule.
    space_a_items = list_memory_items_for_user(
        user.id, db_session=db_session, project_id=space_a.id
    )
    assert {item.memory_text for item in space_a_items} == {
        "The user's favorite color is teal.",
        "Space A ships the Q3 launch.",
    }
    # Without a scope the library lists everything (global page view).
    all_items = list_memory_items_for_user(user.id, db_session=db_session)
    assert len(all_items) == 2


def test_memory_tool_writes_inherit_chat_scope(db_session: Session) -> None:
    """`add_memory` scopes new rows to the chat's space, and
    `update_memory_at_index` resolves the index against the same scoped
    ordering the LLM saw at recall time."""
    user: User = create_test_user(db_session, "memory_scope_write")
    space = _create_project(db_session, user, "Scoped space")

    new_id = add_memory(
        user.id,
        "The user prefers dark mode.",
        db_session=db_session,
        project_id=space.id,
    )
    assert new_id is not None
    created = db_session.get(Memory, new_id)
    assert created is not None and created.project_id == space.id

    # A global memory that is newer would shift indexes if the scope filter
    # were ignored — prove index 0 in the space scope is the scoped row's
    # recall order, not the raw table order.
    global_id = add_memory(user.id, "Global note.", db_session=db_session)
    assert global_id is not None

    scoped_context = get_memories(user, db_session, project_id=space.id)
    # Newest first: the global note, then the scoped memory.
    assert scoped_context.memories[0] == "Global note."
    assert scoped_context.memories[1] == "The user prefers dark mode."

    updated_id = update_memory_at_index(
        user.id,
        index=1,
        new_text="The user prefers dark mode everywhere.",
        db_session=db_session,
        project_id=space.id,
    )
    assert updated_id == new_id


def test_page_project_attribution() -> None:
    """A brain page cited only from one space's sessions is scoped to it;
    mixed or global citations stay global."""

    def session_ref(ref: str, project_id: int | None) -> _SourceRef:
        return _SourceRef(
            ref=ref,
            source_type=MemorySourceType.CHAT_SESSION,
            label="Chat session",
            source_id=f"session-{ref}",
            project_id=project_id,
        )

    doc_ref = _SourceRef(
        ref="D1",
        source_type=MemorySourceType.DOCUMENT,
        label="Doc",
        source_id="doc-1",
    )

    # All cited sessions in one space -> scoped (documents don't break it).
    assert _page_project_id([session_ref("S1", 7), session_ref("S2", 7)]) == 7
    assert _page_project_id([session_ref("S1", 7), doc_ref]) == 7
    # Global session or mixed spaces -> global.
    assert _page_project_id([session_ref("S1", None)]) is None
    assert _page_project_id([session_ref("S1", 7), session_ref("S2", 8)]) is None
    assert _page_project_id([session_ref("S1", 7), session_ref("S2", None)]) is None
    # No citations -> global.
    assert _page_project_id([]) is None
    assert _page_project_id([doc_ref]) is None


def _seed_session_with_messages(
    db_session: Session,
    user: User,
    *,
    description: str,
    project_id: int | None,
    user_text: str,
    assistant_text: str,
) -> str:
    session = create_chat_session(
        db_session=db_session,
        description=description,
        user_id=user.id,
        persona_id=None,
        project_id=project_id,
    )
    root: ChatMessage = get_or_create_root_message(
        chat_session_id=session.id, db_session=db_session
    )
    user_message = create_new_chat_message(
        chat_session_id=session.id,
        parent_message=root,
        message=user_text,
        token_count=10,
        message_type=MessageType.USER,
        db_session=db_session,
    )
    create_new_chat_message(
        chat_session_id=session.id,
        parent_message=user_message,
        message=assistant_text,
        token_count=10,
        message_type=MessageType.ASSISTANT,
        db_session=db_session,
    )
    return str(session.id)


def _mock_llm_returning(pages: list[dict[str, object]]) -> MagicMock:
    llm = MagicMock()
    llm.config.model_name = "test-model"
    llm.config.model_provider = "test-provider"
    llm.config.api_base = None
    response = MagicMock()
    response.choice.message.content = json.dumps({"pages": pages})
    llm.invoke.return_value = response
    return llm


def test_manual_brain_run_creates_scoped_pages_with_session_links(
    db_session: Session,
    tenant_context: None,  # noqa: ARG001
) -> None:
    """Drive the on-demand single-user brain task end to end (mocked LLM):
    it must create the extracted page, scope it to the space every cited
    session belongs to, and cite the sessions with in-app chat URLs."""
    user: User = create_test_user(db_session, "brain_manual_run")
    user.brain_enabled = True
    db_session.commit()
    space = _create_project(db_session, user, "Launch space")

    session_id = _seed_session_with_messages(
        db_session,
        user,
        description="Launch planning",
        project_id=space.id,
        user_text="We are launching Atlas in Q3, Dana owns rollout.",
        assistant_text="Noted: Atlas launches in Q3 with Dana owning rollout.",
    )

    llm = _mock_llm_returning(
        [
            {
                "title": "Atlas launch",
                "category": "workstreams",
                "content": "Atlas launches in Q3; Dana owns the rollout.",
                "related": [],
                "sources": ["S1"],
            }
        ]
    )

    with patch(
        "onyx.background.celery.tasks.brain.tasks.get_default_llm",
        return_value=llm,
    ):
        assert brain_self_improvement_user(user_id=str(user.id)) is True

    memories = list_memory_items_for_user(user.id, db_session=db_session)
    assert len(memories) == 1
    page = memories[0]
    assert page.title == "Atlas launch"
    assert page.category is MemoryCategory.WORKSTREAMS
    # Every cited session lives in the space, so the page is space-scoped.
    assert page.project_id == space.id

    sources = get_memory_sources(db_session, page.id)
    assert len(sources) == 1
    assert sources[0].source_type is MemorySourceType.CHAT_SESSION
    assert sources[0].source_id == session_id
    # Conversation-history citations deep-link back into the app.
    assert sources[0].url == f"/app?chatId={session_id}"

    # The run is recorded so the settings modal can show "last refreshed".
    db_session.refresh(user)
    assert user.brain_last_run_at is not None


def test_manual_brain_run_requires_brain_enabled(
    db_session: Session,
    tenant_context: None,  # noqa: ARG001
) -> None:
    """The task is a no-op for users who never opted into Brain."""
    user: User = create_test_user(db_session, "brain_manual_disabled")
    assert user.brain_enabled is False

    with patch("onyx.background.celery.tasks.brain.tasks.get_default_llm") as get_llm:
        assert brain_self_improvement_user(user_id=str(user.id)) is False
        get_llm.assert_not_called()
