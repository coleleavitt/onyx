from typing import Annotated
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Path
from sqlalchemy.orm import Session

from onyx.auth.permissions import require_permission
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import Permission
from onyx.db.models import User
from onyx.db.workflow_catalog import list_workflow_pins
from onyx.db.workflow_catalog import pin_workflow
from onyx.db.workflow_catalog import unpin_workflow
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.features.build.workflow_catalog.models import WorkflowPinsResponse

router = APIRouter(prefix="/workflow-catalog")


def _user_id(user: User) -> UUID:
    if user.id is None:
        raise OnyxError(OnyxErrorCode.UNAUTHENTICATED)
    return user.id


@router.get("/pins")
def get_current_user_workflow_pins(
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> WorkflowPinsResponse:
    return WorkflowPinsResponse(
        workflow_ids=list_workflow_pins(_user_id(user), db_session=db_session)
    )


@router.put("/pins/{workflow_id}")
def pin_current_user_workflow(
    workflow_id: Annotated[str, Path(min_length=1, max_length=128)],
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> WorkflowPinsResponse:
    pin_workflow(_user_id(user), workflow_id, db_session=db_session)
    return WorkflowPinsResponse(
        workflow_ids=list_workflow_pins(_user_id(user), db_session=db_session)
    )


@router.delete("/pins/{workflow_id}")
def unpin_current_user_workflow(
    workflow_id: Annotated[str, Path(min_length=1, max_length=128)],
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    unpin_workflow(_user_id(user), workflow_id, db_session=db_session)
