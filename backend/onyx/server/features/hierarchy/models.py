from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from pydantic import Field

from onyx.configs.constants import DocumentSource
from onyx.db.enums import ConnectedSourceCurationStatus
from onyx.server.features.hierarchy.constants import DOCUMENT_PAGE_SIZE


class DocumentSortField(str, Enum):
    NAME = "name"
    LAST_UPDATED = "last_updated"


class DocumentSortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class FolderPosition(str, Enum):
    ON_TOP = "on_top"
    MIXED = "mixed"


class HierarchyNodesRequest(BaseModel):
    source: DocumentSource


class HierarchyNodeGovernanceSnapshot(BaseModel):
    curation_status: ConnectedSourceCurationStatus | None = None
    is_default: bool = False
    is_archived: bool = False
    is_hidden: bool = False
    is_diagnostic: bool = False
    is_selectable: bool = True
    denial_reason: str | None = None
    display_label: str | None = None
    tenant_label: str | None = None
    department_label: str | None = None
    sort_order: int = 0
    size_bytes: int | None = None
    document_count_estimate: int | None = None
    indexed_document_count: int = 0
    indexed_chunk_count: int = 0
    indexing_status: str | None = None
    last_synced_at: datetime | None = None
    warning: str | None = None
    allowed_group_ids: list[int] = Field(default_factory=list)
    excluded_hierarchy_node_ids: list[int] = Field(default_factory=list)


class HierarchyNodeSummary(BaseModel):
    id: int
    title: str
    link: str | None
    parent_id: int | None
    governance: HierarchyNodeGovernanceSnapshot | None = None


class HierarchyNodesResponse(BaseModel):
    nodes: list[HierarchyNodeSummary]


class DocumentPageCursor(BaseModel):
    # Fields for last_updated sorting
    last_modified: datetime | None = None
    last_synced: datetime | None = None
    # Field for name sorting
    name: str | None = None
    # Document ID for tie-breaking (always required when cursor is set)
    document_id: str

    @classmethod
    def from_document(
        cls,
        document: "DocumentSummary",
        sort_field: DocumentSortField,
    ) -> "DocumentPageCursor":
        if sort_field == DocumentSortField.NAME:
            return cls(
                name=document.title,
                document_id=document.id,
            )
        # Default: LAST_UPDATED
        return cls(
            last_modified=document.last_modified,
            last_synced=document.last_synced,
            document_id=document.id,
        )


class HierarchyNodeDocumentsRequest(BaseModel):
    parent_hierarchy_node_id: int
    cursor: DocumentPageCursor | None = None
    sort_field: DocumentSortField = DocumentSortField.LAST_UPDATED
    sort_direction: DocumentSortDirection = DocumentSortDirection.DESC
    folder_position: FolderPosition = FolderPosition.ON_TOP


class DocumentSummary(BaseModel):
    id: str
    title: str
    link: str | None
    parent_id: int | None
    last_modified: datetime | None
    last_synced: datetime | None


class HierarchyNodeDocumentsResponse(BaseModel):
    documents: list[DocumentSummary]
    next_cursor: DocumentPageCursor | None
    page_size: int = DOCUMENT_PAGE_SIZE
    sort_field: DocumentSortField = DocumentSortField.LAST_UPDATED
    sort_direction: DocumentSortDirection = DocumentSortDirection.DESC
    folder_position: FolderPosition = FolderPosition.ON_TOP


class HierarchyNodeSearchSummary(BaseModel):
    id: int
    title: str
    link: str | None
    parent_id: int | None
    source: DocumentSource


class HierarchyNodeSearchResponse(BaseModel):
    nodes: list[HierarchyNodeSearchSummary]
