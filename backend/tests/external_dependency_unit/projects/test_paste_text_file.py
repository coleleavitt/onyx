"""F4 paste-text-as-knowledge, verified against the real path.

Pasted text becomes an indexed UserFile linked to the space; empty and oversize
input is rejected.
"""

import pytest
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from onyx.db.models import Project__UserFile
from onyx.db.models import User
from onyx.db.models import UserFile
from onyx.db.models import UserProject
from onyx.error_handling.exceptions import OnyxError
from onyx.server.features.projects.api import MAX_PASTE_TEXT_BYTES
from onyx.server.features.projects.api import paste_text_file
from onyx.server.features.projects.api import PasteTextRequest
from tests.external_dependency_unit.conftest import create_test_user


def _cleanup_user(db_session: Session, user: User) -> None:
    db_session.query(User).filter(User.id == user.id).delete(synchronize_session=False)
    db_session.commit()


def test_paste_rejects_empty(db_session: Session) -> None:
    user = create_test_user(db_session, "paste_empty")
    try:
        with pytest.raises(OnyxError):
            paste_text_file(
                body=PasteTextRequest(name="n", content="   ", project_id=None),
                bg_tasks=BackgroundTasks(),
                user=user,
                db_session=db_session,
            )
    finally:
        _cleanup_user(db_session, user)


def test_paste_rejects_oversize(db_session: Session) -> None:
    user = create_test_user(db_session, "paste_big")
    try:
        with pytest.raises(OnyxError):
            paste_text_file(
                body=PasteTextRequest(
                    name="n",
                    content="x" * (MAX_PASTE_TEXT_BYTES + 1),
                    project_id=None,
                ),
                bg_tasks=BackgroundTasks(),
                user=user,
                db_session=db_session,
            )
    finally:
        _cleanup_user(db_session, user)


def test_paste_creates_linked_user_file(db_session: Session) -> None:
    user = create_test_user(db_session, "paste_ok")
    project = UserProject(user_id=user.id, name="S", instructions="")
    db_session.add(project)
    db_session.commit()
    file_ids: list = []
    try:
        paste_text_file(
            body=PasteTextRequest(
                name="My Note",
                content="Stewart Willis production 40216752.33",
                project_id=project.id,
            ),
            bg_tasks=BackgroundTasks(),
            user=user,
            db_session=db_session,
        )
        links = (
            db_session.query(Project__UserFile)
            .filter(Project__UserFile.project_id == project.id)
            .all()
        )
        assert len(links) == 1
        file_ids = [link.user_file_id for link in links]
        user_file = db_session.get(UserFile, file_ids[0])
        assert user_file is not None
        assert user_file.name == "My Note.txt"
    finally:
        db_session.query(Project__UserFile).filter(
            Project__UserFile.project_id == project.id
        ).delete(synchronize_session=False)
        if file_ids:
            db_session.query(UserFile).filter(UserFile.id.in_(file_ids)).delete(
                synchronize_session=False
            )
        db_session.query(UserProject).filter(UserProject.id == project.id).delete(
            synchronize_session=False
        )
        _cleanup_user(db_session, user)
