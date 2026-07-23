#!/usr/bin/env bash
# Live LLM browser regression for Kandice Garcia + Advisor Services Space chat.
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx
source .venv/bin/activate
python -m dotenv -f .vscode/.env run -- python docs/testsprite/space-connected-source-governance-tests/seed-kandice-advisor-services-e2e.py
cd /home/cole/WebstormProjects/forks/onyx/web
bunx playwright test tests/e2e/spaces/spaces_kandice_advisor_live_chat.spec.ts --project=admin
