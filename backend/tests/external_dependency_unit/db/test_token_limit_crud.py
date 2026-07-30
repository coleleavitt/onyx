"""Focused CRUD coverage for token rate limit DB helpers."""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from onyx.configs.constants import TokenRateLimitScope
from onyx.db.models import TokenRateLimit
from onyx.db.models import TokenRateLimit__UserGroup
from onyx.db.models import UserGroup
from onyx.db.token_limit import delete_token_rate_limit
from onyx.db.token_limit import fetch_all_global_token_rate_limits
from onyx.db.token_limit import fetch_all_user_token_rate_limits
from onyx.db.token_limit import insert_global_token_rate_limit
from onyx.db.token_limit import insert_user_token_rate_limit
from onyx.db.token_limit import update_token_rate_limit
from onyx.server.token_rate_limits.models import TokenRateLimitArgs


@pytest.fixture()
def rate_limit_ids() -> Iterator[list[int]]:
    ids: list[int] = []
    yield ids


@pytest.fixture()
def group_names() -> Iterator[list[str]]:
    names: list[str] = []
    yield names


@pytest.fixture(autouse=True)
def cleanup_rate_limits(
    db_session: Session, rate_limit_ids: list[int], group_names: list[str]
) -> Iterator[None]:
    yield
    if rate_limit_ids:
        db_session.execute(
            delete(TokenRateLimit__UserGroup).where(
                TokenRateLimit__UserGroup.rate_limit_id.in_(rate_limit_ids)
            )
        )
        db_session.execute(
            delete(TokenRateLimit).where(TokenRateLimit.id.in_(rate_limit_ids))
        )
    if group_names:
        db_session.execute(delete(UserGroup).where(UserGroup.name.in_(group_names)))
    db_session.commit()


def _args(
    *,
    enabled: bool = True,
    token_budget: int | None = 100,
    cost_budget_cents: float | None = None,
    period_hours: int = 24,
) -> TokenRateLimitArgs:
    return TokenRateLimitArgs(
        enabled=enabled,
        token_budget=token_budget,
        cost_budget_cents=cost_budget_cents,
        period_hours=period_hours,
    )


def test_token_rate_limit_crud_and_filters(
    db_session: Session, rate_limit_ids: list[int]
) -> None:
    user_limit = insert_user_token_rate_limit(db_session, _args(token_budget=100))
    disabled_user_limit = insert_user_token_rate_limit(
        db_session, _args(enabled=False, token_budget=None, cost_budget_cents=12.5)
    )
    global_limit = insert_global_token_rate_limit(
        db_session, _args(token_budget=500, period_hours=1)
    )
    rate_limit_ids.extend([user_limit.id, disabled_user_limit.id, global_limit.id])

    assert user_limit.scope == TokenRateLimitScope.USER
    assert global_limit.scope == TokenRateLimitScope.GLOBAL

    ordered_user_ids = [
        rate_limit.id
        for rate_limit in fetch_all_user_token_rate_limits(db_session)
        if rate_limit.id in rate_limit_ids
    ]
    assert set(ordered_user_ids) == {user_limit.id, disabled_user_limit.id}

    user_ids = [
        rate_limit.id
        for rate_limit in fetch_all_user_token_rate_limits(db_session, ordered=False)
        if rate_limit.id in rate_limit_ids
    ]
    assert set(user_ids) == {user_limit.id, disabled_user_limit.id}

    enabled_user_ids = [
        rate_limit.id
        for rate_limit in fetch_all_user_token_rate_limits(
            db_session, enabled_only=True, ordered=False
        )
        if rate_limit.id in rate_limit_ids
    ]
    assert enabled_user_ids == [user_limit.id]

    ordered_global_ids = [
        rate_limit.id
        for rate_limit in fetch_all_global_token_rate_limits(db_session)
        if rate_limit.id in rate_limit_ids
    ]
    assert ordered_global_ids == [global_limit.id]

    global_ids = [
        rate_limit.id
        for rate_limit in fetch_all_global_token_rate_limits(
            db_session, enabled_only=True, ordered=False
        )
        if rate_limit.id in rate_limit_ids
    ]
    assert global_ids == [global_limit.id]

    updated = update_token_rate_limit(
        db_session,
        user_limit.id,
        _args(enabled=False, token_budget=250, cost_budget_cents=5.5, period_hours=2),
    )
    assert not updated.enabled
    assert updated.token_budget == 250
    assert updated.cost_budget_cents == 5.5
    assert updated.period_hours == 2

    delete_token_rate_limit(db_session, disabled_user_limit.id)
    rate_limit_ids.remove(disabled_user_limit.id)
    assert db_session.get(TokenRateLimit, disabled_user_limit.id) is None


def test_delete_token_rate_limit_removes_group_links(
    db_session: Session, rate_limit_ids: list[int], group_names: list[str]
) -> None:
    limit = insert_user_token_rate_limit(db_session, _args(token_budget=10))
    rate_limit_ids.append(limit.id)
    group_name = f"token-limit-group-{uuid4().hex[:8]}"
    group_names.append(group_name)
    group = UserGroup(name=group_name)
    db_session.add(group)
    db_session.flush()
    db_session.add(
        TokenRateLimit__UserGroup(rate_limit_id=limit.id, user_group_id=group.id)
    )
    db_session.commit()

    delete_token_rate_limit(db_session, limit.id)
    rate_limit_ids.remove(limit.id)

    assert db_session.get(TokenRateLimit, limit.id) is None
    assert (
        db_session.query(TokenRateLimit__UserGroup)
        .filter(TokenRateLimit__UserGroup.rate_limit_id == limit.id)
        .count()
        == 0
    )


def test_token_rate_limit_missing_rows_raise(db_session: Session) -> None:
    missing_id = -1

    with pytest.raises(ValueError, match="TokenRateLimit with id '-1' not found"):
        update_token_rate_limit(db_session, missing_id, _args(token_budget=1))

    with pytest.raises(ValueError, match="TokenRateLimit with id '-1' not found"):
        delete_token_rate_limit(db_session, missing_id)
