"use client";

import { formatDistanceToNow } from "date-fns";
import { Text } from "@opal/components";
import { Interactive } from "@opal/core";
import { SvgBookOpen } from "@opal/icons";
import { Card } from "@/refresh-components/cards";
import type { MemoryCategory, MemoryItem } from "@/lib/memory/types";

const CATEGORY_LABELS: Record<MemoryCategory, string> = {
  notes: "Notes",
  concepts: "Concepts",
  entities: "Entities",
  workstreams: "Workstreams",
};

export interface MemoryCardProps {
  memory: MemoryItem;
  view: "grid" | "list";
  onClick: (memory: MemoryItem) => void;
}

function updatedLabel(memory: MemoryItem): string {
  return formatDistanceToNow(new Date(memory.updated_at), { addSuffix: true });
}

export default function MemoryCard({ memory, view, onClick }: MemoryCardProps) {
  if (view === "list") {
    return (
      <Interactive.Stateless
        prominence="internal"
        type="button"
        onClick={() => onClick(memory)}
      >
        <Interactive.Container type="button" size="fit" width="full">
          <div className="flex w-full items-start gap-4 px-2 py-4 text-left transition-colors hover:bg-background-tint-01">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-08 bg-background-tint-02">
              <SvgBookOpen className="h-4 w-4 stroke-text-03" />
            </div>
            <div className="min-w-0 flex-1">
              <Text font="main-ui-body" color="text-05" maxLines={1}>
                {memory.title}
              </Text>
              <Text font="secondary-body" color="text-03" maxLines={2}>
                {memory.content}
              </Text>
            </div>
            <div className="hidden shrink-0 flex-col items-end sm:flex">
              <Text font="secondary-body" color="text-03">
                {CATEGORY_LABELS[memory.category]}
              </Text>
              <Text font="secondary-body" color="text-02">
                {updatedLabel(memory)}
              </Text>
            </div>
          </div>
        </Interactive.Container>
      </Interactive.Stateless>
    );
  }

  return (
    <Interactive.Stateless
      prominence="internal"
      type="button"
      onClick={() => onClick(memory)}
      group="group/MemoryCard"
    >
      <Interactive.Container type="button" size="fit" width="full">
        <Card
          height="full"
          padding={1}
          className="min-h-48 text-left transition-colors group-hover/MemoryCard:bg-background-tint-01"
        >
          <div className="flex w-full items-center justify-between gap-2">
            <Text font="secondary-body" color="text-03">
              {CATEGORY_LABELS[memory.category]}
            </Text>
            <Text font="secondary-body" color="text-02">
              {updatedLabel(memory)}
            </Text>
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-2 pt-3">
            <Text font="heading-h3" color="text-05" maxLines={2}>
              {memory.title}
            </Text>
            <Text font="secondary-body" color="text-03" maxLines={5}>
              {memory.content}
            </Text>
          </div>
        </Card>
      </Interactive.Container>
    </Interactive.Stateless>
  );
}
