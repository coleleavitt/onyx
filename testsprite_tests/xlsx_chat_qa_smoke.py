#!/usr/bin/env python3
"""Live regression: an attached XLSX must be readable by chat.

Reproduces the 2026-07-16 bug where an attached spreadsheet spun forever
(celery workers dead), then FAILED (workers missing S3 credentials), and chat
replied "I don't have access to a file_reader or python tool" instead of
answering from the file.

Flow: upload testsprite_tests/fixtures/foundations_2025_production.xlsx →
wait for processing to COMPLETE → ask a question whose answer is a specific
cell value → assert the live LLM answer contains it. Cleans up the chat
session and uploaded file in finally.
"""
from __future__ import annotations

import os
import time

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]
FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "foundations_2025_production.xlsx"
)
# Stewart A Willis, "Sum of Amount(Exclude Previous Yr's -ve) 2025"
EXPECTED_AMOUNT_VARIANTS = ("40,216,752.33", "40216752.33")
PROCESSING_TIMEOUT_SECONDS = 180


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 204, response.text
    return session


def wait_for_completed(session: requests.Session, user_file_id: str) -> None:
    deadline = time.monotonic() + PROCESSING_TIMEOUT_SECONDS
    status = "PROCESSING"
    while time.monotonic() < deadline:
        response = session.post(
            f"{BASE_URL}/api/user/projects/file/statuses",
            json={"file_ids": [user_file_id]},
            timeout=20,
        )
        assert response.ok, response.text
        snapshots = response.json()
        if snapshots:
            status = snapshots[0]["status"]
            if status == "COMPLETED":
                assert snapshots[0]["chunk_count"], "COMPLETED but no chunks"
                return
            assert status in ("PROCESSING", "UPLOADING"), (
                f"file processing entered terminal status {status} — "
                "check celery workers (testsprite_tests/onyx_services_doctor.sh) "
                "and S3 credentials in the worker env"
            )
        time.sleep(3)
    raise AssertionError(
        f"file stuck in {status} after {PROCESSING_TIMEOUT_SECONDS}s — celery "
        "user_file_processing worker is likely down "
        "(run testsprite_tests/onyx_services_doctor.sh heal)"
    )


def main() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)

    with open(FIXTURE, "rb") as fixture_file:
        upload_response = session.post(
            f"{BASE_URL}/api/user/projects/file/upload",
            files=[
                (
                    "files",
                    (
                        "foundations_2025_production.xlsx",
                        fixture_file,
                        "application/vnd.openxmlformats-officedocument"
                        ".spreadsheetml.sheet",
                    ),
                )
            ],
            timeout=60,
        )
    assert upload_response.ok, upload_response.text
    uploaded = upload_response.json()
    assert not uploaded["rejected_files"], uploaded["rejected_files"]
    user_file = uploaded["user_files"][0]

    chat_session_id: str | None = None
    try:
        wait_for_completed(session, user_file["id"])

        send_response = session.post(
            f"{BASE_URL}/api/chat/send-chat-message",
            json={
                "message": (
                    "How much business did Stewart Willis write in 2025? "
                    "Give the exact amount."
                ),
                "stream": False,
                "file_descriptors": [
                    {
                        "id": user_file["file_id"],
                        "type": user_file["chat_file_type"],
                        "name": user_file["name"],
                        "user_file_id": user_file["id"],
                    }
                ],
                "chat_session_info": {
                    "persona_id": 0,
                    "description": "xlsx-chat-qa-smoke",
                },
            },
            timeout=360,
        )
        assert send_response.ok, send_response.text
        payload = send_response.json()
        chat_session_id = payload["chat_session_id"]
        answer = payload["answer"]
        assert payload["error_msg"] is None, payload["error_msg"]
        assert any(v in answer for v in EXPECTED_AMOUNT_VARIANTS), (
            f"answer does not contain Stewart Willis's 2025 amount "
            f"{EXPECTED_AMOUNT_VARIANTS}: {answer[:400]}"
        )
        assert "file_reader" not in answer and "python tool" not in answer, (
            f"answer regressed to 'missing tool' apology: {answer[:400]}"
        )
    finally:
        if chat_session_id:
            session.delete(
                f"{BASE_URL}/api/chat/delete-chat-session/{chat_session_id}",
                timeout=20,
            )
        delete_response = session.delete(
            f"{BASE_URL}/api/user/projects/file/{user_file['id']}", timeout=20
        )
        assert delete_response.ok, delete_response.text

    print("xlsx chat QA smoke passed")


if __name__ == "__main__":
    main()
