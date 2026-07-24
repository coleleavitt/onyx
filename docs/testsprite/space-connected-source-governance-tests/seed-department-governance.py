#!/usr/bin/env python3
"""Seed department-first connected-source governance for the real SharePoint intranets.

Implements Josh Cooksey's requirement from the Teams export (research/): each
department intranet is a curated, group-restricted source so a user only sees the
departments their Onyx group grants — e.g. "kandice.garcia@fiwealth.com only has
access to the Advisor Services Intranet files" — while admins (who bypass the
group policy) see every curated department.

This is the governance-scope layer (enforced in Postgres at picker/space time),
which is independent of the raw connector ACL "safety net". Creating any scope
switches the source into policy mode: uncurated intranets become browse-hidden,
matching Josh's "just the departments, avoid huge unstructured lists" intent.

Idempotent: safe to re-run. Skips departments whose SITE node is not indexed.
"""

from __future__ import annotations

from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from onyx.auth.schemas import UserRole
from onyx.configs.constants import DocumentSource
from onyx.db.connected_source_governance import upsert_connected_source_scope
from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.engine.sql_engine import SqlEngine
from onyx.db.enums import AccountType
from onyx.db.enums import ConnectedSourceAccessType
from onyx.db.enums import ConnectedSourceCurationStatus
from onyx.db.enums import HierarchyNodeType
from onyx.db.models import HierarchyNode
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.models import UserGroup
from shared_configs.configs import POSTGRES_DEFAULT_SCHEMA
from shared_configs.contextvars import CURRENT_TENANT_ID_CONTEXTVAR

KANDICE_EMAIL = "kandice.garcia@fiwealth.com"
KANDICE_PASSWORD = "TestPassword123!"

# Josh's "default-good" department intranets: (SITE display_name, Onyx group, sort_order).
# The group named here gates who may browse/select that department in the picker.
DEPARTMENTS: list[tuple[str, str, int]] = [
    ("AdvisorServicesIntranet", "Advisor Services", -95),
    ("ComplianceIntranet", "Compliance", -90),
    ("FoundationsIntranet", "Foundations", -85),
    ("HumanResourcesIntranet", "Human Resources", -80),
    ("MarketingIntranet", "Marketing", -75),
    ("TradingOperationsIntranet", "Trading Operations", -70),
]

# Kandice is restricted to a single department to mirror Josh's example.
KANDICE_GROUP = "Advisor Services"


def main() -> None:
    CURRENT_TENANT_ID_CONTEXTVAR.set(POSTGRES_DEFAULT_SCHEMA)
    SqlEngine.set_app_name("testsprite_department_governance_seed")
    SqlEngine.init_engine(pool_size=2, max_overflow=2)
    try:
        with get_session_with_current_tenant() as db_session:

            def get_or_create_group(name: str) -> UserGroup:
                group = db_session.scalar(
                    select(UserGroup).where(UserGroup.name == name)
                )
                if group is None:
                    group = UserGroup(
                        name=name,
                        is_up_to_date=True,
                        is_up_for_deletion=False,
                        is_default=False,
                    )
                    db_session.add(group)
                    db_session.flush()
                return group

            # Ensure Kandice exists, is active, and belongs to her one department.
            password_helper = PasswordHelper()
            kandice = db_session.scalar(select(User).where(User.email == KANDICE_EMAIL))
            if kandice is None:
                kandice = User(
                    email=KANDICE_EMAIL,
                    hashed_password=password_helper.hash(KANDICE_PASSWORD),
                    is_active=True,
                    is_superuser=False,
                    is_verified=True,
                    role=UserRole.BASIC,
                    account_type=AccountType.STANDARD,
                )
                db_session.add(kandice)
                db_session.flush()
            kandice_group = get_or_create_group(KANDICE_GROUP)
            if (
                db_session.scalar(
                    select(User__UserGroup).where(
                        User__UserGroup.user_id == kandice.id,
                        User__UserGroup.user_group_id == kandice_group.id,
                    )
                )
                is None
            ):
                db_session.add(
                    User__UserGroup(user_id=kandice.id, user_group_id=kandice_group.id)
                )
                db_session.flush()

            applied: list[dict[str, object]] = []
            for display_name, group_name, sort_order in DEPARTMENTS:
                group = get_or_create_group(group_name)
                sites = list(
                    db_session.scalars(
                        select(HierarchyNode).where(
                            HierarchyNode.source == DocumentSource.SHAREPOINT,
                            HierarchyNode.node_type == HierarchyNodeType.SITE,
                            HierarchyNode.display_name == display_name,
                        )
                    ).all()
                )
                for site in sites:
                    scope = upsert_connected_source_scope(
                        db_session=db_session,
                        hierarchy_node_id=site.id,
                        curation_status=ConnectedSourceCurationStatus.DEFAULT_SAFE,
                        group_ids=[group.id],
                        access_type=ConnectedSourceAccessType.RESTRICTED,
                        excluded_hierarchy_node_ids=[],
                        display_label=f"{group_name} Intranet",
                        tenant_label="Foundations",
                        department_label=group_name,
                        sort_order=sort_order,
                        warning=None,
                    )
                    applied.append(
                        {
                            "department": group_name,
                            "node_id": site.id,
                            "scope_id": scope.id,
                        }
                    )

            db_session.commit()
            print({"kandice_email": KANDICE_EMAIL, "scopes": applied})
    finally:
        SqlEngine.reset_engine()


if __name__ == "__main__":
    main()
