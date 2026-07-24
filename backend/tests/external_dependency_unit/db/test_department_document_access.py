"""Regression tests for department-based document access control.

Documents are gated by "department" when a PRIVATE connector is linked to an
Onyx user_group: only members of that group inherit the connector's documents.

The second test pins the multi-homing hazard that silently defeats isolation in
the real world: a document indexed under ANY PUBLIC connector becomes public to
everyone, regardless of the private per-department connectors it also belongs to
(exactly the SharePoint config observed live — a company-wide public connector
overlapping the per-department ones).
"""

from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

# Call the EE implementations directly: the versioned `onyx.access.access`
# wrappers can resolve to the MIT (no-groups) variant inside the test process,
# which would silently skip the group ACL this suite exercises.
from ee.onyx.access.access import _get_access_for_documents as get_access_for_documents
from ee.onyx.access.access import _get_acl_for_user as get_acl_for_user
from onyx.access.models import DocumentAccess
from onyx.configs.constants import PUBLIC_DOC_PAT
from onyx.db.enums import AccessType
from onyx.db.models import ConnectorCredentialPair
from onyx.db.models import DocumentByConnectorCredentialPair
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.models import UserGroup
from onyx.db.models import UserGroup__ConnectorCredentialPair
from tests.external_dependency_unit.conftest import create_test_user
from tests.external_dependency_unit.indexing_helpers import cleanup_cc_pair
from tests.external_dependency_unit.indexing_helpers import make_cc_pair
from tests.external_dependency_unit.indexing_helpers import seed_cc_pair_documents


class _Tracked:
    def __init__(self) -> None:
        self.cc_pairs: list[ConnectorCredentialPair] = []
        self.group_ids: list[int] = []
        self.user_ids: list = []


@pytest.fixture
def tracked(db_session: Session) -> Generator[_Tracked, None, None]:
    """Track every row the test creates so teardown removes exactly those,
    leaving the shared dev/CI database clean (these tests commit to a real DB)."""
    t = _Tracked()
    yield t
    # Drop the group<->cc_pair links first: they FK to connector_credential_pair,
    # so cleanup_cc_pair() would otherwise hit a foreign-key violation.
    if t.group_ids:
        db_session.query(UserGroup__ConnectorCredentialPair).filter(
            UserGroup__ConnectorCredentialPair.user_group_id.in_(t.group_ids)
        ).delete(synchronize_session=False)
        db_session.commit()
    for pair in t.cc_pairs:
        # Removes the cc_pair's doc links and drops any doc with no remaining
        # references — safe for docs multi-homed across the test's cc_pairs.
        cleanup_cc_pair(db_session, pair)
    if t.group_ids:
        db_session.query(User__UserGroup).filter(
            User__UserGroup.user_group_id.in_(t.group_ids)
        ).delete(synchronize_session=False)
        db_session.query(UserGroup).filter(UserGroup.id.in_(t.group_ids)).delete(
            synchronize_session=False
        )
    if t.user_ids:
        db_session.query(User__UserGroup).filter(
            User__UserGroup.user_id.in_(t.user_ids)
        ).delete(synchronize_session=False)
        db_session.query(User).filter(User.id.in_(t.user_ids)).delete(
            synchronize_session=False
        )
    db_session.commit()


def _make_group(db_session: Session, tracked: _Tracked, name: str) -> UserGroup:
    group = UserGroup(
        name=f"{name}-{uuid4().hex[:8]}",
        is_up_to_date=True,
        is_up_for_deletion=False,
        is_default=False,
    )
    db_session.add(group)
    db_session.flush()
    tracked.group_ids.append(group.id)
    return group


def _private_connector_for_group(
    db_session: Session, tracked: _Tracked, group: UserGroup
) -> ConnectorCredentialPair:
    pair = make_cc_pair(db_session, commit=False)
    pair.access_type = AccessType.PRIVATE
    db_session.add(
        UserGroup__ConnectorCredentialPair(
            user_group_id=group.id, cc_pair_id=pair.id, is_current=True
        )
    )
    db_session.commit()
    tracked.cc_pairs.append(pair)
    return pair


def _grants(user_acl: set[str], doc_access: DocumentAccess) -> bool:
    return not user_acl.isdisjoint(doc_access.to_acl())


def test_private_connector_group_isolates_documents_by_department(
    db_session: Session, tracked: _Tracked
) -> None:
    group = _make_group(db_session, tracked, "Advisor Services")
    member = create_test_user(db_session, "dept_member")
    tracked.user_ids.append(member.id)
    outsider = create_test_user(db_session, "dept_outsider")
    tracked.user_ids.append(outsider.id)
    db_session.add(User__UserGroup(user_id=member.id, user_group_id=group.id))
    db_session.commit()

    cc = _private_connector_for_group(db_session, tracked, group)
    doc_ids = seed_cc_pair_documents(
        db_session, cc, 3, prefix=f"dept-{uuid4().hex[:6]}-"
    )

    access = get_access_for_documents(doc_ids, db_session)
    member_acl = get_acl_for_user(member, db_session)
    outsider_acl = get_acl_for_user(outsider, db_session)

    # Each doc's ACL carries the department group and is NOT public.
    for doc_access in access.values():
        acl = doc_access.to_acl()
        assert any(entry.startswith("group:") for entry in acl)
        assert PUBLIC_DOC_PAT not in acl

    # Only the group member inherits the department's documents.
    assert all(_grants(member_acl, a) for a in access.values())
    assert not any(_grants(outsider_acl, a) for a in access.values())


def test_public_multi_homed_connector_defeats_department_isolation(
    db_session: Session, tracked: _Tracked
) -> None:
    group = _make_group(db_session, tracked, "Advisor Services")
    outsider = create_test_user(db_session, "dept_outsider")
    tracked.user_ids.append(outsider.id)
    db_session.commit()

    private_cc = _private_connector_for_group(db_session, tracked, group)
    doc_ids = seed_cc_pair_documents(
        db_session, private_cc, 2, prefix=f"multi-{uuid4().hex[:6]}-"
    )

    outsider_acl = get_acl_for_user(outsider, db_session)
    isolated = get_access_for_documents(doc_ids, db_session)
    assert not any(_grants(outsider_acl, a) for a in isolated.values())

    # Multi-home the SAME documents into a broad PUBLIC connector.
    public_cc = make_cc_pair(db_session, commit=False)
    public_cc.access_type = AccessType.PUBLIC
    db_session.commit()
    tracked.cc_pairs.append(public_cc)
    for doc_id in doc_ids:
        db_session.add(
            DocumentByConnectorCredentialPair(
                id=doc_id,
                connector_id=public_cc.connector_id,
                credential_id=public_cc.credential_id,
                has_been_indexed=True,
            )
        )
    db_session.commit()

    # The public connector overrides isolation: the docs are now public to
    # everyone, so the outsider gains access despite the private department link.
    leaked = get_access_for_documents(doc_ids, db_session)
    for doc_access in leaked.values():
        assert PUBLIC_DOC_PAT in doc_access.to_acl()
    assert all(_grants(outsider_acl, a) for a in leaked.values())
