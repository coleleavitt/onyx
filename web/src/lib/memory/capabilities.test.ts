import { getMemoryCapabilities } from "@/lib/memory/capabilities";
import type { UserPersonalization } from "@/lib/types";

const enabledPersonalization: UserPersonalization = {
  name: "",
  role: "",
  memories: [],
  use_memories: true,
  enable_memory_tool: true,
  user_preferences: "",
  organization_memories_enabled: true,
  organization_memory_creation_enabled: true,
};

describe("getMemoryCapabilities", () => {
  it("fails closed until organization policy is loaded", () => {
    expect(getMemoryCapabilities(undefined)).toEqual({
      canCreateUpdateRestore: false,
      canDelete: false,
    });
  });

  it("keeps deletion available when creation is disabled", () => {
    expect(
      getMemoryCapabilities({
        ...enabledPersonalization,
        organization_memory_creation_enabled: false,
      })
    ).toEqual({
      canCreateUpdateRestore: false,
      canDelete: true,
    });
  });

  it("enables all owned-memory mutations when policy allows creation", () => {
    expect(getMemoryCapabilities(enabledPersonalization)).toEqual({
      canCreateUpdateRestore: true,
      canDelete: true,
    });
  });
});
