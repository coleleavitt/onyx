"""Seed the real Compliance reporting line so oversight can be exercised end to end.

Mirrors the live org chart, which has three managers inside one department:

    Christopher Shin (Director of Compliance)
    |-- Jeff Dow (Compliance Manager) ---- Andy Joshu, McKenna Nigl
    `-- Kamara Gibson (Compliance Manager) - Jaime Duarte

That shape is the whole point: a department-wide group would let Dow read
Gibson's analyst. Groups are therefore built per manager (the reporting line),
each with the manager as curator, and oversight capability is granted to a
separate managers group so analysts never receive it.

Everything goes through the real HTTP API as an admin, so this doubles as an
integration exercise of registration, grouping, curator assignment and the
group permission grant.

Run (services must be up):
    python docs/testsprite/space-connected-source-governance-tests/seed-compliance-oversight.py
"""

from __future__ import annotations

import sys
from typing import Any

import requests

BASE = "http://localhost:3000"
ADMIN = ("admin_user@example.com", "TestPassword123!")
PASSWORD = "TestPassword123!"

# (email, display name, title)
SHIN = ("christopher.shin@fiwealth.com", "Christopher Shin", "Director of Compliance")
DOW = ("jeff.dow@fiwealth.com", "Jeff Dow", "Compliance Manager")
GIBSON = ("kamara.gibson@fiwealth.com", "Kamara Gibson", "Compliance Manager")
JOSHU = ("andy.joshu@fiwealth.com", "Andy Joshu", "Sr. Compliance Analyst")
NIGL = ("mckenna.nigl@fiwealth.com", "McKenna Nigl", "Compliance Analyst")
DUARTE = ("jaime.duarte@fiwealth.com", "Jaime Duarte", "Sr. Compliance Analyst")

PEOPLE = [SHIN, DOW, GIBSON, JOSHU, NIGL, DUARTE]

# group name -> (curator email, member emails). The manager is a member of the
# group they curate, matching how Onyx models curation.
REPORTING_LINES: dict[str, tuple[str, list[str]]] = {
    "Compliance — Christopher Shin": (SHIN[0], [SHIN[0], DOW[0], GIBSON[0]]),
    "Compliance — Jeff Dow": (DOW[0], [DOW[0], JOSHU[0], NIGL[0]]),
    "Compliance — Kamara Gibson": (GIBSON[0], [GIBSON[0], DUARTE[0]]),
}

# Capability lives here so analysts never hold it.
MANAGERS_GROUP = "Compliance Managers"
MANAGERS = [SHIN[0], DOW[0], GIBSON[0]]


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE}/api/auth/login",
        data={"username": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return session


def register(email: str, password: str) -> None:
    response = requests.post(
        f"{BASE}/api/auth/register",
        json={"email": email, "username": email, "password": password},
        timeout=30,
    )
    if (
        response.status_code >= 400
        and "REGISTER_USER_ALREADY_EXISTS" not in response.text
    ):
        raise RuntimeError(
            f"register {email} failed: {response.status_code} {response.text[:200]}"
        )


def all_users(admin: requests.Session) -> dict[str, str]:
    """email -> id for every accepted user.

    The endpoint pages on `page_num`; a `page` parameter is accepted and then
    ignored, which silently returns page zero forever. The page counter is
    therefore bounded by the reported total rather than trusted to advance.
    """
    page_size = 200
    found: dict[str, str] = {}
    page = 0
    while True:
        response = admin.get(
            f"{BASE}/api/manage/users/accepted",
            params={"page_num": page, "page_size": page_size},
            timeout=30,
        )
        response.raise_for_status()
        payload: Any = response.json()
        items = payload["items"]
        total = payload.get("total_items", len(items))
        for item in items:
            found[item["email"]] = item["id"]
        page += 1
        if not items or len(found) >= total or page > (total // page_size) + 2:
            break
    return found


def existing_groups(admin: requests.Session) -> dict[str, int]:
    response = admin.get(f"{BASE}/api/manage/admin/user-group", timeout=60)
    response.raise_for_status()
    return {g["name"]: g["id"] for g in response.json()}


def ensure_group(
    admin: requests.Session, name: str, user_ids: list[str], groups: dict[str, int]
) -> int:
    if name in groups:
        group_id = groups[name]
        admin.patch(
            f"{BASE}/api/manage/admin/user-group/{group_id}",
            json={"user_ids": user_ids, "cc_pair_ids": []},
            timeout=60,
        ).raise_for_status()
        return group_id
    response = admin.post(
        f"{BASE}/api/manage/admin/user-group",
        json={"name": name, "user_ids": user_ids, "cc_pair_ids": []},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["id"]


def main() -> int:
    for email, name, _title in PEOPLE:
        register(email, PASSWORD)
        print(f"user ready: {name} <{email}>")

    admin = login(*ADMIN)
    ids = all_users(admin)
    missing = [e for e, _, _ in PEOPLE if e not in ids]
    if missing:
        print(f"ERROR: users not visible to admin: {missing}")
        return 1

    groups = existing_groups(admin)

    managers_group_id = ensure_group(
        admin, MANAGERS_GROUP, [ids[e] for e in MANAGERS], groups
    )
    permission_response = admin.put(
        f"{BASE}/api/manage/admin/user-group/{managers_group_id}/permissions",
        json={"permission": "read:query_history", "enabled": True},
        timeout=30,
    )
    permission_response.raise_for_status()
    print(f"{MANAGERS_GROUP}: granted read:query_history")

    for name, (curator_email, member_emails) in REPORTING_LINES.items():
        group_id = ensure_group(admin, name, [ids[e] for e in member_emails], groups)
        curator_response = admin.post(
            f"{BASE}/api/manage/admin/user-group/{group_id}/set-curator",
            json={"user_id": ids[curator_email], "is_curator": True},
            timeout=30,
        )
        curator_response.raise_for_status()
        print(f"{name}: {len(member_emails)} members, curator {curator_email}")

    print("\nExpected oversight scope:")
    print("  Jeff Dow      -> Dow, Joshu, Nigl        (never Duarte)")
    print("  Kamara Gibson -> Gibson, Duarte          (never Joshu/Nigl)")
    print("  Christopher Shin -> Shin, Dow, Gibson    (no cascade to analysts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
