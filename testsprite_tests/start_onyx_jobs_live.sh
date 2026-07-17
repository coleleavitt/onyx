#!/usr/bin/env bash
# Start the Onyx background jobs runner (all celery workers + beat) with the
# same env bootstrap as start_onyx_api_live.sh. Without the S3/MinIO env the
# workers boot fine but every user-file task dies with NoCredentialsError.
set -Eeuo pipefail
ROOT=/home/cole/WebstormProjects/forks/onyx
trim() { local value="$*"; value="${value#"${value%%[![:space:]]*}"}"; value="${value%"${value##*[![:space:]]}"}"; printf '%s' "$value"; }
strip_quotes() { local value="$1"; if [[ "$value" == \"* && "$value" == *\" ]]; then value="${value:1:${#value}-2}"; elif [[ "$value" == \'* && "$value" == *\' ]]; then value="${value:1:${#value}-2}"; fi; printf '%s' "$value"; }
load_env_file() {
  local file="$1"; [[ -f "$file" ]] || return 0
  while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
    local line key value
    line="$(trim "$raw_line")"
    [[ -z "$line" || "$line" == \#* || "$line" != *=* ]] && continue
    key="$(trim "${line%%=*}")"
    value="$(trim "${line#*=}")"
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    [[ "$value" == *"<REPLACE"* || "$value" == *"<ABSOLUTE PATH"* ]] && continue
    value="$(strip_quotes "$value")"
    export "$key=$value"
  done < "$file"
}
load_env_file "$ROOT/.vscode/.env"
export VIRTUAL_ENV="$ROOT/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
export PYTHONPATH="${PYTHONPATH:-$ROOT/backend}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-http://localhost:9004}"
export S3_FILE_STORE_BUCKET_NAME="${S3_FILE_STORE_BUCKET_NAME:-onyx-file-store-bucket}"
export S3_AWS_ACCESS_KEY_ID="${S3_AWS_ACCESS_KEY_ID:-minioadmin}"
export S3_AWS_SECRET_ACCESS_KEY="${S3_AWS_SECRET_ACCESS_KEY:-minioadmin}"
export OPENSEARCH_ADMIN_PASSWORD="${OPENSEARCH_ADMIN_PASSWORD:-${OPENSEARCH_INITIAL_ADMIN_PASSWORD:-StrongPassword123!}}"
unset INTEGRATION_TESTS_MODE
cd "$ROOT/backend"
exec python ./scripts/dev_run_background_jobs.py
