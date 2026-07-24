"""F1 per-thread visibility, verified against the real DB/ORM.

Proves the project_visibility column persists and round-trips, the central
visibility helper resolves correctly on real ChatSession rows, and the setter
enforces owner-only sharing.
"""

from collections.abc import Generator
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from onyx.db.chat import create_chat_session
from onyx.db.chat import is_chat_session_visible_in_project
from onyx.db.chat import set_chat_session_project_visibility
from onyx.db.enums import ChatSessionProjectVisibility
from onyx.db.models import ChatSession
from onyx.db.models import User
from onyx.db.models import UserProject
from tests.external_dependency_unit.conftest import create_test_user


class _Tracked:
    def __init__(self) -> None:
        self.user_ids: list[UUID] = []
        self.project_ids: list[int] = []
        self.session_ids: list[UUID] = []


@pytest.fixture
def tracked(db_session: Session) -> Generator[_Tracked, None, None]:
    t = _Tracked()
    yield t
    if t.session_ids:
        db_session.query(ChatSession).filter(ChatSession.id.in_(t.session_ids)).delete(
            synchronize_session=False
        )
    if t.project_ids:
        db_session.query(UserProject).filter(UserProject.id.in_(t.project_ids)).delete(
            synchronize_session=False
        )
    if t.user_ids:
        db_session.query(User).filter(User.id.in_(t.user_ids)).delete(
            synchronize_session=False
        )
    db_session.commit()


def _thread(
    db_session: Session,
    tracked: _Tracked,
    owner: User,
    project_id: int,
    visibility: ChatSessionProjectVisibility,
) -> ChatSession:
    session = create_chat_session(
        db_session=db_session,
        description="t",
        user_id=owner.id,
        persona_id=None,
        project_id=project_id,
    )
    session.project_visibility = visibility
    db_session.commit()
    tracked.session_ids.append(session.id)
    return session


def test_project_visibility_persists_and_helper_resolves(
    db_session: Session, tracked: _Tracked
) -> None:
    owner = create_test_user(db_session, "vis_owner")
    peer = create_test_user(db_session, "vis_peer")
    tracked.user_ids.extend([owner.id, peer.id])
    project = UserProject(user_id=owner.id, name="Space", instructions="")
    db_session.add(project)
    db_session.commit()
    tracked.project_ids.append(project.id)

    private = _thread(
        db_session, tracked, owner, project.id, ChatSessionProjectVisibility.PRIVATE
    )
    shared = _thread(
        db_session, tracked, owner, project.id, ChatSessionProjectVisibility.SHARED
    )

    # Column round-trips through the DB.
    db_session.expire_all()
    assert (
        db_session.get(ChatSession, private.id).project_visibility
        == ChatSessionProjectVisibility.PRIVATE
    )
    assert (
        db_session.get(ChatSession, shared.id).project_visibility
        == ChatSessionProjectVisibility.SHARED
    )

    # Owner sees both of their own threads.
    assert is_chat_session_visible_in_project(private, owner.id)
    assert is_chat_session_visible_in_project(shared, owner.id)
    # A peer sees the SHARED one but NEVER the PRIVATE one.
    assert not is_chat_session_visible_in_project(private, peer.id)
    assert is_chat_session_visible_in_project(shared, peer.id)


def test_setter_is_owner_only(db_session: Session, tracked: _Tracked) -> None:
    owner = create_test_user(db_session, "vis_setowner")
    peer = create_test_user(db_session, "vis_setpeer")
    tracked.user_ids.extend([owner.id, peer.id])
    project = UserProject(user_id=owner.id, name="Space", instructions="")
    db_session.add(project)
    db_session.commit()
    tracked.project_ids.append(project.id)
    session = _thread(
        db_session, tracked, owner, project.id, ChatSessionProjectVisibility.PRIVATE
    )

    # Owner can share it.
    set_chat_session_project_visibility(
        chat_session_id=session.id,
        visibility=ChatSessionProjectVisibility.SHARED,
        user_id=owner.id,
        db_session=db_session,
    )
    db_session.expire_all()
    assert (
        db_session.get(ChatSession, session.id).project_visibility
        == ChatSessionProjectVisibility.SHARED
    )

    # A non-owner cannot toggle another member's thread (ownership enforced).
    with pytest.raises(ValueError):
        set_chat_session_project_visibility(
            chat_session_id=session.id,
            visibility=ChatSessionProjectVisibility.PRIVATE,
            user_id=peer.id,
            db_session=db_session,
        )


def test_column_default_is_stored_in_the_form_the_orm_can_load(
    db_session: Session,
) -> None:
    """The database default must be an enum NAME.

    `Enum(..., native_enum=False)` persists the member name, so a default
    written as the lowercase value loads fine for freshly inserted rows while
    every pre-existing row raises on read. Pinning the stored form here catches
    that mismatch instead of letting it surface as a 500 on older data.
    """
    column_default = db_session.execute(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'chat_session' "
            "AND column_name = 'project_visibility'"
        )
    ).scalar_one()

    stored = column_default.split("::")[0].strip().strip("'")
    assert stored in ChatSessionProjectVisibility.__members__
