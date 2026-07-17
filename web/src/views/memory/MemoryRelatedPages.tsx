"use client";

import useSWR from "swr";
import type { IconFunctionComponent } from "@opal/types";
import { Text } from "@opal/components";
import { SvgFolder, SvgLightbulbSimple, SvgMenu, SvgUsers } from "@opal/icons";
import { getRelatedMemories } from "@/lib/memory/api";
import type { MemoryCategory, RelatedMemory } from "@/lib/memory/types";

const CATEGORY_ORDER: readonly MemoryCategory[] = [
  "entities",
  "concepts",
  "workstreams",
  "notes",
];

const CATEGORY_META: Record<
  MemoryCategory,
  { label: string; icon: IconFunctionComponent }
> = {
  entities: { label: "Entities", icon: SvgUsers },
  concepts: { label: "Concepts", icon: SvgLightbulbSimple },
  workstreams: { label: "Workstreams", icon: SvgFolder },
  notes: { label: "Notes", icon: SvgMenu },
};

interface MemoryRelatedPagesProps {
  memoryId: number;
}

export default function MemoryRelatedPages({
  memoryId,
}: MemoryRelatedPagesProps) {
  const { data } = useSWR(
    `/api/memory/${memoryId}/related`,
    () => getRelatedMemories(memoryId),
    { revalidateOnFocus: false }
  );

  const groups = data?.groups;
  const nonEmptyCategories = groups
    ? CATEGORY_ORDER.filter((category) => (groups[category]?.length ?? 0) > 0)
    : [];

  return (
    <div className="flex w-full flex-col gap-2">
      <Text font="main-ui-action" color="text-05">
        Related pages
      </Text>
      {data && nonEmptyCategories.length === 0 ? (
        <Text font="secondary-body" color="text-03">
          No linked pages yet.
        </Text>
      ) : (
        <div className="flex flex-col gap-3">
          {nonEmptyCategories.map((category) => {
            const items = (groups?.[category] ?? []) as RelatedMemory[];
            const { label, icon: Icon } = CATEGORY_META[category];
            return (
              <div key={category} className="flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  <Icon className="h-3.5 w-3.5 stroke-text-03" />
                  <Text font="secondary-body" color="text-03">
                    {label}
                  </Text>
                </div>
                <div className="flex flex-wrap gap-2">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="max-w-full rounded-08 border border-border-01 bg-background-tint-02 px-3 py-1.5"
                    >
                      <Text font="secondary-body" color="text-05" maxLines={1}>
                        {item.title}
                      </Text>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
