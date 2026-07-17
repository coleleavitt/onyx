from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from onyx.db.enums import ProjectAccessLevel
from onyx.db.enums import ProjectJoinRequestStatus
from onyx.db.enums import ProjectSharePermission
from onyx.db.enums import UserFileStatus
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
