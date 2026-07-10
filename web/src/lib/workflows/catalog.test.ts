import { WORKFLOW_CATALOG } from "@/lib/workflows/catalog";

describe("workflow catalog", () => {
  it("separates guided workflows from recurring automations", () => {
    expect(
      WORKFLOW_CATALOG.find((item) => item.id === "prompt-refinement")
        ?.execution
    ).toBe("guided");
    expect(
      WORKFLOW_CATALOG.find((item) => item.id === "compliance-monitor")
        ?.execution
    ).toBe("scheduled");
  });

  it("contains unique workflow identifiers", () => {
    const ids = WORKFLOW_CATALOG.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
