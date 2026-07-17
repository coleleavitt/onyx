#!/usr/bin/env python3
"""Admin user-management and own-preference endpoints stay healthy.

Read-only where other users are concerned (never mutates another user's role
or preferences); the only writes are round-trips on the calling admin's own
account, restored in finally.
"""
from __future__ import annotations

import os

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 204, response.text
    return session


def get_json(session: requests.Session, path: str) -> object:
    response = session.get(f"{BASE_URL}{path}", timeout=30)
    assert response.ok, f"GET {path} -> {response.status_code}: {response.text[:300]}"
    return response.json()


def main() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)

    # Admin user listing surfaces (paginated; filter by email to find admin)
    accepted = get_json(
        session, "/api/manage/users/accepted?q=admin_user@example.com"
    )
    assert isinstance(accepted, dict) and accepted["items"], accepted
    emails = {user["email"] for user in accepted["items"]}
    assert "admin_user@example.com" in emails, sorted(emails)[:10]
    assert all(user["role"] for user in accepted["items"])

    counts = get_json(session, "/api/manage/users/counts")
    assert isinstance(counts, dict)

    users_page = get_json(session, "/api/manage/users")
    assert isinstance(users_page, (dict, list))

    # Own-permission surface
    permissions = get_json(session, "/api/me/permissions")
    assert isinstance(permissions, list) and permissions
    assert all(isinstance(permission, str) for permission in permissions)

    # Pinned-assistants round-trip on the calling account, restored after
    me = get_json(session, "/api/me")
    original_pinned = (me.get("preferences") or {}).get("pinned_assistants") or []

    changed = session.patch(
        f"{BASE_URL}/api/user/pinned-assistants",
        json={"ordered_assistant_ids": [0]},
        timeout=20,
    )
    assert changed.ok, changed.text
    try:
        refreshed = get_json(session, "/api/me")
        assert (refreshed.get("preferences") or {}).get("pinned_assistants") == [0]
    finally:
        restore = session.patch(
            f"{BASE_URL}/api/user/pinned-assistants",
            json={"ordered_assistant_ids": original_pinned},
            timeout=20,
        )
        assert restore.ok, restore.text

    # Default-model preference: same-value write proves the endpoint works
    # with zero state risk
    current_default = (me.get("preferences") or {}).get("default_model")
    same_value = session.patch(
        f"{BASE_URL}/api/user/default-model",
        json={"default_model": current_default},
        timeout=20,
    )
    assert same_value.ok, same_value.text

    print("user management smoke passed")


if __name__ == "__main__":
    main()
