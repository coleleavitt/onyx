from unittest.mock import MagicMock

from onyx.connectors.sharepoint.connector import SharepointConnector


def _mock_site(
    *,
    site_id: str,
    display_name: str,
    web_url: str,
    description: str | None = None,
) -> MagicMock:
    site = MagicMock()
    site.id = site_id
    site.properties = {"displayName": display_name}
    site.name = display_name
    site.web_url = web_url
    site.description = description
    return site


def test_discover_sites_returns_sorted_selectable_site_collections() -> None:
    connector = SharepointConnector()
    graph_client = MagicMock()
    connector._graph_client = graph_client
    graph_sites = MagicMock()
    graph_client.sites.get_all_sites.return_value.execute_query.return_value = (
        graph_sites
    )
    connector._handle_paginated_sites = MagicMock(
        return_value=[
            _mock_site(
                site_id="2",
                display_name="Human Resources Intranet",
                web_url="https://example.sharepoint.com/sites/HumanResourcesIntranet",
            ),
            _mock_site(
                site_id="content-storage",
                display_name="Designer",
                web_url="https://example.sharepoint.com/contentstorage/designer",
            ),
            _mock_site(
                site_id="1",
                display_name="Financial Planning Intranet",
                web_url="https://example.sharepoint.com/sites/FinancialPlanningIntranet",
                description="Planning",
            ),
            _mock_site(
                site_id="personal",
                display_name="Personal",
                web_url="https://example-my.sharepoint.com/personal/user",
            ),
        ]
    )

    sites = connector.discover_sites()

    assert [site.model_dump() for site in sites] == [
        {
            "id": "1",
            "display_name": "Financial Planning Intranet",
            "web_url": "https://example.sharepoint.com/sites/FinancialPlanningIntranet",
            "description": "Planning",
        },
        {
            "id": "2",
            "display_name": "Human Resources Intranet",
            "web_url": "https://example.sharepoint.com/sites/HumanResourcesIntranet",
            "description": None,
        },
    ]
