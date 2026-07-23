#!/usr/bin/env bash
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx
source .venv/bin/activate
pytest -q \
  backend/tests/unit/onyx/server/features/projects/test_projects_route_order.py \
  backend/tests/unit/onyx/document_index/test_project_connected_knowledge_filters.py
python -m dotenv -f .vscode/.env run -- pytest -q \
  backend/tests/external_dependency_unit/projects/test_project_connected_knowledge.py
