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

/** The hostname the client actually addressed. request.nextUrl reflects the
 * standalone server's own origin (localhost) behind a proxy, so the proxied
 * Host header is the only usable signal. */
const requestHostname = (request: NextRequest): string => {
  const hostHeader =
    request.headers.get("x-forwarded-host") ??
    request.headers.get("host") ??
    "";
  const hostname = hostHeader.split(",")[0]!.trim().split(":")[0]!;
  return hostname || request.nextUrl.hostname;
};

export const getDomain = (request: NextRequest) => {
  // Redirects must stay on the domain that served the request in multi-domain
  // deployments (a login's session cookie is host-scoped), but the emitted
  // origin must always come from the allowlist — a spoofed Host header can
  // only ever select between allowlisted origins, never mint a new one, so
  // redirect URLs cannot be poisoned. Unlisted hosts fall back to the primary
  // domain.
  const allowed = allowedOrigins();
  const trusted = resolveTrustedOrigin(allowed, requestHostname(request));
  if (trusted) {
    return trusted;
  }

  // Fallback for local development: use Next.js's own origin.
  return request.nextUrl.origin;
};
