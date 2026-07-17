# TestSprite test plan: Brain / Memory system

Paired PRD: `docs/testsprite/memory-system-prd.md`. These proofs cover the memory
lifecycle across all three vehicles (Onyx pytest, Playwright, TestSprite wrappers).
Recall is recency-based, so assertions check presence + recency, never relevance.

## Stored tests

### 1. Memory recall context + brain graph (external-dependency unit)

- **Runs:** `backend/tests/external_dependency_unit/tools/test_memory_recall_and_graph.py`
- **Command:** `python -m dotenv -f .vscode/.env run -- pytest backend/tests/external_dependency_unit/tools/test_memory_recall_and_graph.py`
- **Asserts:**
  - Memories populated across all four categories come back from `get_memories`,
    newest-first, and appear in `as_formatted_list()` (the chat-layer surface).
  - `use_memories=False` still fetches (`user_id` populated); `without_memories()`
    strips the text.
  - Brain graph: 3 nodes / 2 edges, hub node has degree 2, leaves degree 1;
    `get_related_memories` and `get_memory_sources` return the seeded relations
    and citations.
  - The relation writer rejects self-edges and cross-user edges.
- **Regression signals:** recall ordering flips to non-recency; graph degree
  miscount; ownership guard removed.
- **Latest local run:** 4 passed.

### 2. Memory populate + recall (integration, real stack)

- **Runs:** `backend/tests/integration/tests/memory/test_memory_lifecycle.py`
- **Command:** `python -m dotenv -f .vscode/.env run -- pytest backend/tests/integration/tests/memory/test_memory_lifecycle.py`
- **Asserts:**
  - Manual populate via `MemoryManager.create` across categories → list +
    `category_counts` correct.
  - A chat message with `forced_tool_ids=[memory tool]` + `mock_llm_response`
    emits a `MEMORY_TOOL_DELTA` and writes a `source="conversation"` row.
  - With `use_memories=True`, a **new** chat session recalls a stored fact in its
    streamed answer (real `gpt-5-mini`).
- **Regression signals:** memory tool stops persisting; recall no longer injected
  into the system prompt.
- **Latest local run:** registered in TestSprite (id 944ae2c2), runs in the integration harness.

### 3. Memory UI lifecycle (Playwright E2E)

- **Runs:** `web/tests/e2e/customize/memory_lifecycle.spec.ts`
- **Command:** `cd web && bunx playwright test tests/e2e/customize/memory_lifecycle.spec.ts --project admin`
- **Asserts:** at `/app/customize/memory`, a worker user can add a memory (title /
  category / content), see the card, reload and still see it, edit + save, toggle
  Brain settings, and delete it (card gone). Org memory-creation policy is enabled
  first so the Add button is active.
- **Regression signals:** Add button stuck disabled; memory not persisted across
  reload; Brain modal write fails.
- **Latest local run:** 1 passed (TestSprite verdict passed).

### 4. Live memory demo populate (walkthrough)

- **Runs:** `testsprite_tests/memory_demo_populate.py`
- **Command:** `.venv/bin/python testsprite_tests/memory_demo_populate.py`
- **Asserts / shows:** against the running stack as admin, seeds memories across
  categories, runs chat sessions that trigger the memory tool, then a recall query,
  printing the recalled answer plus the resulting `/api/memory` and
  `/api/memory/graph` state. Exit 0 on success.
- **Regression signals:** create/list/recall path broken end to end.
- **Latest local run:** passed (TestSprite verdict passed).

## Notes

- The pre-existing DB tests (`test_memory_tool_integration.py`,
  `test_memory_governance.py`, `test_memory_library.py`,
  `test_memory_tool_packets.py`) remain the unit/DB backbone and are not duplicated
  here.
- Any real-LLM step uses OpenAI `gpt-5-mini` (cheap tier), per repo policy.
