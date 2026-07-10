from pathlib import Path

from onyx.db.enums import ArtifactType

ARTIFACT_LIBRARY_MAX_BYTES = 100 * 1024 * 1024

_EXTENSION_TYPES = {
    ".pptx": ArtifactType.PPTX,
    ".docx": ArtifactType.DOCX,
    ".pdf": ArtifactType.PDF,
    ".png": ArtifactType.IMAGE,
    ".jpg": ArtifactType.IMAGE,
    ".jpeg": ArtifactType.IMAGE,
    ".gif": ArtifactType.IMAGE,
    ".webp": ArtifactType.IMAGE,
    ".svg": ArtifactType.IMAGE,
    ".md": ArtifactType.MARKDOWN,
    ".markdown": ArtifactType.MARKDOWN,
    ".xlsx": ArtifactType.EXCEL,
    ".xls": ArtifactType.EXCEL,
    ".csv": ArtifactType.CSV,
}


def infer_artifact_type(
    *, filename: str, source_path: str, is_directory: bool
) -> ArtifactType:
    if is_directory and Path(source_path.rstrip("/")).name == "web":
        return ArtifactType.WEB_APP
    return _EXTENSION_TYPES.get(Path(filename).suffix.lower(), ArtifactType.OTHER)


def normalize_artifact_name(name: str | None, fallback: str) -> str:
    normalized = (name or fallback).strip()
    if not normalized:
        raise ValueError("Artifact name cannot be empty")
    if len(normalized) > 255:
        raise ValueError("Artifact name must be 255 characters or fewer")
    return normalized
