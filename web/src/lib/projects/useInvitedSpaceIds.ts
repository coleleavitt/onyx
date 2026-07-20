"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { fetchProjectAccessState } from "@/lib/projects/svc";
import type { Project } from "@/lib/projects/types";

/**
 * Derive the set of space (project) ids the current user is "invited to /
 * pending" on, using the real per-project access-state endpoint.
 *
 * A space counts as invited/pending when it carries a join request that is
 * still `PENDING` (either the user's own request awaiting approval, or a share
 * the user has yet to act on). Only NON-OWNER spaces are probed, so the number
 * of requests stays bounded to the small set of shared spaces.
 *
 * Returns a stable `Set<number>` suitable for `groupSpaces({ invitedProjectIds })`.
 */
export function useInvitedSpaceIds(projects: Project[]): ReadonlySet<number> {
  const [invitedIds, setInvitedIds] = useState<ReadonlySet<number>>(
    () => new Set<number>()
  );

  // Only non-owner spaces can be "invited/pending"; owners are never pending.
  const candidateIds = useMemo(
    () =>
      projects
        .filter((project) => project.user_permission !== "OWNER")
        .map((project) => project.id),
    [projects]
  );

  // Stable dependency key so the effect only re-runs when the candidate set
  // actually changes (not on every render / array identity change).
  const candidateKey = useMemo(
    () => [...candidateIds].sort((a, b) => a - b).join(","),
    [candidateIds]
  );

  const latestRequest = useRef(0);

  useEffect(() => {
    if (candidateIds.length === 0) {
      setInvitedIds(new Set<number>());
      return;
    }
    const requestId = ++latestRequest.current;
    let cancelled = false;

    void Promise.all(
      candidateIds.map(async (id) => {
        try {
          const state = await fetchProjectAccessState(id);
          return state.access_request?.status === "PENDING" ? id : null;
        } catch {
          return null;
        }
      })
    ).then((results) => {
      // Ignore stale responses (a newer candidate set superseded this one).
      if (cancelled || requestId !== latestRequest.current) return;
      setInvitedIds(
        new Set(results.filter((id): id is number => id !== null))
      );
    });

    return () => {
      cancelled = true;
    };
    // candidateKey captures the meaningful change; candidateIds is derived from it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidateKey]);

  return invitedIds;
}
