#!/usr/bin/env python3
"""Seed OpenWebUI-parity governance for the real Magellan HR intranet tree.

Mirrors the production Open WebUI deployment on chat-aws, where Spaces
whitelisted folders of the Magellan "Human Resources Intranet" SharePoint site
(Company Wide Files, JF, Medical, Dental, Vision, Policies and Procedures,
Community Initiatives). Here we govern the already-indexed local hierarchy
nodes for that site instead of copying files, per the Onyx model:

- A PUBLIC scope on the actively-indexed HumanResourcesIntranet site (the one
  backed by an ACTIVE connector) labeled like a department row, exposing the
  same folders OpenWebUI spaces used.
- A RESTRICTED scope on the ComplianceIntranet site allowed only for a
  dedicated user group, used by the adversarial spec to prove non-members
  cannot see or attach it.

Prints JSON with the node ids the Playwright spec needs. Idempotent.
"""
from __future__ import annotations

import json

from sqlalchemy import select

from onyx.configs.constants import DocumentSource
from onyx.db.connected_source_governance import upsert_connected_source_scope
from onyx.db.engine.sql_engine import SqlEngine
from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.enums import ConnectedSourceAccessType
from onyx.db.enums import ConnectedSourceCurationStatus
from onyx.db.enums import HierarchyNodeType
from onyx.db.models import HierarchyNode
from onyx.db.models import UserGroup
from shared_configs.configs import POSTGRES_DEFAULT_SCHEMA
from shared_configs.contextvars import CURRENT_TENANT_ID_CONTEXTVAR

RESTRICTED_GROUP_NAME = "OpenWebUI Parity Compliance Group"


def _find_site(db_session, display_name: str, require_children: bool) -> HierarchyNode:
    sites = list(
        db_session.scalars(
            select(HierarchyNode).where(
                HierarchyNode.source == DocumentSource.SHAREPOINT,
                HierarchyNode.node_type == HierarchyNodeType.SITE,
                HierarchyNode.display_name == display_name,
            )
        ).all()
    )
    if not sites:
        raise SystemExit(f"No SharePoint SITE named {display_name!r} is indexed")
    if not require_children:
        return sites[0]
    # Multiple sites can share a display name (Foundations vs Magellan HR).
    # Pick the one carrying the OpenWebUI folder fingerprint: a "JF" folder
    # under its Shared Documents drive, matching chat-aws space whitelists.
    for site in sites:
        shared = _find_child(db_session, site.id, "Shared Documents")
        if shared is not None and _find_child(db_session, shared.id, "JF") is not None:
            return site
    return sites[0]


def _find_child(db_session, parent_id: int, display_name: str) -> HierarchyNode | None:
    return db_session.scalar(
        select(HierarchyNode).where(
            HierarchyNode.parent_id == parent_id,
            HierarchyNode.display_name == display_name,
        )
    )


def main() -> None:
    CURRENT_TENANT_ID_CONTEXTVAR.set(POSTGRES_DEFAULT_SCHEMA)
    SqlEngine.set_app_name("testsprite_openwebui_parity_seed")
    SqlEngine.init_engine(pool_size=2, max_overflow=2)
    try:
        with get_session_with_current_tenant() as db_session:
            hr_site = _find_site(
                db_session, "HumanResourcesIntranet", require_children=True
            )
            shared_documents = _find_child(db_session, hr_site.id, "Shared Documents")
            if shared_documents is None:
                raise SystemExit("HR site has no Shared Documents drive indexed")
            company_wide = _find_child(
                db_session, shared_documents.id, "Company Wide Files"
            )
            jf_folder = _find_child(db_session, shared_documents.id, "JF")
            openwebui_folders = {}
            if company_wide is not None:
                for folder_name in (
                    "Medical",
                    "Dental",
                    "Vision",
                    "Policies and Procedures",
                    "Community Initiatives",
                ):
                    folder = _find_child(db_session, company_wide.id, folder_name)
                    if folder is not None:
                        openwebui_folders[folder_name] = folder.id

            upsert_connected_source_scope(
                db_session=db_session,
                hierarchy_node_id=hr_site.id,
                curation_status=ConnectedSourceCurationStatus.DEFAULT_SAFE,
                group_ids=[],
                access_type=ConnectedSourceAccessType.PUBLIC,
                excluded_hierarchy_node_ids=[],
                display_label="Human Resources Intranet",
                tenant_label="Magellan",
                department_label="Human Resources",
                sort_order=-90,
                warning=None,
            )

            restricted_group = db_session.scalar(
                select(UserGroup).where(UserGroup.name == RESTRICTED_GROUP_NAME)
            )
            if restricted_group is None:
                restricted_group = UserGroup(
                    name=RESTRICTED_GROUP_NAME,
                    is_up_to_date=True,
                    is_up_for_deletion=False,
                    is_default=False,
                )
                db_session.add(restricted_group)
                db_session.flush()

            compliance_site = _find_site(
                db_session, "ComplianceIntranet", require_children=False
            )
            upsert_connected_source_scope(
                db_session=db_session,
                hierarchy_node_id=compliance_site.id,
                curation_status=ConnectedSourceCurationStatus.STANDARD,
                group_ids=[restricted_group.id],
                access_type=ConnectedSourceAccessType.RESTRICTED,
                excluded_hierarchy_node_ids=[],
                display_label="Compliance Intranet",
                tenant_label="Foundations",
                department_label="Compliance",
                sort_order=-80,
                warning=None,
            )
            db_session.commit()

            print(
                json.dumps(
                    {
                        "hr_site_id": hr_site.id,
                        "shared_documents_id": shared_documents.id,
                        "company_wide_id": (
                            company_wide.id if company_wide is not None else None
                        ),
                        "jf_folder_id": jf_folder.id if jf_folder is not None else None,
                        "openwebui_folders": openwebui_folders,
                        "compliance_site_id": compliance_site.id,
                        "restricted_group_id": restricted_group.id,
                        "restricted_group_name": RESTRICTED_GROUP_NAME,
                    },
                    sort_keys=True,
                )
            )
    finally:
        SqlEngine.reset_engine()


if __name__ == "__main__":
    main()
