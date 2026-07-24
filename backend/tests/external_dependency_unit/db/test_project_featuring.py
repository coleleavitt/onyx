"""F2 featured-space surfacing, verified against the real DB.

Featuring auto-surfaces a space to entitled members, but grants NO access: a
space featured to a group is only surfaced to a member when the space is also
shared with that group. A space featured-but-unshared is never surfaced.
"""

from collections.abc import Generator

import pytest
from sqlalchemy.orm import Session

from onyx.db.enums import ProjectSharePermission
from onyx.db.models import Project__UserGroup
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.models import UserGroup
from onyx.db.models import UserProject
from onyx.db.projects import get_featured_project_ids_for_user
from onyx.db.projects import set_project_featuring
from tests.external_dependency_unit.conftest import create_test_user


class _Tracked:
    def __init__(self) -> None:
        self.user_ids: list = []
        self.group_ids: list[int] = []
        self.project_ids: list[int] = []


@pytest.fixture
def tracked(db_session: Session) -> Generator[_Tracked, None, None]:
    t = _Tracked()
    yield t
    if t.project_ids:
        db_session.query(Project__UserGroup).filter(
            Project__UserGroup.project_id.in_(t.project_ids)
        ).delete(synchronize_session=False)
        db_session.query(UserProject).filter(UserProject.id.in_(t.project_ids)).delete(
            synchronize_session=False
        )
    if t.group_ids:
        db_session.query(User__UserGroup).filter(
            User__UserGroup.user_group_id.in_(t.group_ids)
        ).delete(synchronize_session=False)
        db_session.query(UserGroup).filter(UserGroup.id.in_(t.group_ids)).delete(
            synchronize_session=False
        )
    if t.user_ids:
        db_session.query(User).filter(User.id.in_(t.user_ids)).delete(
            synchronize_session=False
        )
    db_session.commit()


def test_featuring_surfaces_only_accessible_spaces_and_grants_no_access(
    db_session: Session, tracked: _Tracked
) -> None:
    owner = create_test_user(db_session, "feat_owner")
    member = create_test_user(db_session, "feat_member")
    outsider = create_test_user(db_session, "feat_outsider")
    tracked.user_ids.extend([owner.id, member.id, outsider.id])

    group = UserGroup(name=f"Dept {owner.email[:8]}")
    db_session.add(group)
    db_session.commit()
    tracked.group_ids.append(group.id)
    db_session.add(
        User__UserGroup(user_id=member.id, user_group_id=group.id, is_curator=False)
    )
    db_session.commit()

    # Space A: shared with the group (accessible) AND featured to it.
    shared_space = UserProject(user_id=owner.id, name="Shared", instructions="")
    # Space B: featured to the group but NOT shared (no access).
    unshared_space = UserProject(user_id=owner.id, name="Unshared", instructions="")
    db_session.add_all([shared_space, unshared_space])
    db_session.commit()
    tracked.project_ids.extend([shared_space.id, unshared_space.id])

    db_session.add(
        Project__UserGroup(
            project_id=shared_space.id,
            user_group_id=group.id,
            permission=ProjectSharePermission.VIEWER,
        )
    )
    db_session.commit()

    for space in (shared_space, unshared_space):
        set_project_featuring(
            project_id=space.id,
            is_org_featured=False,
            featured_for_group_id=group.id,
            db_session=db_session,
        )

    member_featured = get_featured_project_ids_for_user(
        user=member, db_session=db_session
    )
    outsider_featured = get_featured_project_ids_for_user(
        user=outsider, db_session=db_session
    )

    # The member sees the shared+featured space surfaced...
    assert shared_space.id in member_featured
    # ...but the featured-but-unshared space is NOT surfaced (featuring != access).
    assert unshared_space.id not in member_featured
    # A non-member sees neither.
    assert outsider_featured == set()


def test_org_featured_surfaces_only_to_accessible_users(
    db_session: Session, tracked: _Tracked
) -> None:
    owner = create_test_user(db_session, "feat_orgowner")
    other = create_test_user(db_session, "feat_orgother")
    tracked.user_ids.extend([owner.id, other.id])

    # Org-featured but personal (owner-only) space: not accessible to `other`,
    # so org-featuring alone must not surface it to them.
    space = UserProject(user_id=owner.id, name="OrgFeatured", instructions="")
    db_session.add(space)
    db_session.commit()
    tracked.project_ids.append(space.id)
    set_project_featuring(
        project_id=space.id,
        is_org_featured=True,
        featured_for_group_id=None,
        db_session=db_session,
    )

    # Owner (has access) sees it; the other user (no access) does not.
    assert space.id in get_featured_project_ids_for_user(
        user=owner, db_session=db_session
    )
    assert space.id not in get_featured_project_ids_for_user(
        user=other, db_session=db_session
    )
