from sqlalchemy.orm import Session

from onyx.db.enums import SkillReviewStatus
from onyx.db.enums import SkillSharePermission
from onyx.db.models import UserRole
from onyx.db.skill_review import list_skill_review_submissions
from onyx.db.skill_review import resolve_skill_review_submission
from onyx.db.skill_review import submit_skill_for_review
from tests.external_dependency_unit.craft.db_helpers import make_skill
from tests.external_dependency_unit.craft.db_helpers import make_user


def test_skill_review_approval_publishes_exact_bundle(db_session: Session) -> None:
    owner = make_user(db_session, role=UserRole.BASIC)
    reviewer = make_user(db_session, role=UserRole.ADMIN)
    skill = make_skill(db_session, author_user_id=owner.id)

    submission = submit_skill_for_review(
        skill=skill,
        submitter=owner,
        submission_comment="Review the network helper.",
        db_session=db_session,
    )

    assert submission.status == SkillReviewStatus.PENDING
    assert submission in list_skill_review_submissions(
        db_session=db_session,
        status=SkillReviewStatus.PENDING,
    )

    resolved = resolve_skill_review_submission(
        submission_id=submission.id,
        reviewer=reviewer,
        approve=True,
        review_comment="Package inspected.",
        db_session=db_session,
    )

    assert resolved.status == SkillReviewStatus.APPROVED
    assert skill.public_permission == SkillSharePermission.VIEWER
    assert skill.enabled is True


def test_skill_review_cannot_publish_changed_bundle(db_session: Session) -> None:
    owner = make_user(db_session, role=UserRole.BASIC)
    reviewer = make_user(db_session, role=UserRole.ADMIN)
    skill = make_skill(db_session, author_user_id=owner.id)
    submission = submit_skill_for_review(
        skill=skill,
        submitter=owner,
        submission_comment=None,
        db_session=db_session,
    )
    skill.bundle_sha256 = "f" * 64
    db_session.flush()

    resolved = resolve_skill_review_submission(
        submission_id=submission.id,
        reviewer=reviewer,
        approve=True,
        review_comment=None,
        db_session=db_session,
    )

    assert resolved.status == SkillReviewStatus.OUTDATED
    assert skill.public_permission is None
