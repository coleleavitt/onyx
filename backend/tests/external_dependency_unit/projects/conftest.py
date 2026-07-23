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

_TEST_CONNECTOR_PATTERN = "test-connector-%"


def _test_connector_ids(db_session: Session) -> set[int]:
    return set(
        db_session.scalars(
            select(Connector.id).where(Connector.name.like(_TEST_CONNECTOR_PATTERN))
        ).all()
    )


@pytest.fixture(autouse=True)
def cleanup_test_connectors(
    tenant_context: None,
) -> Generator[None, None, None]:
    """Delete any test-connector rows a test leaves behind (commit-leak guard)."""
    SqlEngine.init_engine(pool_size=10, max_overflow=5)
    with get_session_with_current_tenant() as before_session:
        pre_existing_ids = _test_connector_ids(before_session)

    yield

    with get_session_with_current_tenant() as session:
        leaked_ids = _test_connector_ids(session) - pre_existing_ids
        if not leaked_ids:
            return

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
        session.commit()
