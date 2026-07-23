#!/usr/bin/env bash
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx
set -a
. ./.testsprite.env
set +a
cd web
bunx playwright test tests/e2e/spaces/spaces_right_rail_controls.spec.ts --project admin
