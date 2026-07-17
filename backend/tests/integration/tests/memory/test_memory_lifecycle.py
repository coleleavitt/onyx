"""Full-stack proof of the memory lifecycle against a real Onyx deployment.

Covers: manual populate via the /memory API, chat-driven populate via the memory
tool, and recall of a stored fact in a later chat turn. The chat tests make real
LLM calls, so they use the cheap tier (OpenAI gpt-5-mini) per repo policy.

NOTE: this runs against a real deployment through the integration harness — do
not point it at a working instance you care about.
"""

import pytest

from tests.integration.common_utils.managers.chat import ChatSessionManager
from tests.integration.common_utils.managers.llm_provider import LLMProviderManager
from tests.integration.common_utils.managers.memory import MemoryManager
from tests.integration.common_utils.managers.user import UserManager
from tests.integration.common_utils.test_models import DATestLLMProvider
from tests.integration.common_utils.test_models import DATestUser


@pytest.fixture
def memory_llm_provider(admin_user: DATestUser) -> DATestLLMProvider:
    # Cheap-and-fast tier for real LLM calls (never gpt-4o / gpt-4o-mini).
    return LLMProviderManager.create(
        user_performing_action=admin_user,
        default_model_name="gpt-5-mini",
    )


def test_manual_populate_and_list_by_category() -> None:
    """Populate an account across every category via the /memory API and read it
    back with correct totals and per-category counts. No LLM involved."""
    user = UserManager.create()

    seeded = [
        ("The user's favorite color is teal.", "notes"),
        ("Onyx is the user's primary work project.", "entities"),
        ("The user cares deeply about retrieval quality.", "concepts"),
        ("The user is driving the Q3 launch.", "workstreams"),
        ("The user takes meeting notes in Markdown.", "notes"),
    ]
    for content, category in seeded:
        created = MemoryManager.create(content, user, category=category)
        assert created["id"] > 0
        assert created["content"] == content

    listing = MemoryManager.list(user)
    assert listing["total"] == len(seeded)
    assert listing["category_counts"]["notes"] == 2
    assert listing["category_counts"]["entities"] == 1
    assert listing["category_counts"]["concepts"] == 1
    assert listing["category_counts"]["workstreams"] == 1

    notes_only = MemoryManager.list(user, category="notes")
    assert len(notes_only["items"]) == 2
    assert all(item["category"] == "notes" for item in notes_only["items"])


def test_new_chat_session_recalls_stored_memory(
    memory_llm_provider: DATestLLMProvider,
) -> None:
    """A stored memory is recalled (eager system-prompt injection) so a later,
    fresh chat session can answer a question that depends on it."""
    user = UserManager.create()
    # use_memories defaults to True; make the dependency explicit.
    MemoryManager.set_personalization(user, use_memories=True)

    MemoryManager.create(
        "The user's secret project codename is Zephyr-Nine.",
        user,
        title="Project codename",
        category="entities",
    )

    session = ChatSessionManager.create(user_performing_action=user)
    response = ChatSessionManager.send_message(
        chat_session_id=session.id,
        message="What is my secret project codename? Reply with only the codename.",
        user_performing_action=user,
    )

    assert response.error is None
    assert "zephyr-nine" in response.full_message.lower()


def test_chat_memory_tool_persists_a_new_memory(
    memory_llm_provider: DATestLLMProvider,
) -> None:
    """Asking the assistant to remember something triggers the memory tool, which
    persists a new memory row (source="conversation")."""
    user = UserManager.create()
    # enable_memory_tool defaults to True; make it explicit.
    MemoryManager.set_personalization(user, enable_memory_tool=True)

    before = MemoryManager.list(user)["total"]

    session = ChatSessionManager.create(user_performing_action=user)
    response = ChatSessionManager.send_message(
        chat_session_id=session.id,
        message="Please remember that my favorite programming language is Rust.",
        user_performing_action=user,
    )
    assert response.error is None

    after = MemoryManager.list(user)
    assert after["total"] > before
    assert any("rust" in item["content"].lower() for item in after["items"])
