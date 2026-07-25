"""Registry of users the suite creates, so it cleans up after itself.

The suite runs against a shared database. Without this, every test leaves an
account behind and the user table grows without bound, which eventually makes
any admin surface listing users unusable.

This lives in its own module rather than in conftest.py on purpose: tests
import helpers from conftest directly while pytest also loads conftest as a
plugin, which can yield two module objects and therefore two separate
registries. A plain module is imported once, so the registry the helper appends
to is the one the fixture drains.
"""

from uuid import UUID

from sqlalchemy import bindparam
from sqlalchemy import text
from sqlalchemy.orm import Session

# xdist gives each worker its own process, so this is per-worker state.
CREATED_TEST_USER_IDS: list[UUID] = []
CREATED_TEST_GROUP_IDS: list[int] = []

# Most references to "user" cascade on delete, but a handful are NO ACTION and
# would raise instead, so those rows are cleared first. Order matters.
_CLEANUP_STATEMENTS = [
    "DELETE FROM project__user_file WHERE project_id IN"
    " (SELECT id FROM user_project WHERE user_id IN :ids)",
    "UPDATE chat_session SET project_id = NULL WHERE project_id IN"
    " (SELECT id FROM user_project WHERE user_id IN :ids)",
    "DELETE FROM document_set__connector_credential_pair WHERE document_set_id IN"
    " (SELECT id FROM document_set WHERE user_id IN :ids)",
    "DELETE FROM persona__document_set WHERE document_set_id IN"
    " (SELECT id FROM document_set WHERE user_id IN :ids)",
    "DELETE FROM document_set__user WHERE document_set_id IN"
    " (SELECT id FROM document_set WHERE user_id IN :ids)",
    "DELETE FROM document_set__user_group WHERE document_set_id IN"
    " (SELECT id FROM document_set WHERE user_id IN :ids)",
    "DELETE FROM user__user_group WHERE user_id IN :ids",
    "DELETE FROM persona__user WHERE user_id IN :ids",
    "DELETE FROM document_set WHERE user_id IN :ids",
    "DELETE FROM user_project WHERE user_id IN :ids",
    'DELETE FROM "user" WHERE id IN :ids',
]


def record_test_user(user_id: UUID) -> None:
    CREATED_TEST_USER_IDS.append(user_id)


def record_test_group(group_id: int) -> None:
    CREATED_TEST_GROUP_IDS.append(group_id)


def delete_test_users(session: Session, user_ids: list[UUID]) -> None:
    if not user_ids:
        return
    for statement in _CLEANUP_STATEMENTS:
        session.execute(
            text(statement).bindparams(bindparam("ids", expanding=True)),
            {"ids": user_ids},
        )
    session.commit()


def drain_recorded_user_ids() -> list[UUID]:
    unique_ids = list(dict.fromkeys(CREATED_TEST_USER_IDS))
    CREATED_TEST_USER_IDS.clear()
    return unique_ids


# Groups outlive the users that were put in them, so they need their own sweep.
_GROUP_CLEANUP_STATEMENTS = [
    "DELETE FROM user__user_group WHERE user_group_id IN :ids",
    "DELETE FROM document_set__user_group WHERE user_group_id IN :ids",
    "DELETE FROM project__user_group WHERE user_group_id IN :ids",
    "DELETE FROM persona__user_group WHERE user_group_id IN :ids",
    "DELETE FROM connected_source_scope__user_group WHERE user_group_id IN :ids",
    "DELETE FROM credential__user_group WHERE user_group_id IN :ids",
    "DELETE FROM llm_provider__user_group WHERE user_group_id IN :ids",
    "DELETE FROM user_group__connector_credential_pair WHERE user_group_id IN :ids",
    "DELETE FROM user_group WHERE id IN :ids",
]


def delete_test_groups(session: Session, group_ids: list[int]) -> None:
    if not group_ids:
        return
    for statement in _GROUP_CLEANUP_STATEMENTS:
        session.execute(
            text(statement).bindparams(bindparam("ids", expanding=True)),
            {"ids": group_ids},
        )
    session.commit()


def drain_recorded_group_ids() -> list[int]:
    unique_ids = list(dict.fromkeys(CREATED_TEST_GROUP_IDS))
    CREATED_TEST_GROUP_IDS.clear()
    return unique_ids
