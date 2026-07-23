#!/usr/bin/env bash
# Browser coverage for create-space presets and deep SharePoint folder browse.
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx
source .venv/bin/activate
python -m dotenv -f .vscode/.env run -- python docs/testsprite/space-connected-source-governance-tests/seed-openwebui-parity-e2e.py
cd /home/cole/WebstormProjects/forks/onyx/web
bunx playwright test tests/e2e/spaces/spaces_preset_and_deep_browse.spec.ts --project=admin
