"""Project-test fixtures.

The governance tests in this package create real `test-connector-*` Connector /
Credential / ConnectorCredentialPair rows (via `make_cc_pair`) and commit them,
which historically leaked hundreds of rows into the shared dev database. The
autouse fixture below snapshots the existing test-connector ids before each
test and deletes anything new afterwards, including the association rows
(`DocumentByConnectorCredentialPair`, `HierarchyNodeByConnectorCredentialPair`)
that block the FK deletes.
"""
from collections.abc import Generator

import pytest
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.orm import Session

from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.engine.sql_engine import SqlEngine
from onyx.db.models import Connector
from onyx.db.models import ConnectorCredentialPair
from onyx.db.models import Credential
from onyx.db.models import Document
from onyx.db.models import DocumentByConnectorCredentialPair
from onyx.db.models import HierarchyNodeByConnectorCredentialPair
from onyx.db.models import IndexAttempt
from onyx.db.models import UserGroup

_TEST_CONNECTOR_PATTERN = "test-connector-%"
_TEST_GROUP_PATTERNS = (
    "advisor-services-policy-%",
    "mixed-source-allowed-%",
    "mixed-source-denied-%",
    "root-bypass-group-%",
)


def _test_connector_ids(db_session: Session) -> set[int]:
    return set(
        db_session.scalars(
            select(Connector.id).where(Connector.name.like(_TEST_CONNECTOR_PATTERN))
        ).all()
    )


def _test_group_ids(db_session: Session) -> set[int]:
    group_ids: set[int] = set()
    for pattern in _TEST_GROUP_PATTERNS:
        group_ids.update(
            db_session.scalars(
                select(UserGroup.id).where(UserGroup.name.like(pattern))
            ).all()
        )
    return group_ids


@pytest.fixture(autouse=True)
def cleanup_test_resources(
    tenant_context: None,
) -> Generator[None, None, None]:
    """Delete committed test connector/group rows left behind by a test."""
    SqlEngine.init_engine(pool_size=10, max_overflow=5)
    with get_session_with_current_tenant() as before_session:
        pre_existing_connector_ids = _test_connector_ids(before_session)
        pre_existing_group_ids = _test_group_ids(before_session)

    yield

    with get_session_with_current_tenant() as session:
        leaked_ids = _test_connector_ids(session) - pre_existing_connector_ids

        leaked_pairs = list(
            session.scalars(
                select(ConnectorCredentialPair).where(
                    ConnectorCredentialPair.connector_id.in_(leaked_ids)
                )
            ).all()
        )
        credential_ids = {pair.credential_id for pair in leaked_pairs}
        pair_ids = {pair.id for pair in leaked_pairs}

        owned_doc_ids = list(
            session.scalars(
                select(DocumentByConnectorCredentialPair.id).where(
                    DocumentByConnectorCredentialPair.connector_id.in_(leaked_ids)
                )
            ).all()
        )
        session.query(DocumentByConnectorCredentialPair).filter(
            DocumentByConnectorCredentialPair.connector_id.in_(leaked_ids)
        ).delete(synchronize_session=False)
        session.flush()
        if owned_doc_ids:
            # Documents whose only cc_pair references were the leaked pairs
            # are test data too — remove them so they don't accumulate.
            orphan_doc_ids = list(
                session.scalars(
                    select(Document.id)
                    .where(Document.id.in_(owned_doc_ids))
                    .where(
                        ~select(DocumentByConnectorCredentialPair.id)
                        .where(DocumentByConnectorCredentialPair.id == Document.id)
                        .exists()
                    )
                ).all()
            )
            if orphan_doc_ids:
                session.query(Document).filter(
                    Document.id.in_(orphan_doc_ids)
                ).delete(synchronize_session=False)
        session.query(HierarchyNodeByConnectorCredentialPair).filter(
            HierarchyNodeByConnectorCredentialPair.connector_id.in_(leaked_ids)
        ).delete(synchronize_session=False)
        if pair_ids:
            session.query(IndexAttempt).filter(
                IndexAttempt.connector_credential_pair_id.in_(pair_ids)
            ).delete(synchronize_session=False)
        session.query(ConnectorCredentialPair).filter(
            ConnectorCredentialPair.connector_id.in_(leaked_ids)
        ).delete(synchronize_session=False)
        session.query(Connector).filter(Connector.id.in_(leaked_ids)).delete(
            synchronize_session=False
        )
        if credential_ids:
            # Only delete credentials no longer referenced by any surviving
            # cc_pair (make_cc_pair creates one per pair, but stay safe).
            orphan_credential_ids = credential_ids - set(
                session.scalars(
                    select(ConnectorCredentialPair.credential_id).where(
                        ConnectorCredentialPair.credential_id.in_(credential_ids)
                    )
                ).all()
            )
            if orphan_credential_ids:
                session.query(Credential).filter(
                    Credential.id.in_(orphan_credential_ids)
                ).delete(synchronize_session=False)

        leaked_group_ids = _test_group_ids(session) - pre_existing_group_ids
        if leaked_group_ids:
            group_ids = list(leaked_group_ids)
            # Delete from every known group-sharing join table before removing
            # the groups themselves. The project governance tests only create
            # user memberships and connected-source scope links, but keeping the
            # cleanup broad prevents future committed test rows from leaking.
            for statement in (
                "UPDATE persona SET owner_group_id = NULL WHERE owner_group_id = ANY(:group_ids)",
                "DELETE FROM connected_source_scope__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM user__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM user_group__connector_credential_pair WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM document_set__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM persona__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM token_rate_limit__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM llm_provider__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM credential__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM mcp_server__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM scim_group_mapping WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM permission_grant WHERE group_id = ANY(:group_ids)",
                "DELETE FROM skill__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM project__user_group WHERE user_group_id = ANY(:group_ids)",
                "DELETE FROM artifact_library_item__user_group WHERE user_group_id = ANY(:group_ids)",
            ):
                session.execute(text(statement), {"group_ids": group_ids})
            session.query(UserGroup).filter(UserGroup.id.in_(group_ids)).delete(
                synchronize_session=False
            )
        session.commit()
