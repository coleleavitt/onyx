# PRD: TestSprite coverage for the Brain / Memory system

## Problem

Onyx ships a per-user long-term **memory** system (and the "Brain" self-improvement
layer on top of it), but it has almost no automated coverage: a handful of
DB-level unit / external-dependency tests exist, there is no integration test that
drives the real chat stack, no Playwright spec for the memory UI, and no entry in
the local TestSprite suite. That leaves the highest-value behavior — *a stored
memory actually changing a later answer* — untracked.

## Goals

- Document the memory/brain system (this PRD doubles as the code summary).
- Prove the full lifecycle end to end: **populate** memories (manually, from a
  chat via the memory tool, and via the Brain graph) and then **recall** them in a
  later chat turn.
- Track the proofs in TestSprite so regressions produce run history, wrapping the
  existing Onyx pytest + Playwright runners rather than duplicating them.

## Non-goals

- Do not add semantic/embedding retrieval expectations — recall is deliberately
  recency-based (see below); tests must not assume relevance ranking.
- Do not exercise the daily Brain Celery schedule in CI; invoke the extraction
  path directly / seed the graph instead of waiting for `crontab(hour=3)`.
- Do not chase whole-codebase coverage numbers from TestSprite's name-based gaps.

## Code summary — how the memory system works

**Storage (`backend/onyx/db/models.py`)**: `Memory` (flat per-user rows: `title`,
`category`, `memory_text`), `MemoryRevision` (version history, carries `source`),
`MemoryRelation` (undirected graph edges), `MemorySource` (citations),
`MemoryGovernancePolicy` (org singleton), `MemoryGovernanceAudit`.
Categories (`MemoryCategory`): `notes / concepts / entities / workstreams`.
Source types (`MemorySourceType`): `chat_session / document / connector / file / manual`.

**Creation — three paths, one master gate:**
- Manual: `POST /memory` → `create_memory_item(source="manual")`
  (`backend/onyx/db/memory.py`); also the personalization list via
  `PATCH /user/personalization`.
- Chat memory tool: `MemoryTool` / `add_memory`
  (`backend/onyx/tools/tool_implementations/memory/memory_tool.py`); the row is
  written in `backend/onyx/chat/llm_loop.py` with `source="conversation"`. Needs
  `user.enable_memory_tool`.
- Brain self-improvement: `brain_self_improvement()`
  (`backend/onyx/background/celery/tasks/brain/tasks.py`, daily) — an LLM extracts
  pages from recent sessions/cited docs (`source="brain"`) and builds the
  relation graph + source citations. Needs `user.brain_enabled`.
- **Every** path is gated by the org singleton
  `MemoryGovernancePolicy.is_memory_creation_allowed` (`memories_enabled AND
  memory_creation_enabled`), which defaults to enabled.

**Recall — eager, recency-based (no embeddings):** each chat turn calls
`get_memories()` (`backend/onyx/db/memory.py`), a flat
`ORDER BY updated_at DESC LIMIT 20` capped at 8,000 chars. The result is injected
into the `# User Information` system-prompt block
(`backend/onyx/chat/prompt_utils.py`) and passed to Search query-expansion. Gated
by `policy.memories_enabled` (fetch) + `user.use_memories` (inject). The memory
tool is write-only; the relation graph (`backend/onyx/db/brain.py`
`get_related_memories` / `get_memory_graph`) powers the **UI only**, not chat recall.

**API (`backend/onyx/server/features/memory/api.py`, prefix `/memory`)**: list /
create / get / update / delete, `/graph`, `/{id}/history` + `/restore`,
`/{id}/related`, `/{id}/sources`, and `/brain/settings` (GET/PUT). Admin governance
lives at `/admin/memory-governance`.

**UI (`web/src/views/memory/*`, route `/app/customize/memory`)**: MemoryPage
(grid/list/graph views, category tabs, Add/Brain/Settings), MemoryEditorModal
(add/edit + Details/History tabs with Restore), BrainSettingsModal, MemoryGraphView.
The **Add memory** button is gated by `organization_memory_creation_enabled`.

## Source evidence (the proofs)

- `backend/tests/external_dependency_unit/tools/test_memory_recall_and_graph.py` —
  DB/context-layer proof: populate across categories → `get_memories` recall
  context (recency-ordered, exposed via `as_formatted_list`) + brain graph
  (edges, degree, source citations, ownership guards). Deterministic, no LLM.
- `backend/tests/integration/tests/memory/test_memory_lifecycle.py` — full-stack
  proof: manual populate via `MemoryManager`, deterministic chat-tool populate
  (`forced_tool_ids` + `mock_llm_response`), and a real-LLM (`gpt-5-mini`) recall
  where a stored fact changes the answer.
- `web/tests/e2e/customize/memory_lifecycle.spec.ts` — UI proof: add / edit /
  restore / delete a memory + toggle Brain settings at `/app/customize/memory`.
- `testsprite_tests/memory_demo_populate.py` — live walkthrough that populates the
  admin account and demonstrates populate + recall against the running stack.
- Pre-existing DB coverage reused, not duplicated:
  `backend/tests/external_dependency_unit/tools/test_memory_tool_integration.py`,
  `test_memory_governance.py`, `test_memory_library.py`,
  `backend/tests/unit/tools/test_memory_tool_packets.py`.

## Acceptance criteria

- A stored memory is returned by `get_memories`, newest-first, and reaches the
  chat layer via `as_formatted_list()`.
- The brain graph reports correct nodes/edges/degree and source citations; the
  relation writer rejects self-edges and cross-user edges.
- A chat message with the memory tool forced creates a `source="conversation"`
  memory row.
- With `use_memories=True`, a new chat session recalls a previously stored fact in
  its answer (real `gpt-5-mini` call).
- The memory UI can add, edit, restore, and delete a memory and toggle Brain.
- TestSprite runs each proof to a green verdict; `validate_testsprite_artifacts.py`
  stays green.
