from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

from onyx.db.models import IndexingStatus
from onyx.server.documents.models import IndexAttemptSnapshot


def test_index_attempt_snapshot_exposes_source_and_batch_progress() -> None:
    estimate_time = datetime(2026, 7, 9, 19, 20, tzinfo=timezone.utc)
    heartbeat_time = datetime(2026, 7, 9, 19, 21, tzinfo=timezone.utc)
    attempt = SimpleNamespace(
        id=9,
        status=IndexingStatus.IN_PROGRESS,
        from_beginning=True,
        new_docs_indexed=120,
        total_docs_indexed=125,
        docs_removed_from_index=0,
        error_msg=None,
        full_exception_trace=None,
        time_started=datetime(2026, 7, 9, 19, 0, tzinfo=timezone.utc),
        time_updated=datetime(2026, 7, 9, 19, 21, tzinfo=timezone.utc),
        poll_range_start=None,
        poll_range_end=None,
        source_docs_discovered=240,
        source_docs_estimated=715,
        source_doc_estimate_method="microsoft_search",
        source_doc_estimate_time=estimate_time,
        source_progress_label="Documents",
        total_batches=None,
        completed_batches=12,
        last_heartbeat_time=heartbeat_time,
    )

    snapshot = IndexAttemptSnapshot.from_index_attempt_db_model(  # type: ignore[arg-type]
        attempt, error_count=3
    )

    assert snapshot.source_docs_discovered == 240
    assert snapshot.source_docs_estimated == 715
    assert snapshot.source_doc_estimate_method == "microsoft_search"
    assert snapshot.source_doc_estimate_time == estimate_time
    assert snapshot.source_progress_label == "Documents"
    assert snapshot.total_batches is None
    assert snapshot.completed_batches == 12
    assert snapshot.last_heartbeat_time == heartbeat_time
