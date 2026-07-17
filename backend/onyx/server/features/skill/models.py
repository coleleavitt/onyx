"""Pydantic request and response models for the skills API."""

import datetime
from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator
from sqlalchemy.orm import Session

from onyx.db.enums import SkillAccessLevel
from onyx.db.enums import SkillReviewStatus
from onyx.db.enums import SkillSharePermission
from onyx.db.models import Skill
from onyx.db.models import SkillReviewSubmission
from onyx.server.models import MinimalUserSnapshot
from onyx.skills.built_in import BuiltInSkillDefinition
from onyx.skills.bundle import SkillBundleDiff
from onyx.skills.bundle import SkillBundleInspection
from onyx.skills.models import SkillBundleFile


class SkillUserShare(BaseModel):
    user: MinimalUserSnapshot
    permission: SkillSharePermission


class SkillGroupShare(BaseModel):
    group_id: int
    group_name: str
    permission: SkillSharePermission


class SkillResponse(BaseModel):
    source: Literal["builtin", "custom"]
    id: UUID
    slug: str
    name: str
    description: str
    category: str
    user_enabled: bool = True

    is_available: bool | None = None
    unavailable_reason: str | None = None
    is_valid: bool | None = None

    enabled: bool
    can_toggle: bool
    author_user_id: UUID | None = None
    author_email: str | None = None
    owner: MinimalUserSnapshot | None = None
    ownership_vacant: bool = False
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    user_shares: list[SkillUserShare] = Field(default_factory=list)
    group_shares: list[SkillGroupShare] = Field(default_factory=list)
    public_permission: SkillSharePermission | None = None
    is_personal: bool = False
    user_permission: SkillAccessLevel | None = None
    review_status: SkillReviewStatus | None = None
    review_submitted_at: datetime.datetime | None = None

    @classmethod
    def from_builtin(
        cls,
        skill: Skill,
        definition: BuiltInSkillDefinition,
        db_session: Session,
        enabled: bool,
        can_toggle: bool,
    ) -> "SkillResponse":
        return cls(
            source="builtin",
            id=skill.id,
            slug=skill.slug,
            name=skill.name,
            description=skill.description,
            category=skill.category,
            user_enabled=enabled,
            is_available=definition.is_available(db_session),
            unavailable_reason=definition.unavailable_reason,
            enabled=enabled,
            can_toggle=can_toggle,
            user_permission=SkillAccessLevel.VIEWER,
        )

    @classmethod
    def from_custom(
        cls,
        skill: Skill,
        *,
        enabled: bool,
        can_toggle: bool = True,
        user_permission: SkillAccessLevel | None = None,
        include_share_details: bool = False,
    ) -> "SkillResponse":
        user_shares = [
            SkillUserShare(
                user=MinimalUserSnapshot(id=share.user.id, email=share.user.email),
                permission=share.permission,
            )
            for share in skill.user_shares
            if share.user is not None
        ]
        group_shares = [
            SkillGroupShare(
                group_id=share.user_group_id,
                group_name=share.user_group.name,
                permission=share.permission,
            )
            for share in skill.group_shares
            if share.user_group is not None
        ]
        visible_user_shares = user_shares if include_share_details else []
        visible_group_shares = group_shares if include_share_details else []
        latest_review = max(
            skill.review_submissions,
            key=lambda submission: submission.submitted_at,
            default=None,
        )
        review_status = latest_review.status if latest_review is not None else None
        if (
            latest_review is not None
            and latest_review.bundle_sha256 != skill.bundle_sha256
        ):
            review_status = SkillReviewStatus.OUTDATED
        return cls(
            source="custom",
            id=skill.id,
            slug=skill.slug,
            name=skill.name,
            description=skill.description,
            category=skill.category,
            user_enabled=enabled,
            is_valid=skill.is_valid,
            enabled=enabled,
            can_toggle=can_toggle,
            author_user_id=skill.author_user_id,
            author_email=skill.author.email if skill.author is not None else None,
            owner=(
                MinimalUserSnapshot(id=skill.author.id, email=skill.author.email)
                if skill.author is not None
                else None
            ),
            ownership_vacant=skill.author_user_id is None
            or skill.author is None
            or not skill.author.is_active,
            created_at=skill.created_at,
            updated_at=skill.updated_at,
            user_shares=visible_user_shares,
            group_shares=visible_group_shares,
            public_permission=skill.public_permission,
            is_personal=skill.public_permission is None
            and not user_shares
            and not group_shares,
            user_permission=user_permission,
            review_status=review_status,
            review_submitted_at=(
                latest_review.submitted_at if latest_review is not None else None
            ),
        )


class SkillsList(BaseModel):
    builtins: list[SkillResponse]
    customs: list[SkillResponse]


class SkillPreviewResponse(BaseModel):
    source: Literal["builtin", "custom"]
    id: UUID
    name: str
    description: str
    author_email: str | None = None
    instructions_markdown: str

    @classmethod
    def from_builtin(
        cls,
        skill: Skill,
        *,
        instructions_markdown: str,
    ) -> "SkillPreviewResponse":
        return cls(
            source="builtin",
            id=skill.id,
            name=skill.name,
            description=skill.description,
            author_email=None,
            instructions_markdown=instructions_markdown,
        )

    @classmethod
    def from_custom(
        cls,
        skill: Skill,
        *,
        instructions_markdown: str,
    ) -> "SkillPreviewResponse":
        return cls(
            source="custom",
            id=skill.id,
            name=skill.name,
            description=skill.description,
            author_email=skill.author.email if skill.author is not None else None,
            instructions_markdown=instructions_markdown,
        )


class SkillEditableDetailResponse(SkillResponse):
    instructions_markdown: str
    files: list[SkillBundleFile]


class SkillBundleInspectResponse(BaseModel):
    name: str
    description: str
    instructions_markdown: str
    files: list[SkillBundleFile]


class SkillEnableRequest(BaseModel):
    enabled: bool


class SkillCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    instructions_markdown: str

    @model_validator(mode="after")
    def _strip_values(self) -> "SkillCreateRequest":
        for field in ("name", "description", "instructions_markdown"):
            stripped = getattr(self, field).strip()
            if not stripped:
                raise ValueError(f"{field} cannot be empty")
            setattr(self, field, stripped)
        return self


class SkillPackageFile(BaseModel):
    path: str
    size: int
    sha256: str
    is_text: bool
    content: str | None
    content_truncated: bool


class SkillPackageFinding(BaseModel):
    code: str
    severity: Literal["INFO", "WARNING"]
    message: str
    path: str | None


class SkillPackageResponse(BaseModel):
    status: Literal["PASS", "REVIEW"]
    files: list[SkillPackageFile]
    findings: list[SkillPackageFinding]
    total_uncompressed_bytes: int

    @classmethod
    def from_inspection(
        cls, inspection: SkillBundleInspection
    ) -> "SkillPackageResponse":
        return cls.model_validate(inspection, from_attributes=True)


class SkillPackageFileDiff(BaseModel):
    path: str
    change_type: Literal["ADDED", "MODIFIED", "DELETED"]
    diff: str | None


class SkillPackageDiffResponse(BaseModel):
    files: list[SkillPackageFileDiff]
    candidate: SkillPackageResponse

    @classmethod
    def from_diff(cls, diff: SkillBundleDiff) -> "SkillPackageDiffResponse":
        return cls(
            files=[
                SkillPackageFileDiff.model_validate(entry, from_attributes=True)
                for entry in diff.files
            ],
            candidate=SkillPackageResponse.from_inspection(diff.candidate),
        )


class SkillPackageFileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    content: str


class SubmitSkillReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submission_comment: str | None = None


class ResolveSkillReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    review_comment: str | None = None


class SkillReviewSubmissionResponse(BaseModel):
    id: UUID
    skill_id: UUID
    skill_name: str
    skill_slug: str
    submitted_by: MinimalUserSnapshot
    reviewed_by: MinimalUserSnapshot | None
    bundle_sha256: str
    current_bundle_sha256: str | None
    is_current_bundle: bool
    status: SkillReviewStatus
    submission_comment: str | None
    review_comment: str | None
    submitted_at: datetime.datetime
    reviewed_at: datetime.datetime | None

    @classmethod
    def from_model(
        cls, submission: SkillReviewSubmission
    ) -> "SkillReviewSubmissionResponse":
        return cls(
            id=submission.id,
            skill_id=submission.skill_id,
            skill_name=submission.skill.name,
            skill_slug=submission.skill.slug,
            submitted_by=MinimalUserSnapshot(
                id=submission.submitted_by.id,
                email=submission.submitted_by.email,
            ),
            reviewed_by=(
                MinimalUserSnapshot(
                    id=submission.reviewed_by.id,
                    email=submission.reviewed_by.email,
                )
                if submission.reviewed_by is not None
                else None
            ),
            bundle_sha256=submission.bundle_sha256,
            current_bundle_sha256=submission.skill.bundle_sha256,
            is_current_bundle=(
                submission.bundle_sha256 == submission.skill.bundle_sha256
            ),
            status=submission.status,
            submission_comment=submission.submission_comment,
            review_comment=submission.review_comment,
            submitted_at=submission.submitted_at,
            reviewed_at=submission.reviewed_at,
        )


class SkillPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    instructions_markdown: str | None = None
    public_permission: SkillSharePermission | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_nulls(cls, data: Any) -> Any:
        """Omitting a field = 'leave unchanged'. Null is invalid for these
        fields; null ``public_permission`` is valid and revokes org access."""
        if isinstance(data, dict):
            for field in (
                "description",
                "instructions_markdown",
            ):
                if field in data and data[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return data

    @model_validator(mode="after")
    def _strip_values(self) -> "SkillPatchRequest":
        for field in ("description", "instructions_markdown"):
            value = getattr(self, field)
            if value is None:
                continue
            stripped = value.strip()
            if not stripped:
                raise ValueError(f"{field} cannot be empty")
            setattr(self, field, stripped)
        return self

    @property
    def has_details_update(self) -> bool:
        return bool(self.model_fields_set & {"description", "instructions_markdown"})

    @property
    def has_db_field_update(self) -> bool:
        return "public_permission" in self.model_fields_set


class SkillUserSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class SkillUserShareRequest(BaseModel):
    user_id: UUID
    permission: SkillSharePermission


class SkillGroupShareRequest(BaseModel):
    group_id: int
    permission: SkillSharePermission


class SkillShareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_shares: list[SkillUserShareRequest] | None = None
    group_shares: list[SkillGroupShareRequest] | None = None
    public_permission: SkillSharePermission | None = None


class TransferSkillOwnershipRequest(BaseModel):
    new_owner_user_id: UUID
