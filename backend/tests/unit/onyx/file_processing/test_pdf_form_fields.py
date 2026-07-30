"""Filled PDF form values must reach the extracted text.

Production symptom this covers: fifteen different clients' portfolio management
agreements extracted to byte-identical text (51,620 chars differing only in the
filename) because every client-specific value lived in AcroForm fields that page
text extraction never sees. Identical text means identical embeddings, so
retrieval cannot tell one client's contract from another's.
"""

import io
from typing import Any
from unittest.mock import MagicMock

import pytest

from onyx.file_processing.extract_file_text import extract_pdf_form_field_text
from onyx.file_processing.extract_file_text import read_pdf_file


def _reader_with_fields(fields: dict[str, Any] | None) -> MagicMock:
    reader = MagicMock()
    reader.get_fields.return_value = fields
    return reader


def test_filled_text_fields_are_rendered() -> None:
    reader = _reader_with_fields(
        {
            "ClientName": {"/FT": "/Tx", "/V": "Sheila Brown"},
            "AccountNumber": {"/FT": "/Tx", "/V": "MIG-88213"},
        }
    )
    out = extract_pdf_form_field_text(reader)
    assert "ClientName: Sheila Brown" in out
    assert "AccountNumber: MIG-88213" in out


def test_two_clients_of_one_template_no_longer_collide() -> None:
    """The exact production failure: same template, different filled values."""
    brown = extract_pdf_form_field_text(
        _reader_with_fields({"ClientName": {"/FT": "/Tx", "/V": "Sheila Brown"}})
    )
    burkhardt = extract_pdf_form_field_text(
        _reader_with_fields(
            {"ClientName": {"/FT": "/Tx", "/V": "Charles & Jeannie Burkhardt"}}
        )
    )
    assert brown != burkhardt
    assert brown and burkhardt


def test_output_is_sorted_for_stable_content_hash() -> None:
    """Document.content_hash must not churn on dict ordering."""
    a = extract_pdf_form_field_text(
        _reader_with_fields(
            {"b": {"/FT": "/Tx", "/V": "2"}, "a": {"/FT": "/Tx", "/V": "1"}}
        )
    )
    b = extract_pdf_form_field_text(
        _reader_with_fields(
            {"a": {"/FT": "/Tx", "/V": "1"}, "b": {"/FT": "/Tx", "/V": "2"}}
        )
    )
    assert a == b == "a: 1\nb: 2"


@pytest.mark.parametrize("field_type", ["/Btn", "/Sig"])
def test_buttons_and_signatures_are_skipped(field_type: str) -> None:
    out = extract_pdf_form_field_text(
        _reader_with_fields({"noise": {"/FT": field_type, "/V": "/Yes"}})
    )
    assert out == ""


@pytest.mark.parametrize("fields", [None, {}, {"empty": {"/FT": "/Tx", "/V": "  "}}])
def test_no_usable_fields_yields_empty_string(fields: dict[str, Any] | None) -> None:
    assert extract_pdf_form_field_text(_reader_with_fields(fields)) == ""


def test_unreadable_fields_do_not_raise() -> None:
    reader = MagicMock()
    reader.get_fields.side_effect = ValueError("broken xref")
    assert extract_pdf_form_field_text(reader) == ""


def test_bytes_values_are_decoded() -> None:
    out = extract_pdf_form_field_text(
        _reader_with_fields({"name": {"/FT": "/Tx", "/V": b"Sheila Brown"}})
    )
    assert "Sheila Brown" in out


def test_end_to_end_real_pdf_with_form_field() -> None:
    """read_pdf_file surfaces field values alongside page text."""
    pypdf = pytest.importorskip("pypdf")
    from pypdf.generic import NameObject
    from pypdf.generic import TextStringObject

    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.add_metadata({})

    # Attach a text field carrying the only client-identifying value.
    field = pypdf.generic.DictionaryObject()
    field.update(
        {
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject("ClientName"),
            NameObject("/V"): TextStringObject("Sheila Brown"),
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Widget"),
        }
    )
    ref = writer._add_object(field)
    writer.pages[0][NameObject("/Annots")] = pypdf.generic.ArrayObject([ref])
    writer._root_object[NameObject("/AcroForm")] = pypdf.generic.DictionaryObject(
        {NameObject("/Fields"): pypdf.generic.ArrayObject([ref])}
    )

    buf = io.BytesIO()
    writer.write(buf)

    text, _metadata, _images = read_pdf_file(io.BytesIO(buf.getvalue()))
    assert "Sheila Brown" in text, (
        "a filled form value must reach the indexed text, otherwise every copy "
        "of the template is indistinguishable in the index"
    )
