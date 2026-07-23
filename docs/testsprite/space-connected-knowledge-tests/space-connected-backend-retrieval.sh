#!/usr/bin/env bash
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx
source .venv/bin/activate
python -m dotenv -f .vscode/.env run -- pytest -q \
  backend/tests/external_dependency_unit/projects/test_project_connected_knowledge.py \
  backend/tests/unit/onyx/document_index/test_project_connected_knowledge_filters.py
