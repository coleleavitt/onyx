#!/usr/bin/env bash
set -euo pipefail

cd /home/cole/WebstormProjects/forks/onyx/web
bunx jest \
  src/lib/projects/svc.test.ts \
  src/sections/knowledge/SourceHierarchyBrowser.test.tsx \
  src/sections/projects/SpaceConnectedKnowledgeModal.test.tsx \
  --runInBand
bunx oxlint \
  src/lib/projects/svc.ts \
  src/lib/projects/svc.test.ts \
  src/lib/projects/types.ts \
  src/lib/hierarchy/interfaces.ts \
  src/lib/hierarchy/svc.ts \
  src/lib/types.ts \
  src/sections/knowledge/SourceHierarchyBrowser.tsx \
  src/sections/knowledge/SourceHierarchyBrowser.test.tsx \
  src/sections/projects/SpaceConnectedKnowledgeModal.tsx \
  src/sections/projects/SpaceConnectedKnowledgeModal.test.tsx \
  src/sections/modals/CreateProjectModal.tsx \
  src/views/admin/GroupsPage/CreateGroupPage.tsx \
  src/views/admin/GroupsPage/EditGroupPage.tsx \
  src/views/admin/GroupsPage/SharedGroupResources/index.tsx \
  src/views/admin/GroupsPage/svc.ts
