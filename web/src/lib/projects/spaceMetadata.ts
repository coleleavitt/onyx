/**
 * Space "extra metadata" persisted through the project **instructions** channel.
 *
 * The Onyx backend `UserProject` row has no column for per-space links or
 * per-space skill associations (only name/description/emoji/instructions). Both
 * the goal plan and its Risks section authorize persisting these through an
 * already-round-tripping channel rather than adding a migration. The project
 * `instructions` free-text field round-trips via
 * `getProjectInstructions` / `upsertProjectInstructions`, so we append a single
 * fenced, machine-readable block to it:
 *
 *   <user instructions text…>
 *
 *   <!--onyx:space-meta
 *   {"links":[...],"skillIds":[...]}
 *   onyx:space-meta-->
 *
 * The block is stripped from the human-facing instructions everywhere it's
 * displayed/edited, and re-attached on save. This module is pure (no DOM / no
 * network) so it is unit-testable directly.
 */

export interface SpaceLink {
  /** Stable id (so React keys + removal are deterministic). */
  id: string;
  /** The URL the space should reference. */
  url: string;
  /** Optional display label. */
  label?: string;
  /** Email of the user who added it ("Added by …"). */
  addedByEmail?: string;
  /** ISO timestamp when added. */
  addedAt?: string;
}

export interface SpaceMeta {
  links: SpaceLink[];
  /** Ids of skills associated with this space (skill ids are strings). */
  skillIds: string[];
}

const BLOCK_OPEN = "<!--onyx:space-meta";
const BLOCK_CLOSE = "onyx:space-meta-->";

// Matches the whole fenced block (with any surrounding blank lines) so it can
// be stripped from the human-facing instructions.
const BLOCK_RE = new RegExp(
  `\\n*${escapeRegExp(BLOCK_OPEN)}[\\s\\S]*?${escapeRegExp(BLOCK_CLOSE)}\\n*`,
  "g"
);

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function emptySpaceMeta(): SpaceMeta {
  return { links: [], skillIds: [] };
}

/**
 * Split a raw instructions string into the human-facing instructions and the
 * parsed space metadata block. Malformed/absent blocks yield empty metadata and
 * leave the instructions untouched.
 */
export function parseSpaceInstructions(raw: string | null | undefined): {
  instructions: string;
  meta: SpaceMeta;
} {
  const text = raw ?? "";
  const match = text.match(
    new RegExp(
      `${escapeRegExp(BLOCK_OPEN)}([\\s\\S]*?)${escapeRegExp(BLOCK_CLOSE)}`
    )
  );
  const instructions = text.replace(BLOCK_RE, "").trim();
  if (!match) {
    return { instructions, meta: emptySpaceMeta() };
  }
  return { instructions, meta: normalizeMeta(safeParse(match[1] ?? "")) };
}

/**
 * Re-attach a metadata block to the human-facing instructions, producing the
 * raw string to persist. When the metadata is empty, no block is appended (so
 * spaces that never used links/skills keep clean instructions).
 */
export function serializeSpaceInstructions(
  instructions: string,
  meta: SpaceMeta
): string {
  const base = (instructions ?? "").trim();
  const normalized = normalizeMeta(meta);
  if (normalized.links.length === 0 && normalized.skillIds.length === 0) {
    return base;
  }
  const payload = JSON.stringify({
    links: normalized.links,
    skillIds: normalized.skillIds,
  });
  const block = `${BLOCK_OPEN}\n${payload}\n${BLOCK_CLOSE}`;
  return base.length > 0 ? `${base}\n\n${block}` : block;
}

/** Extract just the space metadata from a raw instructions string. */
export function readSpaceMeta(raw: string | null | undefined): SpaceMeta {
  return parseSpaceInstructions(raw).meta;
}

// ---------------------------------------------------------------------------
// Pure link operations
// ---------------------------------------------------------------------------

/** Normalize a user-entered URL, adding https:// when no scheme is present. */
export function normalizeUrl(input: string): string {
  const trimmed = input.trim();
  if (trimmed.length === 0) return "";
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed}`;
}

/** Whether a normalized URL is a valid http(s) URL. */
export function isValidLinkUrl(input: string): boolean {
  const normalized = normalizeUrl(input);
  if (normalized.length === 0) return false;
  try {
    const parsed = new URL(normalized);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

/**
 * Add a link to the list. Returns a NEW array (or the same array unchanged when
 * the URL is invalid or a duplicate). `idFactory`/`now` are injectable for
 * deterministic tests.
 */
export function addLink(
  links: SpaceLink[],
  input: string,
  options: {
    addedByEmail?: string;
    label?: string;
    idFactory?: () => string;
    now?: () => string;
  } = {}
): SpaceLink[] {
  if (!isValidLinkUrl(input)) return links;
  const url = normalizeUrl(input);
  if (links.some((link) => link.url === url)) return links;
  const idFactory =
    options.idFactory ?? (() => `link-${Math.random().toString(36).slice(2)}`);
  const now = options.now ?? (() => new Date().toISOString());
  const link: SpaceLink = {
    id: idFactory(),
    url,
    ...(options.label ? { label: options.label } : {}),
    ...(options.addedByEmail ? { addedByEmail: options.addedByEmail } : {}),
    addedAt: now(),
  };
  return [...links, link];
}

/** Remove a link by id. Returns a NEW array. */
export function removeLink(links: SpaceLink[], id: string): SpaceLink[] {
  return links.filter((link) => link.id !== id);
}

// ---------------------------------------------------------------------------
// Pure skill operations
// ---------------------------------------------------------------------------

/** Add a skill id (deduped). Returns a NEW array. */
export function addSkillId(skillIds: string[], skillId: string): string[] {
  if (skillIds.includes(skillId)) return skillIds;
  return [...skillIds, skillId];
}

/** Remove a skill id. Returns a NEW array. */
export function removeSkillId(skillIds: string[], skillId: string): string[] {
  return skillIds.filter((id) => id !== skillId);
}

/**
 * Diff a desired skill-id selection against the current one.
 * Returns the ids to add and to remove.
 */
export function diffSkillIds(
  current: string[],
  next: string[]
): { added: string[]; removed: string[] } {
  const currentSet = new Set(current);
  const nextSet = new Set(next);
  return {
    added: next.filter((id) => !currentSet.has(id)),
    removed: current.filter((id) => !nextSet.has(id)),
  };
}

// ---------------------------------------------------------------------------
// internals
// ---------------------------------------------------------------------------

function safeParse(json: string): unknown {
  try {
    return JSON.parse(json.trim());
  } catch {
    return null;
  }
}

function normalizeMeta(value: unknown): SpaceMeta {
  if (!value || typeof value !== "object") return emptySpaceMeta();
  const record = value as Record<string, unknown>;
  const links = Array.isArray(record.links)
    ? record.links.flatMap((entry) => {
        const normalized = normalizeLink(entry);
        return normalized ? [normalized] : [];
      })
    : [];
  const skillIds = Array.isArray(record.skillIds)
    ? record.skillIds
        .map((id) => (typeof id === "number" ? String(id) : id))
        .filter((id): id is string => typeof id === "string" && id.length > 0)
    : [];
  // De-dupe defensively.
  const seenUrls = new Set<string>();
  const dedupedLinks = links.filter((link) => {
    if (seenUrls.has(link.url)) return false;
    seenUrls.add(link.url);
    return true;
  });
  return { links: dedupedLinks, skillIds: Array.from(new Set(skillIds)) };
}

function normalizeLink(value: unknown): SpaceLink | null {
  if (!value || typeof value !== "object") return null;
  const record = value as Record<string, unknown>;
  if (typeof record.url !== "string" || record.url.trim().length === 0) {
    return null;
  }
  return {
    id:
      typeof record.id === "string" && record.id.length > 0
        ? record.id
        : `link-${record.url}`,
    url: record.url,
    ...(typeof record.label === "string" ? { label: record.label } : {}),
    ...(typeof record.addedByEmail === "string"
      ? { addedByEmail: record.addedByEmail }
      : {}),
    ...(typeof record.addedAt === "string" ? { addedAt: record.addedAt } : {}),
  };
}
