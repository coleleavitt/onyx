"""Oversight scoping rules for the query-history surface.

Encodes the reported requirements: oversight is granted per group rather than
globally, an excluded tier stays private from everyone including admins, and a
delegated overseer only observes real, active accounts in the groups they
curate.
"""

from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from ee.onyx.db.oversight import can_oversee_user
from ee.onyx.db.oversight import oversight_chat_session_condition
from onyx.auth.schemas import UserRole
from onyx.db.chat import create_chat_session
from onyx.db.enums import Permission
from onyx.db.models import ChatSession
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.models import UserGroup
from tests.external_dependency_unit.conftest import create_test_user


class _Tracked:
    def __init__(self) -> None:
        self.user_ids: list = []
        self.group_ids: list[int] = []
        self.session_ids: list = []


@pytest.fixture
def tracked(db_session: Session) -> Generator[_Tracked, None, None]:
    t = _Tracked()
    yield t
    if t.session_ids:
        db_session.query(ChatSession).filter(ChatSession.id.in_(t.session_ids)).delete(
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


def _user(
    db_session: Session,
    tracked: _Tracked,
    prefix: str,
    *,
    role: UserRole = UserRole.BASIC,
    permissions: list[Permission] | None = None,
    is_active: bool = True,
) -> User:
    user = create_test_user(db_session, prefix, role=role)
    user.effective_permissions = [p.value for p in (permissions or [])]
    user.is_active = is_active
    db_session.commit()
    tracked.user_ids.append(user.id)
    return user


def _group(
    db_session: Session,
    tracked: _Tracked,
    name: str,
    *,
    excluded_from_oversight: bool = False,
) -> UserGroup:
    group = UserGroup(
        name=f"{name} {uuid4().hex[:8]}",
        excluded_from_oversight=excluded_from_oversight,
    )
    db_session.add(group)
    db_session.commit()
    tracked.group_ids.append(group.id)
    return group


def _add_member(
    db_session: Session, user: User, group: UserGroup, *, is_curator: bool = False
) -> None:
    db_session.add(
        User__UserGroup(user_id=user.id, user_group_id=group.id, is_curator=is_curator)
    )
    db_session.commit()


def _session_for(
    db_session: Session, tracked: _Tracked, owner: User | None
) -> ChatSession:
    session = create_chat_session(
        db_session=db_session,
        description="oversight fixture",
        user_id=owner.id if owner else None,
        persona_id=None,
    )
    tracked.session_ids.append(session.id)
    return session


def _visible_session_ids(db_session: Session, overseer: User | None) -> set:
    stmt = select(ChatSession.id).where(oversight_chat_session_condition(overseer))
    return set(db_session.scalars(stmt).all())


def test_excluded_tier_is_invisible_even_to_an_admin(
    db_session: Session, tracked: _Tracked
) -> None:
    """The executive tier stays private from everyone, admins included."""
    admin = _user(
        db_session,
        tracked,
        "ovs_admin",
        role=UserRole.ADMIN,
        permissions=[Permission.FULL_ADMIN_PANEL_ACCESS],
    )
    executive = _user(db_session, tracked, "ovs_exec")
    staff = _user(db_session, tracked, "ovs_staff")

    leadership = _group(db_session, tracked, "Leadership", excluded_from_oversight=True)
    _add_member(db_session, executive, leadership)

    exec_session = _session_for(db_session, tracked, executive)
    staff_session = _session_for(db_session, tracked, staff)

    visible = _visible_session_ids(db_session, admin)
    assert staff_session.id in visible
    assert exec_session.id not in visible

    assert can_oversee_user(admin, staff.id, db_session)
    assert not can_oversee_user(admin, executive.id, db_session)


def test_delegated_overseer_sees_only_their_curated_group(
    db_session: Session, tracked: _Tracked
) -> None:
    overseer = _user(
        db_session,
        tracked,
        "ovs_curator",
        role=UserRole.CURATOR,
        permissions=[Permission.READ_QUERY_HISTORY],
    )
    report = _user(db_session, tracked, "ovs_report")
    outsider = _user(db_session, tracked, "ovs_outsider")

    curated = _group(db_session, tracked, "Advisor Services")
    other = _group(db_session, tracked, "Compliance")
    _add_member(db_session, overseer, curated, is_curator=True)
    _add_member(db_session, report, curated)
    _add_member(db_session, outsider, other)

    report_session = _session_for(db_session, tracked, report)
    outsider_session = _session_for(db_session, tracked, outsider)

    visible = _visible_session_ids(db_session, overseer)
    assert report_session.id in visible
    assert outsider_session.id not in visible

    assert can_oversee_user(overseer, report.id, db_session)
    assert not can_oversee_user(overseer, outsider.id, db_session)


def test_excluded_tier_is_invisible_to_a_delegated_overseer_in_the_same_group(
    db_session: Session, tracked: _Tracked
) -> None:
    """Exclusion outranks curation: curating a group does not expose an
    excluded member who happens to be in it."""
    overseer = _user(
        db_session,
        tracked,
        "ovs_c2",
        role=UserRole.CURATOR,
        permissions=[Permission.READ_QUERY_HISTORY],
    )
    executive = _user(db_session, tracked, "ovs_exec2")

    curated = _group(db_session, tracked, "Shared")
    leadership = _group(db_session, tracked, "Execs", excluded_from_oversight=True)
    _add_member(db_session, overseer, curated, is_curator=True)
    _add_member(db_session, executive, curated)
    _add_member(db_session, executive, leadership)

    exec_session = _session_for(db_session, tracked, executive)

    assert exec_session.id not in _visible_session_ids(db_session, overseer)
    assert not can_oversee_user(overseer, executive.id, db_session)


def test_delegated_overseer_skips_inactive_and_non_login_accounts(
    db_session: Session, tracked: _Tracked
) -> None:
    """Only real, active accounts on this platform are observable."""
    overseer = _user(
        db_session,
        tracked,
        "ovs_c3",
        role=UserRole.CURATOR,
        permissions=[Permission.READ_QUERY_HISTORY],
    )
    inactive = _user(db_session, tracked, "ovs_inactive", is_active=False)
    slack_only = _user(db_session, tracked, "ovs_slack", role=UserRole.SLACK_USER)
    external = _user(db_session, tracked, "ovs_ext", role=UserRole.EXT_PERM_USER)
    real = _user(db_session, tracked, "ovs_real")

    curated = _group(db_session, tracked, "Team")
    _add_member(db_session, overseer, curated, is_curator=True)
    for member in (inactive, slack_only, external, real):
        _add_member(db_session, member, curated)

    assert can_oversee_user(overseer, real.id, db_session)
    for hidden in (inactive, slack_only, external):
        assert not can_oversee_user(overseer, hidden.id, db_session)


def test_ownerless_sessions_are_admin_only(
    db_session: Session, tracked: _Tracked
) -> None:
    """An anonymous session has no owner to scope against, so it stays with
    unrestricted overseers rather than silently vanishing."""
    admin = _user(
        db_session,
        tracked,
        "ovs_admin2",
        role=UserRole.ADMIN,
        permissions=[Permission.FULL_ADMIN_PANEL_ACCESS],
    )
    overseer = _user(
        db_session,
        tracked,
        "ovs_c4",
        role=UserRole.CURATOR,
        permissions=[Permission.READ_QUERY_HISTORY],
    )
    curated = _group(db_session, tracked, "Team")
    _add_member(db_session, overseer, curated, is_curator=True)

    anonymous_session = _session_for(db_session, tracked, None)

    assert anonymous_session.id in _visible_session_ids(db_session, admin)
    assert anonymous_session.id not in _visible_session_ids(db_session, overseer)
    assert can_oversee_user(admin, None, db_session)
    assert not can_oversee_user(overseer, None, db_session)
