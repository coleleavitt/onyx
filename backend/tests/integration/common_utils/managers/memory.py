from typing import Any

from onyx.configs.constants import FASTAPI_USERS_AUTH_COOKIE_NAME
from tests.integration.common_utils.constants import API_SERVER_URL
from tests.integration.common_utils.http_client import client
from tests.integration.common_utils.test_models import DATestUser


def _cookies(user: DATestUser) -> dict:
    return {
        FASTAPI_USERS_AUTH_COOKIE_NAME: user.cookies[FASTAPI_USERS_AUTH_COOKIE_NAME]
    }


class MemoryManager:
    """Thin wrapper over the /memory + /user/personalization APIs for integration
    tests, following the repo convention of using a Manager over raw requests."""

    @staticmethod
    def create(
        content: str,
        user_performing_action: DATestUser,
        *,
        title: str | None = None,
        category: str = "notes",
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"content": content, "category": category}
        if title is not None:
            body["title"] = title
        response = client.post(
            f"{API_SERVER_URL}/memory",
            json=body,
            headers=user_performing_action.headers,
            cookies=_cookies(user_performing_action),
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def list(
        user_performing_action: DATestUser,
        *,
        category: str | None = None,
    ) -> dict[str, Any]:
        response = client.get(
            f"{API_SERVER_URL}/memory",
            params={"category": category} if category else None,
            headers=user_performing_action.headers,
            cookies=_cookies(user_performing_action),
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def delete(memory_id: int, user_performing_action: DATestUser) -> None:
        response = client.delete(
            f"{API_SERVER_URL}/memory/{memory_id}",
            headers=user_performing_action.headers,
            cookies=_cookies(user_performing_action),
        )
        response.raise_for_status()

    @staticmethod
    def get_brain_settings(user_performing_action: DATestUser) -> dict[str, Any]:
        response = client.get(
            f"{API_SERVER_URL}/memory/brain/settings",
            headers=user_performing_action.headers,
            cookies=_cookies(user_performing_action),
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def set_brain_settings(
        user_performing_action: DATestUser,
        *,
        brain_enabled: bool,
        brain_use_connectors: bool,
        brain_focus_instructions: str | None = None,
    ) -> dict[str, Any]:
        response = client.put(
            f"{API_SERVER_URL}/memory/brain/settings",
            json={
                "brain_enabled": brain_enabled,
                "brain_use_connectors": brain_use_connectors,
                "brain_focus_instructions": brain_focus_instructions,
            },
            headers=user_performing_action.headers,
            cookies=_cookies(user_performing_action),
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def set_personalization(
        user_performing_action: DATestUser,
        **payload: Any,
    ) -> None:
        """Patch personalization flags such as ``use_memories`` /
        ``enable_memory_tool`` that gate recall and the chat memory tool."""
        response = client.patch(
            f"{API_SERVER_URL}/user/personalization",
            json=payload,
            headers=user_performing_action.headers,
            cookies=_cookies(user_performing_action),
        )
        response.raise_for_status()
