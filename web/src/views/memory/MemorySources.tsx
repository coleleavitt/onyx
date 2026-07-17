"use client";

import useSWR from "swr";
import type { IconFunctionComponent } from "@opal/types";
import { Text } from "@opal/components";
import {
  SvgBubbleText,
  SvgEdit,
  SvgFile,
  SvgFileText,
  SvgPlug,
} from "@opal/icons";
import { getMemorySources } from "@/lib/memory/api";
import type { MemorySourceType } from "@/lib/memory/types";

const SOURCE_ICON: Record<MemorySourceType, IconFunctionComponent> = {
  chat_session: SvgBubbleText,
  document: SvgFileText,
  connector: SvgPlug,
  file: SvgFile,
  manual: SvgEdit,
};

interface MemorySourcesProps {
  memoryId: number;
}

export default function MemorySources({ memoryId }: MemorySourcesProps) {
  const { data } = useSWR(
    `/api/memory/${memoryId}/sources`,
    () => getMemorySources(memoryId),
    { revalidateOnFocus: false }
  );

  return (
    <div className="flex w-full flex-col gap-2">
      <Text font="main-ui-action" color="text-05">
        Sources
      </Text>
      {data && data.length === 0 ? (
        <Text font="secondary-body" color="text-03">
          No sources yet.
        </Text>
      ) : data && data.length > 0 ? (
        <div className="flex flex-col divide-y divide-border-01 overflow-hidden rounded-08 border border-border-01">
          {data.map((source) => {
            const Icon = SOURCE_ICON[source.source_type];
            const row = (
              <div className="flex items-center gap-2 px-3 py-2">
                <Icon className="h-4 w-4 shrink-0 stroke-text-03" />
                <Text font="secondary-body" color="text-05" maxLines={1}>
                  {source.label}
                </Text>
              </div>
            );
            return source.url ? (
              <a
                key={source.id}
                href={source.url}
                target="_blank"
                rel="noreferrer"
                className="transition-colors hover:bg-background-tint-02"
              >
                {row}
              </a>
            ) : (
              <div key={source.id}>{row}</div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
