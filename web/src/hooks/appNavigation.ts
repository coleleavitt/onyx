"use client";

import { SEARCH_PARAM_NAMES } from "@/app/app/services/searchParams";
import { useRouter, useSearchParams } from "next/navigation";
import type { Route } from "next";
import { useCallback } from "react";
import { spacePath } from "@/lib/projects/slug";

interface UseAppRouterProps {
  chatSessionId?: string;
  agentId?: number;
  projectId?: number;
  projectName?: string | null;
}

export function useAppRouter() {
  const router = useRouter();
  return useCallback(
    ({
      chatSessionId,
      agentId,
      projectId,
      projectName,
    }: UseAppRouterProps = {}) => {
      // Spaces have a canonical pretty path (/app/spaces/{slug}-{id}); other
      // focuses stay on /app with a query param.
      if (!chatSessionId && !agentId && projectId) {
        router.push(spacePath(projectId, projectName));
        return;
      }

      const finalParams = [];
      if (chatSessionId)
        finalParams.push(`${SEARCH_PARAM_NAMES.CHAT_ID}=${chatSessionId}`);
      else if (agentId)
        finalParams.push(`${SEARCH_PARAM_NAMES.PERSONA_ID}=${agentId}`);

      const finalString = finalParams.join("&");
      const finalUrl = `/app?${finalString}`;

      router.push(finalUrl as Route);
    },
    [router]
  );
}

export function useAppParams() {
  const searchParams = useSearchParams();
  return useCallback((name: string) => searchParams.get(name), [searchParams]);
}
