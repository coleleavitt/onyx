#!/usr/bin/env python3
"""Uploaded files of common formats must finish processing.

Guard for the 2026-07-16 outage class where user-file uploads spun forever
(celery workers dead) or FAILED (workers lacked S3 credentials) for EVERY
format. Uploads a small csv, txt, md, and json file, waits for each to reach
COMPLETED with chunks, then deletes them. No LLM calls.
"""
from __future__ import annotations

import os
import time

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]
PROCESSING_TIMEOUT_SECONDS = 180

FILES = [
    (
        "format-smoke.csv",
        "text/csv",
        b"advisor,amount_2025\nStewart A Willis,40216752.33\nErick A Jimenez,61017779.03\n",
    ),
    (
        "format-smoke.txt",
        "text/plain",
        b"Format smoke plain text file. The magic token is ZEBRA-7741.\n",
    ),
    (
        "format-smoke.md",
        "text/markdown",
        b"# Format smoke\n\nMarkdown upload processing check. Token: ZEBRA-7741.\n",
    ),
    (
        "format-smoke.json",
        "application/json",
        b'{"purpose": "format smoke", "token": "ZEBRA-7741"}\n',
    ),
]


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 204, response.text
    return session


def main() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)

    upload_response = session.post(
        f"{BASE_URL}/api/user/projects/file/upload",
        files=[("files", (name, content, mime)) for name, mime, content in FILES],
        timeout=60,
    )
    assert upload_response.ok, upload_response.text
    uploaded = upload_response.json()
    assert not uploaded["rejected_files"], uploaded["rejected_files"]
    user_files = uploaded["user_files"]
    assert len(user_files) == len(FILES), (
        f"expected {len(FILES)} accepted files, got {len(user_files)}"
    )
    ids = [user_file["id"] for user_file in user_files]

    try:
        pending = set(ids)
        deadline = time.monotonic() + PROCESSING_TIMEOUT_SECONDS
        statuses: dict[str, str] = {}
        while pending and time.monotonic() < deadline:
            response = session.post(
                f"{BASE_URL}/api/user/projects/file/statuses",
                json={"file_ids": ids},
                timeout=20,
            )
            assert response.ok, response.text
            for snapshot in response.json():
                statuses[snapshot["id"]] = snapshot["status"]
                if snapshot["status"] == "COMPLETED":
                    pending.discard(snapshot["id"])
                else:
                    assert snapshot["status"] in ("PROCESSING", "UPLOADING"), (
                        f"{snapshot['name']} hit terminal status "
                        f"{snapshot['status']} — check celery workers and the "
                        "S3 env (testsprite_tests/onyx_services_doctor.sh)"
                    )
            if pending:
                time.sleep(3)
        assert not pending, (
            f"files never finished processing: "
            f"{ {i: statuses.get(i) for i in pending} } — celery "
            "user_file_processing worker likely down "
            "(run testsprite_tests/onyx_services_doctor.sh heal)"
        )
    finally:
        for user_file_id in ids:
            session.delete(
                f"{BASE_URL}/api/user/projects/file/{user_file_id}", timeout=20
            )

    print("file formats processing smoke passed")


if __name__ == "__main__":
    main()
