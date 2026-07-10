export interface WorkflowPinsResponse {
  workflow_ids: string[];
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      detail?: string;
    } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function pinWorkflow(
  workflowId: string
): Promise<WorkflowPinsResponse> {
  return handle<WorkflowPinsResponse>(
    await fetch(
      `/api/build/workflow-catalog/pins/${encodeURIComponent(workflowId)}`,
      { method: "PUT" }
    )
  );
}

export async function unpinWorkflow(workflowId: string): Promise<void> {
  await handle<void>(
    await fetch(
      `/api/build/workflow-catalog/pins/${encodeURIComponent(workflowId)}`,
      { method: "DELETE" }
    )
  );
}
