#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.testsprite.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

BASE_URL="${BASE_URL:-http://localhost:3000}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin_user@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-TestPassword123!}"

probe_output="$($ROOT/.venv/bin/python - <<'PY'
import os
import requests

base = os.environ.get("BASE_URL", "http://localhost:3000").rstrip("/")
session = requests.Session()
login = session.post(
    f"{base}/api/auth/login",
    data={
        "username": os.environ.get("ADMIN_EMAIL", "admin_user@example.com"),
        "password": os.environ.get("ADMIN_PASSWORD", "TestPassword123!"),
    },
    timeout=15,
)
login.raise_for_status()
response = session.post(
    f"{base}/api/chat/send-chat-message",
    json={
        "message": "integration mode probe",
        "chat_session_id": "00000000-0000-0000-0000-000000000000",
        "parent_message_id": None,
        "file_descriptors": [],
        "internal_search_filters": None,
        "deep_research": False,
        "mock_llm_response": "{}",
    },
    timeout=20,
)
print(response.text[:300])
PY
)"

if grep -q "mock_llm_response can only be used when INTEGRATION_TESTS_MODE=true" <<<"$probe_output"; then
  echo "SKIP: API server is not running with INTEGRATION_TESTS_MODE=true; forced MCP invocation mock_llm_response test is opt-in."
  exit 0
fi

exec "$ROOT/testsprite_tests/run_playwright_mcp.sh" \
  tests/e2e/mcp/default-agent-mcp.spec.ts \
  --grep "Basic user can create an assistant with MCP actions attached"
