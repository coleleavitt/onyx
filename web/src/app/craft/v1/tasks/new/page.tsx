"use client";

import { useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { Button, Text } from "@opal/components";
import { SvgClock, SvgRefreshCw, SvgSimpleLoader } from "@opal/icons";
import { SettingsLayouts } from "@opal/layouts";
import type { BackendChatSession } from "@/app/app/interfaces";
import ScheduleTaskForm, {
  defaultFormInitial,
  type ScheduleTaskFormInitial,
} from "@/app/craft/v1/tasks/components/ScheduleTaskForm";
import type {
  EditorMode,
  EditorPayload,
} from "@/app/craft/v1/tasks/interfaces";
import { TASKS_PATH } from "@/app/craft/v1/tasks/constants";
import {
  buildChatTaskStarter,
  getScheduledTaskTemplate,
} from "@/app/craft/v1/tasks/task-starters";
import { errorHandlingFetcher } from "@/lib/fetcher";

const VALID_MODES: ReadonlySet<EditorMode> = new Set<EditorMode>([
  "interval",
  "daily_weekly",
]);

export default function NewScheduledTaskPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sourceChatId = searchParams?.get("source_chat_id") ?? null;
  const {
    data: sourceChatSession,
    error: sourceChatError,
    isLoading: sourceChatLoading,
    mutate: reloadSourceChat,
  } = useSWR<BackendChatSession>(
    sourceChatId ? `/api/chat/get-chat-session/${sourceChatId}` : null,
    errorHandlingFetcher,
    { revalidateOnFocus: false }
  );
  const handleBack = useCallback(() => {
    router.push(TASKS_PATH);
  }, [router]);

  const initial: ScheduleTaskFormInitial = useMemo(() => {
    const base = defaultFormInitial();
    const starter = searchParams?.get("starter") ?? null;
    const promptParam = searchParams?.get("prompt") ?? null;
    const modeParam = searchParams?.get("mode") ?? null;
    const payloadParam = searchParams?.get("payload") ?? null;
    const template = getScheduledTaskTemplate(
      searchParams?.get("template") ?? null
    );

    let mode: EditorMode = template?.mode ?? base.mode;
    if (modeParam && VALID_MODES.has(modeParam as EditorMode)) {
      mode = modeParam as EditorMode;
    }

    let payload: EditorPayload = template?.payload ?? base.payload;
    if (payloadParam) {
      try {
        const parsed = JSON.parse(payloadParam) as EditorPayload;
        payload = parsed;
      } catch {
        // ignore — fall back to defaults
      }
    }

    const chatStarter = sourceChatSession
      ? buildChatTaskStarter(sourceChatSession)
      : null;

    return {
      ...base,
      name: chatStarter?.name ?? starter ?? template?.name ?? "",
      prompt: chatStarter?.prompt ?? promptParam ?? template?.prompt ?? "",
      mode,
      payload,
    };
  }, [searchParams, sourceChatSession]);

  if (sourceChatId && sourceChatLoading) {
    return (
      <SettingsLayouts.Root>
        <SettingsLayouts.Header
          backButton={handleBack}
          divider
          icon={SvgClock}
          title="New Scheduled Task"
          description="Preparing an editable task from this conversation."
        />
        <SettingsLayouts.Body>
          <div className="flex items-center justify-center py-12">
            <SvgSimpleLoader className="h-6 w-6" />
          </div>
        </SettingsLayouts.Body>
      </SettingsLayouts.Root>
    );
  }

  if (sourceChatId && sourceChatError) {
    return (
      <SettingsLayouts.Root>
        <SettingsLayouts.Header
          backButton={handleBack}
          divider
          icon={SvgClock}
          title="New Scheduled Task"
          description="The source conversation could not be loaded."
        />
        <SettingsLayouts.Body>
          <div className="flex flex-col items-start gap-2 py-6">
            <Text color="text-03" font="main-ui-body">
              Confirm that the conversation still exists and that you can access
              it, then try again.
            </Text>
            <Button
              icon={SvgRefreshCw}
              prominence="secondary"
              onClick={() => void reloadSourceChat()}
            >
              Try again
            </Button>
          </div>
        </SettingsLayouts.Body>
      </SettingsLayouts.Root>
    );
  }

  return (
    <ScheduleTaskForm
      initial={initial}
      isEdit={false}
      title="New Scheduled Task"
      description={
        sourceChatSession
          ? "Review the workflow extracted from this conversation, then choose when Craft should run it."
          : "Save a prompt + schedule. Craft will run it on a timer."
      }
      onBack={handleBack}
    />
  );
}
