"""F5 member-management guard: contributor cap on space shares."""

import pytest
from sqlalchemy.orm import Session

from onyx.db.enums import ProjectSharePermission
from onyx.db.models import User
from onyx.db.models import UserProject
from onyx.db.projects import MAX_PROJECT_CONTRIBUTORS
from onyx.db.projects import replace_project_shares
from onyx.error_handling.exceptions import OnyxError
from tests.external_dependency_unit.conftest import create_test_user


def test_contributor_cap_rejected(db_session: Session) -> None:
    owner = create_test_user(db_session, "cap_owner")
    project = UserProject(user_id=owner.id, name="S", instructions="")
    db_session.add(project)
    db_session.commit()
    try:
        # Over the cap by group shares — the guard fires before any FK flush,
        # so fake group ids are fine.
        over = {
            i: ProjectSharePermission.VIEWER
            for i in range(1, MAX_PROJECT_CONTRIBUTORS + 2)
        }
        with pytest.raises(OnyxError):
            replace_project_shares(
                project=project,
                organization_permission=None,
                user_shares={},
                group_shares=over,
                db_session=db_session,
            )
    finally:
        db_session.rollback()
        db_session.query(UserProject).filter(UserProject.id == project.id).delete(
            synchronize_session=False
        )
        db_session.query(User).filter(User.id == owner.id).delete(
            synchronize_session=False
        )
        db_session.commit()


def test_within_cap_shares_ok(db_session: Session) -> None:
    owner = create_test_user(db_session, "cap_owner2")
    peer = create_test_user(db_session, "cap_peer")
    project = UserProject(user_id=owner.id, name="S", instructions="")
    db_session.add(project)
    db_session.commit()
    try:
        replace_project_shares(
            project=project,
            organization_permission=None,
            user_shares={peer.id: ProjectSharePermission.VIEWER},
            group_shares={},
            db_session=db_session,
        )
        db_session.commit()
        db_session.refresh(project)
        assert len(project.user_shares) == 1
        assert project.user_shares[0].user_id == peer.id
    finally:
        db_session.query(UserProject).filter(UserProject.id == project.id).delete(
            synchronize_session=False
        )
        db_session.query(User).filter(User.id.in_([owner.id, peer.id])).delete(
            synchronize_session=False
        )
        db_session.commit()
