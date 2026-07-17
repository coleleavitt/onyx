from onyx.server.manage.models import MemoryItem
from onyx.server.manage.users import classify_legacy_memory_list_change
from onyx.server.manage.users import has_disabled_to_enabled_transition
from onyx.server.manage.users import LegacyMemoryListChange


def test_memory_snapshot_classifies_unchanged_rows_as_no_change() -> None:
    existing = [MemoryItem(id=1, content="One"), MemoryItem(id=2, content="Two")]

    assert (
        classify_legacy_memory_list_change(
            [MemoryItem(id=1, content="One"), MemoryItem(id=2, content="Two")],
            existing,
        )
        == LegacyMemoryListChange.NO_CHANGE
    )


def test_memory_snapshot_classifies_removed_rows_as_deletion_only() -> None:
    existing = [MemoryItem(id=1, content="One"), MemoryItem(id=2, content="Two")]

    assert (
        classify_legacy_memory_list_change([MemoryItem(id=1, content="One")], existing)
        == LegacyMemoryListChange.DELETION_ONLY
    )


def test_memory_snapshot_rejects_unknown_null_changed_and_duplicate_ids() -> None:
    existing = [MemoryItem(id=1, content="One")]
    requests = [
        [MemoryItem(id=None, content="New")],
        [MemoryItem(id=2, content="Unknown")],
        [MemoryItem(id=1, content="Changed")],
        [MemoryItem(id=1, content="One"), MemoryItem(id=1, content="One")],
    ]

    for request in requests:
        assert (
            classify_legacy_memory_list_change(request, existing)
            == LegacyMemoryListChange.CREATE_OR_UPDATE
        )


def test_memory_snapshot_omitted_list_is_no_change() -> None:
    assert (
        classify_legacy_memory_list_change(None, [MemoryItem(id=1, content="One")])
        == LegacyMemoryListChange.NO_CHANGE
    )


def test_only_disabled_to_enabled_preference_transitions_are_blocked() -> None:
    assert has_disabled_to_enabled_transition(True, False)
    assert not has_disabled_to_enabled_transition(True, True)
    assert not has_disabled_to_enabled_transition(False, True)
    assert not has_disabled_to_enabled_transition(None, False)
