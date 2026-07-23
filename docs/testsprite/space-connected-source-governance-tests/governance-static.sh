#!/usr/bin/env bash
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx
source .venv/bin/activate
python docs/testsprite/validate_space_connected_source_governance_artifacts.py
