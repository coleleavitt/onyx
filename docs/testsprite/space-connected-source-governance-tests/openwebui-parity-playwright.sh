#!/usr/bin/env bash
# OpenWebUI-parity adversarial browser E2E.
#
# Seeds governance over the real indexed Magellan HR SharePoint tree (the
# folders production Open WebUI spaces whitelisted on chat-aws) plus a
# RESTRICTED compliance scope, then drives a 4-user Playwright scenario:
# space recreation, sharing (viewer/editor), and adversarial probes against
# every governance and ACL boundary.
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx
source .venv/bin/activate
python -m dotenv -f .vscode/.env run -- python docs/testsprite/space-connected-source-governance-tests/seed-openwebui-parity-e2e.py
cd /home/cole/WebstormProjects/forks/onyx/web
bunx playwright test tests/e2e/spaces/spaces_openwebui_parity_adversarial.spec.ts --project=admin
