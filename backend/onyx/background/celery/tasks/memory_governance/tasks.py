from celery import shared_task

from onyx.background.celery.apps.app_base import task_logger
from onyx.configs.constants import OnyxCeleryTask
from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.memory import delete_expired_memories
from onyx.utils.audit import AuditAction
from onyx.utils.audit import AuditOutcome
from onyx.utils.audit import emit_audit_event


@shared_task(name=OnyxCeleryTask.MEMORY_RETENTION_CLEANUP)
def memory_retention_cleanup() -> int:
    with get_session_with_current_tenant() as db_session:
        affected_count = delete_expired_memories(db_session=db_session)

    if affected_count > 0:
        emit_audit_event(
            AuditAction.MEMORY_RETENTION_CLEANUP,
            AuditOutcome.SUCCESS,
            resource_type="memory",
            extra={
                "scope": "expired",
                "trigger": "scheduled",
                "affected_count": affected_count,
            },
        )
        task_logger.info("Memory retention cleanup deleted %s rows", affected_count)
    return affected_count
