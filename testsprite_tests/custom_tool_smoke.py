#!/usr/bin/env python3
"""Live custom tool registry CRUD through the frontend proxy.

Covers the previously untested custom (OpenAPI) tool admin lifecycle:
- POST /api/admin/tool/custom/validate (validate a minimal OpenAPI 3 definition)
- POST /api/admin/tool/custom (register the tool, capture its id)
- GET  /api/tool + GET /api/tool/{id} (the tool is listed and fetchable)
- PUT  /api/admin/tool/custom/{id} (update the definition/description)
- DELETE /api/admin/tool/custom/{id} (remove it, then assert it is gone)

The tool is never invoked, so the servers URL (http://localhost:9999) is only
registered, never called. Cleanup runs in a finally block.
"""
from __future__ import annotations

import copy
import os
from typing import Any

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]

TOOL_NAME = "custom_tool_smoke"

DEFINITION: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {
        "title": "Custom Tool Smoke",
        "version": "1.0.0",
        "description": "smoke test custom tool definition",
    },
    "servers": [{"url": "http://localhost:9999"}],
    "paths": {
        "/ping": {
            "get": {
                "operationId": "pingSmoke",
                "summary": "Ping the smoke endpoint",
                "responses": {"200": {"description": "OK"}},
            }
        }
    },
}


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

    # Validate the definition before registering it.
    validate_response = session.post(
        f"{BASE_URL}/api/admin/tool/custom/validate",
        json={"definition": DEFINITION},
        timeout=20,
    )
    assert validate_response.ok, validate_response.text
    methods = validate_response.json()["methods"]
    assert any(
        method["name"] == "pingSmoke" for method in methods
    ), f"Expected pingSmoke in validated methods: {methods}"

    # Register the custom tool.
    create_response = session.post(
        f"{BASE_URL}/api/admin/tool/custom",
        json={
            "name": TOOL_NAME,
            "description": "custom tool smoke",
            "definition": DEFINITION,
            "passthrough_auth": False,
        },
        timeout=20,
    )
    assert create_response.ok, create_response.text
    created = create_response.json()
    tool_id = created["id"]
    assert created["name"] == TOOL_NAME, created
    assert created["in_code_tool_id"] is None, created

    try:
        # The new tool should appear in the tool listing.
        list_response = session.get(f"{BASE_URL}/api/tool", timeout=20)
        assert list_response.ok, list_response.text
        listed_ids = [tool["id"] for tool in list_response.json()]
        assert tool_id in listed_ids, f"{tool_id} missing from tool list {listed_ids}"

        # The single-tool fetch should round-trip the definition.
        get_response = session.get(f"{BASE_URL}/api/tool/{tool_id}", timeout=20)
        assert get_response.ok, get_response.text
        fetched = get_response.json()
        assert fetched["id"] == tool_id, fetched
        assert fetched["name"] == TOOL_NAME, fetched
        assert (
            fetched["definition"]["info"]["description"]
            == DEFINITION["info"]["description"]
        ), fetched

        # Update the definition's description and confirm the change persists.
        updated_definition = copy.deepcopy(DEFINITION)
        updated_definition["info"]["description"] = "updated smoke description"
        update_response = session.put(
            f"{BASE_URL}/api/admin/tool/custom/{tool_id}",
            json={
                "name": TOOL_NAME,
                "description": "custom tool smoke updated",
                "definition": updated_definition,
                "passthrough_auth": False,
            },
            timeout=20,
        )
        assert update_response.ok, update_response.text
        updated = update_response.json()
        assert updated["description"] == "custom tool smoke updated", updated
        assert (
            updated["definition"]["info"]["description"]
            == "updated smoke description"
        ), updated
    finally:
        delete_response = session.delete(
            f"{BASE_URL}/api/admin/tool/custom/{tool_id}",
            timeout=20,
        )
        assert delete_response.ok, delete_response.text

        after_delete = session.get(f"{BASE_URL}/api/tool", timeout=20)
        assert after_delete.ok, after_delete.text
        remaining_ids = [tool["id"] for tool in after_delete.json()]
        assert (
            tool_id not in remaining_ids
        ), f"{tool_id} still present after delete: {remaining_ids}"

    print("custom tool smoke passed")


if __name__ == "__main__":
    main()
