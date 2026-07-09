from unittest.mock import MagicMock

from onyx.background.indexing.run_docfetching import _enqueue_docprocessing_task
from onyx.configs.constants import CELERY_DOCPROCESSING_TASK_EXPIRES
from onyx.configs.constants import OnyxCeleryPriority
from onyx.configs.constants import OnyxCeleryQueues
from onyx.configs.constants import OnyxCeleryTask


def test_enqueue_docprocessing_task_sets_expiry() -> None:
    app = MagicMock()
    payload: dict[str, int | str] = {
        "index_attempt_id": 7,
        "cc_pair_id": 2,
        "tenant_id": "public",
        "batch_num": 12,
        "enqueue_time_ms": 123456789,
    }

    _enqueue_docprocessing_task(app, payload, OnyxCeleryPriority.MEDIUM)

    app.send_task.assert_called_once_with(
        OnyxCeleryTask.DOCPROCESSING_TASK,
        kwargs=payload,
        queue=OnyxCeleryQueues.DOCPROCESSING,
        priority=OnyxCeleryPriority.MEDIUM,
        expires=CELERY_DOCPROCESSING_TASK_EXPIRES,
    )
