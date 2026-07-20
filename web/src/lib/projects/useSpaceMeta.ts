"use client";

import { useCallback, useMemo } from "react";
import { useProjectsContext } from "@/providers/ProjectsContext";
import {
  parseSpaceInstructions,
  serializeSpaceInstructions,
  type SpaceMeta,
} from "@/lib/projects/spaceMetadata";

/**
 * Read + persist the current space's "extra metadata" (links, per-space skill
 * ids) which is carried inside the project `instructions` free-text channel
 * (see `spaceMetadata.ts` for why). Writing goes through the existing
 * `upsertInstructions` service, so it round-trips and survives reload without a
 * backend schema change.
 */
export function useSpaceMeta() {
  const { currentProjectDetails, upsertInstructions } = useProjectsContext();

  const raw = currentProjectDetails?.project?.instructions ?? "";
  const parsed = useMemo(() => parseSpaceInstructions(raw), [raw]);

  const saveMeta = useCallback(
    async (nextMeta: SpaceMeta) => {
      // Re-attach the block to whatever the human-facing instructions currently
      // are, so we never clobber the user's prose.
      await upsertInstructions(
        serializeSpaceInstructions(parsed.instructions, nextMeta)
      );
    },
    [parsed.instructions, upsertInstructions]
  );

  return {
    /** Human-facing instructions with the metadata block stripped. */
    instructions: parsed.instructions,
    /** Parsed links + skillIds. */
    meta: parsed.meta,
    /** Persist a new metadata object (keeps human instructions intact). */
    saveMeta,
  };
}
