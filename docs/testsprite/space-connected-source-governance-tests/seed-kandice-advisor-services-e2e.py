#!/usr/bin/env python3
"""Seed Kandice Garcia and real Advisor Services source governance for live E2E.

This is intentionally idempotent. It creates/updates:
- `kandice.garcia@fiwealth.com` with password `TestPassword123!`
- stable group `Advisor Services`
- membership: Kandice -> Advisor Services
- connected-source governance scope on the real indexed SharePoint SITE
  `AdvisorServicesIntranet` (node id varies by DB) restricted to that group.

It also removes old synthetic `governed-folder-*` Advisor test nodes/scopes so
browser tests exercise the real indexed SharePoint hierarchy, not stale test data.
"""
from __future__ import annotations

from uuid import uuid4

from fastapi_users.password import PasswordHelper
from sqlalchemy import select

from onyx.auth.schemas import UserRole
from onyx.configs.constants import DocumentSource
from onyx.db.connected_source_governance import upsert_connected_source_scope
from onyx.db.engine.sql_engine import SqlEngine
from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.enums import AccountType
from onyx.db.enums import ConnectedSourceAccessType
from onyx.db.enums import ConnectedSourceCurationStatus
from onyx.db.enums import HierarchyNodeType
from onyx.db.models import ConnectedSourceScope
from onyx.db.models import HierarchyNode
from onyx.db.models import User
from onyx.db.models import UserGroup
from onyx.db.models import User__UserGroup
from shared_configs.configs import POSTGRES_DEFAULT_SCHEMA
from shared_configs.contextvars import CURRENT_TENANT_ID_CONTEXTVAR

KANDICE_EMAIL = "kandice.garcia@fiwealth.com"
KANDICE_PASSWORD = "TestPassword123!"
ADVISOR_GROUP_NAME = "Advisor Services"


def main() -> None:
    CURRENT_TENANT_ID_CONTEXTVAR.set(POSTGRES_DEFAULT_SCHEMA)
    SqlEngine.set_app_name("testsprite_kandice_advisor_services_seed")
    SqlEngine.init_engine(pool_size=2, max_overflow=2)
    try:
        with get_session_with_current_tenant() as db_session:
            password_helper = PasswordHelper()
            kandice = db_session.scalar(select(User).where(User.email == KANDICE_EMAIL))
            if kandice is None:
                kandice = User(
                    id=uuid4(),
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
            else:
                kandice.hashed_password = password_helper.hash(KANDICE_PASSWORD)
                kandice.is_active = True
                kandice.is_verified = True
                kandice.role = UserRole.BASIC
                kandice.account_type = AccountType.STANDARD

            group = db_session.scalar(
                select(UserGroup).where(UserGroup.name == ADVISOR_GROUP_NAME)
            )
            if group is None:
                group = UserGroup(
                    name=ADVISOR_GROUP_NAME,
                    is_up_to_date=True,
                    is_up_for_deletion=False,
                    is_default=False,
                )
                db_session.add(group)
                db_session.flush()

            if (
                db_session.scalar(
                    select(User__UserGroup).where(
                        User__UserGroup.user_id == kandice.id,
                        User__UserGroup.user_group_id == group.id,
                    )
                )
                is None
            ):
                db_session.add(
                    User__UserGroup(user_id=kandice.id, user_group_id=group.id)
                )
                db_session.flush()

            leaked_nodes = list(
                db_session.scalars(
                    select(HierarchyNode).where(
                        HierarchyNode.raw_node_id.like("governed-folder-%")
                    )
                ).all()
            )
            leaked_node_ids = [node.id for node in leaked_nodes]
            if leaked_node_ids:
                db_session.query(ConnectedSourceScope).filter(
                    ConnectedSourceScope.hierarchy_node_id.in_(leaked_node_ids)
                ).delete(synchronize_session=False)
                db_session.query(HierarchyNode).filter(
                    HierarchyNode.id.in_(leaked_node_ids)
                ).delete(synchronize_session=False)
                db_session.flush()

            advisor_site = db_session.scalar(
                select(HierarchyNode).where(
                    HierarchyNode.source == DocumentSource.SHAREPOINT,
                    HierarchyNode.node_type == HierarchyNodeType.SITE,
                    HierarchyNode.display_name == "AdvisorServicesIntranet",
                )
            )
            if advisor_site is None:
                raise SystemExit("Real AdvisorServicesIntranet site is not indexed")

            scope = upsert_connected_source_scope(
                db_session=db_session,
                hierarchy_node_id=advisor_site.id,
                curation_status=ConnectedSourceCurationStatus.DEFAULT_SAFE,
                group_ids=[group.id],
                access_type=ConnectedSourceAccessType.RESTRICTED,
                excluded_hierarchy_node_ids=[],
                display_label="Advisor Services Intranet",
                tenant_label="Foundations",
                department_label="Advisor Services",
                sort_order=-95,
                warning=None,
            )
            db_session.commit()
            print(
                {
                    "kandice_email": KANDICE_EMAIL,
                    "group_id": group.id,
                    "advisor_node_id": advisor_site.id,
                    "scope_id": scope.id,
                }
            )
    finally:
        SqlEngine.reset_engine()


if __name__ == "__main__":
    main()
