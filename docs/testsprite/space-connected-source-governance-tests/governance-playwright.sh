#!/usr/bin/env bash
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx
source .venv/bin/activate
python -m dotenv -f .vscode/.env run -- python docs/testsprite/space-connected-source-governance-tests/seed-governance-e2e.py
cd /home/cole/WebstormProjects/forks/onyx/web
bunx playwright test tests/e2e/spaces/spaces_connected_source_governance.spec.ts --project=admin
