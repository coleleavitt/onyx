#!/usr/bin/env bash
# Opt-in wrapper for the MCP OAuth reauthentication Playwright test.
#
# The test needs a real OAuth IdP configured via MCP_OAUTH_* env vars. When
# they are absent (normal local dev), exit successfully with a SKIP so the
# suite stays honest instead of permanently red — same pattern as
# run_mcp_forced_invocation_if_enabled.sh.
set -uo pipefail

ROOT=/home/cole/WebstormProjects/forks/onyx
cd "$ROOT"
set -a
. ./.testsprite.env 2>/dev/null || true
set +a

REQUIRED_VARS=(
  MCP_OAUTH_CLIENT_ID
  MCP_OAUTH_CLIENT_SECRET
  MCP_OAUTH_ISSUER
  MCP_OAUTH_JWKS_URI
  MCP_OAUTH_USERNAME
  MCP_OAUTH_PASSWORD
)

MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
  [ -n "${!var:-}" ] || MISSING+=("$var")
done

if [ "${#MISSING[@]}" -gt 0 ]; then
  echo "SKIP: MCP OAuth env not configured (missing: ${MISSING[*]}); this test is opt-in."
  exit 0
fi

exec ./testsprite_tests/run_playwright_mcp.sh tests/e2e/mcp/mcp_oauth_flow.spec.ts
