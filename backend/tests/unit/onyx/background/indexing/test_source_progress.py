from unittest.mock import MagicMock
from unittest.mock import patch

from onyx.background.indexing.run_docfetching import _record_source_document_estimate
from onyx.connectors.models import ConnectorCheckpoint
from onyx.connectors.models import SourceDocumentEstimate


class _EstimatingConnector:
    def __init__(self, estimate: SourceDocumentEstimate | Exception) -> None:
        self.estimate = estimate

    def estimate_document_count(self) -> SourceDocumentEstimate | None:
        if isinstance(self.estimate, Exception):
            raise self.estimate
        return self.estimate


def test_checkpoint_preserves_discovered_document_count() -> None:
    checkpoint = ConnectorCheckpoint(has_more=True, source_docs_discovered=240)

    restored = ConnectorCheckpoint.model_validate_json(checkpoint.model_dump_json())

    assert restored.source_docs_discovered == 240


@patch("onyx.background.indexing.run_docfetching.set_source_document_estimate")
@patch("onyx.background.indexing.run_docfetching.get_session_with_current_tenant")
def test_record_source_document_estimate_persists_best_effort_count(
    mock_session_context: MagicMock,
    mock_set_estimate: MagicMock,
) -> None:
    db_session = MagicMock()
    mock_session_context.return_value.__enter__.return_value = db_session
    connector = _EstimatingConnector(
        SourceDocumentEstimate(document_count=715, method="microsoft_search")
    )

    _record_source_document_estimate(connector, index_attempt_id=9)

    mock_set_estimate.assert_called_once_with(
        db_session=db_session,
        index_attempt_id=9,
        document_count=715,
        method="microsoft_search",
    )


@patch("onyx.background.indexing.run_docfetching.set_source_document_estimate")
def test_record_source_document_estimate_does_not_fail_indexing(
    mock_set_estimate: MagicMock,
) -> None:
    connector = _EstimatingConnector(RuntimeError("Search unavailable"))

    _record_source_document_estimate(connector, index_attempt_id=9)

    mock_set_estimate.assert_not_called()
