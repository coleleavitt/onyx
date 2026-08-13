import { resolveTrustedOrigin } from "./redirectSS";

describe("resolveTrustedOrigin", () => {
  const allowed = [
    "https://chat.fiwealth.com",
    "https://chat.magellanfinancial.com",
  ];

  it("returns the allowlist entry matching the request hostname", () => {
    expect(resolveTrustedOrigin(allowed, "chat.magellanfinancial.com")).toBe(
      "https://chat.magellanfinancial.com"
    );
    expect(resolveTrustedOrigin(allowed, "chat.fiwealth.com")).toBe(
      "https://chat.fiwealth.com"
    );
  });

  it("emits the canonical https origin even when matched from an internal http request host", () => {
    // Matching is by hostname, so a TLS-terminating proxy speaking plain http
    // internally still resolves to the allowlisted https origin.
    expect(
      resolveTrustedOrigin(["https://chat.fiwealth.com"], "chat.fiwealth.com")
    ).toBe("https://chat.fiwealth.com");
  });

  it("falls back to the primary (first) origin for unlisted hosts", () => {
    expect(resolveTrustedOrigin(allowed, "evil.example.com")).toBe(
      "https://chat.fiwealth.com"
    );
  });

  it("returns null for an empty allowlist", () => {
    expect(resolveTrustedOrigin([], "chat.fiwealth.com")).toBeNull();
  });

  it("still matches by hostname when a malformed entry precedes the match", () => {
    expect(
      resolveTrustedOrigin(
        ["not a url", ...allowed],
        "chat.magellanfinancial.com"
      )
    ).toBe("https://chat.magellanfinancial.com");
  });
});
