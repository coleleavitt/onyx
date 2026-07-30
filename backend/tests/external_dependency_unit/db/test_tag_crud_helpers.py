"""Focused CRUD/search coverage for document tag DB utilities."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from onyx.configs.constants import DocumentSource
from onyx.db.models import Document
from onyx.db.models import Document__Tag
from onyx.db.models import Tag
from onyx.db.tag import check_tag_validity
from onyx.db.tag import create_or_add_document_tag
from onyx.db.tag import create_or_add_document_tag_list
from onyx.db.tag import delete_document_tags_for_documents__no_commit
from onyx.db.tag import find_tags
from onyx.db.tag import get_structured_tags_for_document
from onyx.db.tag import upsert_document_tags


@pytest.fixture()
def tag_suffix() -> str:
    return uuid4().hex[:8]


@pytest.fixture()
def cleanup_tag_rows(db_session: Session, tag_suffix: str) -> Iterator[None]:
    yield
    docs = db_session.query(Document).filter(Document.id.like(f"%_{tag_suffix}")).all()
    for doc in docs:
        db_session.delete(doc)
    tags = (
        db_session.query(Tag)
        .filter(
            (Tag.tag_key.like(f"%{tag_suffix}%"))
            | (Tag.tag_value.like(f"%{tag_suffix}%"))
        )
        .all()
    )
    for tag in tags:
        db_session.delete(tag)
    db_session.commit()


def _document(document_id: str) -> Document:
    return Document(
        id=document_id,
        semantic_id=f"semantic_{document_id}",
        boost=0,
        hidden=False,
        from_ingestion_api=False,
    )


@pytest.mark.usefixtures("cleanup_tag_rows")
def test_tag_crud_search_and_structured_metadata(
    db_session: Session, tag_suffix: str
) -> None:
    document_id = f"tag_crud_doc_{tag_suffix}"
    db_session.add(_document(document_id))
    db_session.commit()

    assert check_tag_validity("short", "value")
    assert not check_tag_validity("k" * 128, "v" * 128)
    assert (
        create_or_add_document_tag(
            "k" * 128, "v" * 128, DocumentSource.FILE, document_id, db_session
        )
        is None
    )
    assert (
        create_or_add_document_tag_list(
            "k" * 128, ["v" * 128], DocumentSource.FILE, document_id, db_session
        )
        == []
    )

    single_tag = create_or_add_document_tag(
        f"department_{tag_suffix}",
        f"billing_{tag_suffix}",
        DocumentSource.FILE,
        document_id,
        db_session,
    )
    assert single_tag is not None
    duplicate_single_tag = create_or_add_document_tag(
        f"department_{tag_suffix}",
        f"billing_{tag_suffix}",
        DocumentSource.FILE,
        document_id,
        db_session,
    )
    assert duplicate_single_tag is not None
    assert duplicate_single_tag.id == single_tag.id

    list_tags = create_or_add_document_tag_list(
        f"audience_{tag_suffix}",
        [f"advisor_{tag_suffix}", f"ops_{tag_suffix}"],
        DocumentSource.FILE,
        document_id,
        db_session,
    )
    assert {tag.tag_value for tag in list_tags} == {
        f"advisor_{tag_suffix}",
        f"ops_{tag_suffix}",
    }

    metadata = get_structured_tags_for_document(document_id, db_session)
    assert metadata[f"department_{tag_suffix}"] == f"billing_{tag_suffix}"
    assert sorted(metadata[f"audience_{tag_suffix}"]) == [
        f"advisor_{tag_suffix}",
        f"ops_{tag_suffix}",
    ]

    key_matches = find_tags(
        f"department_{tag_suffix}", None, [DocumentSource.FILE], 10, db_session
    )
    assert [tag.id for tag in key_matches] == [single_tag.id]

    value_matches = find_tags(
        None, f"advisor_{tag_suffix}", [DocumentSource.FILE], 10, db_session
    )
    assert {tag.tag_value for tag in value_matches} == {f"advisor_{tag_suffix}"}

    both_matches = find_tags(
        f"audience_{tag_suffix}",
        f"ops_{tag_suffix}",
        [DocumentSource.FILE],
        10,
        db_session,
        require_both_to_match=True,
    )
    assert {tag.tag_value for tag in both_matches} == {f"ops_{tag_suffix}"}

    upserted_tags = upsert_document_tags(
        document_id,
        DocumentSource.FILE,
        {
            f"department_{tag_suffix}": f"compliance_{tag_suffix}",
            f"audience_{tag_suffix}": [f"legal_{tag_suffix}"],
        },
        db_session,
    )
    assert {tag.tag_value for tag in upserted_tags} == {
        f"compliance_{tag_suffix}",
        f"legal_{tag_suffix}",
    }
    replaced_metadata = get_structured_tags_for_document(document_id, db_session)
    assert replaced_metadata == {
        f"department_{tag_suffix}": f"compliance_{tag_suffix}",
        f"audience_{tag_suffix}": [f"legal_{tag_suffix}"],
    }

    delete_document_tags_for_documents__no_commit([document_id], db_session)
    db_session.flush()
    assert get_structured_tags_for_document(document_id, db_session) == {}


@pytest.mark.usefixtures("cleanup_tag_rows")
def test_tag_helpers_reject_missing_documents(
    db_session: Session, tag_suffix: str
) -> None:
    missing_document_id = f"missing_doc_{tag_suffix}"

    with pytest.raises(ValueError, match="Invalid Document, cannot attach Tags"):
        create_or_add_document_tag(
            f"missing_key_{tag_suffix}",
            f"missing_value_{tag_suffix}",
            DocumentSource.FILE,
            missing_document_id,
            db_session,
        )

    with pytest.raises(ValueError, match="Invalid Document, cannot attach Tags"):
        create_or_add_document_tag_list(
            f"missing_list_{tag_suffix}",
            [f"missing_value_{tag_suffix}"],
            DocumentSource.FILE,
            missing_document_id,
            db_session,
        )

    with pytest.raises(ValueError, match="Invalid Document, cannot attach Tags"):
        upsert_document_tags(
            missing_document_id,
            DocumentSource.FILE,
            {f"missing_key_{tag_suffix}": f"missing_value_{tag_suffix}"},
            db_session,
        )

    with pytest.raises(ValueError, match="Invalid Document, cannot find tags"):
        get_structured_tags_for_document(missing_document_id, db_session)


@pytest.mark.usefixtures("cleanup_tag_rows")
def test_structured_metadata_handles_inconsistent_tag_shapes(
    db_session: Session, tag_suffix: str
) -> None:
    document_id = f"inconsistent_tag_doc_{tag_suffix}"
    document = _document(document_id)
    scalar_tag = Tag(
        tag_key=f"mixed_{tag_suffix}",
        tag_value=f"scalar_{tag_suffix}",
        source=DocumentSource.FILE,
        is_list=False,
    )
    list_tag = Tag(
        tag_key=f"mixed_{tag_suffix}",
        tag_value=f"list_{tag_suffix}",
        source=DocumentSource.FILE,
        is_list=True,
    )
    db_session.add_all([document, scalar_tag, list_tag])
    db_session.flush()
    db_session.add_all(
        [
            Document__Tag(document_id=document_id, tag_id=scalar_tag.id),
            Document__Tag(document_id=document_id, tag_id=list_tag.id),
        ]
    )
    db_session.commit()

    metadata = get_structured_tags_for_document(document_id, db_session)
    assert metadata[f"mixed_{tag_suffix}"] == [
        f"scalar_{tag_suffix}",
        f"list_{tag_suffix}",
    ]


@pytest.mark.usefixtures("cleanup_tag_rows")
def test_structured_metadata_preserves_scalar_after_list_tag(
    db_session: Session, tag_suffix: str
) -> None:
    document_id = f"inconsistent_reverse_tag_doc_{tag_suffix}"
    document = _document(document_id)
    list_tag = Tag(
        tag_key=f"mixed_reverse_{tag_suffix}",
        tag_value=f"list_{tag_suffix}",
        source=DocumentSource.FILE,
        is_list=True,
    )
    scalar_tag = Tag(
        tag_key=f"mixed_reverse_{tag_suffix}",
        tag_value=f"scalar_{tag_suffix}",
        source=DocumentSource.FILE,
        is_list=False,
    )
    db_session.add_all([document, list_tag, scalar_tag])
    db_session.flush()
    db_session.add_all(
        [
            Document__Tag(document_id=document_id, tag_id=list_tag.id),
            Document__Tag(document_id=document_id, tag_id=scalar_tag.id),
        ]
    )
    db_session.commit()

    metadata = get_structured_tags_for_document(document_id, db_session)
    assert metadata[f"mixed_reverse_{tag_suffix}"] == [
        f"list_{tag_suffix}",
        f"scalar_{tag_suffix}",
    ]
