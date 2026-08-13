import { NextRequest } from "next/server";

/** Pick the trusted origin for a request's hostname from an allowlist of
 * origins. Returns the matching allowlist entry (canonical scheme/port, so a
 * TLS-terminating proxy speaking plain http internally still yields https),
 * the first entry when nothing matches, or null for an empty allowlist. */
export function resolveTrustedOrigin(
  allowed: string[],
  requestHostname: string
): string | null {
  const match = allowed.find((origin) => {
    try {
      return new URL(origin).hostname === requestHostname;
    } catch {
      return false;
    }
  });
  return match ?? allowed[0] ?? null;
}

/** Origins redirects may target: WEB_DOMAINS (comma-separated) for
 * multi-domain deployments, falling back to the single WEB_DOMAIN. */
const allowedOrigins = (): string[] =>
  (process.env.WEB_DOMAINS || process.env.WEB_DOMAIN || "")
    .split(",")
    .map((origin) => origin.trim().replace(/\/+$/, ""))
    .filter(Boolean);

export const getDomain = (request: NextRequest) => {
  // Redirects must stay on the domain that served the request in multi-domain
  // deployments (a login's session cookie is host-scoped), but the emitted
  // origin must always come from the allowlist — never from X-Forwarded-* or
  // an arbitrary Host header, which an attacker can spoof to poison redirect
  // URLs. Unlisted hosts therefore fall back to the primary domain.
  const allowed = allowedOrigins();
  const trusted = resolveTrustedOrigin(allowed, request.nextUrl.hostname);
  if (trusted) {
    return trusted;
  }

  // Fallback for local development: use Next.js's own origin.
  return request.nextUrl.origin;
};
