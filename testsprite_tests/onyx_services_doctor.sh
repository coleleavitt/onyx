#!/usr/bin/env bash
# Onyx dev services doctor.
#
# There is no supervisor on the local dev processes, so a manual restart of one
# service can silently orphan the others (2026-07-16: the model server was left
# dead and chat search showed "No results found"). This script checks every
# service and, with `heal`, restarts the tmux-managed ones that are down.
#
# Usage:
#   onyx_services_doctor.sh          # check only; exit 1 if anything is down
#   onyx_services_doctor.sh heal     # restart dead tmux-managed services
set -uo pipefail

ROOT=/home/cole/WebstormProjects/forks/onyx
MODE="${1:-check}"
FAILED=0

http_ok() { # url — one retry so a single slow response doesn't trigger a restart
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1" 2>/dev/null)" = "200" ] && return 0
  sleep 3
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$1" 2>/dev/null)" = "200" ]
}

report() { # name status hint
  if [ "$2" = "OK" ]; then
    echo "OK   $1"
  else
    echo "DOWN $1 — $3"
    FAILED=1
  fi
}

heal_tmux() { # session command
  tmux kill-session -t "$1" 2>/dev/null
  tmux new-session -d -s "$1" "$2"
}

check_docker() { # name container
  if docker ps --format '{{.Names}}' | grep -q "^$2$"; then
    report "$1" OK ""
  else
    report "$1" DOWN "docker start $2"
  fi
}

# --- Docker infrastructure (not auto-healed; use docker start) ---
check_docker "postgres (docker)" "onyx-relational_db-1"
check_docker "redis (docker)" "onyx-cache-1"
check_docker "opensearch (docker)" "onyx-opensearch-1"
check_docker "minio (docker)" "onyx-minio-1"

# --- Model server :9000 (embedding — REQUIRED for chat internal search) ---
if http_ok "http://127.0.0.1:9000/api/health"; then
  report "model server :9000" OK ""
else
  if [ "$MODE" = "heal" ]; then
    heal_tmux onyx-model-live \
      "cd $ROOT/backend && $ROOT/.venv/bin/uvicorn model_server.main:app --port 9000 >> $ROOT/backend/log/model_server_debug.log 2>&1"
    for _ in $(seq 1 60); do
      http_ok "http://127.0.0.1:9000/api/health" && break
      sleep 1
    done
    if http_ok "http://127.0.0.1:9000/api/health"; then
      report "model server :9000 (healed)" OK ""
    else
      report "model server :9000" DOWN "heal failed; check backend/log/model_server_debug.log"
    fi
  else
    report "model server :9000" DOWN "run: $0 heal (chat search silently returns no results without it)"
  fi
fi

# --- API server :8080 ---
if http_ok "http://127.0.0.1:8080/health"; then
  report "api server :8080" OK ""
else
  if [ "$MODE" = "heal" ]; then
    heal_tmux onyx-api-live \
      "cd $ROOT/backend && $ROOT/testsprite_tests/start_onyx_api_live.sh >> $ROOT/backend/log/api_server_debug.log 2>&1"
    for _ in $(seq 1 90); do
      http_ok "http://127.0.0.1:8080/health" && break
      sleep 1
    done
    if http_ok "http://127.0.0.1:8080/health"; then
      report "api server :8080 (healed)" OK ""
    else
      report "api server :8080" DOWN "heal failed; check backend/log/api_server_debug.log"
    fi
  else
    report "api server :8080" DOWN "run: $0 heal"
  fi
fi

# --- Background jobs (celery workers + beat — user file processing, indexing, sync) ---
CELERY_COUNT=$(ps -eo cmd | grep 'celery -A onyx.background' | grep -v grep | wc -l)
if [ "$CELERY_COUNT" -ge 8 ]; then
  report "celery workers ($CELERY_COUNT procs)" OK ""
else
  if [ "$MODE" = "heal" ]; then
    heal_tmux onyx-jobs-live \
      "$ROOT/testsprite_tests/start_onyx_jobs_live.sh >> $ROOT/backend/log/background_jobs_runner.log 2>&1"
    for _ in $(seq 1 45); do
      CELERY_COUNT=$(ps -eo cmd | grep 'celery -A onyx.background' | grep -v grep | wc -l)
      [ "$CELERY_COUNT" -ge 8 ] && break
      sleep 2
    done
    if [ "$CELERY_COUNT" -ge 8 ]; then
      report "celery workers (healed, $CELERY_COUNT procs)" OK ""
    else
      report "celery workers" DOWN "heal failed; check backend/log/background_jobs_runner.log"
    fi
  else
    report "celery workers ($CELERY_COUNT/8+ procs)" DOWN "run: $0 heal (uploaded files never finish processing without them)"
  fi
fi

# --- Web server :3000 (Next dev; proxy health needs the API up, so heal it last) ---
if http_ok "http://localhost:3000/api/health"; then
  report "web + proxy :3000" OK ""
else
  if [ "$MODE" = "heal" ]; then
    heal_tmux onyx-web-live \
      "export PATH=\"$HOME/.bun/bin:\$PATH\"; cd $ROOT/web && ./node_modules/.bin/next dev --webpack >> $ROOT/backend/log/web_server_debug.log 2>&1"
    for _ in $(seq 1 90); do
      http_ok "http://localhost:3000/api/health" && break
      sleep 2
    done
    if http_ok "http://localhost:3000/api/health"; then
      report "web + proxy :3000 (healed)" OK ""
    else
      report "web + proxy :3000" DOWN "heal failed; check backend/log/web_server_debug.log"
    fi
  else
    report "web + proxy :3000" DOWN "run: $0 heal"
  fi
fi

if [ "$FAILED" = "0" ]; then
  echo "all onyx dev services healthy"
else
  echo "one or more services down"
fi
exit "$FAILED"
