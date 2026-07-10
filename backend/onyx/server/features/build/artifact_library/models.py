from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field

from onyx.db.enums import ArtifactType
from onyx.db.models import Artifact
from onyx.db.models import ArtifactLibraryItem
from onyx.server.models import MinimalUserSnapshot


class ArtifactLibraryVersionSnapshot(BaseModel):
    id: UUID
    version_number: int
    name: str
    path: str
    mime_type: str | None
    size_bytes: int | None
    created_at: datetime

    @classmethod
    def from_model(cls, version: Artifact) -> "ArtifactLibraryVersionSnapshot":
        return cls(
            id=version.id,
            version_number=version.version_number,
            name=version.name,
            path=version.path,
            mime_type=version.mime_type,
            size_bytes=version.size_bytes,
            created_at=version.created_at,
        )


class ArtifactLibraryUserShareSnapshot(BaseModel):
    user: MinimalUserSnapshot


class ArtifactLibraryGroupShareSnapshot(BaseModel):
    group_id: int
    group_name: str


class ArtifactLibraryItemSnapshot(BaseModel):
    id: UUID
    name: str
    type: ArtifactType
    is_pinned: bool
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    owner: MinimalUserSnapshot
    is_owner: bool
    latest_version: ArtifactLibraryVersionSnapshot
    versions: list[ArtifactLibraryVersionSnapshot]
    version_count: int
    user_shares: list[ArtifactLibraryUserShareSnapshot]
    group_shares: list[ArtifactLibraryGroupShareSnapshot]

    @classmethod
    def from_model(
        cls, item: ArtifactLibraryItem, *, requesting_user_id: UUID
    ) -> "ArtifactLibraryItemSnapshot":
        if not item.versions:
            raise ValueError("Artifact library item has no versions")
        latest = max(item.versions, key=lambda version: version.version_number)
        return cls(
            id=item.id,
            name=item.name,
            type=item.type,
            is_pinned=item.is_pinned,
            published_at=item.published_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
            owner=MinimalUserSnapshot(id=item.owner.id, email=item.owner.email),
            is_owner=item.owner_user_id == requesting_user_id,
            latest_version=ArtifactLibraryVersionSnapshot.from_model(latest),
            versions=[
                ArtifactLibraryVersionSnapshot.from_model(version)
                for version in sorted(
                    item.versions,
                    key=lambda version: version.version_number,
                    reverse=True,
                )
            ],
            version_count=len(item.versions),
            user_shares=[
                ArtifactLibraryUserShareSnapshot(
                    user=MinimalUserSnapshot(
                        id=share.user.id,
                        email=share.user.email,
                    )
                )
                for share in item.user_shares
            ],
            group_shares=[
                ArtifactLibraryGroupShareSnapshot(
                    group_id=share.user_group.id,
                    group_name=share.user_group.name,
                )
                for share in item.group_shares
            ],
        )


class ArtifactLibraryImportRequest(BaseModel):
    session_id: UUID
    path: str = Field(min_length=1, max_length=2048)
    name: str | None = Field(default=None, max_length=255)


class ArtifactLibraryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    is_pinned: bool | None = None
    published: bool | None = None


class ArtifactLibraryShareRequest(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list, max_length=100)
    group_ids: list[int] = Field(default_factory=list, max_length=100)


class ArtifactLibraryBulkAction(str, Enum):
    PIN = "pin"
    UNPIN = "unpin"
    PUBLISH = "publish"
    UNPUBLISH = "unpublish"
    DELETE = "delete"


class ArtifactLibraryBulkRequest(BaseModel):
    item_ids: list[UUID] = Field(min_length=1, max_length=100)
    action: ArtifactLibraryBulkAction


class ArtifactLibraryBulkResponse(BaseModel):
    affected: int
