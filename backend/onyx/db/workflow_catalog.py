from uuid import UUID

from sqlalchemy import delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.db.models import WorkflowPin


def list_workflow_pins(user_id: UUID, *, db_session: Session) -> list[str]:
    return list(
        db_session.scalars(
            select(WorkflowPin.workflow_id)
            .where(WorkflowPin.user_id == user_id)
            .order_by(WorkflowPin.created_at.desc())
        )
    )


def pin_workflow(
    user_id: UUID,
    workflow_id: str,
    *,
    db_session: Session,
) -> None:
    existing = db_session.get(WorkflowPin, (user_id, workflow_id))
    if existing is None:
        db_session.add(WorkflowPin(user_id=user_id, workflow_id=workflow_id))
        db_session.commit()


def unpin_workflow(
    user_id: UUID,
    workflow_id: str,
    *,
    db_session: Session,
) -> None:
    db_session.execute(
        delete(WorkflowPin).where(
            WorkflowPin.user_id == user_id,
            WorkflowPin.workflow_id == workflow_id,
        )
    )
    db_session.commit()
