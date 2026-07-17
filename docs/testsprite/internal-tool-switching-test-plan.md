# TestSprite test plan: internal MCP tool switching

## Stored tests

### 1. Default-agent MCP UI switching and persistence
Runs `web/tests/e2e/mcp/default-agent-mcp.spec.ts` for the UI/persistence cases only:
- admin creates an API-key MCP server through the UI;
- admin attaches MCP tools to the default agent through chat preferences;
- basic user toggles a tool plus Disable All / Enable All in chat actions;
- admin tool switch state persists after reload;
- default-agent instructions persist;
- MCP tools appear in a basic user's chat actions.

### 2. Default-agent MCP forced invocation gates enabled vs disabled tools
Runs the forced invocation case from `default-agent-mcp.spec.ts`:
- creates an assistant with MCP actions attached;
- proves forced invocation emits tool packets while enabled;
- disables the tool from the actions popover;
- proves forced invocation no longer emits packets.

Current local status: opt-in. The TestSprite wrapper preflights `INTEGRATION_TESTS_MODE=true`; without it, the test exits successfully as SKIP because the live API correctly rejects `mock_llm_response`.

### 3. Per-user MCP credential template gates tool availability
Runs `web/tests/e2e/mcp/mcp_per_user_key.spec.ts`:
- admin creates a per-user server with `Authorization` and `X-Username` template headers;
- basic user sees both required credential fields;
- save/update stays disabled until every required field is present;
- authenticated server row drills into the tool list instead of reopening auth.

### 4. OAuth MCP re-auth smoke (opt-in)
Stores `web/tests/e2e/mcp/mcp_oauth_flow.spec.ts`, but do not include it in routine runs unless OAuth env is configured (`MCP_OAUTH_*`, IdP URL, app base URL). This prevents false red runs on machines without IdP credentials.

## Regression signals
- Missing `CustomToolStart`, `CustomToolDelta`, or debug packets when the tool is enabled.
- Any tool packets after disabling the tool in the actions popover.
- `aria-checked` state not persisting across chat-preferences reload.
- Per-user modal omits `username` or enables save/update with only one field filled.
- Sidebar agent navigation assumes the nested `AppSidebar/more-agents` item exists while the Agents group is collapsed.

## Latest local run
- Passed: `Per-user MCP credential template gates tool availability`.
- Passed: `Default-agent MCP UI switching and persistence`.
- Opt-in/skipped unless integration mode is enabled: `Default-agent MCP forced invocation gates enabled vs disabled tools`.

## Model picker / live LLM additions

### 5. Broken GPT-5.6 family stays hidden from model picker
Runs `web/tests/e2e/chat/model_visibility_5_6.spec.ts`:
- confirms the admin Language Models page default is `GPT-5.5`;
- confirms the chat model picker defaults to `GPT-5.5`;
- confirms searching `GPT-5.6` yields no model options;
- confirms `GPT-5.5` remains selectable.

### 6. Live LLM model picker streams real GPT-5.5 response
Runs `web/tests/e2e/chat/live_llm_model_picker.spec.ts` with `LIVE_LLM_E2E=true`:
- opens the real chat page as an admin user;
- selects `GPT-5.5` through the model picker;
- sends a real prompt to `/api/chat/send-chat-message`;
- asserts the SSE body contains non-empty `message_delta` content;
- asserts the rendered assistant message contains `onyx-live-smoke` and no error banner appears.

Latest local status:
- Passed natively and through TestSprite: `Broken GPT-5.6 family stays hidden from model picker`.
- Passed natively and through TestSprite: `Live LLM model picker streams real GPT-5.5 response`.
- Persisted admin state verified: `default_text.model_name = gpt-5.5`; `gpt-5.6-sol`, `gpt-5.6-terra`, and `gpt-5.6-luna` are hidden.

## Endpoint and core chat input additions

### 7. Authenticated core API endpoints stay healthy through frontend proxy
Runs `testsprite_tests/onyx_api_smoke.py`:
- logs in with the provided end-user credentials and checks `/api/me`, `/api/settings`, `/api/llm/provider`, `/api/chat/get-user-chat-sessions`, `/api/persona`, and `/api/notifications`;
- logs in with admin credentials and checks `/api/admin/llm/provider`, `/api/admin/security`, `/api/manage/admin/user-group?include_default=true`, `/api/admin/mcp/servers`, and `/api/tool/openapi`;
- asserts `gpt-5.5` is visible/default and the broken `gpt-5.6-*` models are hidden.

### 8. Chat input core text submission behaviors stay working
Runs the existing `Core Text Input & Submission` block from `web/tests/e2e/chat/input_bar_behaviors.spec.ts`:
- Enter sends a non-empty message;
- send button sends a non-empty message;
- empty and whitespace-only inputs do not send;
- input clears after submit;
- 2000+ character messages render correctly.

Latest added status:
- Passed locally and through TestSprite: `Authenticated core API endpoints stay healthy through frontend proxy`.
- Passed locally and through TestSprite: `Chat input core text submission behaviors stay working`.

## Auth and settings navigation additions

### 9. Authentication UI navigation smoke stays working
Runs `web/tests/e2e/auth/auth_navigation_smoke.spec.ts`:
- unauthenticated `/app` navigation redirects to `/auth/login`;
- the login page exposes email/password fields;
- valid credentials establish a session and open chat;
- invalid password stays on login and shows `Invalid email or password`.

### 10. User and admin settings navigation pages render without app errors
Runs `web/tests/e2e/settings/settings_navigation_smoke.spec.ts`:
- visits Profile, Chats, and Accounts user settings pages;
- visits Language Models, Security & Hardening, and Users admin pages;
- asserts the expected visible header and absence of application/server error text.

Latest added status:
- Passed locally and through TestSprite: `Authentication UI navigation smoke stays working`.
- Passed locally and through TestSprite: `User and admin settings navigation pages render without app errors`.

## Multi-model and expanded API additions

### 11. Multi-model picker sends multiple model overrides
Runs `web/tests/e2e/chat/multi_model_picker_payload.spec.ts`:
- creates a temporary public provider/model through the frontend API;
- opens `/app` as a normal browser user;
- uses the `+` model picker affordance to add a second model;
- sends one chat request through the UI;
- asserts the request payload uses `llm_overrides` with both `gpt-5.5` and the temporary model;
- deletes the temporary provider after the run.

Expanded API smoke coverage:
- `/api/manage/admin/valid-domains`
- `/api/admin/enterprise-settings`

Latest added status:
- Passed locally and through TestSprite: `Multi-model picker sends multiple model overrides`.
- Re-ran and passed through TestSprite: `Authenticated core API endpoints stay healthy through frontend proxy` with the added endpoints.

## Chat search command-menu addition

### 12. Chat search command menu finds sessions and projects
Runs selected non-screenshot cases from `web/tests/e2e/chat/chat-search-command-menu.spec.ts`:
- creates temporary chat sessions and spaces/projects through the frontend API;
- opens the command menu from the sidebar search affordance;
- verifies preview limits for recent chats/projects;
- verifies filter/action entries render;
- verifies search finds a matching project;
- verifies no-result search shows an empty state;
- cleans up created sessions/projects.

Latest added status:
- Passed locally and through TestSprite: `Chat search command menu finds sessions and projects`.

Expanded API smoke coverage:
- chat-session lifecycle via `/api/chat/create-chat-session`, `/api/chat/chat-session/{id}` PATCH, `/api/chat/get-user-chat-sessions`, and `/api/chat/delete-chat-session/{id}`.

Latest added status:
- Re-ran and passed through TestSprite: `Authenticated core API endpoints stay healthy through frontend proxy` with chat-session lifecycle coverage.

## Share and internal-search additions

### 13. Share chat modal creates and removes share link
Runs `web/tests/e2e/chat/share_chat_smoke.spec.ts`:
- sends a mocked chat response through the browser UI;
- opens the share modal;
- creates a public share link and verifies the PATCH body/link UI;
- reopens the modal and makes the chat private again.

### 14. SharePoint source toggle forces internal search payload
Runs `web/tests/e2e/chat/internal_search_sharepoint_smoke.spec.ts`:
- verifies `/api/manage/indexed-sources` includes `sharepoint`;
- ensures default assistant has `SearchTool` enabled;
- opens the chat action/source controls;
- toggles Sharepoint off/on to force internal search;
- sends `tell me about my company's next holiday`;
- asserts the outgoing chat payload includes `forced_tool_id` for SearchTool and `internal_search_filters.source_type` containing `sharepoint`.

Latest added status:
- Passed locally and through TestSprite: `Share chat modal creates and removes share link`.
- Passed locally and through TestSprite: `SharePoint source toggle forces internal search payload`.

Expanded API smoke coverage:
- Space/project lifecycle via `/api/user/projects/create`, `/api/user/projects`, `/api/user/projects/{id}`, `/api/user/projects/{id}/details`, `/api/user/projects/{id}/instructions`, `/api/user/projects/{id}/pin`, metadata PATCH, and DELETE.

Latest added status:
- Re-ran and passed through TestSprite: `Authenticated core API endpoints stay healthy through frontend proxy` with Space/project lifecycle coverage.

Expanded API smoke coverage:
- Assistant/persona lifecycle via `/api/persona`, `/api/persona/{id}`, `/api/persona/{id}/share`, PATCH update, list, and DELETE.

Latest added status:
- Re-ran and passed through TestSprite: `Authenticated core API endpoints stay healthy through frontend proxy` with assistant/persona lifecycle coverage.
