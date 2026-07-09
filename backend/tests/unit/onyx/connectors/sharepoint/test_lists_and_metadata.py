from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

import pytest

from onyx.connectors.models import DocumentSource
from onyx.connectors.sharepoint.connector import _convert_listitem_to_document
from onyx.connectors.sharepoint.connector import _sharepoint_list_item_doc_id
from onyx.connectors.sharepoint.connector import DriveItemData
from onyx.connectors.sharepoint.connector import SharepointConnector
from onyx.connectors.sharepoint.connector import SharepointListData
from onyx.connectors.sharepoint.connector import SharepointListItemData
from onyx.connectors.sharepoint.connector import SiteDescriptor

SITE_ID = "tenant.sharepoint.com,site-id,web-id"
SITE_URL = "https://tenant.sharepoint.com/sites/ops"
LIST_ID = "list-id"


def test_convert_listitem_to_document_includes_fields_and_metadata() -> None:
    item = SharepointListItemData(
        id="42",
        web_url=f"{SITE_URL}/Lists/FAQ/42.aspx",
        fields={
            "Title": "Wire transfer FAQ",
            "Category": "Payments",
            "Tags": ["ops", "cash"],
            "@odata.etag": "ignored",
        },
        content_type_name="FAQ Item",
        content_type_id="0x0100",
        created_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_modified_datetime=datetime(2026, 1, 2, tzinfo=timezone.utc),
        created_by_display_name="Ada Lovelace",
        created_by_email="ada@example.com",
    )
    list_data = SharepointListData(
        id=LIST_ID,
        name="FAQ",
        display_name="FAQ",
        web_url=f"{SITE_URL}/Lists/FAQ",
        template="genericList",
    )

    doc = _convert_listitem_to_document(
        item,
        site_id=SITE_ID,
        site_url=SITE_URL,
        list_data=list_data,
        ctx=None,
        graph_client=object(),  # ty: ignore[invalid-argument-type]
        include_permissions=False,
        version_summaries=["v1 - 2026-01-01"],
        activity_summaries=["2026-01-02 - Ada - edit"],
        parent_hierarchy_raw_node_id=SITE_URL,
    )

    assert doc.id == _sharepoint_list_item_doc_id(SITE_ID, LIST_ID, "42")
    assert doc.source == DocumentSource.SHAREPOINT
    assert doc.semantic_identifier == "Wire transfer FAQ"
    assert doc.metadata["sharepoint_item_type"] == "list_item"
    assert doc.metadata["list"] == "FAQ"
    assert doc.metadata["content_type"] == "FAQ Item"
    assert doc.metadata["field:Category"] == "Payments"
    assert doc.metadata["field:Tags"] == ["ops", "cash"]
    assert "Wire transfer FAQ" in doc.sections[0].text
    assert "Category: Payments" in doc.sections[0].text
    assert "Versions:" in doc.sections[0].text
    assert "Recent activity:" in doc.sections[0].text
    assert doc.primary_owners
    assert doc.primary_owners[0].email == "ada@example.com"


def test_fetch_lists_skips_document_libraries_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SharepointConnector(include_lists=True)
    connector.graph_api_base = "https://graph.microsoft.com/v1.0"

    def fake_get_json(
        self: SharepointConnector,  # noqa: ARG001
        url: str,
        params: dict[str, str] | None = None,  # noqa: ARG001
    ) -> dict[str, Any]:
        assert url == f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/lists"
        return {
            "value": [
                {
                    "id": "docs",
                    "name": "Documents",
                    "displayName": "Documents",
                    "list": {"template": "documentLibrary", "hidden": False},
                },
                {
                    "id": LIST_ID,
                    "name": "FAQ",
                    "displayName": "FAQ",
                    "list": {"template": "genericList", "hidden": False},
                },
                {
                    "id": "hidden",
                    "name": "Hidden",
                    "displayName": "Hidden",
                    "list": {"template": "genericList", "hidden": True},
                },
            ]
        }

    monkeypatch.setattr(SharepointConnector, "_graph_api_get_json", fake_get_json)

    lists = list(connector._fetch_lists(SITE_ID))

    assert [list_data.id for list_data in lists] == [LIST_ID]


def test_fetch_list_items_expands_fields_and_filters_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SharepointConnector(include_lists=True)
    connector.graph_api_base = "https://graph.microsoft.com/v1.0"

    def fake_get_json(
        self: SharepointConnector,  # noqa: ARG001
        url: str,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        assert url == (
            f"https://graph.microsoft.com/v1.0/sites/{SITE_ID}/lists/{LIST_ID}/items"
        )
        assert params == {"$expand": "fields", "$top": "200"}
        return {
            "value": [
                {
                    "id": "old",
                    "lastModifiedDateTime": "2025-01-01T00:00:00Z",
                    "fields": {"Title": "Old"},
                },
                {
                    "id": "new",
                    "lastModifiedDateTime": "2026-01-01T00:00:00Z",
                    "fields": {"Title": "New"},
                },
            ]
        }

    monkeypatch.setattr(SharepointConnector, "_graph_api_get_json", fake_get_json)

    items = list(
        connector._fetch_list_items(
            SITE_ID,
            LIST_ID,
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )

    assert [item.id for item in items] == ["new"]
    assert items[0].fields["Title"] == "New"


def test_folder_scoped_drive_uses_delta_with_prefix_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connector = SharepointConnector()
    inside = DriveItemData(
        id="inside",
        name="guide.pdf",
        web_url=f"{SITE_URL}/Documents/Policies/guide.pdf",
        parent_reference_path="/drives/d1/root:/Policies",
        drive_id="d1",
    )
    outside = DriveItemData(
        id="outside",
        name="other.pdf",
        web_url=f"{SITE_URL}/Documents/Other/other.pdf",
        parent_reference_path="/drives/d1/root:/Other",
        drive_id="d1",
    )

    def fake_delta(
        self: SharepointConnector,  # noqa: ARG001
        drive_id: str,  # noqa: ARG001
        start: datetime | None = None,  # noqa: ARG001
        end: datetime | None = None,  # noqa: ARG001
        page_size: int = 200,  # noqa: ARG001
    ) -> list[DriveItemData]:
        return [inside, outside]

    monkeypatch.setattr(SharepointConnector, "_iter_drive_items_delta", fake_delta)

    items = list(
        connector._get_drive_items_for_drive_id(
            site_descriptor=SiteDescriptor(
                url=SITE_URL,
                drive_name="Documents",
                folder_path="Policies",
            ),
            drive_id="d1",
        )
    )

    assert [item.id for item in items] == ["inside"]
