from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi_users.password import PasswordHelper
from sqlalchemy.orm import Session

from onyx.db.artifact_library import ArtifactLibraryScope
from onyx.db.artifact_library import create_artifact_library_item
from onyx.db.artifact_library import dismiss_shared_artifact_library_item
from onyx.db.artifact_library import fetch_artifact_library_item
from onyx.db.artifact_library import list_artifact_library_items
from onyx.db.artifact_library import replace_artifact_library_shares
from onyx.db.artifact_library import set_artifact_library_item_pin
from onyx.db.enums import AccountType
from onyx.db.enums import ArtifactType
from onyx.db.models import User
from onyx.db.models import UserRole


@pytest.fixture
def artifact_viewer(db_session: Session) -> Generator[User, None, None]:
    password_helper = PasswordHelper()
    viewer = User(
        id=uuid4(),
        email=f"artifact_viewer_{uuid4().hex[:8]}@example.com",
        hashed_password=password_helper.hash(password_helper.generate()),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role=UserRole.EXT_PERM_USER,
        account_type=AccountType.EXT_PERM_USER,
    )
    db_session.add(viewer)
    db_session.commit()
    yield viewer
    db_session.rollback()
    persisted = db_session.get(User, viewer.id)
    if persisted is not None:
        db_session.delete(persisted)
        db_session.commit()


def _create_shared_artifact(db_session: Session, owner: User, viewer: User):
    assert owner.id is not None
    assert viewer.id is not None
    item = create_artifact_library_item(
        owner_user_id=owner.id,
        name="Quarterly plan.pdf",
        artifact_type=ArtifactType.PDF,
        storage_file_id=f"artifact-test-{uuid4()}",
        source_path="outputs/quarterly-plan.pdf",
        mime_type="application/pdf",
        size_bytes=128,
        db_session=db_session,
    )
    replace_artifact_library_shares(
        item=item,
        user_ids={viewer.id},
        group_ids=set(),
        db_session=db_session,
    )
    db_session.commit()
    return item


def test_artifact_pins_are_user_scoped(
    db_session: Session,
    test_user: User,
    artifact_viewer: User,
) -> None:
    item = _create_shared_artifact(db_session, test_user, artifact_viewer)

    set_artifact_library_item_pin(
        item=item,
        user=test_user,
        pinned=True,
        db_session=db_session,
    )
    db_session.commit()

    assert [
        candidate.id
        for candidate in list_artifact_library_items(
            user=test_user, db_session=db_session, pinned=True
        )
    ] == [item.id]
    assert (
        list_artifact_library_items(
            user=artifact_viewer, db_session=db_session, pinned=True
        )
        == []
    )

    set_artifact_library_item_pin(
        item=item,
        user=artifact_viewer,
        pinned=True,
        db_session=db_session,
    )
    db_session.commit()

    assert [
        candidate.id
        for candidate in list_artifact_library_items(
            user=artifact_viewer, db_session=db_session, pinned=True
        )
    ] == [item.id]


def test_removing_shared_artifact_only_hides_it_from_the_recipient_library(
    db_session: Session,
    test_user: User,
    artifact_viewer: User,
) -> None:
    item = _create_shared_artifact(db_session, test_user, artifact_viewer)

    assert [
        candidate.id
        for candidate in list_artifact_library_items(
            user=artifact_viewer,
            db_session=db_session,
            scope=ArtifactLibraryScope.SHARED,
        )
    ] == [item.id]

    dismiss_shared_artifact_library_item(
        item=item,
        user=artifact_viewer,
        db_session=db_session,
    )
    db_session.commit()

    assert (
        list_artifact_library_items(
            user=artifact_viewer,
            db_session=db_session,
            scope=ArtifactLibraryScope.SHARED,
        )
        == []
    )
    assert (
        fetch_artifact_library_item(
            item.id,
            user=artifact_viewer,
            db_session=db_session,
        )
        is not None
    )
    assert [
        candidate.id
        for candidate in list_artifact_library_items(
            user=test_user,
            db_session=db_session,
            scope=ArtifactLibraryScope.CREATED,
        )
    ] == [item.id]
