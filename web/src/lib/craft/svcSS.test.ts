const mockRequireAuth = jest.fn();
const mockFetchSettingsSS = jest.fn();
const mockRedirect = jest.fn((path: string) => {
  throw new Error(`redirect:${path}`);
});

jest.mock("@/lib/auth/svcSS", () => ({
  requireAuth: mockRequireAuth,
}));
jest.mock("@/lib/settings/svcSS", () => ({
  fetchSettingsSS: mockFetchSettingsSS,
}));
jest.mock("next/navigation", () => ({
  redirect: mockRedirect,
}));

import { requireOnyxCraftAccessSS } from "@/lib/craft/svcSS";

describe("requireOnyxCraftAccessSS", () => {
  beforeEach(() => {
    mockRequireAuth.mockResolvedValue({ user: { id: "user" } });
    mockFetchSettingsSS.mockResolvedValue({
      settings: { onyx_craft_enabled: true },
    });
  });

  it("allows only explicit Craft enablement", async () => {
    await expect(requireOnyxCraftAccessSS()).resolves.toBeUndefined();
    expect(mockRedirect).not.toHaveBeenCalled();
  });

  it("redirects to the app when settings are missing or Craft is disabled", async () => {
    mockFetchSettingsSS.mockResolvedValue(null);

    await expect(requireOnyxCraftAccessSS()).rejects.toThrow("redirect:/app");
    expect(mockRedirect).toHaveBeenCalledWith("/app");
  });

  it("preserves authentication redirects", async () => {
    mockRequireAuth.mockResolvedValue({ redirect: "/auth/login" });

    await expect(requireOnyxCraftAccessSS()).rejects.toThrow(
      "redirect:/auth/login"
    );
    expect(mockRedirect).toHaveBeenCalledWith("/auth/login");
  });
});
