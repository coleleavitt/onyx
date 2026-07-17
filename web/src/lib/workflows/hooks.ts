"use client";

import useSWR from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { useSettings } from "@/lib/settings/hooks";
import type { WorkflowPinsResponse } from "@/lib/workflows/api";

export const WORKFLOW_PINS_KEY = "/api/build/workflow-catalog/pins";

export function useWorkflowPins() {
  const settings = useSettings();
  return useSWR<WorkflowPinsResponse>(
    settings.onyx_craft_enabled === true ? WORKFLOW_PINS_KEY : null,
    errorHandlingFetcher,
    { revalidateOnFocus: false }
  );
}
