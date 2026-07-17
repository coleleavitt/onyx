import { groupArtifactLibraryItems } from "@/app/craft/v1/artifacts/grouping";
import type { ArtifactLibraryItem } from "@/app/craft/v1/artifacts/types";

function artifact(
  id: string,
  updatedAt: string,
  isPinned = false
): ArtifactLibraryItem {
  return {
    id,
    name: `${id}.pdf`,
    type: "pdf",
    is_pinned: isPinned,
    published_at: null,
    created_at: updatedAt,
    updated_at: updatedAt,
    owner: { id: "owner", email: "owner@example.com" },
    is_owner: true,
    latest_version: {
      id: `${id}-version`,
      version_number: 1,
      name: `${id}.pdf`,
      path: `${id}.pdf`,
      mime_type: "application/pdf",
      size_bytes: 10,
      created_at: updatedAt,
    },
    versions: [],
    version_count: 1,
    user_shares: [],
    group_shares: [],
  };
}

const monthTitle = (iso: string) =>
  new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" }).format(
    new Date(iso)
  );

describe("groupArtifactLibraryItems", () => {
  it("places pinned items first, then groups remaining items by month", () => {
    const groups = groupArtifactLibraryItems([
      artifact("older-pinned", "2026-05-01T12:00:00Z", true),
      artifact("july-a", "2026-07-10T09:00:00Z"),
      artifact("july-b", "2026-07-02T09:00:00Z"),
      artifact("june", "2026-06-20T09:00:00Z"),
    ]);

    expect(groups.map((group) => group.title)).toEqual([
      "Pinned",
      monthTitle("2026-07-10T09:00:00Z"),
      monthTitle("2026-06-20T09:00:00Z"),
    ]);
    expect(
      groups.flatMap((group) => group.items.map((item) => item.id))
    ).toEqual(["older-pinned", "july-a", "july-b", "june"]);
  });

  it("sorts each month group by most recently updated", () => {
    const [group] = groupArtifactLibraryItems([
      artifact("first", "2026-07-02T08:00:00Z"),
      artifact("second", "2026-07-10T12:00:00Z"),
    ]);

    expect(group?.items.map((item) => item.id)).toEqual(["second", "first"]);
  });
});
