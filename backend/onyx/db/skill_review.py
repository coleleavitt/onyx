import datetime
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from onyx.db.enums import SkillReviewStatus
from onyx.db.enums import SkillSharePermission
from onyx.db.models import Skill
from onyx.db.models import SkillReviewSubmission
from onyx.db.models import User
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError


def _review_select() -> Select[tuple[SkillReviewSubmission]]:
    return select(SkillReviewSubmission).options(
        selectinload(SkillReviewSubmission.skill),
        selectinload(SkillReviewSubmission.submitted_by),
        selectinload(SkillReviewSubmission.reviewed_by),
    )


def submit_skill_for_review(
    *,
    skill: Skill,
    submitter: User,
    submission_comment: str | None,
    db_session: Session,
) -> SkillReviewSubmission:
    if skill.bundle_sha256 is None or submitter.id is None:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "Custom skill bundle is missing.")

    pending = list(
        db_session.scalars(
            _review_select().where(
                SkillReviewSubmission.skill_id == skill.id,
                SkillReviewSubmission.status == SkillReviewStatus.PENDING,
            )
        )
    )
    for submission in pending:
        if submission.bundle_sha256 == skill.bundle_sha256:
            return submission
        submission.status = SkillReviewStatus.OUTDATED
        submission.review_comment = "Superseded by a newer package submission."
        submission.reviewed_at = datetime.datetime.now(datetime.timezone.utc)

    submission = SkillReviewSubmission(
        skill_id=skill.id,
        submitted_by_user_id=submitter.id,
        bundle_sha256=skill.bundle_sha256,
        submission_comment=submission_comment.strip() if submission_comment else None,
    )
    db_session.add(submission)
    db_session.flush()
    return submission


def list_skill_review_submissions(
    *,
    db_session: Session,
    status: SkillReviewStatus | None = None,
) -> list[SkillReviewSubmission]:
    stmt = _review_select().order_by(SkillReviewSubmission.submitted_at.desc())
    if status is not None:
        stmt = stmt.where(SkillReviewSubmission.status == status)
    return list(db_session.scalars(stmt))


def resolve_skill_review_submission(
    *,
    submission_id: UUID,
    reviewer: User,
    approve: bool,
    review_comment: str | None,
    db_session: Session,
) -> SkillReviewSubmission:
    submission = db_session.scalar(
        _review_select().where(SkillReviewSubmission.id == submission_id)
    )
    if submission is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Skill review submission not found.")
    if submission.status != SkillReviewStatus.PENDING:
        raise OnyxError(OnyxErrorCode.CONFLICT, "Skill review is already resolved.")
    if reviewer.id is None:
        raise OnyxError(OnyxErrorCode.UNAUTHENTICATED)

    now = datetime.datetime.now(datetime.timezone.utc)
    submission.reviewed_by_user_id = reviewer.id
    submission.reviewed_at = now
    submission.review_comment = review_comment.strip() if review_comment else None

    if submission.bundle_sha256 != submission.skill.bundle_sha256:
        submission.status = SkillReviewStatus.OUTDATED
        submission.review_comment = (
            submission.review_comment or "The skill package changed after submission."
        )
        db_session.flush()
        return submission

    submission.status = (
        SkillReviewStatus.APPROVED if approve else SkillReviewStatus.REJECTED
    )
    if approve:
        submission.skill.public_permission = SkillSharePermission.VIEWER
        submission.skill.enabled = True
    db_session.flush()
    return submission
