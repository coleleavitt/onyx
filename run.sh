#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
WEB_DIR="$ROOT_DIR/web"
COMPOSE_DIR="$ROOT_DIR/deployment/docker_compose"
VSCODE_ENV="$ROOT_DIR/.vscode/.env"
VSCODE_WEB_ENV="$ROOT_DIR/.vscode/.env.web"
DOCKER_ENV="$COMPOSE_DIR/.env"

MODE="dev"
SETUP="auto"
INSTALL_PLAYWRIGHT="auto"
PIDS=()

usage() {
  cat <<'USAGE'
Usage:
  ./run.sh                 Start source dev mode: infra + web + model server + jobs + API.
  ./run.sh --infra-only    Start only Postgres/OpenSearch/Redis/MinIO.
  ./run.sh --docker        Start the full Docker Compose stack from prebuilt images.
  ./run.sh --setup         Force uv sync, Playwright install, and bun install before starting.
  ./run.sh --no-setup      Skip dependency setup checks.

Source dev serves Onyx at http://localhost:3000 and keeps logs in this terminal.
USAGE
}

log() {
  printf '[run.sh] %s\n' "$*"
}

die() {
  printf '[run.sh] error: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

random_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif command -v uuidgen >/dev/null 2>&1; then
    uuidgen | tr -d '-' | sha256sum | awk '{print $1}'
  else
    date +%s%N | sha256sum | awk '{print $1}'
  fi
}

trim() {
  local value="$*"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

strip_quotes() {
  local value="$1"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0

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

env_value_is_empty() {
  local file="$1"
  local key="$2"
  local value
  value="$(grep -E "^${key}=" "$file" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  value="$(strip_quotes "$(trim "$value")")"
  [[ -z "$value" || "$value" == *"<REPLACE"* ]]
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp
  tmp="$(mktemp)"

  if grep -Eq "^${key}=" "$file" 2>/dev/null; then
    awk -v key="$key" -v replacement="${key}=${value}" '
      BEGIN { replaced = 0 }
      $0 ~ "^" key "=" {
        if (replaced == 0) {
          print replacement
          replaced = 1
        }
        next
      }
      { print }
    ' "$file" > "$tmp"
  else
    cp "$file" "$tmp"
    printf '\n%s=%s\n' "$key" "$value" >> "$tmp"
  fi

  mv "$tmp" "$file"
}

ensure_local_env_files() {
  if [[ ! -f "$VSCODE_ENV" ]]; then
    cp "$ROOT_DIR/.vscode/env_template.txt" "$VSCODE_ENV"
    log "created .vscode/.env from template"
  fi

  if [[ ! -f "$VSCODE_WEB_ENV" && -f "$ROOT_DIR/.vscode/env.web_template.txt" ]]; then
    cp "$ROOT_DIR/.vscode/env.web_template.txt" "$VSCODE_WEB_ENV"
    log "created .vscode/.env.web from template"
  fi

  load_env_file "$VSCODE_ENV"
  load_env_file "$VSCODE_WEB_ENV"

  export AUTH_TYPE="${AUTH_TYPE:-basic}"
  export DEV_MODE="${DEV_MODE:-true}"
  export PYTHONPATH="${PYTHONPATH:-$BACKEND_DIR}"
  export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
  export S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-http://localhost:9004}"
  export S3_FILE_STORE_BUCKET_NAME="${S3_FILE_STORE_BUCKET_NAME:-onyx-file-store-bucket}"
  export S3_AWS_ACCESS_KEY_ID="${S3_AWS_ACCESS_KEY_ID:-minioadmin}"
  export S3_AWS_SECRET_ACCESS_KEY="${S3_AWS_SECRET_ACCESS_KEY:-minioadmin}"
  export OPENSEARCH_ADMIN_PASSWORD="${OPENSEARCH_ADMIN_PASSWORD:-${OPENSEARCH_INITIAL_ADMIN_PASSWORD:-StrongPassword123!}}"

  if [[ -z "${USER_AUTH_SECRET:-}" ]]; then
    USER_AUTH_SECRET="$(random_hex)"
    export USER_AUTH_SECRET
  fi

  if [[ -z "${OPENAI_API_KEY:-}" && -z "${GEN_AI_API_KEY:-}" ]]; then
    log "OPENAI_API_KEY / GEN_AI_API_KEY are unset; add one to .vscode/.env or configure a provider in the UI."
  fi
}

ensure_docker_env_file() {
  if [[ ! -f "$DOCKER_ENV" ]]; then
    cp "$COMPOSE_DIR/env.template" "$DOCKER_ENV"
    log "created deployment/docker_compose/.env from template"
  fi

  if env_value_is_empty "$DOCKER_ENV" "USER_AUTH_SECRET"; then
    set_env_value "$DOCKER_ENV" "USER_AUTH_SECRET" "$(random_hex)"
    log "generated USER_AUTH_SECRET in deployment/docker_compose/.env"
  fi

  if env_value_is_empty "$DOCKER_ENV" "OPENSEARCH_ADMIN_PASSWORD"; then
    set_env_value "$DOCKER_ENV" "OPENSEARCH_ADMIN_PASSWORD" "StrongPassword123!"
  fi

  if [[ -n "${OPENAI_API_KEY:-}" ]] && env_value_is_empty "$DOCKER_ENV" "OPENAI_API_KEY"; then
    set_env_value "$DOCKER_ENV" "OPENAI_API_KEY" "$OPENAI_API_KEY"
  fi
}

setup_dependencies() {
  [[ "$SETUP" == "never" ]] && return 0

  require_cmd uv
  require_cmd bun

  if [[ "$SETUP" == "always" || ! -x "$ROOT_DIR/.venv/bin/uvicorn" || ! -x "$ROOT_DIR/.venv/bin/alembic" ]]; then
    log "syncing Python dependencies"
    (cd "$ROOT_DIR" && uv sync --frozen)
  fi

  if [[ "$INSTALL_PLAYWRIGHT" == "always" || ! -d "${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}" ]]; then
    log "installing Playwright browsers"
    (cd "$ROOT_DIR" && uv run playwright install)
  fi

  if [[ "$SETUP" == "always" || ! -d "$WEB_DIR/node_modules" ]]; then
    log "installing web dependencies"
    (cd "$WEB_DIR" && bun install)
  fi
}

compose() {
  (cd "$COMPOSE_DIR" && docker compose -f docker-compose.yml -f docker-compose.dev.yml "$@")
}

start_infra() {
  require_cmd docker
  log "starting Postgres, OpenSearch, Redis, and MinIO"
  OPENSEARCH_ADMIN_PASSWORD="$OPENSEARCH_ADMIN_PASSWORD" compose up -d --wait opensearch relational_db cache minio
}

run_migrations() {
  log "running database migrations"
  (cd "$BACKEND_DIR" && "$ROOT_DIR/.venv/bin/alembic" upgrade head)
}

start_service() {
  local name="$1"
  local dir="$2"
  shift 2

  (
    cd "$dir"
    exec "$@"
  ) > >(sed -u "s/^/[$name] /") 2> >(sed -u "s/^/[$name] /" >&2) &

  PIDS+=("$!")
}

stop_services() {
  if [[ "${#PIDS[@]}" -eq 0 ]]; then
    return 0
  fi

  log "stopping local services"
  for pid in "${PIDS[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  wait "${PIDS[@]}" >/dev/null 2>&1 || true
}

run_source_dev() {
  ensure_local_env_files
  setup_dependencies
  start_infra
  run_migrations

  trap stop_services EXIT INT TERM

  log "starting source dev services"
  start_service "web" "$WEB_DIR" bun run dev
  start_service "model" "$BACKEND_DIR" "$ROOT_DIR/.venv/bin/uvicorn" model_server.main:app --reload --port 9000
  start_service "jobs" "$BACKEND_DIR" "$ROOT_DIR/.venv/bin/python" ./scripts/dev_run_background_jobs.py
  start_service "api" "$BACKEND_DIR" env AUTH_TYPE="$AUTH_TYPE" "$ROOT_DIR/.venv/bin/uvicorn" onyx.main:app --reload --port 8080

  log "Onyx source dev is starting at http://localhost:3000"
  set +e
  wait -n "${PIDS[@]}"
  local status="$?"
  set -e
  exit "$status"
}

run_infra_only() {
  ensure_local_env_files
  start_infra
  log "infra is running"
}

run_docker_stack() {
  require_cmd docker
  ensure_local_env_files
  ensure_docker_env_file
  log "starting full Docker Compose stack"
  (cd "$COMPOSE_DIR" && docker compose up -d --wait)
  log "Onyx Docker stack is running at http://localhost:3000"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --docker)
      MODE="docker"
      ;;
    --infra-only)
      MODE="infra"
      ;;
    --setup)
      SETUP="always"
      INSTALL_PLAYWRIGHT="always"
      ;;
    --no-setup)
      SETUP="never"
      INSTALL_PLAYWRIGHT="never"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die "unknown argument: $1"
      ;;
  esac
  shift
done

case "$MODE" in
  dev)
    run_source_dev
    ;;
  infra)
    run_infra_only
    ;;
  docker)
    run_docker_stack
    ;;
esac
