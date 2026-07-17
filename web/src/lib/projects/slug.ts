import type { Route } from "next";

/**
 * Canonical Space-detail routing. Spaces live at
 * `/app/spaces/{name-slug}-{id}` (Perplexity-style pretty URL). The trailing
 * integer is authoritative; the name slug is cosmetic. The legacy
 * `/app?projectId={id}` form is still resolved for backward compatibility.
 */

export function slugifySpaceName(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

export function spacePath(id: number, name?: string | null): Route {
  const slug = name ? slugifySpaceName(name) : "";
  return (slug ? `/app/spaces/${slug}-${id}` : `/app/spaces/${id}`) as Route;
}

/**
 * Extract the project id from a `/app/spaces/{slug}-{id}` pathname, or null if
 * the pathname is not a Space-detail route.
 */
export function parseSpaceIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/app\/spaces\/([^/?]+)/);
  const segment = match?.[1];
  if (!segment) return null;
  const trailing = segment.match(/(\d+)$/)?.[1];
  if (!trailing) return null;
  const id = Number.parseInt(trailing, 10);
  return Number.isNaN(id) ? null : id;
}
