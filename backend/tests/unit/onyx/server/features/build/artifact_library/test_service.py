import pytest

from onyx.db.enums import ArtifactType
from onyx.server.features.build.artifact_library.service import infer_artifact_type
from onyx.server.features.build.artifact_library.service import normalize_artifact_name


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("report.pdf", ArtifactType.PDF),
        ("forecast.XLSX", ArtifactType.EXCEL),
        ("data.csv", ArtifactType.CSV),
        ("notes.md", ArtifactType.MARKDOWN),
        ("archive.zip", ArtifactType.OTHER),
    ],
)
def test_infer_artifact_type_from_extension(
    filename: str, expected: ArtifactType
) -> None:
    assert (
        infer_artifact_type(
            filename=filename,
            source_path=f"outputs/{filename}",
            is_directory=False,
        )
        == expected
    )


def test_infer_web_app_from_web_directory() -> None:
    assert (
        infer_artifact_type(
            filename="web.zip", source_path="outputs/web", is_directory=True
        )
        == ArtifactType.WEB_APP
    )


def test_normalize_artifact_name_uses_fallback_and_rejects_blank() -> None:
    assert normalize_artifact_name(None, "report.pdf") == "report.pdf"
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_artifact_name("   ", "report.pdf")
