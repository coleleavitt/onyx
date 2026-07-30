"""Drive items carry the file's byte checksum, not just a text hash.

Document.content_hash covers *extracted text*, which collides whenever many
files share one template: in production a single content_hash spanned fifteen
different clients' portfolio management agreements, because the client-specific
values lived in PDF form fields that never reached the text. Keying dedup or
aliasing on that hash would merge distinct contracts.

The Graph `file.hashes` facet fingerprints the actual bytes, so it stays
distinct across filled copies of one template and matches only true duplicates.
"""

from typing import Any

import pytest

from onyx.connectors.sharepoint.connector import _drive_item_content_fingerprint
from onyx.connectors.sharepoint.connector import DriveItemData


def _item(hashes: dict[str, Any] | None, **overrides: Any) -> dict[str, Any]:
    file_facet: dict[str, Any] = {"mimeType": "application/pdf"}
    if hashes is not None:
        file_facet["hashes"] = hashes
    item: dict[str, Any] = {
        "id": "item-1",
        "name": "agreement.pdf",
        "webUrl": "https://contoso.sharepoint.com/x/agreement.pdf",
        "file": file_facet,
    }
    item.update(overrides)
    return item


def test_quick_xor_hash_is_preferred() -> None:
    fp = _drive_item_content_fingerprint(
        _item({"quickXorHash": "ABC123", "sha1Hash": "DEF456"})
    )
    assert fp == "quickXorHash:ABC123"


def test_falls_back_through_available_hash_types() -> None:
    assert _drive_item_content_fingerprint(_item({"sha256Hash": "S"})) == "sha256Hash:S"
    assert _drive_item_content_fingerprint(_item({"crc32Hash": "C"})) == "crc32Hash:C"


@pytest.mark.parametrize("hashes", [None, {}, {"quickXorHash": "   "}])
def test_missing_or_blank_hashes_yield_none(hashes: dict[str, Any] | None) -> None:
    assert _drive_item_content_fingerprint(_item(hashes)) is None


def test_non_dict_hashes_facet_does_not_raise() -> None:
    item = _item(None)
    item["file"]["hashes"] = "unexpected"
    assert _drive_item_content_fingerprint(item) is None


def test_item_without_file_facet_yields_none() -> None:
    assert _drive_item_content_fingerprint({"id": "x", "name": "folder"}) is None


def test_fingerprint_is_parsed_onto_the_drive_item() -> None:
    parsed = DriveItemData.from_graph_json(_item({"quickXorHash": "XOR=="}))
    assert parsed.content_fingerprint == "quickXorHash:XOR=="
    # regression: the fingerprint edit must not displace sibling parsed fields
    assert parsed.mime_type == "application/pdf"
    assert parsed.name == "agreement.pdf"


def test_drive_id_still_parsed_alongside_fingerprint() -> None:
    """Guards the parentReference fields next to the new one."""
    parsed = DriveItemData.from_graph_json(
        _item(
            {"quickXorHash": "XOR=="},
            parentReference={"driveId": "drive-9", "path": "/drive/root:/Docs"},
        )
    )
    assert parsed.drive_id == "drive-9"
    assert parsed.parent_reference_path == "/drive/root:/Docs"
    assert parsed.content_fingerprint == "quickXorHash:XOR=="


def test_two_filled_copies_of_one_template_stay_distinct() -> None:
    """The production case: same template, same extracted text, different files."""
    brown = DriveItemData.from_graph_json(
        _item({"quickXorHash": "BROWN=="}, name="Brown, Sheila - MIG.pdf")
    )
    burkhardt = DriveItemData.from_graph_json(
        _item({"quickXorHash": "BURK=="}, name="Burkhardt, Charles - MIG.pdf")
    )
    assert brown.content_fingerprint != burkhardt.content_fingerprint


def test_true_duplicates_share_a_fingerprint() -> None:
    """Same file in two sites: dedup should match these."""
    a = DriveItemData.from_graph_json(_item({"quickXorHash": "SAME=="}, id="a"))
    b = DriveItemData.from_graph_json(_item({"quickXorHash": "SAME=="}, id="b"))
    assert a.id != b.id
    assert a.content_fingerprint == b.content_fingerprint
