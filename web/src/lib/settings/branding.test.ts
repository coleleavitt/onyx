import { getBrandAccentVariables } from "@/lib/settings/branding";

describe("getBrandAccentVariables", () => {
  it("builds a restrained interaction scale from an accent color", () => {
    expect(getBrandAccentVariables("#e3530f")).toEqual({
      "--theme-primary-04": "#e6682c",
      "--theme-primary-05": "#e3530f",
      "--theme-primary-06": "#c1470d",
    });
  });

  it("ignores absent or malformed colors", () => {
    expect(getBrandAccentVariables(null)).toBeNull();
    expect(getBrandAccentVariables("orange")).toBeNull();
  });
});
