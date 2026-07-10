"""Custom skill bundle validation and helpers."""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import stat
import zipfile
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import BinaryIO
from typing import Final
from typing import Literal

import yaml

from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.skills.built_in import BUILT_IN_SKILLS
from onyx.skills.built_in import SLUG_REGEX

DEFAULT_PER_FILE_MAX_BYTES: Final[int] = int(
    os.environ.get("SKILL_BUNDLE_PER_FILE_MAX_BYTES") or 25 * 1024 * 1024
)
DEFAULT_TOTAL_MAX_BYTES: Final[int] = int(
    os.environ.get("SKILL_BUNDLE_TOTAL_MAX_BYTES") or 100 * 1024 * 1024
)
DEFAULT_TEXT_PREVIEW_MAX_BYTES: Final[int] = 256 * 1024
DEFAULT_DIFF_MAX_CHARS: Final[int] = 20_000

SKILL_MD_NAME: Final[str] = "SKILL.md"
TEMPLATE_SUFFIX: Final[str] = ".template"

_FRONTMATTER_REGEX: Final[re.Pattern[str]] = re.compile(
    r"\A---[ \t]*\r?\n(?P<frontmatter>.*?)(?:\r?\n)---[ \t]*(?:\r?\n|\Z)",
    re.DOTALL,
)

_ZIP_UNIX_CREATE_SYSTEM: Final[int] = 3

_SCRIPT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".bat", ".cmd", ".js", ".ps1", ".py", ".sh", ".ts"}
)
_EXECUTABLE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".dll", ".dylib", ".exe", ".so"}
)
_SECRET_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)(?:api[_-]?key|token|secret)\s*[:=]\s*[^\s]{8,}"),
)


@dataclass(frozen=True)
class SkillBundleFileInspection:
    path: str
    size: int
    sha256: str
    is_text: bool
    content: str | None
    content_truncated: bool


@dataclass(frozen=True)
class SkillBundleSecurityFinding:
    code: str
    severity: Literal["INFO", "WARNING"]
    message: str
    path: str | None = None


@dataclass(frozen=True)
class SkillBundleInspection:
    status: Literal["PASS", "REVIEW"]
    files: list[SkillBundleFileInspection]
    findings: list[SkillBundleSecurityFinding]
    total_uncompressed_bytes: int


@dataclass(frozen=True)
class SkillBundleFileDiff:
    path: str
    change_type: Literal["ADDED", "MODIFIED", "DELETED"]
    diff: str | None


@dataclass(frozen=True)
class SkillBundleDiff:
    files: list[SkillBundleFileDiff]
    candidate: SkillBundleInspection


def check_slug(slug: str) -> None:
    if not SLUG_REGEX.match(slug):
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, f"invalid slug '{slug}'")


def slug_from_filename(filename: str | None) -> str:
    """Derive a skill slug from the uploaded bundle's filename.

    The bundle ships as ``<slug>.zip`` — strip the extension and validate. We
    don't take basename here: any directory component is suspicious enough
    that we'd rather fail than silently massage the input.
    """
    if not filename:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "bundle upload is missing a filename",
        )
    candidate = filename
    if candidate.lower().endswith(".zip"):
        candidate = candidate[:-4]
    check_slug(candidate)
    return candidate


def read_bundle_file(bundle_file: BinaryIO) -> bytes:
    """Read a bundle stream without buffering an arbitrarily large body."""
    data = bundle_file.read(DEFAULT_TOTAL_MAX_BYTES + 1)
    if len(data) > DEFAULT_TOTAL_MAX_BYTES:
        raise OnyxError(
            OnyxErrorCode.PAYLOAD_TOO_LARGE,
            f"Skill bundle exceeds the {DEFAULT_TOTAL_MAX_BYTES} byte limit.",
        )
    return data


def parse_skill_md_metadata(zip_bytes: bytes) -> tuple[str, str]:
    """Extract ``(name, description)`` from the bundle's SKILL.md frontmatter.

    The bundle is the source of truth for skill metadata. ``validate_custom_bundle``
    has already confirmed structural shape; here we re-open the zip just for the
    SKILL.md payload because parsing frontmatter requires the contents, not the
    archive layout.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "bundle is not a valid zip")

    with zf:
        try:
            raw = zf.read(SKILL_MD_NAME)
        except KeyError:
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT,
                "SKILL.md missing at bundle root",
            )

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "SKILL.md must be UTF-8 encoded",
        ) from exc

    match = _FRONTMATTER_REGEX.match(content)
    if match is None:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "SKILL.md must start with YAML frontmatter delimited by two --- lines",
        )

    try:
        parsed = yaml.safe_load(match.group("frontmatter")) or {}
    except yaml.YAMLError as exc:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"SKILL.md frontmatter is not valid YAML: {exc}",
        ) from exc
    if not isinstance(parsed, dict):
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "SKILL.md frontmatter must be a mapping",
        )

    name = parsed.get("name")
    description = parsed.get("description")
    if not isinstance(name, str) or not name.strip():
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "SKILL.md frontmatter must include a non-empty 'name'",
        )
    if not isinstance(description, str) or not description.strip():
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "SKILL.md frontmatter must include a non-empty 'description'",
        )
    return name.strip(), description.strip()


def strip_skill_md_frontmatter(content: str) -> str:
    match = _FRONTMATTER_REGEX.match(content)
    if match is None:
        return content.strip()
    return content[match.end() :].strip()


def read_custom_bundle_instructions(zip_bytes: bytes) -> str:
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise OnyxError(
            OnyxErrorCode.INTERNAL_ERROR,
            "Stored skill bundle is not a valid zip.",
        ) from exc

    with zf:
        try:
            raw_skill_md = zf.read(SKILL_MD_NAME)
        except KeyError as exc:
            raise OnyxError(
                OnyxErrorCode.INTERNAL_ERROR,
                "Stored skill bundle is missing SKILL.md.",
            ) from exc

    try:
        skill_md = raw_skill_md.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OnyxError(
            OnyxErrorCode.INTERNAL_ERROR,
            "Stored skill bundle SKILL.md must be UTF-8 encoded.",
        ) from exc

    return strip_skill_md_frontmatter(skill_md)


def _decode_text_preview(raw: bytes) -> tuple[bool, str | None, bool]:
    if b"\x00" in raw:
        return False, None, False
    truncated = len(raw) > DEFAULT_TEXT_PREVIEW_MAX_BYTES
    preview = raw[:DEFAULT_TEXT_PREVIEW_MAX_BYTES]
    try:
        return True, preview.decode("utf-8"), truncated
    except UnicodeDecodeError:
        return False, None, False


def inspect_custom_bundle(zip_bytes: bytes, *, slug: str) -> SkillBundleInspection:
    validate_custom_bundle(zip_bytes, slug=slug)
    files: list[SkillBundleFileInspection] = []
    findings: list[SkillBundleSecurityFinding] = []
    total_uncompressed_bytes = 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in sorted(zf.infolist(), key=lambda entry: entry.filename):
            if info.is_dir():
                continue
            path = _validated_bundle_path(info)
            raw = zf.read(info)
            total_uncompressed_bytes += len(raw)
            is_text, content, content_truncated = _decode_text_preview(raw)
            files.append(
                SkillBundleFileInspection(
                    path=path,
                    size=len(raw),
                    sha256=hashlib.sha256(raw).hexdigest(),
                    is_text=is_text,
                    content=content,
                    content_truncated=content_truncated,
                )
            )

            suffix = Path(path).suffix.lower()
            if suffix in _EXECUTABLE_SUFFIXES:
                findings.append(
                    SkillBundleSecurityFinding(
                        code="EXECUTABLE_FILE",
                        severity="WARNING",
                        message="Compiled executable content requires review.",
                        path=path,
                    )
                )
            elif suffix in _SCRIPT_SUFFIXES:
                findings.append(
                    SkillBundleSecurityFinding(
                        code="SCRIPT_FILE",
                        severity="INFO",
                        message="Executable script content requires review.",
                        path=path,
                    )
                )

            if (
                is_text
                and content is not None
                and any(pattern.search(content) for pattern in _SECRET_PATTERNS)
            ):
                findings.append(
                    SkillBundleSecurityFinding(
                        code="POTENTIAL_SECRET",
                        severity="WARNING",
                        message="Potential embedded credential detected; the value is hidden.",
                        path=path,
                    )
                )

    return SkillBundleInspection(
        status="REVIEW" if findings else "PASS",
        files=files,
        findings=findings,
        total_uncompressed_bytes=total_uncompressed_bytes,
    )


def diff_custom_bundles(
    current_zip_bytes: bytes,
    candidate_zip_bytes: bytes,
    *,
    slug: str,
) -> SkillBundleDiff:
    current = inspect_custom_bundle(current_zip_bytes, slug=slug)
    candidate = inspect_custom_bundle(candidate_zip_bytes, slug=slug)
    current_by_path = {file.path: file for file in current.files}
    candidate_by_path = {file.path: file for file in candidate.files}
    diffs: list[SkillBundleFileDiff] = []

    for path in sorted(set(current_by_path) | set(candidate_by_path)):
        before = current_by_path.get(path)
        after = candidate_by_path.get(path)
        if before is not None and after is not None and before.sha256 == after.sha256:
            continue

        if before is None:
            change_type: Literal["ADDED", "MODIFIED", "DELETED"] = "ADDED"
        elif after is None:
            change_type = "DELETED"
        else:
            change_type = "MODIFIED"

        text_diff: str | None = None
        if (before is None or before.is_text) and (after is None or after.is_text):
            before_lines = (
                (before.content or "").splitlines(keepends=True) if before else []
            )
            after_lines = (
                (after.content or "").splitlines(keepends=True) if after else []
            )
            rendered = "".join(
                unified_diff(
                    before_lines,
                    after_lines,
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
            )
            text_diff = rendered[:DEFAULT_DIFF_MAX_CHARS]

        diffs.append(
            SkillBundleFileDiff(
                path=path,
                change_type=change_type,
                diff=text_diff,
            )
        )

    return SkillBundleDiff(files=diffs, candidate=candidate)


def build_skill_md(
    *,
    name: str,
    description: str,
    instructions_markdown: str,
) -> str:
    name = name.strip()
    description = description.strip()
    instructions_markdown = instructions_markdown.strip()
    if not name:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "Skill name cannot be empty.")
    if not description:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "Skill description cannot be empty.",
        )
    if not instructions_markdown:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            "Skill instructions cannot be empty.",
        )

    frontmatter = yaml.safe_dump(
        {"name": name, "description": description},
        sort_keys=False,
        allow_unicode=True,
    ).strip()
    return f"---\n{frontmatter}\n---\n\n{instructions_markdown}\n"


def rewrite_custom_bundle_skill_md(
    zip_bytes: bytes,
    *,
    slug: str,
    name: str,
    description: str,
    instructions_markdown: str,
) -> bytes:
    """Return a new custom bundle with root SKILL.md replaced.

    Existing supporting files are copied through unchanged. The resulting
    archive is validated with the normal custom-bundle validator before it is
    returned to callers for storage.
    """
    check_slug(slug)
    if slug in BUILT_IN_SKILLS:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, f"slug '{slug}' is reserved")

    new_skill_md = build_skill_md(
        name=name,
        description=description,
        instructions_markdown=instructions_markdown,
    ).encode("utf-8")
    if len(new_skill_md) > DEFAULT_PER_FILE_MAX_BYTES:
        raise OnyxError(
            OnyxErrorCode.PAYLOAD_TOO_LARGE,
            f"file '{SKILL_MD_NAME}' exceeds "
            f"{DEFAULT_PER_FILE_MAX_BYTES // (1024 * 1024)} MiB",
        )

    try:
        source_zip = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise OnyxError(
            OnyxErrorCode.INTERNAL_ERROR,
            "Stored skill bundle is not a valid zip.",
        ) from exc

    output = io.BytesIO()
    saw_skill_md = False
    with (
        source_zip,
        zipfile.ZipFile(
            output, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as target_zip,
    ):
        for info in source_zip.infolist():
            try:
                normalized = _validated_bundle_path(info)
            except OnyxError as exc:
                raise OnyxError(
                    OnyxErrorCode.INTERNAL_ERROR,
                    "Stored skill bundle contains an unsafe path or symlink.",
                ) from exc

            if normalized == SKILL_MD_NAME:
                if saw_skill_md:
                    continue
                fresh_info = zipfile.ZipInfo(filename=SKILL_MD_NAME)
                fresh_info.compress_type = zipfile.ZIP_DEFLATED
                target_zip.writestr(fresh_info, new_skill_md)
                saw_skill_md = True
                continue

            if info.is_dir():
                target_zip.writestr(info, b"")
            else:
                try:
                    target_zip.writestr(info, source_zip.read(info))
                except Exception as exc:
                    raise OnyxError(
                        OnyxErrorCode.INTERNAL_ERROR,
                        "Failed to read stored skill bundle entry.",
                    ) from exc

    if not saw_skill_md:
        raise OnyxError(
            OnyxErrorCode.INTERNAL_ERROR,
            "Stored skill bundle is missing SKILL.md.",
        )

    rewritten = output.getvalue()
    validate_custom_bundle(rewritten, slug=slug)
    return rewritten


def rewrite_custom_bundle_text_file(
    zip_bytes: bytes,
    *,
    slug: str,
    path: str,
    content: str,
) -> bytes:
    validate_custom_bundle(zip_bytes, slug=slug)
    normalized_path = _validated_bundle_path(zipfile.ZipInfo(filename=path))
    encoded_content = content.encode("utf-8")
    if len(encoded_content) > DEFAULT_PER_FILE_MAX_BYTES:
        raise OnyxError(
            OnyxErrorCode.PAYLOAD_TOO_LARGE,
            f"file '{normalized_path}' exceeds "
            f"{DEFAULT_PER_FILE_MAX_BYTES // (1024 * 1024)} MiB",
        )

    output = io.BytesIO()
    found = False
    with (
        zipfile.ZipFile(io.BytesIO(zip_bytes)) as source_zip,
        zipfile.ZipFile(
            output, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as target_zip,
    ):
        for info in source_zip.infolist():
            normalized = _validated_bundle_path(info)
            if info.is_dir():
                target_zip.writestr(info, b"")
                continue

            raw = source_zip.read(info)
            if normalized == normalized_path:
                if b"\x00" in raw:
                    raise OnyxError(
                        OnyxErrorCode.INVALID_INPUT,
                        f"file '{normalized_path}' is binary and cannot be edited as text",
                    )
                try:
                    raw.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise OnyxError(
                        OnyxErrorCode.INVALID_INPUT,
                        f"file '{normalized_path}' is not UTF-8 text",
                    ) from exc
                raw = encoded_content
                found = True
            target_zip.writestr(info, raw)

    if not found:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"file '{normalized_path}' was not found in the skill bundle",
        )

    rewritten = output.getvalue()
    validate_custom_bundle(rewritten, slug=slug)
    if normalized_path == SKILL_MD_NAME:
        parse_skill_md_metadata(rewritten)
    return rewritten


def _validated_bundle_path(info: zipfile.ZipInfo) -> str:
    """Return the normalized bundle path, rejecting traversal and symlinks."""
    name = info.filename
    trimmed = name.rstrip("/")
    if not trimmed:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"bundle entry has empty path: '{name}'",
        )
    if trimmed.startswith("/") or "\\" in trimmed:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"bundle entry escapes root: '{name}'",
        )
    parts = trimmed.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"bundle entry escapes root: '{name}'",
        )
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    if info.create_system == _ZIP_UNIX_CREATE_SYSTEM and stat.S_ISLNK(unix_mode):
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"bundle contains a symlink: '{trimmed}'",
        )
    return trimmed


def validate_custom_bundle(
    zip_bytes: bytes,
    slug: str,
    *,
    per_file_max_bytes: int = DEFAULT_PER_FILE_MAX_BYTES,
    total_max_bytes: int = DEFAULT_TOTAL_MAX_BYTES,
) -> None:
    """Validate a custom skill bundle. Returns on success, raises on failure.

    Args:
        zip_bytes: Raw zip bytes uploaded by an admin.
        slug: Caller-supplied slug for this skill.
        per_file_max_bytes: Per-entry uncompressed cap.
        total_max_bytes: Total uncompressed cap.

    Raises:
        OnyxError(INVALID_INPUT): structural violations (bad slug, missing
            SKILL.md, traversal, symlink, template, unreadable entry).
        OnyxError(PAYLOAD_TOO_LARGE): per-file or total size cap exceeded.
    """
    check_slug(slug)
    if slug in BUILT_IN_SKILLS:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, f"slug '{slug}' is reserved")

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "bundle is not a valid zip")

    with zf:
        total = 0
        saw_skill_md = False
        seen_paths: set[str] = set()

        for info in zf.infolist():
            normalized = _validated_bundle_path(info)
            if normalized in seen_paths:
                raise OnyxError(
                    OnyxErrorCode.INVALID_INPUT,
                    f"bundle contains duplicate path: '{normalized}'",
                )
            seen_paths.add(normalized)
            if info.is_dir():
                continue

            if normalized.endswith(TEMPLATE_SUFFIX):
                raise OnyxError(
                    OnyxErrorCode.INVALID_INPUT,
                    "custom skills cannot ship templates",
                )

            size = 0
            try:
                with zf.open(info, mode="r") as fh:
                    while True:
                        chunk = fh.read(64 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > per_file_max_bytes:
                            raise OnyxError(
                                OnyxErrorCode.PAYLOAD_TOO_LARGE,
                                f"file '{normalized}' exceeds "
                                f"{per_file_max_bytes // (1024 * 1024)} MiB",
                            )
                        total += len(chunk)
                        if total > total_max_bytes:
                            raise OnyxError(
                                OnyxErrorCode.PAYLOAD_TOO_LARGE,
                                f"bundle exceeds "
                                f"{total_max_bytes // (1024 * 1024)} MiB uncompressed",
                            )
            except OnyxError:
                raise
            except Exception as exc:
                raise OnyxError(
                    OnyxErrorCode.INVALID_INPUT,
                    f"cannot read '{normalized}': {exc}",
                ) from exc

            if normalized == SKILL_MD_NAME:
                saw_skill_md = True

        if not saw_skill_md:
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT,
                "SKILL.md missing at bundle root",
            )


def _safe_unzip(
    zip_bytes: bytes,
    dest: Path,
    *,
    per_file_max_bytes: int = DEFAULT_PER_FILE_MAX_BYTES,
    total_max_bytes: int = DEFAULT_TOTAL_MAX_BYTES,
) -> None:
    """Defensive unzip into ``dest`` for use at materialization time.

    The validator should have already rejected traversal/symlink/oversized
    bundles at upload, but a validator bug or a tampered blob shouldn't equal
    a sandbox escape or a disk-exhaustion incident. We re-check everything
    here — traversal, symlinks, and the same per-file + total size caps.

    On any failure mid-extraction (size cap hit, OS error, unsupported
    compression, etc.) the entire ``dest`` directory is removed before the
    error propagates, so the caller never sees a half-populated skill tree.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "bundle is not a valid zip")

    _mkdir_or_raise(dest)
    dest_resolved = dest.resolve()

    try:
        with zf:
            total = 0
            for info in zf.infolist():
                normalized = _validated_bundle_path(info)
                target = (dest / normalized).resolve()
                try:
                    target.relative_to(dest_resolved)
                except ValueError:
                    raise OnyxError(
                        OnyxErrorCode.INVALID_INPUT,
                        f"bundle entry escapes root: '{info.filename}'",
                    )
                if info.is_dir():
                    _mkdir_or_raise(target)
                    continue
                _mkdir_or_raise(target.parent)
                size = 0
                try:
                    with zf.open(info, mode="r") as src, open(target, "wb") as out:
                        while True:
                            chunk = src.read(64 * 1024)
                            if not chunk:
                                break
                            size += len(chunk)
                            if size > per_file_max_bytes:
                                raise OnyxError(
                                    OnyxErrorCode.PAYLOAD_TOO_LARGE,
                                    f"file '{normalized}' exceeds "
                                    f"{per_file_max_bytes // (1024 * 1024)} MiB",
                                )
                            total += len(chunk)
                            if total > total_max_bytes:
                                raise OnyxError(
                                    OnyxErrorCode.PAYLOAD_TOO_LARGE,
                                    f"bundle exceeds "
                                    f"{total_max_bytes // (1024 * 1024)} MiB uncompressed",
                                )
                            out.write(chunk)
                except OnyxError:
                    raise
                except Exception as exc:
                    raise OnyxError(
                        OnyxErrorCode.INVALID_INPUT,
                        f"cannot extract '{normalized}': {exc}",
                    ) from exc
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise


def _mkdir_or_raise(path: Path) -> None:
    """``path.mkdir(parents=True, exist_ok=True)`` with OS errors translated
    to ``OnyxError`` so failed bundle extraction never surfaces as a 500."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"cannot create '{path}': {exc}",
        ) from exc


def compute_bundle_sha256(zip_bytes: bytes) -> str:
    """SHA-256 of the raw upload bytes.

    Hashed over the zip-as-uploaded — two zips with identical contents but
    different timestamps still hash differently. We're detecting "this is the
    exact same upload," not "the contents match."
    """
    return hashlib.sha256(zip_bytes).hexdigest()
