"use client";

import type { Route } from "next";
import { Button, Tag, Text } from "@opal/components";
import {
  SvgArrowRight,
  SvgClock,
  SvgFileChartPie,
  SvgPin,
  SvgPinned,
} from "@opal/icons";
import { Card } from "@/refresh-components/cards";
import { SEARCH_PARAM_NAMES } from "@/app/app/services/searchParams";
import { newTaskFromTemplatePath } from "@/app/craft/v1/tasks/constants";
import type { WorkflowCatalogItem } from "@/lib/workflows/catalog";

export interface WorkflowCardProps {
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

export default function WorkflowCard({
  workflow,
  pinned,
  busy,
  onTogglePin,
}: WorkflowCardProps) {
  const isScheduled = workflow.execution === "scheduled";

  return (
    <article className="h-full">
      <Card className="h-full" height="full" padding={0} gap={0}>
        <div className="flex min-h-36 w-full flex-col p-3">
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-08 bg-background-tint-02">
              <SvgFileChartPie className="h-4 w-4 stroke-text-03" />
            </div>
            <div className="min-w-0 flex-1">
              <Text font="main-ui-body" color="text-05" maxLines={1}>
                {workflow.name}
              </Text>
              <Text font="secondary-body" color="text-03" maxLines={2}>
                {workflow.description}
              </Text>
            </div>
            <Button
              icon={pinned ? SvgPinned : SvgPin}
              prominence="tertiary"
              size="sm"
              tooltip={pinned ? "Unpin workflow" : "Pin workflow"}
              aria-label={pinned ? "Unpin workflow" : "Pin workflow"}
              disabled={busy}
              onClick={() => onTogglePin(workflow)}
            />
          </div>

          <div className="flex flex-1 items-end pt-3">
            <div className="flex w-full items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-1">
                <Tag color="gray" title={workflow.category} />
                <Tag
                  color={isScheduled ? "blue" : "gray"}
                  title={isScheduled ? "Recurring" : "Guided"}
                />
              </div>
              <Button
                href={workflowLaunchPath(workflow)}
                rightIcon={isScheduled ? SvgClock : SvgArrowRight}
                prominence="secondary"
                size="sm"
              >
                {isScheduled ? "Schedule" : "Start"}
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </article>
  );
}
