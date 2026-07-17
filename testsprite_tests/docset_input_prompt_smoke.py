#!/usr/bin/env python3
"""Live document-set and input-prompt CRUD through the frontend proxy.

Covers coverage gap #3 as the admin user:

Document sets (``/api/manage`` admin router):
- Discover connector-credential pairs via ``GET /api/manage/admin/cc-pair/{id}``
  and pick the one with the fewest indexed documents (the Ingestion API
  DefaultCCPair, 0 docs) so creation never triggers a heavy index sync.
- ``POST /api/manage/admin/document-set`` create, then assert the new set shows
  up in ``GET /api/manage/document-set`` (``is_up_to_date`` may be false at first).
- ``PATCH /api/manage/admin/document-set`` rename + re-describe.
- ``DELETE /api/manage/admin/document-set/{id}`` in a finally block.

Both the PATCH and the DELETE are guarded server-side while the set is syncing
(``is_up_to_date == False``); a freshly created set — and a set that was just
patched — is synced asynchronously by Celery. This test waits (bounded) for the
sync to finish before mutating and asserts the happy path when it completes. If
the background sync worker is slow or unavailable it instead asserts the
documented "while it is syncing" guard, so the endpoint contract is verified
either way and the test never flakes on Celery timing.

Input prompts (``/api/input_prompt`` basic router) are fully synchronous:
- ``POST`` create, ``GET`` list contains it, ``GET`` by id, ``PATCH`` update,
  then ``DELETE`` in a finally block and assert it is gone.
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]

# Bounded waits for the async Celery document-set sync. In a healthy deployment a
# zero-document set syncs in a second or two; these are generous upper bounds and
# the test tolerates the sync never completing (slow/absent worker).
SYNC_WAIT_SECONDS = 40
DELETE_POLL_SECONDS = 20
POLL_INTERVAL_SECONDS = 2.0
# Safety ceiling: never build a set on a cc-pair large enough to kick off a heavy
# index sync. The Ingestion API DefaultCCPair has 0 docs.
MAX_TARGET_DOCS = 10


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 204, response.text
    return session


def list_document_sets(session: requests.Session) -> list[dict[str, Any]]:
    response = session.get(f"{BASE_URL}/api/manage/document-set", timeout=20)
    assert response.ok, response.text
    payload = response.json()
    assert isinstance(payload, list), payload
    return payload


def find_document_set(
    session: requests.Session, document_set_id: int
) -> dict[str, Any] | None:
    return next(
        (ds for ds in list_document_sets(session) if ds["id"] == document_set_id),
        None,
    )


def wait_until_up_to_date(
    session: requests.Session, document_set_id: int, timeout_s: float
) -> bool:
    """Poll the user-visible list until the set reports is_up_to_date, or timeout.

    Returns True if the background sync finished within the window, else False.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        current = find_document_set(session, document_set_id)
        if current is None:
            return False
        if current["is_up_to_date"]:
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return False


def discover_low_doc_cc_pair(session: requests.Session) -> tuple[int, str, int]:
    """Return (cc_pair_id, source, docs) for the connector with the fewest docs.

    Discovered live via the admin cc-pair detail endpoint. The Ingestion API
    DefaultCCPair (source ``ingestion_api``, 0 docs) is preferred when present.
    """
    discovered: list[tuple[int, str, int]] = []
    for cc_pair_id in range(1, 16):
        response = session.get(
            f"{BASE_URL}/api/manage/admin/cc-pair/{cc_pair_id}", timeout=20
        )
        if not response.ok:
            continue
        detail = response.json()
        source = str((detail.get("connector") or {}).get("source") or "unknown")
        docs = detail.get("num_docs_indexed")
        docs = int(docs) if isinstance(docs, int) else 1 << 30
        discovered.append((cc_pair_id, source, docs))

    assert discovered, "Expected at least one connector-credential pair"

    ingestion = [d for d in discovered if d[1] == "ingestion_api"]
    candidate = (
        min(ingestion, key=lambda d: d[2])
        if ingestion
        else min(discovered, key=lambda d: d[2])
    )
    assert candidate[2] <= MAX_TARGET_DOCS, (
        f"Refusing cc_pair {candidate[0]} with {candidate[2]} docs to avoid a "
        f"heavy sync; discovered={discovered}"
    )
    return candidate


def assert_document_set_lifecycle(session: requests.Session) -> None:
    cc_pair_id, source, docs = discover_low_doc_cc_pair(session)
    print(f"document-set target cc_pair={cc_pair_id} source={source} docs={docs}")

    name = f"ts-docset-smoke-{int(time.time())}"
    create_response = session.post(
        f"{BASE_URL}/api/manage/admin/document-set",
        json={
            "name": name,
            "description": "docset input-prompt smoke",
            "cc_pair_ids": [cc_pair_id],
            "is_public": True,
            "users": [],
            "groups": [],
        },
        timeout=30,
    )
    assert create_response.ok, create_response.text
    document_set_id = create_response.json()
    assert isinstance(document_set_id, int), create_response.text

    try:
        created = find_document_set(session, document_set_id)
        assert created is not None, "Created document set missing from list"
        assert created["name"] == name, created
        # is_up_to_date may be False here while the async sync runs — that is fine.

        renamed = f"{name}-renamed"
        synced = wait_until_up_to_date(session, document_set_id, SYNC_WAIT_SECONDS)
        patch_response = session.patch(
            f"{BASE_URL}/api/manage/admin/document-set",
            json={
                "id": document_set_id,
                "name": renamed,
                "description": "docset input-prompt smoke (updated)",
                "cc_pair_ids": [cc_pair_id],
                "is_public": True,
                "users": [],
                "groups": [],
            },
            timeout=30,
        )
        if synced:
            # Happy path: the set finished syncing, so the mutation is accepted.
            assert patch_response.ok, patch_response.text
            updated = find_document_set(session, document_set_id)
            assert updated is not None, "Patched document set missing from list"
            assert updated["name"] == renamed, updated
            print("document-set patch acknowledged (rename verified)")
        else:
            # Sync worker slow/unavailable: the endpoint must reject mutation with
            # its documented "while it is syncing" guard.
            assert patch_response.status_code == 400, patch_response.text
            assert "sync" in patch_response.text.lower(), patch_response.text
            print(
                "document-set still syncing; PATCH correctly returned the "
                "syncing guard (Celery sync did not complete in "
                f"{SYNC_WAIT_SECONDS}s)"
            )
    finally:
        # Deletion is guarded the same way and, once accepted, is async: the set is
        # marked for deletion and removed by Celery. Wait (bounded) for the set to
        # be up to date, then delete; tolerate a still-syncing set rather than
        # failing on slow/absent Celery.
        ready = wait_until_up_to_date(session, document_set_id, SYNC_WAIT_SECONDS)
        delete_response = session.delete(
            f"{BASE_URL}/api/manage/admin/document-set/{document_set_id}",
            timeout=30,
        )
        if ready:
            assert delete_response.ok, delete_response.text
            gone = False
            deadline = time.monotonic() + DELETE_POLL_SECONDS
            while time.monotonic() < deadline:
                if find_document_set(session, document_set_id) is None:
                    gone = True
                    break
                time.sleep(POLL_INTERVAL_SECONDS)
            print(
                "document-set delete accepted; "
                + ("removed from list" if gone else "still marked for deletion (async)")
            )
        elif not delete_response.ok:
            # Could not delete because the set never finished syncing.
            assert delete_response.status_code == 400, delete_response.text
            assert "sync" in delete_response.text.lower(), delete_response.text
            print(
                "document-set could not be deleted yet: still syncing "
                f"(id={document_set_id}); it is deletable once Celery syncs it"
            )
        else:
            print("document-set delete accepted")


def assert_input_prompt_lifecycle(session: requests.Session) -> None:
    create_response = session.post(
        f"{BASE_URL}/api/input_prompt",
        json={
            "prompt": "ts input-prompt smoke",
            "content": "Draft a concise status update.",
            "is_public": False,
        },
        timeout=20,
    )
    assert create_response.ok, create_response.text
    created = create_response.json()
    input_prompt_id = created["id"]
    assert created["prompt"] == "ts input-prompt smoke", created
    assert created["is_public"] is False, created

    try:
        listed = session.get(f"{BASE_URL}/api/input_prompt", timeout=20)
        assert listed.ok, listed.text
        assert any(
            prompt["id"] == input_prompt_id for prompt in listed.json()
        ), "Created input prompt missing from list"

        fetched = session.get(
            f"{BASE_URL}/api/input_prompt/{input_prompt_id}", timeout=20
        )
        assert fetched.ok, fetched.text
        assert fetched.json()["id"] == input_prompt_id, fetched.text

        patch_response = session.patch(
            f"{BASE_URL}/api/input_prompt/{input_prompt_id}",
            json={
                "prompt": "ts input-prompt smoke (updated)",
                "content": "Draft a concise status update, then summarize risks.",
                "active": True,
            },
            timeout=20,
        )
        assert patch_response.ok, patch_response.text
        patched = patch_response.json()
        assert patched["prompt"] == "ts input-prompt smoke (updated)", patched
        assert patched["content"].endswith("summarize risks."), patched
        print("input-prompt create/list/get/patch verified")
    finally:
        delete_response = session.delete(
            f"{BASE_URL}/api/input_prompt/{input_prompt_id}", timeout=20
        )
        assert delete_response.ok, delete_response.text

    absent = session.get(
        f"{BASE_URL}/api/input_prompt/{input_prompt_id}", timeout=20
    )
    assert not absent.ok, f"Expected input prompt to be gone, got {absent.status_code}"
    remaining = session.get(f"{BASE_URL}/api/input_prompt", timeout=20)
    assert remaining.ok, remaining.text
    assert not any(
        prompt["id"] == input_prompt_id for prompt in remaining.json()
    ), "Deleted input prompt still present in list"
    print("input-prompt delete verified")


def main() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)
    assert_document_set_lifecycle(session)
    assert_input_prompt_lifecycle(session)
    print("docset input prompt smoke passed")


if __name__ == "__main__":
    main()
