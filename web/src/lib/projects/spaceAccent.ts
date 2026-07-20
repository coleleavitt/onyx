/**
 * Pure emoji → accent-color derivation for Spaces.
 *
 * Perplexity themes each Space's icon/pill/card with an accent color derived
 * from the Space emoji (they render the emoji to a canvas and read its dominant
 * hue). We can't run a canvas in a pure, unit-testable function, so instead we
 * derive a *stable* hue directly from the emoji's Unicode codepoints. The same
 * emoji always maps to the same hue, and we express the accent as `oklch(...)`
 * tokens (light + dark) so the color has consistent perceived lightness/chroma
 * regardless of hue — matching Perplexity's `oklch()` accent scheme.
 *
 * This module is intentionally free of React/DOM so it can be tested directly.
 */

/** Full hue circle, in degrees. */
const HUE_RANGE = 360;

/**
 * The accent color tokens for a Space, for both color schemes. Values are
 * `oklch(L C H)` strings — directly usable as CSS colors or CSS variables.
 */
export interface SpaceAccent {
  /** Stable hue in [0, 360) derived from the emoji. */
  hue: number;
  /** Light-mode background fill (very light, low chroma). */
  backgroundLight: string;
  /** Light-mode foreground/icon color (mid lightness, higher chroma). */
  foregroundLight: string;
  /** Dark-mode background fill (dark, low chroma). */
  backgroundDark: string;
  /** Dark-mode foreground/icon color (light, higher chroma). */
  foregroundDark: string;
}

/**
 * Neutral fallback used when no emoji is set. Zero chroma keeps it grey in both
 * schemes while still returning a well-formed, stable token.
 */
const NEUTRAL_HUE = 0;

/**
 * Derive a stable hue in [0, 360) from an emoji string.
 *
 * Uses the full sequence of Unicode code points (so multi-codepoint emoji like
 * ZWJ sequences and skin-tone modifiers are all accounted for) folded into a
 * bounded accumulator. Deterministic: equal input → equal output.
 *
 * Returns `null` for empty/whitespace-only input so callers can choose a
 * neutral fallback.
 */
export function hueFromEmoji(emoji: string | null | undefined): number | null {
  if (!emoji) return null;
  const trimmed = emoji.trim();
  if (trimmed.length === 0) return null;

  // FNV-1a-style fold over code points keeps the result stable and well-spread
  // across the hue circle without pulling in a hashing dependency.
  let acc = 0x811c9dc5;
  for (const char of trimmed) {
    const codePoint = char.codePointAt(0);
    if (codePoint === undefined) continue;
    acc ^= codePoint;
    // Multiply by the FNV prime, kept in 32-bit unsigned range.
    acc = Math.imul(acc, 0x01000193) >>> 0;
  }

  return acc % HUE_RANGE;
}

/**
 * Format an `oklch()` token. Lightness and chroma are fixed per role; only the
 * hue varies per emoji, guaranteeing consistent contrast across all Spaces.
 */
function oklch(lightness: number, chroma: number, hue: number): string {
  // Trim to a compact, stable string form (no locale formatting).
  const l = Number(lightness.toFixed(4));
  const c = Number(chroma.toFixed(4));
  const h = Number(hue.toFixed(2));
  return `oklch(${l} ${c} ${h})`;
}

/**
 * Derive the full accent-color token set for a Space emoji.
 *
 * When no emoji is present the returned tokens are neutral (zero chroma) but
 * still well-formed `oklch(...)` strings, so the icon/card always has a valid,
 * stable background/foreground.
 */
export function spaceAccentFromEmoji(
  emoji: string | null | undefined
): SpaceAccent {
  const derivedHue = hueFromEmoji(emoji);
  const hasEmoji = derivedHue !== null;
  const hue = hasEmoji ? derivedHue : NEUTRAL_HUE;
  const chromaBg = hasEmoji ? 0.02 : 0;
  const chromaFg = hasEmoji ? 0.08 : 0;

  return {
    hue,
    backgroundLight: oklch(0.96, chromaBg, hue),
    foregroundLight: oklch(0.45, chromaFg, hue),
    backgroundDark: oklch(0.25, chromaBg === 0 ? 0 : 0.025, hue),
    foregroundDark: oklch(0.65, chromaFg, hue),
  };
}
