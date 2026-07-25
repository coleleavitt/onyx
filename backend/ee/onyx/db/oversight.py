"""Scoping rules for the oversight (query history) surface.

Every query-history read path funnels through this module, so who may observe
whom is decided in exactly one place rather than per endpoint.

Two independent rules apply:

1. Exclusion is absolute. Sessions owned by a member of a group flagged
   ``excluded_from_oversight`` are never returned to anyone, including admins.
   This keeps an executive tier's chats private rather than merely
   admin-gated.
2. Delegated overseers are curator-scoped. Someone holding
   ``READ_QUERY_HISTORY`` without full admin access observes only members of
   the groups they curate, and only real, active accounts on this platform.
"""

from uuid import UUID

from sqlalchemy import and_
from sqlalchemy import ColumnElement
from sqlalchemy import or_
from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy.orm import aliased
from sqlalchemy.orm import Session

from onyx.auth.permissions import get_effective_permissions
from onyx.auth.schemas import UserRole
from onyx.db.enums import Permission
from onyx.db.models import ChatSession
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.models import UserGroup

# Roles that never sign in to the web app, so overseeing them is noise rather
# than supervision.
OVERSIGHT_INELIGIBLE_ROLES = frozenset(
    {
        UserRole.SLACK_USER,
        UserRole.EXT_PERM_USER,
    }
)


def _excluded_user_ids() -> Select:
    return (
        select(User__UserGroup.user_id)
        .join(UserGroup, UserGroup.id == User__UserGroup.user_group_id)
        .where(UserGroup.excluded_from_oversight.is_(True))
        .where(User__UserGroup.user_id.isnot(None))
    )


def _curated_user_ids(overseer_id: UUID) -> Select:
    """Everyone below ``overseer_id`` in the curation tree.

    Oversight follows the reporting line, so it cascades: a director observes
    their managers' reports as well as the managers themselves. The walk starts
    at the groups the overseer curates and repeatedly adds the groups curated
    by anyone already reachable, so depth is not capped. UNION dedupes, which
    also makes a cycle terminate rather than spin.
    """
    reachable_groups = (
        select(User__UserGroup.user_group_id.label("user_group_id"))
        .where(User__UserGroup.user_id == overseer_id)
        .where(User__UserGroup.is_curator.is_(True))
        .cte("reachable_curated_groups", recursive=True)
    )
    member = aliased(User__UserGroup)
    curated_by_member = aliased(User__UserGroup)
    reachable_groups = reachable_groups.union(
        select(curated_by_member.user_group_id)
        .select_from(reachable_groups)
        .join(
            member,
            member.user_group_id == reachable_groups.c.user_group_id,
        )
        .join(
            curated_by_member,
            and_(
                curated_by_member.user_id == member.user_id,
                curated_by_member.is_curator.is_(True),
            ),
        )
    )
    return select(User__UserGroup.user_id).where(
        User__UserGroup.user_group_id.in_(select(reachable_groups.c.user_group_id))
    )


def is_unrestricted_overseer(overseer: User | None) -> bool:
    """Full admins see every non-excluded user. ``None`` is the background
    export path, which has no requesting user and is only reachable from an
    admin-only endpoint."""
    if overseer is None:
        return True
    return Permission.FULL_ADMIN_PANEL_ACCESS in get_effective_permissions(overseer)


def oversight_chat_session_condition(overseer: User | None) -> ColumnElement[bool]:
    """Restrict chat sessions to the ones ``overseer`` is allowed to observe."""
    # NOT IN yields NULL for an ownerless session, which would silently drop
    # anonymous sessions, so they are admitted explicitly here and excluded
    # from curator scope below (they belong to no curated group).
    not_excluded = or_(
        ChatSession.user_id.is_(None),
        ChatSession.user_id.notin_(_excluded_user_ids()),
    )
    if is_unrestricted_overseer(overseer):
        return not_excluded

    assert overseer is not None  # narrowed by is_unrestricted_overseer
    observable = select(User.id).where(
        User.is_active.is_(True),
        User.role.notin_(OVERSIGHT_INELIGIBLE_ROLES),
        User.id.in_(_curated_user_ids(overseer.id)),
    )
    return and_(not_excluded, ChatSession.user_id.in_(observable))


def can_oversee_user(
    overseer: User | None,
    target_user_id: UUID | None,
    db_session: Session,
) -> bool:
    """Whether ``overseer`` may observe ``target_user_id``.

    Mirrors ``oversight_chat_session_condition`` for the endpoints that address
    a single user or session instead of running a filtered query.
    """
    if target_user_id is None:
        # An ownerless (anonymous) session has no user to scope against.
        return is_unrestricted_overseer(overseer)

    stmt = select(User.id).where(
        User.id == target_user_id,
        User.id.notin_(_excluded_user_ids()),
    )
    if not is_unrestricted_overseer(overseer):
        assert overseer is not None  # narrowed by is_unrestricted_overseer
        stmt = stmt.where(
            User.is_active.is_(True),
            User.role.notin_(OVERSIGHT_INELIGIBLE_ROLES),
            User.id.in_(_curated_user_ids(overseer.id)),
        )
    return db_session.scalar(stmt) is not None
