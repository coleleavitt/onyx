"""Coverage for persisted background error helpers."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from onyx.db.background_error import create_background_error
from onyx.db.models import BackgroundError


@pytest.fixture()
def error_messages() -> Iterator[list[str]]:
    messages: list[str] = []
    yield messages


@pytest.fixture(autouse=True)
def cleanup_background_errors(
    db_session: Session, error_messages: list[str]
) -> Iterator[None]:
    yield
    if error_messages:
        db_session.execute(
            delete(BackgroundError).where(BackgroundError.message.in_(error_messages))
        )
        db_session.commit()


def test_create_background_error_persists_message_without_cc_pair(
    db_session: Session, error_messages: list[str]
) -> None:
    message = f"background error test {uuid4().hex}"
    error_messages.append(message)

    create_background_error(db_session, message=message, cc_pair_id=None)

    persisted = (
        db_session.query(BackgroundError)
        .filter(BackgroundError.message == message)
        .one()
    )
    assert persisted.cc_pair_id is None
    assert persisted.time_created is not None
