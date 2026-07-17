#!/usr/bin/env python3
"""Live LLM provider admin CRUD through the frontend proxy.

Covers the previously untested admin LLM provider lifecycle:
- PUT /api/admin/llm/provider?is_creation=true  (create a brand-new provider)
- GET /api/admin/llm/provider                   (admin list + default_text)
- PUT /api/admin/llm/provider?is_creation=false (benign update / rename)
- GET /api/llm/provider                          (user-visible basics list)
- DELETE /api/admin/llm/provider/{id}            (cleanup)

Protected state guarded here (must survive byte-identical): the default text
model stays 'gpt-5.5' on existing provider id 1, and the hidden models
gpt-5.6-sol/terra/luna stay non-visible. Never touches provider id 1, never
calls a set-default endpoint, and never hits a /test endpoint (the key is fake).
"""
from __future__ import annotations

import os

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
USER_EMAIL = os.environ["EMAIL"]
USER_PASSWORD = os.environ["PASSWORD"]

PROVIDER_NAME = "api-smoke-provider"
PROVIDER_NAME_RENAMED = "api-smoke-provider-renamed"
HIDDEN_MODELS = {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"}
DEFAULT_TEXT_MODEL = "gpt-5.5"


def login(email: str, password: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{BASE_URL}/api/auth/login",
        data={"username": email, "password": password},
        timeout=20,
    )
    assert response.status_code == 204, response.text
    return session


def get_admin_providers(session: requests.Session) -> dict:
    response = session.get(f"{BASE_URL}/api/admin/llm/provider", timeout=30)
    assert response.ok, response.text
    return response.json()


def assert_default_text_intact(payload: dict) -> None:
    default_text = payload.get("default_text")
    assert default_text is not None, "default_text unexpectedly missing"
    assert (
        default_text["model_name"] == DEFAULT_TEXT_MODEL
    ), f"default_text was altered: {default_text}"


def main() -> None:
    session = login(USER_EMAIL, USER_PASSWORD)

    # Baseline: capture default before touching anything.
    baseline = get_admin_providers(session)
    assert_default_text_intact(baseline)

    create_body = {
        "name": PROVIDER_NAME,
        "provider": "openai",
        "api_key": "sk-api-smoke-fake",
        "api_key_changed": True,
        "custom_config_changed": False,
        "is_public": True,
        "model_configurations": [{"name": "gpt-4o-mini", "is_visible": True}],
    }
    create_response = session.put(
        f"{BASE_URL}/api/admin/llm/provider",
        params={"is_creation": "true"},
        json=create_body,
        timeout=30,
    )
    assert create_response.ok, create_response.text
    created = create_response.json()
    provider_id = created["id"]

    # Enter the try immediately so every post-create assertion is covered by the
    # finally's DELETE. Otherwise a regression here (e.g. an echoed raw key) would
    # abort before cleanup and orphan the persisted provider row.
    try:
        assert created["name"] == PROVIDER_NAME, created
        assert created["provider"] == "openai", created
        # The raw fake key must never be echoed back; it is masked on return.
        assert created["api_key"] != "sk-api-smoke-fake", "api_key should be masked"
        assert provider_id != 1, "must never collide with protected provider id 1"

        # Creating a provider must not steal the global default text model.
        after_create = get_admin_providers(session)
        assert_default_text_intact(after_create)
        listed = {p["id"]: p for p in after_create["providers"]}
        assert provider_id in listed, "new provider missing from admin list"
        assert listed[provider_id]["name"] == PROVIDER_NAME, listed[provider_id]

        # Benign update: rename the provider (reusing the stored key).
        update_body = {
            "id": provider_id,
            "name": PROVIDER_NAME_RENAMED,
            "provider": "openai",
            "api_key_changed": False,
            "custom_config_changed": False,
            "is_public": True,
            "model_configurations": [{"name": "gpt-4o-mini", "is_visible": True}],
        }
        update_response = session.put(
            f"{BASE_URL}/api/admin/llm/provider",
            params={"is_creation": "false"},
            json=update_body,
            timeout=30,
        )
        assert update_response.ok, update_response.text
        updated = update_response.json()
        assert updated["id"] == provider_id, updated
        assert updated["name"] == PROVIDER_NAME_RENAMED, updated

        after_update = get_admin_providers(session)
        assert_default_text_intact(after_update)
        listed_after_update = {p["id"]: p for p in after_update["providers"]}
        assert (
            listed_after_update[provider_id]["name"] == PROVIDER_NAME_RENAMED
        ), listed_after_update[provider_id]

        # User-visible basics list: assert the response shape is sane.
        basic_response = session.get(f"{BASE_URL}/api/llm/provider", timeout=30)
        assert basic_response.ok, basic_response.text
        basic = basic_response.json()
        assert isinstance(basic.get("providers"), list), basic
        assert "default_text" in basic and "default_vision" in basic, basic
        assert basic["providers"], "expected at least one visible provider"
        for descriptor in basic["providers"]:
            for key in ("id", "name", "provider", "model_configurations"):
                assert key in descriptor, f"basic descriptor missing {key}: {descriptor}"
        basic_by_id = {p["id"]: p for p in basic["providers"]}
        assert provider_id in basic_by_id, "public provider missing from basics list"
    finally:
        delete_response = session.delete(
            f"{BASE_URL}/api/admin/llm/provider/{provider_id}",
            timeout=30,
        )
        assert delete_response.ok, delete_response.text

    # Post-cleanup: provider gone, default intact, hidden models still hidden.
    final_admin = get_admin_providers(session)
    assert_default_text_intact(final_admin)
    assert provider_id not in {
        p["id"] for p in final_admin["providers"]
    }, "provider was not cleaned up"

    final_basic = session.get(f"{BASE_URL}/api/llm/provider", timeout=30)
    assert final_basic.ok, final_basic.text
    for descriptor in final_basic.json()["providers"]:
        for model_config in descriptor["model_configurations"]:
            if model_config["name"] in HIDDEN_MODELS:
                assert (
                    model_config["is_visible"] is False
                ), f"protected hidden model became visible: {model_config['name']}"

    print("LLM provider admin smoke passed")


if __name__ == "__main__":
    main()
