import type { Project } from "@/lib/projects/types";

/**
 * Pure grouping of the Spaces landing list, mirroring Perplexity's
 * Invited / Pinned / Your spaces / Shared sections.
 *
 * Kept free of React/SWR so it can be unit-tested directly. The "invited"
 * (pending) signal is injected as a set of project ids the caller derived from
 * the access/join-request state, since a `Project` row itself does not carry a
 * pending flag.
 */

export type SpaceGroupKey = "invited" | "pinned" | "owned" | "shared";

export interface SpaceGroup {
  key: SpaceGroupKey;
  title: string;
  items: Project[];
}

const GROUP_TITLES: Record<SpaceGroupKey, string> = {
  invited: "Invited",
  pinned: "Pinned",
  owned: "Your Spaces",
  shared: "Shared with you",
};

export interface GroupSpacesOptions {
  /**
   * Ids of spaces the current user has been invited to / has a pending access
   * decision on. These are surfaced first, ABOVE all other groups, and are
   * removed from the other buckets so a space appears exactly once.
   */
  invitedProjectIds?: ReadonlySet<number> | number[];
}

function toSet(
  value: ReadonlySet<number> | number[] | undefined
): ReadonlySet<number> {
  if (!value) return new Set<number>();
  return value instanceof Set ? value : new Set(value);
}

/**
 * Partition projects into ordered, non-empty groups.
 *
 * Order: Invited → Pinned → Your Spaces → Shared with you. Each project lands in
 * exactly one group (invited wins over pinned wins over owned/shared). Empty
 * groups are omitted.
 */
export function groupSpaces(
  projects: Project[],
  options: GroupSpacesOptions = {}
): SpaceGroup[] {
  const invitedIds = toSet(options.invitedProjectIds);

  const invited: Project[] = [];
  const pinned: Project[] = [];
  const owned: Project[] = [];
  const shared: Project[] = [];

  for (const project of projects) {
    if (invitedIds.has(project.id)) {
      invited.push(project);
    } else if (project.is_pinned) {
      pinned.push(project);
    } else if (project.user_permission === "OWNER") {
      owned.push(project);
    } else {
      shared.push(project);
    }
  }

  const ordered: Array<[SpaceGroupKey, Project[]]> = [
    ["invited", invited],
    ["pinned", pinned],
    ["owned", owned],
    ["shared", shared],
  ];

  return ordered
    .filter(([, items]) => items.length > 0)
    .map(([key, items]) => ({ key, title: GROUP_TITLES[key], items }));
}
