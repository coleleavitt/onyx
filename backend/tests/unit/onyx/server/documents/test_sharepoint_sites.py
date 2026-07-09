from unittest.mock import MagicMock
from unittest.mock import patch

from onyx.configs.constants import DocumentSource
from onyx.connectors.sharepoint.connector import SharepointSite
from onyx.server.documents.connector import list_sharepoint_sites


@patch("onyx.server.documents.connector.SharepointConnector")
@patch("onyx.server.documents.connector.fetch_credential_by_id_for_user")
def test_list_sharepoint_sites_uses_selected_credential(
    mock_fetch_credential: MagicMock,
    mock_connector_class: MagicMock,
) -> None:
    credential = MagicMock()
    credential.source = DocumentSource.SHAREPOINT
    credential.credential_json.get_value.return_value = {
        "sp_client_id": "client-id",
        "sp_client_secret": "secret",
        "sp_directory_id": "directory-id",
    }
    mock_fetch_credential.return_value = credential
    expected_sites = [
        SharepointSite(
            id="site-id",
            display_name="Human Resources Intranet",
            web_url="https://example.sharepoint.com/sites/HumanResourcesIntranet",
        )
    ]
    mock_connector_class.return_value.discover_sites.return_value = expected_sites
    user = MagicMock()
    db_session = MagicMock()

    sites = list_sharepoint_sites(
        credential_id=7,
        authority_host="https://login.microsoftonline.com",
        graph_api_host="https://graph.microsoft.com",
        sharepoint_domain_suffix="sharepoint.com",
        user=user,
        db_session=db_session,
    )

    assert sites == expected_sites
    mock_fetch_credential.assert_called_once_with(7, user, db_session)
    mock_connector_class.return_value.load_credentials.assert_called_once_with(
        credential.credential_json.get_value.return_value
    )
