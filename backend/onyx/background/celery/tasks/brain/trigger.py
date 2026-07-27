"""Rate-limited enqueue for per-user brain runs.

A brain run is an LLM extraction pass over the user's recent sessions, so it is
expensive enough that it must never be queued twice for overlapping reasons.
Every caller — the manual "refresh now" endpoint and the automatic post-chat
trigger — routes through :func:`queue_brain_run_for_user`, which shares one
Redis guard so a passive run and a manual one cannot both be in flight.
"""

from uuid import UUID

from onyx.configs.constants import OnyxCeleryPriority
from onyx.configs.constants import OnyxCeleryQueues
from onyx.configs.constants import OnyxCeleryTask
from onyx.redis.redis_pool import get_redis_client
from onyx.utils.logger import setup_logger

logger = setup_logger()

# Manual refreshes are user-visible, so they get a short cooldown. The passive
# post-chat trigger fires on every turn, so it waits much longer between runs —
# a busy conversation would otherwise spend an LLM extraction pass per message.
BRAIN_MANUAL_RUN_COOLDOWN_SECONDS = 5 * 60
BRAIN_PASSIVE_RUN_COOLDOWN_SECONDS = 15 * 60

# Bound on how long a queued run may sit before the worker drops it. Past this
# the session content it would extract from is better handled by the next run.
BRAIN_RUN_TASK_EXPIRES_SECONDS = 60 * 60

_BRAIN_RUN_GUARD_PREFIX = "brain_run:"


def queue_brain_run_for_user(
    *,
    user_id: UUID,
    tenant_id: str,
    cooldown_seconds: int,
) -> bool:
    """Queue a brain run for *user_id* unless one ran inside the cooldown.

    :param user_id: Owner of the memories the run would update.
    :param tenant_id: Tenant schema the task should execute against.
    :param cooldown_seconds: How long this run suppresses the next one.
    :returns: ``True`` when the task was sent, ``False`` when the guard
        rejected it because a run is already queued or recently finished.
    """
    redis_client = get_redis_client(tenant_id=tenant_id)
    # NX+EX = atomic dedupe (a queued-but-unstarted run can't be double-queued)
    # and cooldown in one call.
    guard_set = redis_client.set(
        f"{_BRAIN_RUN_GUARD_PREFIX}{user_id}",
        1,
        nx=True,
        ex=cooldown_seconds,
    )
    if not guard_set:
        return False

    # Imported lazily: the client app pulls in the Celery config, which the
    # request path should not pay for until a task is actually sent.
    from onyx.background.celery.versioned_apps.client import app as client_app

    client_app.send_task(
        OnyxCeleryTask.BRAIN_SELF_IMPROVEMENT_USER,
        kwargs={"user_id": str(user_id), "tenant_id": tenant_id},
        queue=OnyxCeleryQueues.PRIMARY,
        priority=OnyxCeleryPriority.HIGH,
        expires=BRAIN_RUN_TASK_EXPIRES_SECONDS,
    )
    return True
