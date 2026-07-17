"use client";

import { Text } from "@opal/components";
import { Content } from "@opal/layouts";
import { SvgBookOpen } from "@opal/icons";

// Placeholder Memory panel rendered inside the Space (project) view's
// Sessions/Memory tabs. Space-scoped memory is not yet persisted on the
// backend; this is intentionally a shell (see ProjectContextPanel follow-ups).
export default function ProjectMemoryPanel() {
  return (
    <div className="mx-auto flex w-full max-w-(--app-page-main-content-width) flex-col gap-2 px-3 pt-6">
      <Content
        sizePreset="main-ui"
        variant="section"
        icon={SvgBookOpen}
        title="Memory"
        description="Notes and memories the agent can reference in this space."
      />
      <div className="flex h-12 items-center rounded-xl border border-dashed border-border-01 pl-2 text-text-02">
        <Text as="p" font="secondary-body" color="inherit">
          Space-scoped memory is coming soon.
        </Text>
      </div>
    </div>
  );
}
