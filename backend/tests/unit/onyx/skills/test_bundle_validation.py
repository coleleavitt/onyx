"""Unit tests for the custom skill bundle validator.

Covers slug validation, missing SKILL.md, template rejection, size caps, and
the SHA-256 helper. Security-boundary tests (path traversal, symlinks,
_safe_unzip extraction safety) live in test_bundle_safety.py.
"""

from __future__ import annotations

import io
import stat
import zipfile

import pytest

from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.skills.bundle import _ZIP_UNIX_CREATE_SYSTEM
from onyx.skills.bundle import compute_bundle_sha256
from onyx.skills.bundle import diff_custom_bundles
from onyx.skills.bundle import inspect_custom_bundle
from onyx.skills.bundle import parse_skill_md_metadata
from onyx.skills.bundle import read_custom_bundle_instructions
from onyx.skills.bundle import rewrite_custom_bundle_skill_md
from onyx.skills.bundle import rewrite_custom_bundle_text_file
from onyx.skills.bundle import slug_from_filename
from onyx.skills.bundle import strip_skill_md_frontmatter
from onyx.skills.bundle import validate_custom_bundle


def _build_zip(
    entries: list[tuple[str, bytes]],
    *,
    symlinks: list[tuple[str, bytes]] | None = None,
    fixed_date: tuple[int, int, int, int, int, int] = (2026, 1, 1, 0, 0, 0),
) -> bytes:
    """Build a zip in-memory. ``symlinks`` is a list of (path, target) pairs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, data in entries:
            info = zipfile.ZipInfo(filename=path, date_time=fixed_date)
            zf.writestr(info, data)
        for path, target in symlinks or []:
            info = zipfile.ZipInfo(filename=path, date_time=fixed_date)
            info.create_system = _ZIP_UNIX_CREATE_SYSTEM
            info.external_attr = (stat.S_IFLNK | 0o755) << 16
            zf.writestr(info, target)
    return buf.getvalue()


VALID_SKILL_MD = b"# Hello\n\nBody content.\n"


def _valid_bundle() -> bytes:
    return _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("scripts/run.sh", b"#!/bin/sh\necho hi\n"),
            ("docs/notes.md", b"# Notes\n"),
        ]
    )


def test_validator_accepts_a_well_formed_bundle() -> None:
    # No raise = pass; validator returns None.
    assert validate_custom_bundle(_valid_bundle(), slug="hello") is None


def test_validator_rejects_non_zip() -> None:
    with pytest.raises(OnyxError, match="not a valid zip"):
        validate_custom_bundle(b"not a zip", slug="hello")


def test_validator_rejects_missing_skill_md() -> None:
    zip_bytes = _build_zip([("scripts/run.sh", b"#!/bin/sh\n")])
    with pytest.raises(OnyxError, match="SKILL.md missing at bundle root"):
        validate_custom_bundle(zip_bytes, slug="hello")


def test_validator_rejects_skill_md_not_at_root() -> None:
    zip_bytes = _build_zip([("subdir/SKILL.md", VALID_SKILL_MD)])
    with pytest.raises(OnyxError, match="SKILL.md missing at bundle root"):
        validate_custom_bundle(zip_bytes, slug="hello")


def test_validator_rejects_template_file() -> None:
    zip_bytes = _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("SKILL.md.template", b"# templated\n"),
        ]
    )
    with pytest.raises(OnyxError, match="cannot ship templates"):
        validate_custom_bundle(zip_bytes, slug="hello")


def test_validator_rejects_oversized_single_file() -> None:
    zip_bytes = _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("big.bin", b"\x00" * 64),
        ]
    )
    with pytest.raises(OnyxError, match="exceeds"):
        validate_custom_bundle(zip_bytes, slug="hello", per_file_max_bytes=32)


def test_validator_rejects_oversized_total() -> None:
    zip_bytes = _build_zip(
        [
            ("SKILL.md", b"x" * 64),
            ("a.bin", b"y" * 64),
            ("b.bin", b"z" * 64),
        ]
    )
    with pytest.raises(OnyxError, match="uncompressed"):
        validate_custom_bundle(
            zip_bytes,
            slug="hello",
            per_file_max_bytes=1024,
            total_max_bytes=128,
        )


@pytest.mark.parametrize(
    "bad_slug",
    [
        "",
        "Hello",
        "1starts-with-digit",
        "has_underscore",
        "a" * 65,
        "..",
    ],
)
def test_validator_rejects_invalid_slug(bad_slug: str) -> None:
    with pytest.raises(OnyxError, match="invalid slug"):
        validate_custom_bundle(_valid_bundle(), slug=bad_slug)


def test_validator_rejects_reserved_slug() -> None:
    """``pptx`` is a codified built-in — bundle uploads using that slug
    are rejected so custom uploads can't shadow a built-in row."""
    with pytest.raises(OnyxError, match="reserved"):
        validate_custom_bundle(_valid_bundle(), slug="pptx")


def test_compute_bundle_sha256_is_deterministic_for_same_bytes() -> None:
    bundle = _valid_bundle()
    assert compute_bundle_sha256(bundle) == compute_bundle_sha256(bundle)


def test_compute_bundle_sha256_differs_when_bytes_differ() -> None:
    a = _valid_bundle()
    b = _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("scripts/run.sh", b"#!/bin/sh\necho different\n"),
        ]
    )
    assert compute_bundle_sha256(a) != compute_bundle_sha256(b)


def test_compute_bundle_sha256_differs_for_same_content_different_timestamps() -> None:
    """compute_bundle_sha256 is a raw-bytes hash — same contents repacked with
    different timestamps deliberately hash differently.

    ``deterministic over raw bytes`` — we want to detect "this is the
    exact same upload," not "the contents match."
    """
    entries = [
        ("SKILL.md", VALID_SKILL_MD),
        ("scripts/run.sh", b"#!/bin/sh\n"),
    ]
    a = _build_zip(entries, fixed_date=(2026, 1, 1, 0, 0, 0))
    b = _build_zip(entries, fixed_date=(2026, 6, 15, 12, 30, 0))
    assert a != b
    assert compute_bundle_sha256(a) != compute_bundle_sha256(b)


def test_strip_skill_md_frontmatter_returns_instruction_body() -> None:
    content = (
        "---\nname: Demo\ndescription: Demo skill\n---\n\n# Instructions\n\nDo it."
    )
    assert strip_skill_md_frontmatter(content) == "# Instructions\n\nDo it."


def test_read_custom_bundle_instructions_returns_instruction_body() -> None:
    zip_bytes = _build_zip(
        [
            (
                "SKILL.md",
                b"---\nname: Demo\ndescription: Demo skill\n---\n\n# Instructions\n\nDo it.",
            ),
            ("scripts/run.py", b"print('hi')\n"),
            ("docs/notes.md", b"# Notes\n"),
        ]
    )
    assert read_custom_bundle_instructions(zip_bytes) == "# Instructions\n\nDo it."


def test_read_custom_bundle_instructions_does_not_require_frontmatter() -> None:
    zip_bytes = _build_zip([("SKILL.md", b"# Instructions\n\nDo it.")])
    assert read_custom_bundle_instructions(zip_bytes) == "# Instructions\n\nDo it."


def test_rewrite_custom_bundle_skill_md_preserves_supporting_files() -> None:
    original = _build_zip(
        [
            (
                "SKILL.md",
                b"---\nname: Old\ndescription: Old desc\n---\n\nOld instructions.",
            ),
            ("scripts/run.py", b"print('hi')\n"),
            ("docs/notes.md", b"# Notes\n"),
        ]
    )

    rewritten = rewrite_custom_bundle_skill_md(
        original,
        slug="hello",
        name="New",
        description="New desc",
        instructions_markdown="# New instructions\n\nDo it.",
    )

    assert validate_custom_bundle(rewritten, slug="hello") is None
    assert parse_skill_md_metadata(rewritten) == ("New", "New desc")
    assert read_custom_bundle_instructions(rewritten) == "# New instructions\n\nDo it."
    with zipfile.ZipFile(io.BytesIO(rewritten)) as zf:
        assert zf.read("scripts/run.py") == b"print('hi')\n"
        assert zf.read("docs/notes.md") == b"# Notes\n"


def test_inspect_custom_bundle_returns_tree_content_and_findings() -> None:
    bundle = _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("scripts/run.sh", b"#!/bin/sh\necho hi\n"),
            ("config.txt", b"OPENAI_API_KEY=sk-example-not-real\n"),
            ("asset.bin", b"\x00\x01\x02"),
        ]
    )

    inspection = inspect_custom_bundle(bundle, slug="hello")

    assert [file.path for file in inspection.files] == [
        "SKILL.md",
        "asset.bin",
        "config.txt",
        "scripts/run.sh",
    ]
    assert inspection.files[0].content == VALID_SKILL_MD.decode()
    assert inspection.files[1].content is None
    assert inspection.status == "REVIEW"
    assert {finding.code for finding in inspection.findings} == {
        "POTENTIAL_SECRET",
        "SCRIPT_FILE",
    }
    assert all("sk-example" not in finding.message for finding in inspection.findings)


def test_diff_custom_bundles_reports_file_changes_and_text_diff() -> None:
    current = _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("notes.md", b"old line\n"),
            ("removed.txt", b"gone\n"),
        ]
    )
    candidate = _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("notes.md", b"new line\n"),
            ("added.txt", b"new\n"),
        ]
    )

    diff = diff_custom_bundles(current, candidate, slug="hello")

    assert [(entry.path, entry.change_type) for entry in diff.files] == [
        ("added.txt", "ADDED"),
        ("notes.md", "MODIFIED"),
        ("removed.txt", "DELETED"),
    ]
    notes_diff = next(entry.diff for entry in diff.files if entry.path == "notes.md")
    assert notes_diff is not None
    assert "-old line" in notes_diff
    assert "+new line" in notes_diff


def test_rewrite_custom_bundle_text_file_preserves_and_revalidates_bundle() -> None:
    original = _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("scripts/run.py", b"print('old')\n"),
            ("docs/notes.md", b"keep me\n"),
        ]
    )

    rewritten = rewrite_custom_bundle_text_file(
        original,
        slug="hello",
        path="scripts/run.py",
        content="print('new')\n",
    )

    assert validate_custom_bundle(rewritten, slug="hello") is None
    with zipfile.ZipFile(io.BytesIO(rewritten)) as zf:
        assert zf.read("scripts/run.py") == b"print('new')\n"
        assert zf.read("docs/notes.md") == b"keep me\n"


def test_validator_rejects_duplicate_file_paths() -> None:
    bundle = _build_zip([("SKILL.md", VALID_SKILL_MD), ("notes.md", b"first")])
    source = io.BytesIO(bundle)
    output = io.BytesIO()
    with (
        zipfile.ZipFile(source) as source_zip,
        zipfile.ZipFile(output, mode="w") as target_zip,
    ):
        for info in source_zip.infolist():
            target_zip.writestr(info, source_zip.read(info))
        target_zip.writestr("notes.md", b"second")

    with pytest.raises(OnyxError, match="duplicate path"):
        validate_custom_bundle(output.getvalue(), slug="hello")


def test_rewrite_custom_bundle_skill_md_rejects_oversized_skill_md_before_zip_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("onyx.skills.bundle.DEFAULT_PER_FILE_MAX_BYTES", 128)

    with pytest.raises(OnyxError) as exc_info:
        rewrite_custom_bundle_skill_md(
            b"not a zip",
            slug="hello",
            name="New",
            description="New desc",
            instructions_markdown="x" * 256,
        )

    assert exc_info.value.error_code == OnyxErrorCode.PAYLOAD_TOO_LARGE


def test_rewrite_custom_bundle_skill_md_rejects_missing_skill_md() -> None:
    original = _build_zip([("scripts/run.py", b"print('hi')\n")])

    with pytest.raises(OnyxError) as exc_info:
        rewrite_custom_bundle_skill_md(
            original,
            slug="hello",
            name="New",
            description="New desc",
            instructions_markdown="# New instructions\n\nDo it.",
        )

    assert exc_info.value.error_code == OnyxErrorCode.INTERNAL_ERROR
    assert exc_info.value.detail == "Stored skill bundle is missing SKILL.md."


def _zip_with_patched_compression_method(payload: bytes, method: int) -> bytes:
    """Build a valid ZIP_STORED zip, then patch the compression-method field
    in both the local header and the central directory to ``method``.

    `zipfile.ZipFile(...).writestr()` refuses to write an unknown method, but
    `zipfile.ZipFile(...).open()` happily reads what it can and raises
    `NotImplementedError` when it can't — which is exactly the failure mode we
    want to exercise.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("SKILL.md", payload)
    raw = bytearray(buf.getvalue())
    # Patch every occurrence of the compression-method field. In each header
    # the method is a little-endian uint16 at a fixed offset from the magic.
    for magic, offset in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
        pos = raw.find(magic)
        if pos != -1:
            raw[pos + offset : pos + offset + 2] = method.to_bytes(2, "little")
    return bytes(raw)


def test_validator_rejects_unsupported_compression() -> None:
    """A ZIP using a stdlib-unknown compression method raises NotImplementedError
    from zf.open() — we must translate that to OnyxError, not a 500."""
    zip_bytes = _zip_with_patched_compression_method(VALID_SKILL_MD, method=99)
    with pytest.raises(OnyxError, match="cannot read"):
        validate_custom_bundle(zip_bytes, slug="hello")


def test_validator_size_violation_returns_413() -> None:
    """Size-cap violations should return HTTP 413, not 400."""
    zip_bytes = _build_zip(
        [
            ("SKILL.md", VALID_SKILL_MD),
            ("big.bin", b"\x00" * 64),
        ]
    )
    with pytest.raises(OnyxError) as exc_info:
        validate_custom_bundle(zip_bytes, slug="hello", per_file_max_bytes=32)
    assert exc_info.value.status_code == 413


def test_validator_non_size_violation_returns_400() -> None:
    """Non-size violations still return 400."""
    with pytest.raises(OnyxError) as exc_info:
        validate_custom_bundle(b"not a zip", slug="hello")
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# slug_from_filename
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("deal-summary.zip", "deal-summary"),
        ("hello.ZIP", "hello"),
        ("plain", "plain"),
    ],
)
def test_slug_from_filename_strips_zip_extension(filename: str, expected: str) -> None:
    assert slug_from_filename(filename) == expected


@pytest.mark.parametrize("bad", [None, "", "Bad-Caps.zip", "with space.zip"])
def test_slug_from_filename_rejects_invalid(bad: str | None) -> None:
    with pytest.raises(OnyxError):
        slug_from_filename(bad)


# ---------------------------------------------------------------------------
# parse_skill_md_metadata
# ---------------------------------------------------------------------------


def _bundle_with_skill_md(body: bytes) -> bytes:
    return _build_zip([("SKILL.md", body)])


def test_parse_skill_md_metadata_happy_path() -> None:
    body = b"---\nname: My Skill\ndescription: Helpful description\n---\n\nbody\n"
    name, description = parse_skill_md_metadata(_bundle_with_skill_md(body))
    assert name == "My Skill"
    assert description == "Helpful description"


def test_parse_skill_md_metadata_strips_whitespace() -> None:
    body = b"---\nname: '  spaced  '\ndescription: ' desc '\n---\n\nbody\n"
    name, description = parse_skill_md_metadata(_bundle_with_skill_md(body))
    assert name == "spaced"
    assert description == "desc"


def test_parse_skill_md_metadata_rejects_missing_frontmatter() -> None:
    with pytest.raises(OnyxError, match="frontmatter"):
        parse_skill_md_metadata(_bundle_with_skill_md(b"no frontmatter here\n"))


def test_parse_skill_md_metadata_rejects_missing_name() -> None:
    body = b"---\ndescription: only a description\n---\n\nbody\n"
    with pytest.raises(OnyxError, match="name"):
        parse_skill_md_metadata(_bundle_with_skill_md(body))


def test_parse_skill_md_metadata_rejects_missing_description() -> None:
    body = b"---\nname: only a name\n---\n\nbody\n"
    with pytest.raises(OnyxError, match="description"):
        parse_skill_md_metadata(_bundle_with_skill_md(body))


def test_parse_skill_md_metadata_rejects_empty_name() -> None:
    body = b"---\nname: ''\ndescription: desc\n---\n\nbody\n"
    with pytest.raises(OnyxError, match="name"):
        parse_skill_md_metadata(_bundle_with_skill_md(body))


def test_parse_skill_md_metadata_rejects_missing_skill_md() -> None:
    zip_bytes = _build_zip([("other.txt", b"hi")])
    with pytest.raises(OnyxError, match="SKILL.md missing"):
        parse_skill_md_metadata(zip_bytes)


def test_parse_skill_md_metadata_rejects_bad_zip() -> None:
    with pytest.raises(OnyxError, match="not a valid zip"):
        parse_skill_md_metadata(b"not a zip")
