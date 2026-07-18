import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from onyx.db.enums import MemoryCategory
from onyx.db.enums import MemorySourceType
from onyx.db.models import Memory
from onyx.db.models import MemoryRevision
from onyx.db.models import MemorySource


class MemorySnapshot(BaseModel):
    id: int
    title: str
    category: MemoryCategory
    content: str
    # Space scope: set when the memory only applies inside one project (space);
    # both None for global memories.
    project_id: int | None
    project_name: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @classmethod
    def from_model(cls, memory: Memory) -> "MemorySnapshot":
        return cls(
            id=memory.id,
            title=memory.title or "Untitled memory",
            category=memory.category,
            content=memory.memory_text,
            project_id=memory.project_id,
            project_name=memory.project.name if memory.project else None,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
        )


class MemoryListResponse(BaseModel):
    items: list[MemorySnapshot]
    total: int
    category_counts: dict[MemoryCategory, int]


class MemoryCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    category: MemoryCategory = MemoryCategory.NOTES
    content: str = Field(min_length=1, max_length=20_000)
    # Scope the new memory to a project (space); omit for a global memory.
    project_id: int | None = None


class MemoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    category: MemoryCategory | None = None
    content: str | None = Field(default=None, min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def require_update(self) -> "MemoryUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one memory field must be provided")
        return self


class MemoryRevisionSnapshot(BaseModel):
    id: UUID
    memory_id: int
    title: str
    category: MemoryCategory
    content: str
    source: str
    created_at: datetime.datetime

    @classmethod
    def from_model(cls, revision: MemoryRevision) -> "MemoryRevisionSnapshot":
        return cls(
            id=revision.id,
            memory_id=revision.memory_id,
            title=revision.title or "Untitled memory",
            category=revision.category,
            content=revision.memory_text,
            source=revision.source,
            created_at=revision.created_at,
        )


class MemorySourceSnapshot(BaseModel):
    id: int
    source_type: MemorySourceType
    source_id: str | None
    label: str
    url: str | None
    created_at: datetime.datetime

    @classmethod
    def from_model(cls, source: MemorySource) -> "MemorySourceSnapshot":
        return cls(
            id=source.id,
            source_type=source.source_type,
            source_id=source.source_id,
            label=source.label,
            url=source.url,
            created_at=source.created_at,
        )


class RelatedMemory(BaseModel):
    id: int
    title: str
    category: MemoryCategory


class RelatedMemoriesResponse(BaseModel):
    # Related pages grouped by their category (entities / concepts / workstreams
    # / notes), mirroring the reference "Related pages" section.
    groups: dict[MemoryCategory, list[RelatedMemory]]


class BrainSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    brain_enabled: bool
    brain_use_connectors: bool
    brain_focus_instructions: str | None = Field(default=None, max_length=2000)


class BrainRunTriggerResponse(BaseModel):
    queued: bool
    # How long until another manual run may be requested.
    cooldown_seconds: int
