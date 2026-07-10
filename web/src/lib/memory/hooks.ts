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
