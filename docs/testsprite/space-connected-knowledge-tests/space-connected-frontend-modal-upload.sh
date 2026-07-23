#!/usr/bin/env bash
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx/web
bunx jest \
  src/sections/projects/SpaceConnectedKnowledgeModal.test.tsx \
  src/providers/__tests__/ProjectsContext.test.tsx \
  --runInBand
