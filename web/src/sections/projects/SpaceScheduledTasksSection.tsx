"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import { Button, Text } from "@opal/components";
import { ContentAction } from "@opal/layouts";
import { SvgChevronRight, SvgClock, SvgPlusCircle } from "@opal/icons";
import { cn } from "@opal/utils";
import { SWR_KEYS } from "@/lib/swr-keys";
import { errorHandlingFetcher } from "@/lib/fetcher";
import type {
  ScheduledTaskListItem,
  ScheduledTaskListResponse,
} from "@/app/craft/v1/tasks/interfaces";
import {
  filterTasksForSpace,
  partitionTasksByStatus,
  spaceTaskTag,
  stripSpaceTag,
} from "@/lib/projects/spaceScheduledTasks";

interface SpaceScheduledTasksSectionProps {
  projectId: number;
  canEdit: boolean;
  compact?: boolean;
}

function TaskRow({ task }: { task: ScheduledTaskListItem }) {
  return (
    <div className="flex items-center gap-2 rounded-12 border border-border-01 bg-background-tint-02 px-3 py-2">
      <SvgClock className="h-4 w-4 shrink-0 stroke-text-03" />
      <div className="flex min-w-0 flex-1 flex-col">
        <Text font="main-ui-body" color="text-05" nowrap>
          {stripSpaceTag(task.name)}
        </Text>
        <Text font="secondary-body" color="text-03" nowrap>
          {task.human_readable_schedule}
        </Text>
      </div>
    </div>
  );
}

/**
 * Scheduled Tasks section for the Space rail. Lists the recurring tasks scoped
 * to this space (active + collapsible paused group) from the existing
 * scheduled-tasks data path, and offers an affordance to create one pre-scoped
 * to the current space.
 *
 * Tasks carry no backend project id, so space scoping uses the `[space:{id}]`
 * name tag (see `spaceScheduledTasks.ts`); the create affordance prefills a
 * tagged name.
 */
export default function SpaceScheduledTasksSection({
  projectId,
  canEdit,
  compact = false,
}: SpaceScheduledTasksSectionProps) {
  const router = useRouter();
  const [showPaused, setShowPaused] = useState(false);
  const { data, isLoading } = useSWR<ScheduledTaskListResponse>(
    SWR_KEYS.scheduledTasks,
    errorHandlingFetcher,
    { revalidateOnFocus: false },
  );

  const { active, paused } = useMemo(() => {
    const forSpace = filterTasksForSpace(data?.items ?? [], projectId);
    return partitionTasksByStatus(forSpace);
  }, [data?.items, projectId]);

  function createForSpace() {
    // Prefill the new-task form with a space-tagged name so the created task is
    // associated with this space.
    const starter = encodeURIComponent(spaceTaskTag(projectId));
    router.push(`/app/craft/v1/tasks/new?starter=${starter}` as Route);
  }

  const hasAny = active.length > 0 || paused.length > 0;

  return (
    <div className="flex flex-col gap-2">
      <ContentAction
        sizePreset="main-ui"
        variant="section"
        title="Scheduled Tasks"
        description={
          compact
            ? undefined
            : "Recurring tasks that run on a schedule for this space."
        }
        padding="fit"
        center
        rightChildren={
          canEdit ? (
            <Button
              icon={SvgPlusCircle}
              prominence="tertiary"
              aria-label="Create scheduled task"
              tooltip={compact ? "Create scheduled task" : undefined}
              tooltipSide="bottom"
              onClick={createForSpace}
            >
              {compact ? undefined : "Create scheduled task"}
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <div className="flex min-h-12 items-center rounded-12 border border-dashed border-border-01 px-3 py-2.5">
          <Text as="p" font="secondary-body" color="text-03">
            Loading scheduled tasks…
          </Text>
        </div>
      ) : hasAny ? (
        <div className="flex flex-col gap-1.5">
          {active.map((task) => (
            <TaskRow key={task.id} task={task} />
          ))}

          {paused.length > 0 ? (
            <>
              <button
                type="button"
                aria-expanded={showPaused}
                onClick={() => setShowPaused((prev) => !prev)}
                className="flex items-center gap-1.5 rounded-08 px-1 py-1 text-left transition-colors hover:bg-background-tint-01"
              >
                <SvgChevronRight
                  className={cn(
                    "h-3.5 w-3.5 shrink-0 stroke-text-03 transition-transform",
                    showPaused && "rotate-90",
                  )}
                />
                <Text font="secondary-action" color="text-03">
                  {`Paused (${paused.length})`}
                </Text>
              </button>
              {showPaused
                ? paused.map((task) => <TaskRow key={task.id} task={task} />)
                : null}
            </>
          ) : null}
        </div>
      ) : (
        <div className="flex min-h-12 items-center rounded-12 border border-dashed border-border-01 px-3 py-2.5">
          <Text as="p" font="secondary-body" color="text-03">
            {canEdit
              ? "No scheduled tasks for this space yet."
              : "No scheduled tasks in this space yet."}
          </Text>
        </div>
      )}
    </div>
  );
}
