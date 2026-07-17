import {
  parseSpaceIdFromPath,
  slugifySpaceName,
  spacePath,
} from "@/lib/projects/slug";

describe("space slug routing", () => {
  it("slugifies names", () => {
    expect(slugifySpaceName("Angelina's Romance Websites")).toBe(
      "angelina-s-romance-websites"
    );
    expect(slugifySpaceName("  CSC 120  ")).toBe("csc-120");
    expect(slugifySpaceName("!!!")).toBe("");
  });

  it("builds pretty paths with a trailing id", () => {
    expect(spacePath(1, "work")).toBe("/app/spaces/work-1");
    expect(spacePath(42, "CSC 120")).toBe("/app/spaces/csc-120-42");
    expect(spacePath(7)).toBe("/app/spaces/7");
    expect(spacePath(7, "!!!")).toBe("/app/spaces/7");
  });

  it("parses the id back from the path", () => {
    expect(parseSpaceIdFromPath("/app/spaces/work-1")).toBe(1);
    expect(parseSpaceIdFromPath("/app/spaces/csc-120-42")).toBe(42);
    expect(parseSpaceIdFromPath("/app/spaces/7")).toBe(7);
    expect(parseSpaceIdFromPath("/app/spaces/work-1?tab=files")).toBe(1);
  });

  it("returns null for non-space paths", () => {
    expect(parseSpaceIdFromPath("/app")).toBeNull();
    expect(parseSpaceIdFromPath("/app/spaces")).toBeNull();
    expect(parseSpaceIdFromPath("/app/artifacts")).toBeNull();
    expect(parseSpaceIdFromPath("/app/spaces/no-trailing-id")).toBeNull();
  });
});
