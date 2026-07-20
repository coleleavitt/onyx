import {
  addLink,
  addSkillId,
  diffSkillIds,
  emptySpaceMeta,
  isValidLinkUrl,
  normalizeUrl,
  parseSpaceInstructions,
  readSpaceMeta,
  removeLink,
  removeSkillId,
  serializeSpaceInstructions,
  type SpaceLink,
} from "@/lib/projects/spaceMetadata";

/**
 * Drives the SHIPPED space-metadata helpers directly (no mocks, no re-impl).
 * These are the persistence + link/skill model criteria (links round-trip;
 * skills add/remove/diff).
 */

describe("space instructions round-trip", () => {
  it("parses empty/absent input to empty meta and empty instructions", () => {
    expect(parseSpaceInstructions(null)).toEqual({
      instructions: "",
      meta: emptySpaceMeta(),
    });
    expect(parseSpaceInstructions("")).toEqual({
      instructions: "",
      meta: emptySpaceMeta(),
    });
  });

  it("keeps plain instructions untouched when there is no meta block", () => {
    const { instructions, meta } = parseSpaceInstructions(
      "Summarize weekly."
    );
    expect(instructions).toBe("Summarize weekly.");
    expect(meta).toEqual(emptySpaceMeta());
  });

  it("does not append a block when meta is empty", () => {
    expect(serializeSpaceInstructions("Hi", emptySpaceMeta())).toBe("Hi");
  });

  it("round-trips links + skillIds through serialize→parse", () => {
    const link: SpaceLink = {
      id: "l1",
      url: "https://example.com",
      addedByEmail: "a@b.com",
      addedAt: "2026-01-01T00:00:00.000Z",
    };
    const raw = serializeSpaceInstructions("Do the thing.", {
      links: [link],
      skillIds: ["skill-7", "skill-9"],
    });
    // The human-facing instructions must come first and be recoverable.
    const parsed = parseSpaceInstructions(raw);
    expect(parsed.instructions).toBe("Do the thing.");
    expect(parsed.meta.links).toEqual([link]);
    expect(parsed.meta.skillIds).toEqual(["skill-7", "skill-9"]);
  });

  it("strips the meta block from the human-facing instructions", () => {
    const raw = serializeSpaceInstructions("Visible text", {
      links: [{ id: "l1", url: "https://x.com" }],
      skillIds: [],
    });
    expect(raw).toContain("onyx:space-meta");
    expect(parseSpaceInstructions(raw).instructions).toBe("Visible text");
    expect(parseSpaceInstructions(raw).instructions).not.toContain(
      "space-meta"
    );
  });

  it("tolerates a malformed meta block (returns empty meta, keeps text)", () => {
    const raw =
      "Real text\n\n<!--onyx:space-meta\n{not json]\nonyx:space-meta-->";
    const parsed = parseSpaceInstructions(raw);
    expect(parsed.instructions).toBe("Real text");
    expect(parsed.meta).toEqual(emptySpaceMeta());
  });

  it("readSpaceMeta is a convenience over parseSpaceInstructions", () => {
    const raw = serializeSpaceInstructions("x", {
      links: [],
      skillIds: ["skill-3"],
    });
    expect(readSpaceMeta(raw).skillIds).toEqual(["skill-3"]);
  });

  it("coerces legacy numeric skill ids to strings on parse", () => {
    const raw =
      'x\n\n<!--onyx:space-meta\n{"links":[],"skillIds":[3,4]}\nonyx:space-meta-->';
    expect(readSpaceMeta(raw).skillIds).toEqual(["3", "4"]);
  });
});

describe("link url normalization + validation", () => {
  it("adds https:// when no scheme is present", () => {
    expect(normalizeUrl("example.com")).toBe("https://example.com");
    expect(normalizeUrl("http://x.com")).toBe("http://x.com");
    expect(normalizeUrl("https://x.com")).toBe("https://x.com");
    expect(normalizeUrl("   ")).toBe("");
  });

  it("accepts valid http(s) urls and rejects junk", () => {
    expect(isValidLinkUrl("example.com")).toBe(true);
    expect(isValidLinkUrl("https://a.b/c?d=e")).toBe(true);
    expect(isValidLinkUrl("")).toBe(false);
    expect(isValidLinkUrl("not a url with spaces")).toBe(false);
    expect(isValidLinkUrl("ftp://x.com")).toBe(false);
  });
});

describe("link add/remove", () => {
  const idFactory = () => "fixed-id";
  const now = () => "2026-02-02T00:00:00.000Z";

  it("adds a normalized link with attribution", () => {
    const result = addLink([], "example.com", {
      addedByEmail: "me@co.com",
      idFactory,
      now,
    });
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      id: "fixed-id",
      url: "https://example.com",
      addedByEmail: "me@co.com",
      addedAt: "2026-02-02T00:00:00.000Z",
    });
  });

  it("ignores invalid or duplicate urls (same array returned)", () => {
    const existing = addLink([], "example.com", { idFactory, now });
    expect(addLink(existing, "not valid", { idFactory, now })).toBe(existing);
    // Duplicate (normalizes to same url) is a no-op.
    expect(addLink(existing, "https://example.com", { idFactory, now })).toBe(
      existing
    );
  });

  it("removes by id without mutating the input", () => {
    const a = addLink([], "a.com", { idFactory: () => "a", now });
    const both = addLink(a, "b.com", { idFactory: () => "b", now });
    const removed = removeLink(both, "a");
    expect(removed.map((l) => l.id)).toEqual(["b"]);
    // original untouched
    expect(both.map((l) => l.id)).toEqual(["a", "b"]);
  });
});

describe("skill selection", () => {
  it("adds and de-dupes skill ids", () => {
    expect(addSkillId([], "s5")).toEqual(["s5"]);
    expect(addSkillId(["s5"], "s5")).toEqual(["s5"]);
    expect(addSkillId(["s5"], "s6")).toEqual(["s5", "s6"]);
  });

  it("removes skill ids", () => {
    expect(removeSkillId(["s5", "s6"], "s5")).toEqual(["s6"]);
    expect(removeSkillId(["s5"], "s9")).toEqual(["s5"]);
  });

  it("diffs a desired selection into added/removed", () => {
    expect(diffSkillIds(["s1", "s2", "s3"], ["s2", "s3", "s4"])).toEqual({
      added: ["s4"],
      removed: ["s1"],
    });
    expect(diffSkillIds([], [])).toEqual({ added: [], removed: [] });
  });
});
