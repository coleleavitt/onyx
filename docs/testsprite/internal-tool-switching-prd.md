# PRD: TestSprite coverage for internal MCP tool switching

## Problem
Onyx already has Playwright coverage for MCP server setup, default-agent tool toggles, per-user credential gates, and forced MCP tool invocation. That coverage is not yet represented in the local TestSprite suite, so TestSprite cannot track regressions or produce run history for the internal tool-switching surface.

## Goals
- Track the high-risk MCP/tool-switching flows in TestSprite without duplicating Playwright helpers.
- Prove that enabling a tool allows a forced chat invocation and disabling it prevents invocation.
- Cover admin default-agent persistence and basic-user actions-popover toggles.
- Cover per-user multi-field credential gating because missing template fields break tool availability.

## Non-goals
- Do not replace the existing Playwright specs.
- Do not run the OAuth suite by default; it needs extra IdP environment and is better kept as an opt-in TestSprite test.
- Do not chase whole-codebase percentage coverage from TestSprite's name-based gap report.

## Source evidence
- `web/tests/e2e/mcp/default-agent-mcp.spec.ts` covers admin API-key server creation, default-agent tool attachment, user toggles, forced invocation, and persisted chat-preference tool state.
- `web/tests/e2e/mcp/mcp_per_user_key.spec.ts` covers per-user API key templates with both `api_key` and `username` required.
- `web/tests/e2e/mcp/mcpToolInvocation.ts` captures stream packets and asserts invoked vs not-invoked behavior.
- `web/tests/e2e/pages/ActionsPopover.ts` wraps the tool list, per-tool switches, enable/disable-all controls, credentials modal, and re-auth rows.

## Acceptance criteria
- A TestSprite test exists for default-agent MCP tool switching and invocation gating.
- A TestSprite test exists for per-user credential field gating.
- The TestSprite suite can run the focused tests through existing Playwright specs from repo root.
- Local TestSprite credentials live only in `.testsprite.env`, which is gitignored.
- TestSprite code summary exists at `testsprite_tests/tmp/code_summary.yaml`.

## Addendum: model picker and live LLM guardrails

The visible default model `GPT-5.6 Sol` returned an empty OpenAI stream in live end-user chat. The admin-configured default was moved to `GPT-5.5`, and the broken `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` model configurations were hidden through the Language Models admin page.

Additional acceptance criteria:
- The admin Language Models page shows `GPT-5.5` as the default model.
- End-user model picker search for `GPT-5.6` returns no models.
- End-user model picker still exposes `GPT-5.5`.
- A live prompt sent through the selected `GPT-5.5` model streams non-empty `message_delta` packets and renders the assistant response.
