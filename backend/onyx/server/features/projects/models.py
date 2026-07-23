from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from onyx.configs.constants import DocumentSource
from onyx.db.enums import ConnectedSourceCurationStatus
from onyx.db.enums import ProjectAccessLevel
from onyx.db.enums import ProjectJoinRequestStatus
from onyx.db.enums import ProjectSharePermission
from onyx.db.enums import UserFileStatus
from onyx.db.models import ConnectedSourceScope
from onyx.db.models import Document
from onyx.db.models import HierarchyNode
from onyx.db.models import ProjectConnectedKnowledgePreset
from onyx.db.models import ProjectJoinRequest
from onyx.db.models import UserFile
from onyx.db.models import UserProject
from onyx.db.projects import CategorizedFilesResult
from onyx.db.projects import compute_project_last_activity
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.file_store.models import ChatFileType
from onyx.server.models import MinimalUserSnapshot
from onyx.server.query_and_chat.chat_utils import mime_type_to_chat_file_type
from onyx.server.query_and_chat.models import ChatSessionDetails


class UserFileSnapshot(BaseModel):
    id: UUID
    temp_id: str | None = None  # Client-side temporary ID for optimistic updates
    name: str
    project_id: int | None = None
    user_id: UUID | None
    file_id: str
    created_at: datetime
    status: UserFileStatus
    last_accessed_at: datetime | None
    file_type: str | None
    chat_file_type: ChatFileType
    token_count: int | None
    chunk_count: int | None

    @classmethod
    def from_model(
        cls, model: UserFile, temp_id_map: dict[str, str] = {}
    ) -> "UserFileSnapshot":
        return cls(
            id=model.id,
            temp_id=temp_id_map.get(str(model.id)),
            name=model.name,
            project_id=None,
            user_id=model.user_id,
            file_id=model.file_id,
            created_at=model.created_at,
            status=model.status,
            last_accessed_at=model.last_accessed_at,
            file_type=model.content_type,
            chat_file_type=mime_type_to_chat_file_type(model.content_type),
            token_count=model.token_count,
            chunk_count=model.chunk_count,
        )


class TokenCountResponse(BaseModel):
    total_tokens: int


class RejectedFile(BaseModel):
    file_name: str
    reason: str


class CategorizedFilesSnapshot(BaseModel):
    user_files: list[UserFileSnapshot]
    rejected_files: list[RejectedFile]

    @classmethod
    def from_result(cls, result: CategorizedFilesResult) -> "CategorizedFilesSnapshot":
        return cls(
            user_files=[
                UserFileSnapshot.from_model(user_file, temp_id_map=result.id_to_temp_id)
                for user_file in result.user_files
            ],
            rejected_files=[
                RejectedFile(
                    file_name=rejected_file.filename,
                    reason=rejected_file.reason,
                )
                for rejected_file in result.rejected_files
            ],
        )


class ProjectConnectedDocumentSnapshot(BaseModel):
    id: str
    title: str
    link: str | None = None
    source: DocumentSource | None = None
    parent_hierarchy_node_id: int | None = None
    last_modified: datetime | None = None
    last_synced: datetime | None = None

    @classmethod
    def from_model(cls, model: Document) -> "ProjectConnectedDocumentSnapshot":
        parent = model.parent_hierarchy_node
        return cls(
            id=model.id,
            title=model.semantic_id,
            link=model.link,
            source=parent.source if parent else None,
            parent_hierarchy_node_id=model.parent_hierarchy_node_id,
            last_modified=model.last_modified,
            last_synced=model.last_synced,
        )


class ProjectConnectedHierarchyNodeSnapshot(BaseModel):
    id: int
    title: str
    link: str | None = None
    source: DocumentSource
    parent_id: int | None = None

    @classmethod
    def from_model(
        cls, model: HierarchyNode
    ) -> "ProjectConnectedHierarchyNodeSnapshot":
        return cls(
            id=model.id,
            title=model.display_name,
            link=model.link,
            source=model.source,
            parent_id=model.parent_id,
        )


class ProjectConnectedKnowledgeSnapshot(BaseModel):
    documents: list[ProjectConnectedDocumentSnapshot]
    hierarchy_nodes: list[ProjectConnectedHierarchyNodeSnapshot]

    @classmethod
    def from_project(cls, model: UserProject) -> "ProjectConnectedKnowledgeSnapshot":
        documents = sorted(model.attached_documents, key=lambda doc: doc.semantic_id)
        hierarchy_nodes = sorted(
            model.hierarchy_nodes,
            key=lambda node: (node.source.value, node.display_name),
        )
        return cls(
            documents=[
                ProjectConnectedDocumentSnapshot.from_model(document)
                for document in documents
            ],
            hierarchy_nodes=[
                ProjectConnectedHierarchyNodeSnapshot.from_model(node)
                for node in hierarchy_nodes
            ],
        )


class ProjectConnectedKnowledgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_ids: list[str] = Field(default_factory=list)
    hierarchy_node_ids: list[int] = Field(default_factory=list)


class ConnectedSourceScopeSnapshot(BaseModel):
    id: int
    hierarchy_node_id: int
    title: str
    source: DocumentSource
    link: str | None = None
    parent_id: int | None = None
    curation_status: ConnectedSourceCurationStatus
    display_label: str | None = None
    tenant_label: str | None = None
    department_label: str | None = None
    sort_order: int
    size_bytes: int | None = None
    document_count_estimate: int | None = None
    warning: str | None = None
    group_ids: list[int]
    excluded_hierarchy_node_ids: list[int]

    @classmethod
    def from_model(cls, model: ConnectedSourceScope) -> "ConnectedSourceScopeSnapshot":
        node = model.hierarchy_node
        return cls(
            id=model.id,
            hierarchy_node_id=model.hierarchy_node_id,
            title=node.display_name,
            source=node.source,
            link=node.link,
            parent_id=node.parent_id,
            curation_status=model.curation_status,
            display_label=model.display_label,
            tenant_label=model.tenant_label,
            department_label=model.department_label,
            sort_order=model.sort_order,
            size_bytes=model.size_bytes,
            document_count_estimate=model.document_count_estimate,
            warning=model.warning,
            group_ids=sorted(link.user_group_id for link in model.group_links),
            excluded_hierarchy_node_ids=sorted(
                link.excluded_hierarchy_node_id for link in model.excluded_links
            ),
        )


class ConnectedSourceScopeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curation_status: ConnectedSourceCurationStatus = (
        ConnectedSourceCurationStatus.STANDARD
    )
    display_label: str | None = None
    tenant_label: str | None = None
    department_label: str | None = None
    sort_order: int = 0
    size_bytes: int | None = None
    document_count_estimate: int | None = None
    warning: str | None = None
    group_ids: list[int] = Field(default_factory=list)
    excluded_hierarchy_node_ids: list[int] = Field(default_factory=list)


class ProjectConnectedKnowledgePresetSnapshot(BaseModel):
    id: int
    name: str
    description: str | None = None
    emoji: str | None = None
    instructions: str | None = None
    is_default: bool
    is_archived: bool
    connected_knowledge: ProjectConnectedKnowledgeSnapshot

    @classmethod
    def from_model(
        cls, model: ProjectConnectedKnowledgePreset
    ) -> "ProjectConnectedKnowledgePresetSnapshot":
        return cls(
            id=model.id,
            name=model.name,
            description=model.description,
            emoji=model.emoji,
            instructions=model.instructions,
            is_default=model.is_default,
            is_archived=model.is_archived,
            connected_knowledge=ProjectConnectedKnowledgeSnapshot(
                documents=[
                    ProjectConnectedDocumentSnapshot.from_model(document)
                    for document in sorted(
                        model.attached_documents,
                        key=lambda document: document.semantic_id,
                    )
                ],
                hierarchy_nodes=[
                    ProjectConnectedHierarchyNodeSnapshot.from_model(node)
                    for node in sorted(
                        model.hierarchy_nodes,
                        key=lambda node: (node.source.value, node.display_name),
                    )
                ],
            ),
        )


class ProjectConnectedKnowledgePresetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    emoji: str | None = None
    instructions: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    hierarchy_node_ids: list[int] = Field(default_factory=list)
    is_default: bool = False
    is_archived: bool = False


class UserProjectSnapshot(BaseModel):
    id: int
    name: str
    description: str | None
    emoji: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    user_id: UUID | None
    owner: MinimalUserSnapshot | None = None
    user_permission: ProjectAccessLevel = ProjectAccessLevel.OWNER
    organization_permission: ProjectSharePermission | None = None
    is_personal: bool = True
    is_pinned: bool = False
    instructions: str | None = None
    chat_sessions: list[ChatSessionDetails]

    @classmethod
    def from_model(
        cls,
        model: UserProject,
        *,
        requesting_user_id: UUID | None = None,
        user_permission: ProjectAccessLevel = ProjectAccessLevel.OWNER,
        is_pinned: bool = False,
    ) -> "UserProjectSnapshot":
        return cls(
            id=model.id,
            name=model.name,
            description=model.description,
            emoji=model.emoji,
            created_at=model.created_at,
            updated_at=compute_project_last_activity(model),
            user_id=model.user_id,
            is_pinned=is_pinned,
            owner=(
                MinimalUserSnapshot(
                    id=model.user.id,
                    email=model.user.email,
                    full_name=model.user.personal_name,
                )
                if model.user is not None
                else None
            ),
            user_permission=user_permission,
            organization_permission=model.organization_permission,
            is_personal=model.organization_permission is None
            and not model.user_shares
            and not model.group_shares,
            instructions=model.instructions,
            chat_sessions=[
                ChatSessionDetails.from_model(chat)
                for chat in model.chat_sessions
                if not chat.deleted
                and (requesting_user_id is None or chat.user_id == requesting_user_id)
            ],
        )


class ProjectUserShareSnapshot(BaseModel):
    user: MinimalUserSnapshot
    permission: ProjectSharePermission


class ProjectGroupShareSnapshot(BaseModel):
    group_id: int
    group_name: str
    permission: ProjectSharePermission


class ProjectJoinRequestSnapshot(BaseModel):
    id: int
    requester: MinimalUserSnapshot
    requested_permission: ProjectSharePermission
    status: ProjectJoinRequestStatus
    resolution_comment: str | None
    created_at: datetime
    resolved_at: datetime | None

    @classmethod
    def from_model(cls, model: ProjectJoinRequest) -> "ProjectJoinRequestSnapshot":
        return cls(
            id=model.id,
            requester=MinimalUserSnapshot(
                id=model.requester.id,
                email=model.requester.email,
            ),
            requested_permission=model.requested_permission,
            status=model.status,
            resolution_comment=model.resolution_comment,
            created_at=model.created_at,
            resolved_at=model.resolved_at,
        )


class ProjectSharingSnapshot(BaseModel):
    owner: MinimalUserSnapshot | None
    organization_permission: ProjectSharePermission | None
    user_shares: list[ProjectUserShareSnapshot]
    group_shares: list[ProjectGroupShareSnapshot]
    join_requests: list[ProjectJoinRequestSnapshot]

    @classmethod
    def from_model(cls, model: UserProject) -> "ProjectSharingSnapshot":
        return cls(
            owner=(
                MinimalUserSnapshot(id=model.user.id, email=model.user.email)
                if model.user is not None
                else None
            ),
            organization_permission=model.organization_permission,
            user_shares=[
                ProjectUserShareSnapshot(
                    user=MinimalUserSnapshot(
                        id=share.user.id,
                        email=share.user.email,
                    ),
                    permission=share.permission,
                )
                for share in model.user_shares
                if share.user is not None
            ],
            group_shares=[
                ProjectGroupShareSnapshot(
                    group_id=share.user_group_id,
                    group_name=share.user_group.name,
                    permission=share.permission,
                )
                for share in model.group_shares
                if share.user_group is not None
            ],
            join_requests=[
                ProjectJoinRequestSnapshot.from_model(request)
                for request in sorted(
                    model.join_requests,
                    key=lambda request: request.created_at,
                    reverse=True,
                )
            ],
        )


PROJECT_NAME_MAX_LENGTH = 255
PROJECT_DESCRIPTION_MAX_LENGTH = 255
PROJECT_EMOJI_MAX_LENGTH = 32


def normalize_project_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "Project name cannot be empty.")
    if len(normalized) > PROJECT_NAME_MAX_LENGTH:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"Project name must be {PROJECT_NAME_MAX_LENGTH} characters or fewer.",
        )
    return normalized


def normalize_project_description(description: str | None) -> str | None:
    if description is None:
        return None
    normalized = description.strip()
    if not normalized:
        return None
    if len(normalized) > PROJECT_DESCRIPTION_MAX_LENGTH:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"Project description must be {PROJECT_DESCRIPTION_MAX_LENGTH} characters or fewer.",
        )
    return normalized


def normalize_project_emoji(emoji: str | None) -> str | None:
    if emoji is None:
        return None
    normalized = emoji.strip()
    if not normalized:
        return None
    if len(normalized) > PROJECT_EMOJI_MAX_LENGTH:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"Project emoji must be {PROJECT_EMOJI_MAX_LENGTH} characters or fewer.",
        )
    return normalized


class ProjectMetadataUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    emoji: str | None = None

    def normalized_name(self) -> str | None:
        if "name" not in self.model_fields_set:
            return None
        if self.name is None:
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT, "Project name cannot be empty."
            )
        return normalize_project_name(self.name)

    def normalized_description(self) -> str | None:
        if "description" not in self.model_fields_set:
            return None
        return normalize_project_description(self.description)

    def has_description_update(self) -> bool:
        return "description" in self.model_fields_set

    def normalized_emoji(self) -> str | None:
        if "emoji" not in self.model_fields_set:
            return None
        return normalize_project_emoji(self.emoji)

    def has_emoji_update(self) -> bool:
        return "emoji" in self.model_fields_set

    def validate_has_update(self) -> None:
        if not self.model_fields_set:
            raise OnyxError(
                OnyxErrorCode.INVALID_INPUT,
                "At least one project field must be provided.",
            )


class ProjectUserShareRequest(BaseModel):
    user_id: UUID
    permission: ProjectSharePermission


class ProjectGroupShareRequest(BaseModel):
    group_id: int
    permission: ProjectSharePermission


class ProjectShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_permission: ProjectSharePermission | None = None
    user_shares: list[ProjectUserShareRequest] = Field(
        default_factory=list, max_length=100
    )
    group_shares: list[ProjectGroupShareRequest] = Field(
        default_factory=list, max_length=100
    )


class ProjectAccessRequest(BaseModel):
    requested_permission: ProjectSharePermission = ProjectSharePermission.VIEWER


class ProjectAccessRequestSnapshot(BaseModel):
    id: int
    requested_permission: ProjectSharePermission
    status: ProjectJoinRequestStatus
    created_at: datetime
    resolved_at: datetime | None

    @classmethod
    def from_model(cls, model: ProjectJoinRequest) -> "ProjectAccessRequestSnapshot":
        return cls(
            id=model.id,
            requested_permission=model.requested_permission,
            status=model.status,
            created_at=model.created_at,
            resolved_at=model.resolved_at,
        )


class ProjectAccessStateSnapshot(BaseModel):
    has_access: bool
    access_request: ProjectAccessRequestSnapshot | None = None

    @property
    def pending_request(self) -> ProjectAccessRequestSnapshot | None:
        if (
            self.access_request is not None
            and self.access_request.status == ProjectJoinRequestStatus.PENDING
        ):
            return self.access_request
        return None


class ResolveProjectAccessRequest(BaseModel):
    approve: bool
    resolution_comment: str | None = None


class ChatSessionRequest(BaseModel):
    chat_session_id: str
