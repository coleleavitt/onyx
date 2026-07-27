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
CLEAN_ORPHANS=1
PIDS=()
NAMES=()
STOPPING=0
CLAIMED_PORTS=()
RESOLVED_PORT=""
RESOLVED_PORT_MOVED=0
COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-onyx}"

usage() {
  cat <<'USAGE'
Usage:
  ./run.sh                 Start source dev mode: infra + web + model server + jobs + API.
  ./run.sh --infra-only    Start only Postgres/OpenSearch/Redis/MinIO.
  ./run.sh --docker        Start the full Docker Compose stack from prebuilt images.
  ./run.sh --check         Verify local commands/env needed by source dev mode.
  ./run.sh --clean-only    Stop orphaned source-dev workers from this checkout.
  ./run.sh --setup         Force uv sync, Playwright install, and bun install before starting.
  ./run.sh --no-setup      Skip dependency installation; fail if the installed web runtime is stale.
  ./run.sh --no-clean-orphans
                           Do not stop pre-existing source-dev workers before starting.

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

  export VIRTUAL_ENV="$ROOT_DIR/.venv"
  export PATH="$VIRTUAL_ENV/bin:$PATH"
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
    (cd "$WEB_DIR" && bun install --frozen-lockfile)
  fi
}

verify_web_runtime() {
  require_cmd bun

  local expected_next_version
  local installed_next_version
  expected_next_version="$({
    cd "$WEB_DIR"
    bun -e 'process.stdout.write(require("./package.json").dependencies.next)'
  })"
  installed_next_version="$({
    cd "$WEB_DIR"
    bun -e 'process.stdout.write(require("./node_modules/next/package.json").version)'
  } 2>/dev/null || true)"

  if [[ "$installed_next_version" == "$expected_next_version" ]]; then
    return 0
  fi

  if [[ "$SETUP" == "never" ]]; then
    die "web dependencies are stale (Next.js ${installed_next_version:-missing}; expected $expected_next_version). Run ./run.sh --setup."
  fi

  log "web dependencies changed (Next.js ${installed_next_version:-missing} -> $expected_next_version); installing"
  (cd "$WEB_DIR" && bun install --frozen-lockfile)

  installed_next_version="$({
    cd "$WEB_DIR"
    bun -e 'process.stdout.write(require("./node_modules/next/package.json").version)'
  })"
  [[ "$installed_next_version" == "$expected_next_version" ]] ||
    die "installed Next.js $installed_next_version does not match expected $expected_next_version"
}

check_source_dev() {
  ensure_local_env_files
  require_cmd uv
  require_cmd bun
  require_cmd docker
  require_cmd setsid
  require_cmd python
  require_cmd alembic
  require_cmd uvicorn
  require_cmd celery

  log "source dev command check passed"
}

port_in_use() {
  local port="$1"
  local claimed

  for claimed in "${CLAIMED_PORTS[@]:-}"; do
    [[ "$claimed" == "$port" ]] && return 0
  done

  if command -v ss >/dev/null 2>&1; then
    [[ -n "$(ss -ltnH "sport = :${port}" 2>/dev/null)" ]]
    return
  fi

  if (exec 3<>"/dev/tcp/127.0.0.1/${port}") 2>/dev/null; then
    exec 3<&-
    return 0
  fi

  return 1
}

port_holder() {
  local port="$1"
  local holder=""

  if command -v docker >/dev/null 2>&1; then
    holder="$(docker ps --filter "publish=${port}" --format '{{.Names}}' 2>/dev/null | paste -sd, - || true)"
  fi

  if [[ -z "$holder" ]] && command -v ss >/dev/null 2>&1; then
    holder="$(ss -ltnpH "sport = :${port}" 2>/dev/null | sed -n 's/.*users:(("\([^"]*\)".*/\1/p' | head -n 1 || true)"
  fi

  printf '%s' "$holder"
}

port_owned_by_service() {
  local port="$1"
  local service="$2"

  [[ -n "$service" ]] || return 1
  command -v docker >/dev/null 2>&1 || return 1
  docker ps --filter "publish=${port}" --format '{{.Names}}' 2>/dev/null |
    grep -qE "^${COMPOSE_PROJECT}-${service}-[0-9]+$"
}

next_free_port() {
  local port="$1"
  local limit=$(( port + 50 ))

  while (( port <= limit )); do
    if ! port_in_use "$port"; then
      printf '%s' "$port"
      return 0
    fi
    port=$(( port + 1 ))
  done

  return 1
}

# Resolve one host port, stepping off the default when a foreign process owns it.
# Result lands in RESOLVED_PORT; RESOLVED_PORT_MOVED records whether it changed.
resolve_host_port() {
  local var="$1"
  local default="$2"
  local service="$3"
  local label="$4"
  local port="${!var:-$default}"
  local holder replacement

  RESOLVED_PORT_MOVED=0

  if port_in_use "$port" && ! port_owned_by_service "$port" "$service"; then
    holder="$(port_holder "$port")"
    replacement="$(next_free_port "$(( port + 1 ))")" ||
      die "${label} host port ${port} is in use${holder:+ by ${holder}} and no free port was found nearby; free it or set ${var}"
    log "${label} host port ${port} is in use${holder:+ by ${holder}}; using ${replacement} instead (pin with ${var})"
    port="$replacement"
    RESOLVED_PORT_MOVED=1
  fi

  CLAIMED_PORTS+=("$port")
  RESOLVED_PORT="$port"
}

require_free_host_port() {
  local port="$1"
  local label="$2"
  local holder

  port_in_use "$port" || return 0
  holder="$(port_holder "$port")"
  die "${label} port ${port} is already in use${holder:+ by ${holder}}; this port is fixed (web proxy and auth callbacks assume it), so stop that process and retry"
}

persist_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  local current

  [[ -f "$file" ]] || return 0
  current="$(grep -E "^${key}=" "$file" 2>/dev/null | tail -n 1 | cut -d= -f2- || true)"
  current="$(strip_quotes "$(trim "$current")")"
  [[ "$current" == "$value" ]] && return 0
  set_env_value "$file" "$key" "$value"
  log "pinned ${key}=${value} in ${file#"$ROOT_DIR/"}"
}

# Keep the ports compose publishes and the ports the source-dev processes dial in
# sync. Unrelated local stacks routinely squat on 5432/6379/9000, and a silent
# remap would otherwise leave pytest and the VSCode debugger pointed at them.
resolve_service_ports() {
  local minio_api minio_default

  minio_default="${MINIO_API_HOST_PORT:-}"
  if [[ -z "$minio_default" && "${S3_ENDPOINT_URL:-}" =~ :([0-9]+)/?$ ]]; then
    minio_default="${BASH_REMATCH[1]}"
  fi

  resolve_host_port POSTGRES_HOST_PORT "${POSTGRES_PORT:-5432}" relational_db "Postgres"
  export POSTGRES_HOST_PORT="$RESOLVED_PORT" POSTGRES_PORT="$RESOLVED_PORT"
  if (( RESOLVED_PORT_MOVED )); then
    persist_env_value "$VSCODE_ENV" POSTGRES_PORT "$RESOLVED_PORT"
    persist_env_value "$DOCKER_ENV" POSTGRES_HOST_PORT "$RESOLVED_PORT"
  fi

  resolve_host_port REDIS_HOST_PORT "${REDIS_PORT:-6379}" cache "Redis"
  export REDIS_HOST_PORT="$RESOLVED_PORT" REDIS_PORT="$RESOLVED_PORT"
  if (( RESOLVED_PORT_MOVED )); then
    persist_env_value "$VSCODE_ENV" REDIS_PORT "$RESOLVED_PORT"
    persist_env_value "$DOCKER_ENV" REDIS_HOST_PORT "$RESOLVED_PORT"
  fi

  resolve_host_port OPENSEARCH_HOST_PORT "${OPENSEARCH_REST_API_PORT:-9200}" opensearch "OpenSearch"
  export OPENSEARCH_HOST_PORT="$RESOLVED_PORT" OPENSEARCH_REST_API_PORT="$RESOLVED_PORT"
  if (( RESOLVED_PORT_MOVED )); then
    persist_env_value "$VSCODE_ENV" OPENSEARCH_REST_API_PORT "$RESOLVED_PORT"
    persist_env_value "$DOCKER_ENV" OPENSEARCH_HOST_PORT "$RESOLVED_PORT"
  fi

  resolve_host_port MINIO_API_HOST_PORT "${minio_default:-9004}" minio "MinIO"
  minio_api="$RESOLVED_PORT"
  export MINIO_API_HOST_PORT="$minio_api" S3_ENDPOINT_URL="http://localhost:${minio_api}"
  if (( RESOLVED_PORT_MOVED )); then
    persist_env_value "$VSCODE_ENV" S3_ENDPOINT_URL "$S3_ENDPOINT_URL"
    persist_env_value "$DOCKER_ENV" MINIO_API_HOST_PORT "$minio_api"
  fi

  resolve_host_port MINIO_CONSOLE_HOST_PORT "${MINIO_CONSOLE_HOST_PORT:-9005}" minio "MinIO console"
  export MINIO_CONSOLE_HOST_PORT="$RESOLVED_PORT"
  if (( RESOLVED_PORT_MOVED )); then
    persist_env_value "$DOCKER_ENV" MINIO_CONSOLE_HOST_PORT "$RESOLVED_PORT"
  fi

  resolve_host_port MODEL_SERVER_HOST_PORT "${MODEL_SERVER_PORT:-9000}" "" "Model server"
  export MODEL_SERVER_HOST_PORT="$RESOLVED_PORT" MODEL_SERVER_PORT="$RESOLVED_PORT"
  if (( RESOLVED_PORT_MOVED )); then
    persist_env_value "$VSCODE_ENV" MODEL_SERVER_PORT "$RESOLVED_PORT"
    persist_env_value "$DOCKER_ENV" MODEL_SERVER_HOST_PORT "$RESOLVED_PORT"
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

check_disk_headroom() {
  command -v df >/dev/null 2>&1 || return 0
  local use
  use="$(df --output=pcent / 2>/dev/null | tail -n 1 | tr -dc '0-9' || true)"
  [[ -n "$use" ]] || return 0
  if (( use >= 95 )); then
    log "warning: disk at ${use}% — at/above OpenSearch flood-stage watermark (95%); indices can re-lock read-only. Free space (e.g. 'docker system prune -f')."
  elif (( use >= 90 )); then
    log "notice: disk at ${use}% — above OpenSearch high watermark (90%); approaching flood-stage (95%)."
  fi
}

clear_opensearch_readonly_block() {
  local base="$1"
  # Only data indices: exclude dot-indices (.opendistro_security, .plugins-ml-config)
  # and security-auditlog-*, which admin cannot modify — including them 403s the whole
  # wildcard request so nothing clears.
  local pattern='*,-.*,-security-auditlog-*'
  local blocked
  blocked="$(curl -sk -u "admin:${OPENSEARCH_ADMIN_PASSWORD}" \
    "${base}/${pattern}/_settings/index.blocks.read_only_allow_delete?flat_settings=true" 2>/dev/null || true)"
  [[ "$blocked" == *'"index.blocks.read_only_allow_delete":"true"'* ]] || return 0

  log "clearing stale read-only-allow-delete block on OpenSearch data indices (disk-watermark residue)"
  if ! curl -sk -u "admin:${OPENSEARCH_ADMIN_PASSWORD}" -X PUT \
    "${base}/${pattern}/_settings" \
    -H 'Content-Type: application/json' \
    -d '{"index.blocks.read_only_allow_delete": null}' >/dev/null 2>&1; then
    log "warning: failed to clear read-only block; check disk space (df -h /)."
  fi
}

wait_for_opensearch() {
  # OpenSearch has no compose healthcheck, so 'compose up --wait' returns before it is
  # actually serving. Gate startup on a real readiness probe here, and clear any stale
  # flood-stage read-only block left behind by prior disk pressure (it does not auto-clear).
  if ! command -v curl >/dev/null 2>&1; then
    log "curl not found; skipping OpenSearch readiness probe"
    return 0
  fi

  check_disk_headroom

  local host="${OPENSEARCH_HOST:-localhost}"
  local port="${OPENSEARCH_REST_API_PORT:-9200}"
  local deadline=$(( SECONDS + 120 ))
  local base="" scheme code=""

  log "waiting for OpenSearch to be ready at ${host}:${port}"
  while (( SECONDS < deadline )); do
    for scheme in https http; do
      code="$(curl -sk -u "admin:${OPENSEARCH_ADMIN_PASSWORD}" -o /dev/null \
        -w '%{http_code}' --max-time 4 "${scheme}://${host}:${port}/_cluster/health" 2>/dev/null || true)"
      if [[ "$code" == "200" ]]; then
        base="${scheme}://${host}:${port}"
        break 2
      fi
    done
    sleep 2
  done

  if [[ -z "$base" ]]; then
    log "warning: OpenSearch not confirmed healthy within 120s (last HTTP ${code:-none}); continuing anyway"
    return 0
  fi

  log "OpenSearch is ready (${base})"
  clear_opensearch_readonly_block "$base"
}

matching_dev_process_groups() {
  ps -eo pid=,pgid=,cmd= | awk -v root="$ROOT_DIR" '
    {
      pid = $1
      pgid = $2
      $1 = ""
      $2 = ""
      cmd = $0
      is_match = 0

      if (cmd ~ /^[[:space:]]*(\/usr\/bin\/|\/bin\/)?bash -c / || cmd ~ /^[[:space:]]*rg / || cmd ~ /^[[:space:]]*awk /) {
        next
      }

      if (index(cmd, root "/.venv/bin/celery -A onyx.background")) {
        is_match = 1
      }
      if (index(cmd, root "/.venv/bin/python") && index(cmd, root "/.venv/bin/celery -A onyx.background")) {
        is_match = 1
      }
      if (index(cmd, root "/.venv/bin/uvicorn onyx.main:app") || index(cmd, root "/.venv/bin/uvicorn model_server.main:app")) {
        is_match = 1
      }
      if (index(cmd, root "/.venv/bin/python") && index(cmd, root "/.venv/bin/uvicorn") && (index(cmd, "onyx.main:app") || index(cmd, "model_server.main:app"))) {
        is_match = 1
      }
      if (index(cmd, root "/backend/./scripts/dev_run_background_jobs.py") || index(cmd, root "/backend/scripts/dev_run_background_jobs.py")) {
        is_match = 1
      }
      if (cmd ~ /^[[:space:]]*bun run dev([[:space:]]|$)/) {
        is_match = 1
      }
      if (index(cmd, root "/web/node_modules/.bin/next dev")) {
        is_match = 1
      }

      if (is_match) {
        print pgid
      }
    }
  ' | sort -n -u
}

cleanup_orphan_dev_processes() {
  [[ "$CLEAN_ORPHANS" -eq 1 ]] || return 0

  local current_pgid
  current_pgid="$(ps -o pgid= -p "$$" | tr -d ' ')"

  local pgids=()
  while IFS= read -r pgid; do
    [[ -n "$pgid" ]] || continue
    [[ "$pgid" == "$current_pgid" ]] && continue
    pgids+=("$pgid")
  done < <(matching_dev_process_groups)

  [[ "${#pgids[@]}" -gt 0 ]] || return 0

  log "stopping orphaned source-dev process groups: ${pgids[*]}"
  for pgid in "${pgids[@]}"; do
    kill -TERM -- "-$pgid" >/dev/null 2>&1 || true
  done

  sleep 2

  for pgid in "${pgids[@]}"; do
    kill -KILL -- "-$pgid" >/dev/null 2>&1 || true
  done
}

start_service() {
  local name="$1"
  local dir="$2"
  shift 2

  # shellcheck disable=SC2016
  setsid bash -c '
    cd "$1" || exit
    shift
    exec "$@"
  ' _ "$dir" "$@" > >(sed -u "s/^/[$name] /") 2> >(sed -u "s/^/[$name] /" >&2) &

  PIDS+=("$!")
  NAMES+=("$name")
}

stop_services() {
  if [[ "$STOPPING" -eq 1 ]]; then
    return 0
  fi
  STOPPING=1

  if [[ "${#PIDS[@]}" -eq 0 ]]; then
    return 0
  fi

  log "stopping local services"
  for pid in "${PIDS[@]}"; do
    kill -TERM -- "-$pid" >/dev/null 2>&1 || kill "$pid" >/dev/null 2>&1 || true
  done

  sleep 2

  for pid in "${PIDS[@]}"; do
    kill -KILL -- "-$pid" >/dev/null 2>&1 || true
  done

  wait "${PIDS[@]}" >/dev/null 2>&1 || true
  cleanup_orphan_dev_processes
}

run_source_dev() {
  ensure_local_env_files
  cleanup_orphan_dev_processes
  resolve_service_ports
  require_free_host_port 3000 "Web"
  require_free_host_port 8080 "API"
  setup_dependencies
  verify_web_runtime
  start_infra
  wait_for_opensearch
  run_migrations

  trap stop_services EXIT
  trap 'stop_services; exit 130' INT TERM

  log "starting source dev services"
  start_service "web" "$WEB_DIR" bun run dev
  start_service "model" "$BACKEND_DIR" "$ROOT_DIR/.venv/bin/uvicorn" model_server.main:app --reload --port "$MODEL_SERVER_PORT"
  start_service "jobs" "$BACKEND_DIR" "$ROOT_DIR/.venv/bin/python" ./scripts/dev_run_background_jobs.py
  start_service "api" "$BACKEND_DIR" env AUTH_TYPE="$AUTH_TYPE" "$ROOT_DIR/.venv/bin/uvicorn" onyx.main:app --reload --port 8080

  log "Onyx source dev is starting at http://localhost:3000"
  set +e
  wait -n "${PIDS[@]}"
  local status="$?"
  set -e

  local i dead="unknown"
  for i in "${!PIDS[@]}"; do
    if ! kill -0 "${PIDS[$i]}" 2>/dev/null; then
      dead="${NAMES[$i]:-unknown}"
      break
    fi
  done
  log "service '${dead}' exited (status ${status}); stopping the rest"
  exit "$status"
}

run_infra_only() {
  ensure_local_env_files
  resolve_service_ports
  start_infra
  wait_for_opensearch
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

run_clean_only() {
  cleanup_orphan_dev_processes
  log "orphan cleanup complete"
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --docker)
      MODE="docker"
      ;;
    --check)
      MODE="check"
      ;;
    --clean-only)
      MODE="clean"
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
    --no-clean-orphans)
      CLEAN_ORPHANS=0
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
  check)
    check_source_dev
    ;;
  clean)
    run_clean_only
    ;;
esac
