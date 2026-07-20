import {
  PERMISSION_OPTIONS,
  SCOPE_OPTIONS,
} from "@/sections/modals/shareAccessConstants";

/**
 * Drives the shipped share/access option sets used by ShareProjectModal.
 * This guards the Spaces sharing surface against losing the owner/private/editor/viewer/
 * organization affordances required for the Perplexity-parity sharing model.
 */
describe("shareAccessConstants", () => {
  it("exposes the editor/viewer permission options with labels", () => {
    expect(PERMISSION_OPTIONS.map((option) => option.value)).toEqual([
      "VIEWER",
      "EDITOR",
    ]);
    expect(PERMISSION_OPTIONS.map((option) => option.label)).toEqual([
      "View & Chat",
      "Edit",
    ]);
    for (const option of PERMISSION_OPTIONS) {
      expect(option.icon).toBeDefined();
      expect(option.label.length).toBeGreaterThan(0);
    }
  });

  it("exposes private vs organization-wide scope options", () => {
    expect(SCOPE_OPTIONS.map((option) => option.value)).toEqual([
      "PRIVATE",
      "PUBLIC",
    ]);
    expect(SCOPE_OPTIONS.map((option) => option.label)).toEqual([
      "Only people with access can view",
      "Anyone in your organization can view",
    ]);
    for (const option of SCOPE_OPTIONS) {
      expect(option.icon).toBeDefined();
      expect(option.label.length).toBeGreaterThan(0);
    }
  });
});
