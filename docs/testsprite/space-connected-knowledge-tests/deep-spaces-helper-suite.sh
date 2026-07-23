#!/usr/bin/env bash
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx/web
npx jest --runTestsByPath \
  src/lib/projects/spaceMetadata.test.ts \
  src/lib/projects/spaceGrouping.test.ts \
  src/lib/projects/spaceScheduledTasks.test.ts \
  src/lib/projects/spaceAccent.test.ts \
  src/lib/projects/slug.test.ts \
  src/sections/modals/shareAccessConstants.test.ts
