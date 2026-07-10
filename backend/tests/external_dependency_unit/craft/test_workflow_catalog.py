from sqlalchemy.orm import Session

from onyx.db.models import User
from onyx.db.workflow_catalog import list_workflow_pins
from onyx.db.workflow_catalog import pin_workflow
from onyx.db.workflow_catalog import unpin_workflow
from tests.external_dependency_unit.craft.db_helpers import make_user


def test_workflow_pins_are_user_scoped(
    db_session: Session,
    test_user: User,
) -> None:
    other_user = make_user(db_session)

    pin_workflow(test_user.id, "compliance-monitor", db_session=db_session)
    pin_workflow(test_user.id, "final-pass", db_session=db_session)

    assert list_workflow_pins(test_user.id, db_session=db_session) == [
        "final-pass",
        "compliance-monitor",
    ]
    assert list_workflow_pins(other_user.id, db_session=db_session) == []

    unpin_workflow(test_user.id, "final-pass", db_session=db_session)
    assert list_workflow_pins(test_user.id, db_session=db_session) == [
        "compliance-monitor"
    ]
