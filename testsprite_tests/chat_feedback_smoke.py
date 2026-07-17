#!/usr/bin/env python3
"""Live chat feedback lifecycle through the frontend proxy.

Covers the previously untested chat streaming-adjacent behaviors:
- POST /api/chat/send-chat-message (stream=false, live LLM, tools disabled)
- POST /api/chat/create-chat-message-feedback
- DELETE /api/chat/remove-chat-message-feedback
with chat-session cleanup.
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


def main() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)

    send_response = session.post(
        f"{BASE_URL}/api/chat/send-chat-message",
        json={
            "message": "Reply with exactly: OK",
            "stream": False,
            "allowed_tool_ids": [],
            "chat_session_info": {
                "persona_id": 0,
                "description": "chat-feedback-smoke",
            },
        },
        timeout=120,
    )
    assert send_response.ok, send_response.text
    payload = send_response.json()
    message_id = payload["message_id"]
    chat_session_id = payload["chat_session_id"]
    assert payload["answer"], "Expected a non-empty live LLM answer"
    assert payload["error_msg"] is None, payload["error_msg"]

    try:
        feedback_response = session.post(
            f"{BASE_URL}/api/chat/create-chat-message-feedback",
            json={
                "chat_message_id": message_id,
                "is_positive": True,
                "feedback_text": "api smoke feedback",
            },
            timeout=20,
        )
        assert feedback_response.ok, feedback_response.text

        remove_response = session.delete(
            f"{BASE_URL}/api/chat/remove-chat-message-feedback",
            params={"chat_message_id": message_id},
            timeout=20,
        )
        assert remove_response.ok, remove_response.text
    finally:
        delete_response = session.delete(
            f"{BASE_URL}/api/chat/delete-chat-session/{chat_session_id}",
            timeout=20,
        )
        assert delete_response.ok, delete_response.text

    print("chat feedback smoke passed")


if __name__ == "__main__":
    main()
