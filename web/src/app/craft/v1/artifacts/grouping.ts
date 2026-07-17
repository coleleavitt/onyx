import type { ArtifactLibraryItem } from "@/app/craft/v1/artifacts/types";

export interface ArtifactLibraryGroup {
  key: string;
  title: string;
  items: ArtifactLibraryItem[];
}

const MONTH_FORMATTER = new Intl.DateTimeFormat(undefined, {
  month: "long",
  year: "numeric",
});

function monthKey(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}`;
}

/**
 * Groups artifacts into a leading "Pinned" section followed by month sections
 * (e.g. "July 2026", "June 2026"), each sorted newest-first — mirroring the
 * month-based timeline used on comparable artifact libraries.
 */
export function groupArtifactLibraryItems(
  items: ArtifactLibraryItem[]
): ArtifactLibraryGroup[] {
  const sorted = [...items].sort(
    (left, right) =>
      new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
  );

  const groups: ArtifactLibraryGroup[] = [];

  const pinned = sorted.filter((item) => item.is_pinned);
  if (pinned.length > 0) {
    groups.push({ key: "pinned", title: "Pinned", items: pinned });
  }

  const byMonth = new Map<string, ArtifactLibraryGroup>();
  for (const item of sorted) {
    if (item.is_pinned) continue;
    const date = new Date(item.updated_at);
    const key = monthKey(date);
    const existing = byMonth.get(key);
    if (existing) {
      existing.items.push(item);
    } else {
      byMonth.set(key, {
        key,
        title: MONTH_FORMATTER.format(date),
        items: [item],
      });
    }
  }

  // Map iteration order follows insertion, which is already newest-first
  // because `sorted` is descending by updated_at.
  groups.push(...Array.from(byMonth.values()));

  return groups;
}
