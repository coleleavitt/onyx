"""Seed department Space templates (F3).

A "template" is a ConnectedKnowledgePreset — CreateProjectModal surfaces these in
the create-space flow and create_project(connected_knowledge_preset_id) applies
the preset's instructions + connected knowledge. This seeds one template per
department so a new space for that department is one click.

Each template links its department intranet as connected knowledge when a matching
governance scope (connected_source_scope.department_label) is found; otherwise the
template ships instructions only (still a valid, useful template).

Run:
    python -m dotenv -f .vscode/.env run -- \
        env PYTHONPATH=backend python docs/testsprite/space-connected-source-governance-tests/seed-department-space-templates.py
"""

from __future__ import annotations

from sqlalchemy import select

from onyx.db.connected_source_governance import create_connected_knowledge_preset
from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.engine.sql_engine import SqlEngine
from onyx.db.models import ConnectedSourceScope
from onyx.db.models import ProjectConnectedKnowledgePreset
from shared_configs.configs import POSTGRES_DEFAULT_SCHEMA
from shared_configs.contextvars import CURRENT_TENANT_ID_CONTEXTVAR

# (name, emoji, instructions). department_label is matched against
# connected_source_scope.department_label to attach the intranet.
DEPARTMENT_TEMPLATES: list[tuple[str, str, str]] = [
    (
        "Advisor Services",
        "📈",
        "You are the Advisor Services assistant. Answer only from the Advisor "
        "Services intranet and always cite the source document.",
    ),
    (
        "Compliance",
        "🛡️",
        "You are the Compliance assistant. Ground every answer in the Compliance "
        "intranet; flag anything that needs a compliance officer's review.",
    ),
    (
        "Financial Planning",
        "🧮",
        "You are the Financial Planning assistant. Use the Financial Planning "
        "intranet and cite the underlying documents.",
    ),
    (
        "Human Resources",
        "👥",
        "You are the HR assistant. Answer from the Human Resources intranet only "
        "and respect employee confidentiality.",
    ),
    (
        "Marketing",
        "📣",
        "You are the Marketing assistant. Use the Marketing intranet and cite "
        "brand/collateral sources.",
    ),
    (
        "Trading Operations",
        "💹",
        "You are the Trading Operations assistant. Ground answers in the Trading "
        "Operations intranet and cite the source.",
    ),
]


def _intranet_node_ids(db_session, department_label: str) -> list[int]:
    scopes = db_session.scalars(
        select(ConnectedSourceScope).where(
            ConnectedSourceScope.department_label == department_label
        )
    ).all()
    return [scope.hierarchy_node_id for scope in scopes]


def main() -> None:
    CURRENT_TENANT_ID_CONTEXTVAR.set(POSTGRES_DEFAULT_SCHEMA)
    SqlEngine.set_app_name("testsprite_department_space_templates_seed")
    SqlEngine.init_engine(pool_size=2, max_overflow=2)
    with get_session_with_current_tenant() as db_session:
        existing = {
            preset.name
            for preset in db_session.scalars(
                select(ProjectConnectedKnowledgePreset)
            ).all()
        }
        created = 0
        for name, emoji, instructions in DEPARTMENT_TEMPLATES:
            if name in existing:
                print(f"skip (exists): {name}")
                continue
            node_ids = _intranet_node_ids(db_session, name)
            create_connected_knowledge_preset(
                db_session=db_session,
                name=name,
                hierarchy_node_ids=node_ids,
                document_ids=[],
                emoji=emoji,
                instructions=instructions,
                description=f"{name} department template",
            )
            created += 1
            print(f"created template: {name} (intranet nodes: {len(node_ids)})")
        print(f"done. created={created}")
    SqlEngine.reset_engine()


if __name__ == "__main__":
    main()
