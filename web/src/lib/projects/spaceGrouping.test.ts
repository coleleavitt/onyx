import { groupSpaces } from "@/lib/projects/spaceGrouping";
import type { Project } from "@/lib/projects/types";

/** Minimal Project factory for grouping tests (only the fields the grouping reads). */
function project(overrides: Partial<Project> & { id: number }): Project {
  return {
    id: overrides.id,
    name: overrides.name ?? `Space ${overrides.id}`,
    description: null,
    emoji: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: null,
    user_id: null,
    owner: null,
    user_permission: overrides.user_permission ?? "OWNER",
    organization_permission: null,
    is_personal: true,
    is_pinned: overrides.is_pinned ?? false,
    instructions: null,
    chat_sessions: [],
  };
}

describe("groupSpaces", () => {
  it("returns Pinned / Your Spaces / Shared with you in order, omitting empties", () => {
    const groups = groupSpaces([
      project({ id: 1, is_pinned: true }),
      project({ id: 2, user_permission: "OWNER" }),
      project({ id: 3, user_permission: "VIEWER" }),
    ]);
    expect(groups.map((g) => g.key)).toEqual(["pinned", "owned", "shared"]);
    expect(groups.map((g) => g.title)).toEqual([
      "Pinned",
      "Your Spaces",
      "Shared with you",
    ]);
  });

  it("surfaces an Invited group FIRST when invitedProjectIds is provided", () => {
    const groups = groupSpaces(
      [
        project({ id: 1, is_pinned: true }),
        project({ id: 2, user_permission: "OWNER" }),
        project({ id: 7, user_permission: "VIEWER" }),
      ],
      { invitedProjectIds: new Set([7]) }
    );
    const first = groups[0];
    expect(first).toBeDefined();
    expect(first?.key).toBe("invited");
    expect(first?.title).toBe("Invited");
    expect(first?.items.map((p) => p.id)).toEqual([7]);
    // Space 7 must NOT also appear under "shared".
    const shared = groups.find((g) => g.key === "shared");
    expect(shared).toBeUndefined();
  });

  it("invited wins over pinned (a space appears exactly once)", () => {
    const groups = groupSpaces(
      [project({ id: 5, is_pinned: true, user_permission: "EDITOR" })],
      { invitedProjectIds: [5] }
    );
    expect(groups).toHaveLength(1);
    expect(groups[0]?.key).toBe("invited");
  });

  it("accepts an array for invitedProjectIds and an empty list yields no invited group", () => {
    const groups = groupSpaces([project({ id: 1 })], {
      invitedProjectIds: [],
    });
    expect(groups.find((g) => g.key === "invited")).toBeUndefined();
  });

  it("returns an empty array for no projects", () => {
    expect(groupSpaces([])).toEqual([]);
  });
});
