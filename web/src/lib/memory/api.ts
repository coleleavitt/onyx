import type {
  BrainRunTrigger,
  BrainSettings,
  BrainSettingsUpdate,
  MemoryGraph,
  MemoryInput,
  MemoryItem,
  MemoryRevision,
  MemorySourceItem,
  RelatedMemoriesResponse,
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

export async function getMemoryGraph(): Promise<MemoryGraph> {
  return handle<MemoryGraph>(await fetch("/api/memory/graph"));
}

export async function getRelatedMemories(
  memoryId: number
): Promise<RelatedMemoriesResponse> {
  return handle<RelatedMemoriesResponse>(
    await fetch(`/api/memory/${memoryId}/related`)
  );
}

export async function getMemorySources(
  memoryId: number
): Promise<MemorySourceItem[]> {
  return handle<MemorySourceItem[]>(
    await fetch(`/api/memory/${memoryId}/sources`)
  );
}

export async function getBrainSettings(): Promise<BrainSettings> {
  return handle<BrainSettings>(await fetch("/api/memory/brain/settings"));
}

export async function updateBrainSettings(
  input: BrainSettingsUpdate
): Promise<BrainSettings> {
  return handle<BrainSettings>(
    await fetch("/api/memory/brain/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    })
  );
}

export async function triggerBrainRun(): Promise<BrainRunTrigger> {
  return handle<BrainRunTrigger>(
    await fetch("/api/memory/brain/run", { method: "POST" })
  );
}
