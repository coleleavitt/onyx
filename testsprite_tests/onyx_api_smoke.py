#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Any

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", USER_EMAIL)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", USER_PASSWORD)
BROKEN_MODEL_NAMES = {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"}
WORKING_DEFAULT_MODEL = "gpt-5.5"


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 204, response.text
    return session


def get_json(session: requests.Session, path: str) -> Any:
    response = session.get(f"{BASE_URL}{path}", timeout=20)
    assert response.ok, f"GET {path} -> {response.status_code}: {response.text[:500]}"
    return response.json()


def assert_chat_session_lifecycle(session: requests.Session) -> None:
    name = "api-smoke-chat-session"
    create_response = session.post(
        f"{BASE_URL}/api/chat/create-chat-session",
        json={"persona_id": 0, "description": name},
        timeout=20,
    )
    assert create_response.ok, create_response.text
    chat_session_id = create_response.json()["chat_session_id"]

    try:
        patch_response = session.patch(
            f"{BASE_URL}/api/chat/chat-session/{chat_session_id}",
            json={"sharing_status": "public"},
            timeout=20,
        )
        assert patch_response.ok, patch_response.text

        sessions = get_json(session, "/api/chat/get-user-chat-sessions")["sessions"]
        created_session = next(
            (session for session in sessions if session["id"] == chat_session_id),
            None,
        )
        assert created_session is not None
        assert created_session["name"] == name
        assert created_session["shared_status"] == "public"
    finally:
        delete_response = session.delete(
            f"{BASE_URL}/api/chat/delete-chat-session/{chat_session_id}",
            timeout=20,
        )
        assert delete_response.ok, delete_response.text


def assert_project_lifecycle(session: requests.Session) -> None:
    name = "api-smoke-space"
    create_response = session.post(
        f"{BASE_URL}/api/user/projects/create",
        params={
            "name": name,
            "description": "api smoke description",
            "instructions": "api smoke instructions",
            "emoji": "🧪",
        },
        timeout=20,
    )
    assert create_response.ok, create_response.text
    project = create_response.json()
    project_id = project["id"]
    assert project["name"] == name
    assert project["user_permission"] == "OWNER"

    try:
        projects = get_json(session, "/api/user/projects")
        assert any(project["id"] == project_id for project in projects)

        fetched = get_json(session, f"/api/user/projects/{project_id}")
        assert fetched["name"] == name

        details = get_json(session, f"/api/user/projects/{project_id}/details")
        assert details["project"]["id"] == project_id
        assert isinstance(details["files"], list)

        instructions = get_json(session, f"/api/user/projects/{project_id}/instructions")
        assert instructions["instructions"] == "api smoke instructions"

        updated_instructions = session.post(
            f"{BASE_URL}/api/user/projects/{project_id}/instructions",
            json={"instructions": "updated api smoke instructions"},
            timeout=20,
        )
        assert updated_instructions.ok, updated_instructions.text
        assert updated_instructions.json()["instructions"] == (
            "updated api smoke instructions"
        )

        pinned = session.patch(
            f"{BASE_URL}/api/user/projects/{project_id}/pin",
            json={"pinned": True},
            timeout=20,
        )
        assert pinned.ok, pinned.text
        assert pinned.json()["is_pinned"] is True

        renamed = session.patch(
            f"{BASE_URL}/api/user/projects/{project_id}",
            json={
                "name": f"{name} renamed",
                "description": "updated api smoke description",
                "emoji": "🚀",
            },
            timeout=20,
        )
        assert renamed.ok, renamed.text
        renamed_json = renamed.json()
        assert renamed_json["name"] == f"{name} renamed"
        assert renamed_json["description"] == "updated api smoke description"
        assert renamed_json["emoji"] == "🚀"
    finally:
        delete_response = session.delete(
            f"{BASE_URL}/api/user/projects/{project_id}",
            timeout=20,
        )
        assert delete_response.status_code == 204, delete_response.text


def _agent_payload(name: str, description: str, is_public: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "system_prompt": "You are an API smoke test agent.",
        "task_prompt": "",
        "datetime_aware": True,
        "document_set_ids": [],
        "is_public": is_public,
        "default_model_configuration_id": None,
        "starter_messages": None,
        "users": [],
        "groups": [],
        "tool_ids": [],
        "remove_image": False,
        "uploaded_image_id": None,
        "icon_name": None,
        "search_start_date": None,
        "is_featured": False,
        "display_priority": None,
        "label_ids": None,
        "user_file_ids": None,
        "replace_base_system_prompt": False,
        "hierarchy_node_ids": [],
        "document_ids": [],
    }


def assert_persona_lifecycle(session: requests.Session) -> None:
    name = "api-smoke-agent"
    create_response = session.post(
        f"{BASE_URL}/api/persona",
        json=_agent_payload(name, "API smoke agent"),
        timeout=20,
    )
    assert create_response.ok, create_response.text
    created = create_response.json()
    agent_id = created["id"]
    assert created["name"] == name
    assert created["description"] == "API smoke agent"
    assert created["is_public"] is False

    try:
        fetched = get_json(session, f"/api/persona/{agent_id}")
        assert fetched["id"] == agent_id
        assert fetched["user_permission"] == "OWNER"

        share_response = session.patch(
            f"{BASE_URL}/api/persona/{agent_id}/share",
            json={"is_public": True},
            timeout=20,
        )
        assert share_response.ok, share_response.text

        update_response = session.patch(
            f"{BASE_URL}/api/persona/{agent_id}",
            json=_agent_payload(f"{name} updated", "Updated API smoke agent", True),
            timeout=20,
        )
        assert update_response.ok, update_response.text
        updated = update_response.json()
        assert updated["id"] == agent_id
        assert updated["name"] == f"{name} updated"
        assert updated["description"] == "Updated API smoke agent"
        assert updated["is_public"] is True

        agents = get_json(session, "/api/persona")
        assert any(agent["id"] == agent_id for agent in agents)
    finally:
        delete_response = session.delete(
            f"{BASE_URL}/api/persona/{agent_id}",
            timeout=20,
        )
        assert delete_response.ok, delete_response.text


def assert_memory_lifecycle(session: requests.Session) -> None:
    create_response = session.post(
        f"{BASE_URL}/api/memory",
        json={"title": "api-smoke-memory", "content": "original memory content"},
        timeout=20,
    )
    assert create_response.ok, create_response.text
    memory_id = create_response.json()["id"]

    try:
        memories = get_json(session, "/api/memory")
        assert any(memory["id"] == memory_id for memory in memories["items"])

        update_response = session.patch(
            f"{BASE_URL}/api/memory/{memory_id}",
            json={"content": "updated memory content"},
            timeout=20,
        )
        assert update_response.ok, update_response.text

        history = get_json(session, f"/api/memory/{memory_id}/history")
        assert history, "Expected at least one revision after an update"
        revision_id = history[0]["id"]

        restore_response = session.post(
            f"{BASE_URL}/api/memory/{memory_id}/history/{revision_id}/restore",
            timeout=20,
        )
        assert restore_response.ok, restore_response.text
    finally:
        delete_response = session.delete(
            f"{BASE_URL}/api/memory/{memory_id}", timeout=20
        )
        assert delete_response.ok, delete_response.text


def assert_notifications_endpoints(session: requests.Session) -> None:
    notifications = get_json(session, "/api/notifications")
    assert isinstance(notifications["notifications"], list)

    summary = get_json(session, "/api/notifications/summary")
    assert isinstance(summary, dict)

    dismiss_all = session.post(f"{BASE_URL}/api/notifications/dismiss-all", timeout=20)
    assert dismiss_all.ok, dismiss_all.text


def assert_chat_search_endpoint(session: requests.Session) -> None:
    response = session.get(
        f"{BASE_URL}/api/chat/search", params={"query": "holiday"}, timeout=30
    )
    assert response.ok, response.text
    assert isinstance(response.json(), (dict, list))


def assert_artifact_library_list(session: requests.Session) -> None:
    response = session.get(f"{BASE_URL}/api/build/artifact-library", timeout=20)
    assert response.ok, response.text
    assert isinstance(response.json(), list)


def assert_theme_preference_roundtrip(session: requests.Session) -> None:
    me = get_json(session, "/api/me")
    original = (me.get("preferences") or {}).get("theme_preference") or me.get(
        "theme_preference"
    )

    changed = session.patch(
        f"{BASE_URL}/api/user/theme-preference",
        json={"theme_preference": "light"},
        timeout=20,
    )
    assert changed.ok, changed.text
    try:
        refreshed = get_json(session, "/api/me")
        refreshed_theme = (refreshed.get("preferences") or {}).get(
            "theme_preference"
        ) or refreshed.get("theme_preference")
        assert refreshed_theme == "light", refreshed_theme
    finally:
        if original and original != "light":
            restore = session.patch(
                f"{BASE_URL}/api/user/theme-preference",
                json={"theme_preference": original},
                timeout=20,
            )
            assert restore.ok, restore.text


def assert_user_endpoints() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)

    me = get_json(session, "/api/me")
    assert me["email"] == USER_EMAIL
    assert me["is_active"] is True
    assert me["role"] in {"admin", "curator", "global_curator", "basic"}

    settings = get_json(session, "/api/settings")
    assert settings["application_status"] == "active"
    assert isinstance(settings["multi_model_chat_enabled"], bool)
    assert isinstance(settings["search_ui_enabled"], bool)

    providers = get_json(session, "/api/llm/provider")["providers"]
    assert providers, "Expected at least one visible LLM provider"
    visible_models = {
        model["name"]
        for provider in providers
        for model in provider["model_configurations"]
        if model["is_visible"]
    }
    assert WORKING_DEFAULT_MODEL in visible_models
    assert not (BROKEN_MODEL_NAMES & visible_models), BROKEN_MODEL_NAMES & visible_models

    sessions = get_json(session, "/api/chat/get-user-chat-sessions")
    assert isinstance(sessions["sessions"], list)

    personas = get_json(session, "/api/persona")
    assert isinstance(personas, list)

    notifications = get_json(session, "/api/notifications")
    assert isinstance(notifications["notifications"], list)

    assert_chat_session_lifecycle(session)
    assert_project_lifecycle(session)
    assert_persona_lifecycle(session)
    assert_memory_lifecycle(session)
    assert_notifications_endpoints(session)
    assert_chat_search_endpoint(session)
    assert_artifact_library_list(session)
    assert_theme_preference_roundtrip(session)


def assert_admin_endpoints() -> None:
    session = login(ADMIN_EMAIL, ADMIN_PASSWORD)

    admin_providers = get_json(session, "/api/admin/llm/provider")
    assert admin_providers["default_text"]["model_name"] == WORKING_DEFAULT_MODEL

    provider_models = {
        model["name"]: model["is_visible"]
        for provider in admin_providers["providers"]
        for model in provider["model_configurations"]
    }
    for model_name in BROKEN_MODEL_NAMES:
        assert provider_models.get(model_name) is False, model_name

    security = get_json(session, "/api/admin/security")
    assert security["ssrf_protection_level"] == "validate_all"
    assert isinstance(security["mask_credential_prefix"], bool)

    groups = get_json(session, "/api/manage/admin/user-group?include_default=true")
    assert isinstance(groups, list)
    assert any(group["name"] == "Admin" for group in groups)

    valid_domains = get_json(session, "/api/manage/admin/valid-domains")
    assert isinstance(valid_domains, list)

    enterprise_settings = get_json(session, "/api/admin/enterprise-settings")
    assert "application_name" in enterprise_settings
    assert isinstance(enterprise_settings["use_custom_logo"], bool)

    mcp_servers = get_json(session, "/api/admin/mcp/servers")
    assert "mcp_servers" in mcp_servers
    assert isinstance(mcp_servers["mcp_servers"], list)

    openapi_tools = get_json(session, "/api/tool/openapi")
    assert isinstance(openapi_tools, list)


if __name__ == "__main__":
    assert_user_endpoints()
    assert_admin_endpoints()
    print("onyx API smoke passed")
