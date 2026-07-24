"""F3 templates: creating a space from a ConnectedKnowledgePreset (a template)
inherits the preset's instructions.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from onyx.db.connected_source_governance import create_connected_knowledge_preset
from onyx.db.models import ProjectConnectedKnowledgePreset
from onyx.db.models import User
from onyx.db.models import UserProject
from onyx.server.features.projects.api import create_project
from tests.external_dependency_unit.conftest import create_test_user


def test_create_project_from_template_applies_instructions(
    db_session: Session,
) -> None:
    user = create_test_user(db_session, "tmpl_user")
    preset = create_connected_knowledge_preset(
        db_session=db_session,
        name=f"Advisor Services Template {uuid4().hex[:8]}",
        hierarchy_node_ids=[],
        document_ids=[],
        emoji="📈",
        instructions="Advisor Services: always cite the intranet.",
    )
    project_id: int | None = None
    try:
        snapshot = create_project(
            name="From Template",
            description=None,
            instructions=None,
            emoji=None,
            connected_knowledge_preset_id=preset.id,
            user=user,
            db_session=db_session,
        )
        project_id = snapshot.id
        project = db_session.get(UserProject, project_id)
        assert project is not None
        # The blank new space inherited the template's instructions.
        assert project.instructions == "Advisor Services: always cite the intranet."
    finally:
        if project_id is not None:
            db_session.query(UserProject).filter(UserProject.id == project_id).delete(
                synchronize_session=False
            )
        db_session.query(ProjectConnectedKnowledgePreset).filter(
            ProjectConnectedKnowledgePreset.id == preset.id
        ).delete(synchronize_session=False)
        db_session.query(User).filter(User.id == user.id).delete(
            synchronize_session=False
        )
        db_session.commit()
