"""The Site Pages library must not be ingested twice.

Production symptom this covers: fourteen sites' Home.aspx pages each produced a
`sharepoint_list_item` document whose entire body was 880 characters of list
metadata (AuthorLookupId, ContentType, DocIcon, FileLeafRef, FileSizeDisplay)
with no page text. Every one hashed identically, so fourteen distinct site
homepages were indistinguishable in the index and shadowed the real pages
produced by the dedicated site-pages path.
"""

import pytest

from onyx.connectors.sharepoint.connector import SharepointListData


def _list(template: str | None, display_name: str) -> SharepointListData:
    return SharepointListData(
        id="list-1",
        name=display_name,
        display_name=display_name,
        web_url="https://contoso.sharepoint.com/sites/X/SitePages",
        template=template,
    )


def test_site_pages_library_is_detected_by_template() -> None:
    assert _list("sitePages", "Site Pages").is_site_pages_library


def test_site_pages_library_is_detected_by_display_name_fallback() -> None:
    """Some tenants report no template; the name still identifies it."""
    assert _list(None, "Site Pages").is_site_pages_library


@pytest.mark.parametrize(
    ("template", "name"),
    [
        ("genericList", "Announcements"),
        ("documentLibrary", "Shared Documents"),
        ("genericList", "Site Assets"),
    ],
)
def test_ordinary_lists_are_not_treated_as_site_pages(template: str, name: str) -> None:
    assert not _list(template, name).is_site_pages_library


def test_site_pages_and_document_library_are_distinct() -> None:
    site_pages = _list("sitePages", "Site Pages")
    doc_library = _list("documentLibrary", "Shared Documents")

    assert site_pages.is_site_pages_library and not site_pages.is_document_library
    assert doc_library.is_document_library and not doc_library.is_site_pages_library
