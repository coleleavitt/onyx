import type { ArtifactLibraryItem } from "@/app/craft/v1/artifacts/types";

export interface ArtifactLibraryGroup {
  key: "pinned" | "today" | "previous-week" | "earlier";
  title: string;
  items: ArtifactLibraryItem[];
}

function startOfDay(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

export function groupArtifactLibraryItems(
  items: ArtifactLibraryItem[],
  now = new Date()
): ArtifactLibraryGroup[] {
  const today = startOfDay(now).getTime();
  const previousWeek = today - 6 * 24 * 60 * 60 * 1000;
  const sorted = [...items].sort(
    (left, right) =>
      new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
  );

  const groups: ArtifactLibraryGroup[] = [
    {
      key: "pinned",
      title: "Pinned",
      items: sorted.filter((item) => item.is_pinned),
    },
    {
      key: "today",
      title: "Today",
      items: sorted.filter((item) => {
        const updated = startOfDay(new Date(item.updated_at)).getTime();
        return !item.is_pinned && updated === today;
      }),
    },
    {
      key: "previous-week",
      title: "Previous 7 days",
      items: sorted.filter((item) => {
        const updated = startOfDay(new Date(item.updated_at)).getTime();
        return !item.is_pinned && updated < today && updated >= previousWeek;
      }),
    },
    {
      key: "earlier",
      title: "Earlier",
      items: sorted.filter((item) => {
        const updated = startOfDay(new Date(item.updated_at)).getTime();
        return !item.is_pinned && updated < previousWeek;
      }),
    },
  ];

  return groups.filter((group) => group.items.length > 0);
}
