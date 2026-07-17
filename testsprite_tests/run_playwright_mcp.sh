#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.testsprite.env"
PYTHON="$ROOT/.venv/bin/python"
SPEC_PATH="${1:?usage: run_playwright_mcp.sh <spec> [playwright args...]}"
shift || true

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

export PATH="$ROOT/.venv/bin:$PATH"
export BASE_URL="${BASE_URL:-http://localhost:3000}"
export ADMIN_EMAIL="${ADMIN_EMAIL:-admin_user@example.com}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-TestPassword123!}"

get_ssrf_level() {
  "$PYTHON" - <<'PY'
import os
import requests

base = os.environ.get("BASE_URL", "http://localhost:3000")
session = requests.Session()
login = session.post(
    f"{base}/api/auth/login",
    data={
        "username": os.environ["ADMIN_EMAIL"],
        "password": os.environ["ADMIN_PASSWORD"],
    },
    timeout=15,
)
login.raise_for_status()
response = session.get(f"{base}/api/admin/security", timeout=15)
response.raise_for_status()
print(response.json()["ssrf_protection_level"])
PY
}

set_ssrf_level() {
  local level="$1"
  "$PYTHON" - "$level" <<'PY'
import os
import sys
import requests

level = sys.argv[1]
base = os.environ.get("BASE_URL", "http://localhost:3000")
session = requests.Session()
login = session.post(
    f"{base}/api/auth/login",
    data={
        "username": os.environ["ADMIN_EMAIL"],
        "password": os.environ["ADMIN_PASSWORD"],
    },
    timeout=15,
)
login.raise_for_status()
response = session.put(
    f"{base}/api/admin/security",
    json={"ssrf_protection_level": level},
    timeout=15,
)
response.raise_for_status()
PY
}

previous_ssrf_level="$(get_ssrf_level)"
restore_ssrf_level() {
  set_ssrf_level "$previous_ssrf_level" || true
}
trap restore_ssrf_level EXIT
set_ssrf_level disabled

cd "$ROOT/web"
bunx playwright test "$SPEC_PATH" --project admin "$@"
