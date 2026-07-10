"use client";

import { useMemo, useState } from "react";
import type { Route } from "next";
import { Button, InputTypeIn, Tabs, Tag, Text } from "@opal/components";
import { IllustrationContent, SettingsLayouts } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import {
  SvgArrowRight,
  SvgClock,
  SvgFileChartPie,
  SvgPin,
  SvgPinned,
  SvgSimpleLoader,
  SvgSparkle,
  SvgWorkflow,
} from "@opal/icons";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import type { ScheduledTaskTemplateCategory } from "@/app/craft/v1/tasks/task-starters";
import { SEARCH_PARAM_NAMES } from "@/app/app/services/searchParams";
import {
  newTaskFromTemplatePath,
  TASKS_PATH,
} from "@/app/craft/v1/tasks/constants";
import { pinWorkflow, unpinWorkflow } from "@/lib/workflows/api";
import { useWorkflowPins } from "@/lib/workflows/hooks";
import {
  WORKFLOW_CATALOG,
  type WorkflowCatalogItem,
} from "@/lib/workflows/catalog";
import { toast } from "@/hooks/useToast";

type CatalogScope = "browse" | "pinned";
type CategoryFilter = "All" | ScheduledTaskTemplateCategory;

const FEATURED_IDS = new Set([
  "sharepoint-change-digest",
  "compliance-monitor",
  "weekly-status-review",
]);

interface WorkflowCardProps {
  workflow: WorkflowCatalogItem;
  pinned: boolean;
  busy: boolean;
  onTogglePin: (workflow: WorkflowCatalogItem) => void;
}

function workflowLaunchPath(workflow: WorkflowCatalogItem): Route {
  return workflow.execution === "scheduled"
    ? newTaskFromTemplatePath(workflow.id)
    : (`/app?${SEARCH_PARAM_NAMES.USER_PROMPT}=${encodeURIComponent(workflow.prompt)}` as Route);
}

function WorkflowCard({
  workflow,
  pinned,
  busy,
  onTogglePin,
}: WorkflowCardProps) {
  return (
    <article className="flex min-h-52 flex-col rounded-08 border border-border-01 bg-background-01 p-4 transition-colors hover:bg-background-tint-01">
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-08 bg-background-tint-02">
          <SvgFileChartPie className="h-5 w-5 stroke-text-03" />
        </div>
        <Button
          icon={pinned ? SvgPinned : SvgPin}
          prominence="tertiary"
          size="xs"
          tooltip={pinned ? "Unpin workflow" : "Pin workflow"}
          disabled={busy}
          onClick={() => onTogglePin(workflow)}
        />
      </div>
      <div className="mt-4 min-w-0 flex-1">
        <Text font="heading-h3" color="text-05" maxLines={2}>
          {workflow.name}
        </Text>
        <div className="mt-1">
          <Text font="secondary-body" color="text-03" maxLines={4}>
            {workflow.description}
          </Text>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1">
          <Tag color="gray" title={workflow.category} />
          <Tag
            color={workflow.execution === "scheduled" ? "blue" : "gray"}
            title={workflow.execution === "scheduled" ? "Recurring" : "Guided"}
          />
        </div>
        <Button
          href={workflowLaunchPath(workflow)}
          icon={workflow.execution === "scheduled" ? SvgClock : SvgArrowRight}
          prominence="secondary"
          size="sm"
        >
          {workflow.execution === "scheduled" ? "Schedule" : "Start"}
        </Button>
      </div>
    </article>
  );
}

export default function WorkflowCatalogPage() {
  const { data: pinData, isLoading: pinsLoading, mutate } = useWorkflowPins();
  const [scope, setScope] = useState<CatalogScope>("browse");
  const [category, setCategory] = useState<CategoryFilter>("All");
  const [query, setQuery] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const pinnedIds = useMemo(
    () => new Set(pinData?.workflow_ids ?? []),
    [pinData?.workflow_ids]
  );
  const categories = useMemo(
    () => [
      "All" as const,
      ...Array.from(
        new Set(WORKFLOW_CATALOG.map((item) => item.category))
      ).sort(),
    ],
    []
  );
  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return WORKFLOW_CATALOG.filter((workflow) => {
      const matchesScope = scope === "browse" || pinnedIds.has(workflow.id);
      const matchesCategory =
        category === "All" || workflow.category === category;
      const matchesQuery =
        !normalized ||
        workflow.name.toLowerCase().includes(normalized) ||
        workflow.description.toLowerCase().includes(normalized);
      return matchesScope && matchesCategory && matchesQuery;
    });
  }, [category, pinnedIds, query, scope]);
  const recommended = useMemo(
    () =>
      filtered.filter((workflow) => FEATURED_IDS.has(workflow.id)).slice(0, 3),
    [filtered]
  );
  const grouped = useMemo(() => {
    const groups = new Map<
      ScheduledTaskTemplateCategory,
      WorkflowCatalogItem[]
    >();
    for (const workflow of filtered) {
      if (recommended.some((item) => item.id === workflow.id)) continue;
      const values = groups.get(workflow.category) ?? [];
      values.push(workflow);
      groups.set(workflow.category, values);
    }
    return [...groups.entries()];
  }, [filtered, recommended]);

  async function togglePin(workflow: WorkflowCatalogItem) {
    setBusyId(workflow.id);
    const wasPinned = pinnedIds.has(workflow.id);
    const optimisticIds = wasPinned
      ? [...pinnedIds].filter((id) => id !== workflow.id)
      : [...pinnedIds, workflow.id];
    await mutate({ workflow_ids: optimisticIds }, { revalidate: false });
    try {
      if (wasPinned) await unpinWorkflow(workflow.id);
      else await pinWorkflow(workflow.id);
      await mutate();
    } catch (error) {
      await mutate();
      toast.error(
        error instanceof Error ? error.message : "Workflow pin update failed."
      );
    } finally {
      setBusyId(null);
    }
  }

  const renderGrid = (workflows: WorkflowCatalogItem[]) => (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      {workflows.map((workflow) => (
        <WorkflowCard
          key={workflow.id}
          workflow={workflow}
          pinned={pinnedIds.has(workflow.id)}
          busy={busyId === workflow.id}
          onTogglePin={(item) => void togglePin(item)}
        />
      ))}
    </div>
  );

  return (
    <SettingsLayouts.Root width="full">
      <SettingsLayouts.Header
        icon={SvgWorkflow}
        title="Workflows"
        description="Start guided work or schedule recurring, reviewable automations."
        rightChildren={
          <div className="hidden sm:block">
            <Button href={TASKS_PATH} icon={SvgClock} prominence="secondary">
              Scheduled workflows
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-2">
          <div className="sm:hidden">
            <Button href={TASKS_PATH} icon={SvgClock} prominence="secondary">
              Scheduled workflows
            </Button>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="w-full shrink-0 sm:w-64">
              <Tabs
                value={scope}
                onValueChange={(value) => setScope(value as CatalogScope)}
              >
                <Tabs.List>
                  <Tabs.Trigger value="browse">Browse</Tabs.Trigger>
                  <Tabs.Trigger value="pinned">Pinned</Tabs.Trigger>
                </Tabs.List>
              </Tabs>
            </div>
            <div className="min-w-0 flex-1">
              <InputTypeIn
                clearButton
                placeholder="Search workflows"
                searchIcon
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            <div className="w-full sm:w-52">
              <InputSelect
                value={category}
                onValueChange={(value) => setCategory(value as CategoryFilter)}
              >
                <InputSelect.Trigger>{category}</InputSelect.Trigger>
                <InputSelect.Content>
                  {categories.map((value) => (
                    <InputSelect.Item key={value} value={value}>
                      {value}
                    </InputSelect.Item>
                  ))}
                </InputSelect.Content>
              </InputSelect>
            </div>
          </div>
        </div>
      </SettingsLayouts.Header>
      <SettingsLayouts.Body>
        {pinsLoading ? (
          <div className="flex justify-center py-16">
            <SvgSimpleLoader className="h-6 w-6" />
          </div>
        ) : filtered.length === 0 ? (
          <IllustrationContent
            illustration={SvgNoResult}
            title={
              scope === "pinned" ? "No pinned workflows" : "No workflows found"
            }
            description={
              scope === "pinned"
                ? "Pin workflows you use often to keep them close at hand."
                : "Try a different search or category."
            }
          />
        ) : (
          <div className="flex w-full flex-col gap-8">
            {recommended.length > 0 ? (
              <section className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <SvgSparkle className="h-4 w-4 stroke-text-03" />
                  <Text font="heading-h3" color="text-05">
                    Recommended
                  </Text>
                </div>
                {renderGrid(recommended)}
              </section>
            ) : null}
            {grouped.map(([groupCategory, workflows]) => (
              <section key={groupCategory} className="flex flex-col gap-3">
                <Text font="heading-h3" color="text-05">
                  {groupCategory}
                </Text>
                {renderGrid(workflows)}
              </section>
            ))}
          </div>
        )}
      </SettingsLayouts.Body>
    </SettingsLayouts.Root>
  );
}
