"""SSO login-flow diagnostic for the multi-IdP OIDC providers.

Walks every leg of the login flow that can be exercised without a human
completing IdP authentication, and reports where the flow breaks:

  1. authorize:  GET {base}/api/auth/oidc/{provider}/authorize
                 -> sanity-check the authorization_url (tenant, redirect_uri,
                    scopes, PKCE, signed state)
  2. idp:        GET the authorization_url at the IdP with no session
                 -> a login page means the IdP accepts client_id+redirect_uri;
                    an AADSTS error here means the app registration rejects
                    the request before any user signs in
  3. callback:   GET the registered redirect_uri with the real signed state
                 from step 1 and a dummy code (cookies carried from step 1)
                 -> expected result is 400 "Authorization code exchange
                    failed", which proves wrapper routing, state validation,
                    and CSRF/PKCE cookie handling all work and the server
                    reached the token-exchange step. Any other error message
                    pinpoints the leg that broke before the exchange.

Usage:
    python sso_flow_check.py https://chat.fiwealth.com:fiwealth \
        https://chat.magellanfinancial.com:magellan
"""

import base64
import json
import re
import sys
from urllib.parse import parse_qs
from urllib.parse import urlsplit

import httpx

AADSTS_RE = re.compile(r"AADSTS\d+[^<\"]{0,200}")
UA = "Mozilla/5.0 (X11; Linux x86_64) sso-flow-check"


def jwt_payload(token: str) -> dict[str, object]:
    try:
        body = token.split(".")[1]
        body += "=" * (-len(body) % 4)
        return json.loads(base64.urlsafe_b64decode(body))
    except Exception:
        return {}


def mask(value: str, keep: int = 8) -> str:
    return value[:keep] + "***" if len(value) > keep else value


def check(base: str, provider: str) -> bool:
    print(f"\n{'=' * 20} {provider} @ {base} {'=' * 20}")
    ok = True
    with httpx.Client(timeout=20, headers={"User-Agent": UA}) as client:
        # -- leg 1: authorize ------------------------------------------------
        r = client.get(f"{base}/api/auth/oidc/{provider}/authorize")
        print(f"[authorize] HTTP {r.status_code}")
        if r.status_code != 200:
            print(f"  FAIL: {r.text[:300]}")
            return False
        auth_url = r.json().get("authorization_url", "")
        parts = urlsplit(auth_url)
        q = {k: v[0] for k, v in parse_qs(parts.query).items()}
        state = q.get("state", "")
        print(f"  idp host:     {parts.netloc}{parts.path}")
        print(f"  client_id:    {mask(q.get('client_id', ''))}")
        print(f"  redirect_uri: {q.get('redirect_uri')}")
        print(f"  scope:        {q.get('scope')}")
        print(f"  pkce:         {'code_challenge' in q}")
        print(f"  state claims: {jwt_payload(state)}")
        print(f"  cookies set:  {list(r.cookies.keys())}")

        # -- leg 2: IdP accepts the request ----------------------------------
        r2 = client.get(auth_url, follow_redirects=True)
        errors = AADSTS_RE.findall(r2.text)
        landed = urlsplit(str(r2.url)).netloc
        if errors:
            print(f"[idp] HTTP {r2.status_code} at {landed} -> FAIL")
            for e in dict.fromkeys(errors):
                print(f"  {e}")
            ok = False
        else:
            print(
                f"[idp] HTTP {r2.status_code} at {landed} -> login page, "
                "client_id+redirect_uri accepted"
            )

        # -- leg 3: callback plumbing with dummy code ------------------------
        redirect_uri = q.get("redirect_uri", "")
        cb = f"{redirect_uri}?code=dummy-code-flow-check&state={state}"
        r3 = client.get(cb, follow_redirects=False)
        detail = ""
        loc = r3.headers.get("location", "")
        try:
            detail = r3.json().get("detail", "")
        except Exception:
            detail = r3.text[:200]
        print(f"[callback] HTTP {r3.status_code} {('-> ' + loc) if loc else ''}")
        print(f"  detail: {detail}")
        if (
            "code exchange failed" in str(detail).lower()
            or "authorization code" in loc.lower()
        ):
            print(
                "  PASS: routing + state + cookies OK; server reached the "
                "token-exchange step (dummy code correctly rejected)"
            )
        elif r3.status_code in (301, 302, 307):
            print(
                "  NOTE: redirect — inspect target above (error page = "
                "reached exchange; login page = state/cookie leg failed)"
            )
        else:
            print("  FAIL before token exchange — this leg is the broken one")
            ok = False
    return ok


def main() -> None:
    targets = [a.rsplit(":", 1) for a in sys.argv[1:]] or [
        ["https://chat.fiwealth.com", "fiwealth"],
        ["https://chat.magellanfinancial.com", "magellan"],
    ]
    results = {p: check(b, p) for b, p in targets}
    print(f"\n{'=' * 58}")
    for p, r in results.items():
        print(f"  {p}: {'all reachable legs OK' if r else 'BROKEN — see above'}")


if __name__ == "__main__":
    main()
