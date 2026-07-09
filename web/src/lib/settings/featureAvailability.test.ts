import { enterpriseFeaturesAvailable } from "@/lib/settings/featureAvailability";

describe("enterpriseFeaturesAvailable", () => {
  it("waits for runtime settings", () => {
    expect(
      enterpriseFeaturesAvailable({
        isLoading: true,
        error: undefined,
        enabled: true,
      })
    ).toBe(false);
  });

  it("honors a disabled runtime feature set", () => {
    expect(
      enterpriseFeaturesAvailable({
        isLoading: false,
        error: undefined,
        enabled: false,
      })
    ).toBe(false);
  });

  it("allows enabled and backward-compatible settings responses", () => {
    expect(
      enterpriseFeaturesAvailable({
        isLoading: false,
        error: undefined,
        enabled: true,
      })
    ).toBe(true);
    expect(
      enterpriseFeaturesAvailable({
        isLoading: false,
        error: undefined,
        enabled: undefined,
      })
    ).toBe(true);
  });
});
