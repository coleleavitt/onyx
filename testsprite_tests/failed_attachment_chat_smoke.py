#!/usr/bin/env python3
"""An unreadable attachment must be surfaced to the user, not silently ignored.

Regression for the 2026-07-16 bug: a chat referencing an attachment that never
finished processing gave the LLM zero signal, so it flailed through internal
search and apologized about missing file_reader/python tools. The fix
(_build_unreadable_attachment_context in process_message.py) injects
LLM-facing context naming any attachment whose status is not COMPLETED.

Corrupt files are rejected at upload time (rejected_files), so a FAILED row
cannot be minted through the API. Instead this exercises the same code path
via the PROCESSING state: upload the large xlsx fixture (~12s to process) and
ask about it immediately — the injected note must make the model say the file
is still being processed rather than guess or apologize about tools. The
truly-FAILED variant was verified live 2026-07-16 against a real FAILED row
(answer named the file and asked for re-upload).
"""
from __future__ import annotations

import os

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]
FIXTURE = os.path.join(
    os.path.dirname(__file__), "fixtures", "foundations_2025_production.xlsx"
)
FILE_NAME = "processing-race-fixture.xlsx"
# The specific value the model could only know by reading the file — it must
# NOT appear while the file is unreadable.
FORBIDDEN_ANSWER_FRAGMENTS = ("40,216,752", "40216752")


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

    with open(FIXTURE, "rb") as fixture_file:
        upload_response = session.post(
            f"{BASE_URL}/api/user/projects/file/upload",
            files=[
                (
                    "files",
                    (
                        FILE_NAME,
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
    assert uploaded["user_files"], uploaded
    user_file = uploaded["user_files"][0]
    assert user_file["status"] in ("PROCESSING", "UPLOADING"), (
        f"expected freshly uploaded file to be PROCESSING, got "
        f"{user_file['status']} — cannot exercise the unreadable-attachment path"
    )

    chat_session_id: str | None = None
    try:
        # Ask immediately, while the worker is still chunking the file.
        send_response = session.post(
            f"{BASE_URL}/api/chat/send-chat-message",
            json={
                "message": (
                    "How much business did Stewart Willis write in 2025 "
                    "according to the attached spreadsheet?"
                ),
                "stream": False,
                "file_descriptors": [
                    {
                        "id": user_file["file_id"],
                        "type": user_file["chat_file_type"],
                        "name": FILE_NAME,
                        "user_file_id": user_file["id"],
                    }
                ],
                "chat_session_info": {
                    "persona_id": 0,
                    "description": "unreadable-attachment-smoke",
                },
            },
            timeout=280,
        )
        assert send_response.ok, send_response.text
        payload = send_response.json()
        chat_session_id = payload["chat_session_id"]
        answer = payload["answer"]
        answer_lower = answer.lower()

        assert any(
            phrase in answer_lower
            for phrase in ("still being processed", "processing", "not available")
        ), f"answer does not surface the processing state: {answer[:400]}"
        assert not any(f in answer for f in FORBIDDEN_ANSWER_FRAGMENTS), (
            f"answer contains file data it could not have read: {answer[:400]}"
        )
        assert "file_reader" not in answer_lower, (
            f"answer regressed to the missing-tool apology: {answer[:400]}"
        )
    finally:
        if chat_session_id:
            session.delete(
                f"{BASE_URL}/api/chat/delete-chat-session/{chat_session_id}",
                timeout=20,
            )
        session.delete(
            f"{BASE_URL}/api/user/projects/file/{user_file['id']}", timeout=20
        )

    print("unreadable attachment chat smoke passed")


if __name__ == "__main__":
    main()
