export type MemoryGovernanceAuditAction =
  | "POLICY_UPDATED"
  | "RETENTION_CLEANUP"
  | "BULK_DELETE";

export interface MemoryGovernancePolicy {
  memories_enabled: boolean;
  memory_creation_enabled: boolean;
  retention_days: number | null;
  updated_at: string | null;
}

export interface MemoryGovernanceStats {
  memory_count: number;
  user_count: number;
  oldest_memory_at: string | null;
}

export interface MemoryGovernanceAuditEvent {
  id: number;
  action: MemoryGovernanceAuditAction;
  actor_email: string | null;
  affected_count: number;
  details: Record<string, unknown>;
  created_at: string;
}

export interface MemoryGovernanceOverview {
  policy: MemoryGovernancePolicy;
  stats: MemoryGovernanceStats;
  audit_events: MemoryGovernanceAuditEvent[];
}

const API_PATH = "/api/admin/memory-governance";

async function handle<T>(response: Response, fallback: string): Promise<T> {
  if (!response.ok) {
    let detail = fallback;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // Keep the operation-specific fallback when the response is not JSON.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function updateMemoryGovernancePolicy(
  policy: Omit<MemoryGovernancePolicy, "updated_at">
): Promise<MemoryGovernanceOverview> {
  const response = await fetch(API_PATH, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policy),
  });
  return handle(response, "Failed to update memory policy");
}

export async function bulkDeleteMemories(
  scope: "expired" | "all",
  confirmation?: string
): Promise<{ affected_count: number }> {
  const response = await fetch(`${API_PATH}/bulk-delete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scope, confirmation }),
  });
  return handle(response, "Failed to delete memories");
}
