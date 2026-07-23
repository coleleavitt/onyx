#!/usr/bin/env python3
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
from onyx.db.models import ConnectedSourceScope
from onyx.db.models import HierarchyNode
from shared_configs.configs import POSTGRES_DEFAULT_SCHEMA
from shared_configs.contextvars import CURRENT_TENANT_ID_CONTEXTVAR

ROOT_RAW_ID = "sharepoint"
SITE_RAW_ID = "testsprite-governance-sharepoint-site"
FOLDER_RAW_ID = "testsprite-governance-sharepoint-folder"


def main() -> None:
    CURRENT_TENANT_ID_CONTEXTVAR.set(POSTGRES_DEFAULT_SCHEMA)
    SqlEngine.set_app_name("testsprite_governance_e2e_seed")
    SqlEngine.init_engine(pool_size=2, max_overflow=2)
    try:
        with get_session_with_current_tenant() as db_session:
            existing_nodes = list(
                db_session.scalars(
                    select(HierarchyNode).where(
                        HierarchyNode.raw_node_id.in_([SITE_RAW_ID, FOLDER_RAW_ID]),
                        HierarchyNode.source == DocumentSource.SHAREPOINT,
                    )
                ).all()
            )
            if existing_nodes:
                scope_node_ids = [node.id for node in existing_nodes]
                db_session.query(ConnectedSourceScope).filter(
                    ConnectedSourceScope.hierarchy_node_id.in_(scope_node_ids)
                ).delete(synchronize_session=False)
                db_session.query(HierarchyNode).filter(
                    HierarchyNode.id.in_(scope_node_ids)
                ).delete(synchronize_session=False)
                db_session.commit()

            source_root = db_session.scalar(
                select(HierarchyNode).where(
                    HierarchyNode.source == DocumentSource.SHAREPOINT,
                    HierarchyNode.node_type == HierarchyNodeType.SOURCE,
                )
            )
            if source_root is None:
                source_root = HierarchyNode(
                    raw_node_id=ROOT_RAW_ID,
                    display_name="SharePoint",
                    source=DocumentSource.SHAREPOINT,
                    node_type=HierarchyNodeType.SOURCE,
                    is_public=True,
                )
                db_session.add(source_root)
                db_session.flush()

            site = HierarchyNode(
                raw_node_id=SITE_RAW_ID,
                display_name="TestSprite Advisor Services",
                source=DocumentSource.SHAREPOINT,
                node_type=HierarchyNodeType.SITE,
                parent_id=source_root.id,
                link="https://testsprite.invalid/sites/AdvisorServicesIntranet",
                is_public=True,
            )
            db_session.add(site)
            db_session.flush()

            folder = HierarchyNode(
                raw_node_id=FOLDER_RAW_ID,
                display_name="TestSprite Policies",
                source=DocumentSource.SHAREPOINT,
                node_type=HierarchyNodeType.FOLDER,
                parent_id=site.id,
                link="https://testsprite.invalid/sites/AdvisorServicesIntranet/Documents/Policies",
                is_public=True,
            )
            db_session.add(folder)
            db_session.commit()
            db_session.refresh(site)
            db_session.refresh(folder)

            upsert_connected_source_scope(
                db_session=db_session,
                hierarchy_node_id=site.id,
                curation_status=ConnectedSourceCurationStatus.DEFAULT_SAFE,
                group_ids=[],
                access_type=ConnectedSourceAccessType.PUBLIC,
                excluded_hierarchy_node_ids=[],
                display_label="TestSprite Advisor Services",
                tenant_label="TestSprite Tenant",
                department_label="Advisor Services",
                sort_order=-100,
                size_bytes=1_048_576,
                document_count_estimate=1,
                warning="Synthetic governed source for TestSprite E2E.",
            )

            print(json.dumps({"site_id": site.id, "folder_id": folder.id}, sort_keys=True))
    finally:
        SqlEngine.reset_engine()


if __name__ == "__main__":
    main()
