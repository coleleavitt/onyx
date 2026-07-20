import {
  hueFromEmoji,
  spaceAccentFromEmoji,
  type SpaceAccent,
} from "@/lib/projects/spaceAccent";

/**
 * These tests drive the SHIPPED pure helpers directly (no re-implementation,
 * no mocking). They assert the two properties the UI relies on:
 *   1. Determinism — the same emoji always yields the same token.
 *   2. Well-formedness — every token is a parseable `oklch(L C H)` string with
 *      values in range and a hue in [0, 360).
 */

/** Parse an `oklch(L C H)` token into numbers, or fail the test. */
function parseOklch(token: string): { l: number; c: number; h: number } {
  const match = token.match(
    /^oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)$/
  );
  expect(match).not.toBeNull();
  const [, l, c, h] = match as RegExpMatchArray;
  return { l: Number(l), c: Number(c), h: Number(h) };
}

function expectWellFormed(accent: SpaceAccent): void {
  expect(accent.hue).toBeGreaterThanOrEqual(0);
  expect(accent.hue).toBeLessThan(360);
  for (const token of [
    accent.backgroundLight,
    accent.foregroundLight,
    accent.backgroundDark,
    accent.foregroundDark,
  ]) {
    const { l, c, h } = parseOklch(token);
    expect(l).toBeGreaterThan(0);
    expect(l).toBeLessThanOrEqual(1);
    expect(c).toBeGreaterThanOrEqual(0);
    expect(h).toBeGreaterThanOrEqual(0);
    expect(h).toBeLessThan(360);
  }
}

describe("hueFromEmoji", () => {
  it("returns null for empty / whitespace / nullish input", () => {
    expect(hueFromEmoji("")).toBeNull();
    expect(hueFromEmoji("   ")).toBeNull();
    expect(hueFromEmoji(null)).toBeNull();
    expect(hueFromEmoji(undefined)).toBeNull();
  });

  it("is deterministic: same emoji → same hue", () => {
    for (const emoji of ["🚀", "📁", "🧠", "⭐", "❤️"]) {
      expect(hueFromEmoji(emoji)).toBe(hueFromEmoji(emoji));
    }
  });

  it("keeps the hue within [0, 360)", () => {
    for (const emoji of ["🚀", "📁", "🧠", "⭐", "❤️", "🤖", "🌈", "🔥"]) {
      const hue = hueFromEmoji(emoji);
      expect(hue).not.toBeNull();
      expect(hue as number).toBeGreaterThanOrEqual(0);
      expect(hue as number).toBeLessThan(360);
    }
  });

  it("distinguishes at least some different emojis (not a constant)", () => {
    const hues = new Set(
      ["🚀", "📁", "🧠", "⭐", "❤️", "🤖", "🌈", "🔥", "💻", "🎯"].map((e) =>
        hueFromEmoji(e)
      )
    );
    // A constant function would collapse to a single hue; require spread.
    expect(hues.size).toBeGreaterThan(3);
  });

  it("ignores surrounding whitespace", () => {
    expect(hueFromEmoji("  🚀  ")).toBe(hueFromEmoji("🚀"));
  });
});

describe("spaceAccentFromEmoji", () => {
  it("returns well-formed oklch tokens for representative emojis", () => {
    for (const emoji of ["🚀", "📁", "🧠", "⭐", "❤️", "🤖"]) {
      expectWellFormed(spaceAccentFromEmoji(emoji));
    }
  });

  it("is deterministic for a given emoji", () => {
    const a = spaceAccentFromEmoji("🚀");
    const b = spaceAccentFromEmoji("🚀");
    expect(a).toEqual(b);
  });

  it("returns a neutral (zero-chroma) but well-formed accent when empty", () => {
    const neutral = spaceAccentFromEmoji("");
    expectWellFormed(neutral);
    // Neutral means zero chroma in every token.
    expect(parseOklch(neutral.backgroundLight).c).toBe(0);
    expect(parseOklch(neutral.foregroundLight).c).toBe(0);
    expect(parseOklch(neutral.backgroundDark).c).toBe(0);
    expect(parseOklch(neutral.foregroundDark).c).toBe(0);
  });

  it("applies non-zero chroma once an emoji is set", () => {
    const accent = spaceAccentFromEmoji("🚀");
    expect(parseOklch(accent.foregroundLight).c).toBeGreaterThan(0);
    expect(parseOklch(accent.backgroundLight).c).toBeGreaterThan(0);
  });

  it("keeps light bg lighter than light fg, and dark bg darker than dark fg", () => {
    const accent = spaceAccentFromEmoji("🌈");
    expect(parseOklch(accent.backgroundLight).l).toBeGreaterThan(
      parseOklch(accent.foregroundLight).l
    );
    expect(parseOklch(accent.backgroundDark).l).toBeLessThan(
      parseOklch(accent.foregroundDark).l
    );
  });
});
