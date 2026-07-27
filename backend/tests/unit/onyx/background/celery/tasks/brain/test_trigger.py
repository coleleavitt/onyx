"""Guard behavior for the shared per-user brain-run trigger."""

from unittest.mock import MagicMock
from unittest.mock import patch
from uuid import uuid4

from onyx.background.celery.tasks.brain.trigger import (
    BRAIN_PASSIVE_RUN_COOLDOWN_SECONDS,
)
from onyx.background.celery.tasks.brain.trigger import BRAIN_RUN_TASK_EXPIRES_SECONDS
from onyx.background.celery.tasks.brain.trigger import queue_brain_run_for_user
from onyx.configs.constants import OnyxCeleryTask


def _patched(guard_set: bool) -> tuple[MagicMock, MagicMock]:
    """Return (redis_client, celery_app) mocks with the guard forced."""
    redis_client = MagicMock()
    redis_client.set.return_value = guard_set
    celery_app = MagicMock()
    return redis_client, celery_app


def test_queues_task_when_guard_is_free() -> None:
    redis_client, celery_app = _patched(guard_set=True)
    user_id = uuid4()

    with (
        patch(
            "onyx.background.celery.tasks.brain.trigger.get_redis_client",
            return_value=redis_client,
        ),
        patch(
            "onyx.background.celery.versioned_apps.client.app",
            celery_app,
        ),
    ):
        queued = queue_brain_run_for_user(
            user_id=user_id, tenant_id="tenant-a", cooldown_seconds=42
        )

    assert queued is True
    celery_app.send_task.assert_called_once()
    args, kwargs = celery_app.send_task.call_args
    assert args[0] == OnyxCeleryTask.BRAIN_SELF_IMPROVEMENT_USER
    assert kwargs["kwargs"] == {"user_id": str(user_id), "tenant_id": "tenant-a"}
    # An unbounded queue is how a stalled worker turns into unbounded backlog.
    assert kwargs["expires"] == BRAIN_RUN_TASK_EXPIRES_SECONDS


def test_guard_is_set_atomically_with_the_cooldown() -> None:
    redis_client, celery_app = _patched(guard_set=True)
    user_id = uuid4()

    with (
        patch(
            "onyx.background.celery.tasks.brain.trigger.get_redis_client",
            return_value=redis_client,
        ),
        patch("onyx.background.celery.versioned_apps.client.app", celery_app),
    ):
        queue_brain_run_for_user(
            user_id=user_id, tenant_id="tenant-a", cooldown_seconds=42
        )

    # NX+EX in one call: a check-then-set would let two turns finishing at once
    # both queue a run.
    _, set_kwargs = redis_client.set.call_args
    assert set_kwargs["nx"] is True
    assert set_kwargs["ex"] == 42
    assert str(user_id) in redis_client.set.call_args[0][0]


def test_does_not_queue_while_a_run_is_in_the_cooldown() -> None:
    redis_client, celery_app = _patched(guard_set=False)

    with (
        patch(
            "onyx.background.celery.tasks.brain.trigger.get_redis_client",
            return_value=redis_client,
        ),
        patch("onyx.background.celery.versioned_apps.client.app", celery_app),
    ):
        queued = queue_brain_run_for_user(
            user_id=uuid4(), tenant_id="tenant-a", cooldown_seconds=42
        )

    assert queued is False
    celery_app.send_task.assert_not_called()


def test_manual_and_passive_paths_share_one_guard_key() -> None:
    """A passive run must suppress a manual one and vice versa."""
    redis_client, celery_app = _patched(guard_set=True)
    user_id = uuid4()

    with (
        patch(
            "onyx.background.celery.tasks.brain.trigger.get_redis_client",
            return_value=redis_client,
        ),
        patch("onyx.background.celery.versioned_apps.client.app", celery_app),
    ):
        queue_brain_run_for_user(user_id=user_id, tenant_id="t", cooldown_seconds=300)
        queue_brain_run_for_user(
            user_id=user_id,
            tenant_id="t",
            cooldown_seconds=BRAIN_PASSIVE_RUN_COOLDOWN_SECONDS,
        )

    manual_key = redis_client.set.call_args_list[0][0][0]
    passive_key = redis_client.set.call_args_list[1][0][0]
    assert manual_key == passive_key
