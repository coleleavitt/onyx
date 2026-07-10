"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import type { WorkflowPinsResponse } from "@/lib/workflows/api";

export const WORKFLOW_PINS_KEY = "/api/build/workflow-catalog/pins";

export function useWorkflowPins() {
  return useSWR<WorkflowPinsResponse>(WORKFLOW_PINS_KEY, errorHandlingFetcher, {
    revalidateOnFocus: false,
  });
}
