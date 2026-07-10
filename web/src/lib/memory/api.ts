import type {
  MemoryInput,
  MemoryItem,
  MemoryRevision,
} from "@/lib/memory/types";

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

export async function createMemory(input: MemoryInput): Promise<MemoryItem> {
  return handle<MemoryItem>(
    await fetch("/api/memory", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  );
}

export async function updateMemory(
  memoryId: number,
  input: Partial<MemoryInput>
): Promise<MemoryItem> {
  return handle<MemoryItem>(
    await fetch(`/api/memory/${memoryId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  );
}

export async function deleteMemory(memoryId: number): Promise<void> {
  await handle<void>(
    await fetch(`/api/memory/${memoryId}`, { method: "DELETE" })
  );
}

export async function getMemoryHistory(
  memoryId: number
): Promise<MemoryRevision[]> {
  return handle<MemoryRevision[]>(
    await fetch(`/api/memory/${memoryId}/history`)
  );
}

export async function restoreMemoryRevision(
  memoryId: number,
  revisionId: string
): Promise<MemoryItem> {
  return handle<MemoryItem>(
    await fetch(`/api/memory/${memoryId}/history/${revisionId}/restore`, {
      method: "POST",
    })
  );
}
