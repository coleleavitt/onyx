"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import type { MemoryListResponse } from "@/lib/memory/types";

export const MEMORY_LIST_KEY = "/api/memory";

export function useMemoryLibrary() {
  const result = useSWR<MemoryListResponse>(
    MEMORY_LIST_KEY,
    errorHandlingFetcher,
    { revalidateOnFocus: false }
  );
  return {
    ...result,
    memories: result.data?.items ?? [],
  };
}

/** SWR key for the memories scoped to a single space (project). */
export function spaceMemoryListKey(projectId: number): string {
  return `${MEMORY_LIST_KEY}?project_id=${projectId}`;
}

/**
 * List memories scoped to a single space via `/api/memory?project_id=...`.
 * Pass `null` to skip fetching (e.g. before a space is selected).
 */
export function useSpaceMemories(projectId: number | null) {
  const result = useSWR<MemoryListResponse>(
    projectId !== null ? spaceMemoryListKey(projectId) : null,
    errorHandlingFetcher,
    { revalidateOnFocus: false }
  );
  return {
    ...result,
    memories: result.data?.items ?? [],
  };
}
