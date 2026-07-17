"use client";

import { useCallback, useMemo, useState } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { SettingsLayouts, toast } from "@opal/layouts";
import { Section } from "@/layouts/general-layouts";
import {
  Button,
  Table,
  Text,
  Tooltip,
  createTableColumns,
} from "@opal/components";
import { IllustrationContent } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import ConfirmationModalLayout from "@/refresh-components/layouts/ConfirmationModalLayout";
import {
  SvgClock,
  SvgArrowRight,
  SvgPlus,
  SvgRefreshCw,
  SvgSparkle,
  SvgTrash,
  SvgSimpleLoader,
} from "@opal/icons";
import { deleteScheduledTask } from "@/app/craft/v1/tasks/api";
import {
  RunStatusBadge,
  TaskStatusBadge,
} from "@/app/craft/v1/tasks/components/StatusBadge";
import {
  NEW_TASK_PATH,
  TASK_TEMPLATES_PATH,
  TASKS_PAGE_SIZE,
  taskDetailPath,
} from "@/app/craft/v1/tasks/constants";
import type {
  ScheduledTaskListItem,
  ScheduledTaskListResponse,
} from "@/app/craft/v1/tasks/interfaces";
import {
  formatAbsolute,
  formatRelativeShort,
} from "@/app/craft/v1/tasks/utils";
import { humanReadableScheduleFromCron } from "@/app/craft/v1/tasks/schedule";
import { SWR_KEYS } from "@/lib/swr-keys";
import { errorHandlingFetcher } from "@/lib/fetcher";

const tc = createTableColumns<ScheduledTaskListItem>();

interface RowActionHandlers {
  busyTaskId: string | null;
  onDelete: (task: ScheduledTaskListItem) => void;
}

function buildColumns(handlers: RowActionHandlers) {
  return [
    tc.column("name", {
      header: "Name",
      weight: 25,
      enableSorting: false,
      cell: (value) => (
        <Text font="main-ui-body" color="text-05" nowrap>
          {value}
        </Text>
      ),
    }),
    tc.column("human_readable_schedule", {
      header: "Schedule",
      weight: 22,
      enableSorting: false,
      cell: (value) => (
        <Text font="main-ui-body" color="text-03" nowrap>
          {value}
        </Text>
      ),
    }),
    tc.column("status", {
      header: "Status",
      weight: 12,
      enableSorting: false,
      cell: (status) => <TaskStatusBadge status={status} />,
    }),
    tc.column("last_run", {
      header: "Last run",
      weight: 18,
      enableSorting: false,
      cell: (lastRun) => {
        if (!lastRun) {
          return (
            <Text font="main-ui-body" color="text-03">
              —
            </Text>
          );
        }
        return (
          <div className="flex flex-col gap-0.5">
            <RunStatusBadge status={lastRun.status} />
            <Text font="secondary-body" color="text-03">
              {formatRelativeShort(lastRun.started_at)}
            </Text>
          </div>
        );
      },
    }),
    tc.column("next_run_at", {
      header: "Next run",
      weight: 13,
      enableSorting: false,
      cell: (nextRunAt) => {
        if (!nextRunAt) {
          return (
            <Text font="main-ui-body" color="text-03">
              —
            </Text>
          );
        }
        return (
          <Tooltip tooltip={formatAbsolute(nextRunAt)} side="top">
            <Text font="main-ui-body" color="text-03" nowrap>
              {formatRelativeShort(nextRunAt)}
            </Text>
          </Tooltip>
        );
      },
    }),
    tc.actions({
      showColumnVisibility: false,
      showSorting: false,
      cell: (task) => <TaskRowActions task={task} handlers={handlers} />,
    }),
  ];
}

export default function ScheduledTasksListPage() {
  const router = useRouter();
  const { data, error, isLoading, mutate } = useSWR<ScheduledTaskListResponse>(
    SWR_KEYS.scheduledTasks,
    errorHandlingFetcher,
    { revalidateOnFocus: false }
  );
  const tasks = useMemo<ScheduledTaskListItem[]>(
    () =>
      data?.items.map((task) => ({
        ...task,
        human_readable_schedule: humanReadableScheduleFromCron(
          task.editor_mode,
          task.cron_expression
        ),
      })) ?? [],
    [data?.items]
  );
  const [pendingDelete, setPendingDelete] =
    useState<ScheduledTaskListItem | null>(null);
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    void mutate();
  }, [mutate]);

  const handleDelete = useCallback(async () => {
    if (!pendingDelete) return;
    setBusyTaskId(pendingDelete.id);
    try {
      await deleteScheduledTask(pendingDelete.id);
      toast.success(`Deleted "${pendingDelete.name}".`);
      setPendingDelete(null);
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete task");
    } finally {
      setBusyTaskId(null);
    }
  }, [pendingDelete, refresh]);

  const columns = useMemo(
    () =>
      buildColumns({
        busyTaskId,
        onDelete: (task) => setPendingDelete(task),
      }),
    [busyTaskId]
  );

  const renderHeaderActions = () => (
    <div className="flex w-full items-center gap-2 md:w-auto">
      <Button
        variant="default"
        prominence="secondary"
        icon={SvgSparkle}
        href={TASK_TEMPLATES_PATH}
      >
        Templates
      </Button>
      <Button
        variant="default"
        prominence="primary"
        icon={SvgPlus}
        href={NEW_TASK_PATH}
        data-testid="new-task-button"
      >
        New workflow
      </Button>
    </div>
  );

  return (
    <SettingsLayouts.Root>
      <SettingsLayouts.Header
        icon={SvgClock}
        title="Workflows"
        description="Run reusable Craft prompts on a schedule and review every execution."
        rightChildren={
          <div className="hidden md:block">{renderHeaderActions()}</div>
        }
      >
        <div className="md:hidden">{renderHeaderActions()}</div>
      </SettingsLayouts.Header>
      <SettingsLayouts.Body>
        {isLoading ? (
          <div className="flex justify-center py-12">
            <SvgSimpleLoader className="h-6 w-6" />
          </div>
        ) : error ? (
          <Section gap={0.5}>
            <Text font="main-ui-body" color="text-03">
              Failed to load scheduled tasks.
            </Text>
            <Button
              variant="default"
              prominence="secondary"
              icon={SvgRefreshCw}
              onClick={refresh}
            >
              Try again
            </Button>
          </Section>
        ) : tasks.length === 0 ? (
          <IllustrationContent
            illustration={SvgNoResult}
            title="No workflows found"
            description="Create a workflow from a template or schedule a new one."
          />
        ) : (
          <>
            <div className="hidden md:block">
              <Table
                data={tasks}
                columns={columns}
                getRowId={(row) => row.id}
                pageSize={Math.min(tasks.length, TASKS_PAGE_SIZE)}
                selectionBehavior="single-select"
                onRowClick={(row) => router.push(taskDetailPath(row.id))}
                emptyState={
                  <IllustrationContent
                    illustration={SvgNoResult}
                    title="No workflows found"
                    description="Create a workflow from a template or schedule a new one."
                  />
                }
              />
            </div>
            <div className="flex w-full flex-col gap-3 md:hidden">
              {tasks.map((task) => (
                <article
                  key={task.id}
                  className="flex flex-col gap-3 rounded-08 border border-border-01 bg-background-01 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <Text font="main-ui-body" color="text-05" maxLines={2}>
                        {task.name}
                      </Text>
                      <Text font="secondary-body" color="text-03" maxLines={2}>
                        {task.human_readable_schedule}
                      </Text>
                    </div>
                    <TaskStatusBadge status={task.status} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <Text font="secondary-body" color="text-02">
                        Last run
                      </Text>
                      {task.last_run ? (
                        <div className="flex flex-wrap items-center gap-1">
                          <RunStatusBadge status={task.last_run.status} />
                          <Text font="secondary-body" color="text-03">
                            {formatRelativeShort(task.last_run.started_at)}
                          </Text>
                        </div>
                      ) : (
                        <Text font="secondary-body" color="text-03">
                          Not run
                        </Text>
                      )}
                    </div>
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <Text font="secondary-body" color="text-02">
                        Next run
                      </Text>
                      <Text font="secondary-body" color="text-03" maxLines={1}>
                        {task.next_run_at
                          ? formatRelativeShort(task.next_run_at)
                          : "Not scheduled"}
                      </Text>
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      icon={SvgTrash}
                      variant="danger"
                      prominence="tertiary"
                      size="sm"
                      tooltip="Delete workflow"
                      onClick={() => setPendingDelete(task)}
                      disabled={busyTaskId === task.id}
                    />
                    <Button
                      rightIcon={SvgArrowRight}
                      prominence="secondary"
                      size="sm"
                      onClick={() => router.push(taskDetailPath(task.id))}
                    >
                      Open
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </SettingsLayouts.Body>

      {pendingDelete && (
        <ConfirmationModalLayout
          icon={SvgTrash}
          title={`Delete "${pendingDelete.name}"?`}
          description="This stops future runs and removes the task. Past run history (and the underlying sessions) will be preserved for audit."
          onClose={() => setPendingDelete(null)}
          submit={
            <Button
              variant="danger"
              prominence="primary"
              onClick={() => void handleDelete()}
              disabled={busyTaskId === pendingDelete.id}
              data-testid="confirm-delete-task"
            >
              {busyTaskId === pendingDelete.id ? "Deleting..." : "Delete"}
            </Button>
          }
        />
      )}
    </SettingsLayouts.Root>
  );
}

// ---------------------------------------------------------------------------
// Row actions
// ---------------------------------------------------------------------------

interface TaskRowActionsProps {
  task: ScheduledTaskListItem;
  handlers: RowActionHandlers;
}

function TaskRowActions({ task, handlers }: TaskRowActionsProps) {
  const disabled = handlers.busyTaskId === task.id;
  return (
    <div className="flex items-center gap-0.5">
      <Tooltip tooltip="Delete" side="top">
        <Button
          icon={SvgTrash}
          variant="danger"
          prominence="tertiary"
          size="sm"
          onClick={() => handlers.onDelete(task)}
          disabled={disabled}
          data-testid={`row-delete-${task.id}`}
        />
      </Tooltip>
    </div>
  );
}
