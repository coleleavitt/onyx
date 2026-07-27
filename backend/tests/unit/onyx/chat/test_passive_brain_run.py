"""Gating for the post-turn brain run queued from a finished chat turn."""

from contextlib import contextmanager
from typing import Iterator
from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

from onyx.chat.process_message import _queue_passive_brain_run


@contextmanager
def _hooks(
    *,
    creation_allowed: bool,
    brain_enabled: bool,
    queue: MagicMock,
) -> Iterator[None]:
    @contextmanager
    def _fake_session() -> Iterator[MagicMock]:
        yield MagicMock()

    with (
        patch(
            "onyx.chat.process_message.get_session_with_current_tenant",
            _fake_session,
        ),
        patch(
            "onyx.chat.process_message.is_memory_creation_allowed",
            return_value=creation_allowed,
        ),
        patch(
            "onyx.chat.process_message.is_brain_enabled_for_user",
            return_value=brain_enabled,
        ),
        patch("onyx.chat.process_message.get_current_tenant_id", return_value="t"),
        patch("onyx.chat.process_message.queue_brain_run_for_user", queue),
    ):
        yield


def test_queues_a_run_for_a_brain_enabled_user() -> None:
    queue = MagicMock(return_value=True)
    user_id = uuid4()

    with _hooks(creation_allowed=True, brain_enabled=True, queue=queue):
        _queue_passive_brain_run(user_id)

    queue.assert_called_once()
    assert queue.call_args.kwargs["user_id"] == user_id
    assert queue.call_args.kwargs["tenant_id"] == "t"


def test_skips_when_the_org_disabled_memory_creation() -> None:
    queue = MagicMock()

    with _hooks(creation_allowed=False, brain_enabled=True, queue=queue):
        _queue_passive_brain_run(uuid4())

    queue.assert_not_called()


def test_skips_when_the_user_has_not_enabled_brain() -> None:
    queue = MagicMock()

    with _hooks(creation_allowed=True, brain_enabled=False, queue=queue):
        _queue_passive_brain_run(uuid4())

    queue.assert_not_called()


def test_skips_an_anonymous_turn() -> None:
    """An anonymous turn has no user to attach memories to."""
    queue = MagicMock()

    with _hooks(creation_allowed=True, brain_enabled=True, queue=queue):
        _queue_passive_brain_run(None)

    queue.assert_not_called()


def test_a_broken_queue_never_fails_the_chat_turn() -> None:
    """The turn already answered the user; a follow-up must not surface as an error."""
    queue = MagicMock(side_effect=RuntimeError("redis is down"))

    with _hooks(creation_allowed=True, brain_enabled=True, queue=queue):
        _queue_passive_brain_run(uuid4())  # must not raise
