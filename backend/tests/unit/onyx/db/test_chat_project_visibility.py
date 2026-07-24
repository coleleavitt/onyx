"""Per-thread space-visibility matrix (F1).

`is_chat_session_visible_in_project` is the single source of truth for whether a
viewer may see a thread inside a space. The security-critical property: a PRIVATE
thread is never visible to anyone but its owner, while a SHARED thread is visible
to every space member.
"""

from types import SimpleNamespace
from uuid import uuid4

from onyx.db.chat import is_chat_session_visible_in_project
from onyx.db.enums import ChatSessionProjectVisibility


def _thread(owner_id: object, visibility: ChatSessionProjectVisibility) -> object:
    return SimpleNamespace(user_id=owner_id, project_visibility=visibility)


def test_owner_sees_own_private_and_shared_threads() -> None:
    owner = uuid4()
    assert is_chat_session_visible_in_project(
        _thread(owner, ChatSessionProjectVisibility.PRIVATE), owner
    )
    assert is_chat_session_visible_in_project(
        _thread(owner, ChatSessionProjectVisibility.SHARED), owner
    )


def test_peer_sees_shared_but_never_private() -> None:
    owner = uuid4()
    peer = uuid4()
    # Security-critical: a peer must NOT see another member's PRIVATE thread.
    assert not is_chat_session_visible_in_project(
        _thread(owner, ChatSessionProjectVisibility.PRIVATE), peer
    )
    # A thread explicitly shared to the space is visible to the peer.
    assert is_chat_session_visible_in_project(
        _thread(owner, ChatSessionProjectVisibility.SHARED), peer
    )


def test_admin_or_no_auth_sees_everything() -> None:
    owner = uuid4()
    assert is_chat_session_visible_in_project(
        _thread(owner, ChatSessionProjectVisibility.PRIVATE), None
    )
    assert is_chat_session_visible_in_project(
        _thread(owner, ChatSessionProjectVisibility.SHARED), None
    )
