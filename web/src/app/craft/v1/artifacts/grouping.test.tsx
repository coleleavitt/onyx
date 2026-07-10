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

describe("groupArtifactLibraryItems", () => {
  it("places pinned items once and groups remaining items by recency", () => {
    const groups = groupArtifactLibraryItems(
      [
        artifact("older-pinned", "2026-06-01T12:00:00Z", true),
        artifact("today", "2026-07-10T09:00:00Z"),
        artifact("week", "2026-07-06T09:00:00Z"),
        artifact("earlier", "2026-06-20T09:00:00Z"),
      ],
      new Date("2026-07-10T15:00:00Z")
    );

    expect(groups.map((group) => group.title)).toEqual([
      "Pinned",
      "Today",
      "Previous 7 days",
      "Earlier",
    ]);
    expect(
      groups.flatMap((group) => group.items.map((item) => item.id))
    ).toEqual(["older-pinned", "today", "week", "earlier"]);
  });

  it("sorts each group by most recently updated", () => {
    const [group] = groupArtifactLibraryItems(
      [
        artifact("first", "2026-07-10T08:00:00Z"),
        artifact("second", "2026-07-10T12:00:00Z"),
      ],
      new Date("2026-07-10T15:00:00Z")
    );

    expect(group?.items.map((item) => item.id)).toEqual(["second", "first"]);
  });
});
