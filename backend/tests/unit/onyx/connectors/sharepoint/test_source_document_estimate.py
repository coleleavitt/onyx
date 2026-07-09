from unittest.mock import MagicMock

from onyx.connectors.sharepoint.connector import SharepointConnector
from onyx.connectors.sharepoint.connector import SharepointConnectorCheckpoint


def test_estimate_document_count_queries_configured_paths_once() -> None:
    connector = SharepointConnector(
        sites=[
            "https://example.sharepoint.com/sites/HR",
            "https://example.sharepoint.com/sites/Operations/Documents/Policies",
        ],
        microsoft_search_region="NAM",
    )
    connector._graph_api_post_json = MagicMock(  # type: ignore[method-assign]
        return_value={
            "value": [
                {"hitsContainers": [{"total": 715, "hits": []}]},
            ]
        }
    )

    estimate = connector.estimate_document_count()

    assert estimate is not None
    assert estimate.document_count == 715
    assert estimate.method == "microsoft_search"
    connector._graph_api_post_json.assert_called_once()
    first_request = connector._graph_api_post_json.call_args.args[1]
    assert first_request["requests"][0] == {
        "entityTypes": ["driveItem"],
        "query": {
            "queryString": '(path:"https://example.sharepoint.com/sites/HR" OR path:"https://example.sharepoint.com/sites/Operations/Documents/Policies") AND isDocument=true'
        },
        "from": 0,
        "size": 1,
        "region": "NAM",
    }
    assert connector._graph_api_post_json.call_args.kwargs == {
        "max_retries": 0,
        "timeout": 15,
    }


def test_estimate_document_count_omits_unconfigured_search_region() -> None:
    connector = SharepointConnector(sites=["https://example.sharepoint.com/sites/HR"])
    connector._graph_api_post_json = MagicMock(  # type: ignore[method-assign]
        return_value={"value": [{"hitsContainers": [{"total": 12}]}]}
    )

    estimate = connector.estimate_document_count()

    assert estimate is not None
    assert estimate.document_count == 12
    request = connector._graph_api_post_json.call_args.args[1]["requests"][0]
    assert "region" not in request


def test_estimate_document_count_uses_tenant_root_when_sites_are_unrestricted() -> None:
    connector = SharepointConnector(microsoft_search_region="NAM")
    connector.sp_tenant_domain = "example"
    connector._graph_api_post_json = MagicMock(  # type: ignore[method-assign]
        return_value={"value": [{"hitsContainers": [{"total": 900}]}]}
    )

    estimate = connector.estimate_document_count()

    assert estimate is not None
    request = connector._graph_api_post_json.call_args.args[1]["requests"][0]
    assert request["query"]["queryString"] == (
        '(path:"https://example.sharepoint.com") AND isDocument=true'
    )


def test_existing_microsoft_search_queries_do_not_require_region() -> None:
    connector = SharepointConnector(microsoft_search_queries=["policy"])

    connector.validate_connector_settings()


def test_supplemental_search_omits_region_when_not_configured() -> None:
    connector = SharepointConnector(microsoft_search_queries=["policy"])
    connector._graph_api_post_json = MagicMock(  # type: ignore[method-assign]
        return_value={"value": [{"hitsContainers": []}]}
    )

    assert list(connector._fetch_microsoft_search_documents(False)) == []

    request = connector._graph_api_post_json.call_args.args[1]["requests"][0]
    assert "region" not in request


def test_search_only_connector_checkpoints_stage_before_searching() -> None:
    connector = SharepointConnector(
        include_site_documents=False,
        include_site_pages=False,
        include_lists=False,
        microsoft_search_queries=["policy"],
    )
    connector._graph_client = object()  # ty: ignore[invalid-assignment]
    generator = connector._load_from_checkpoint(
        0,
        1,
        SharepointConnectorCheckpoint(has_more=True),
        include_permissions=False,
    )

    try:
        next(generator)
    except StopIteration as stop:
        checkpoint = stop.value
    else:
        raise AssertionError("stage checkpoint should not yield documents")

    assert checkpoint.source_progress_label == "Microsoft Search"
    assert checkpoint.search_done is False
