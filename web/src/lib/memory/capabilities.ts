import type { UserPersonalization } from "@/lib/types";

export interface MemoryCapabilities {
  canCreateUpdateRestore: boolean;
  canDelete: boolean;
}

export function getMemoryCapabilities(
  personalization: UserPersonalization | undefined
): MemoryCapabilities {
  return {
    canCreateUpdateRestore:
      personalization?.organization_memory_creation_enabled === true,
    canDelete: personalization !== undefined,
  };
}
