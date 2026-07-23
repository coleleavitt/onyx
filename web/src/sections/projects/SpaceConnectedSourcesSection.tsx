"use client";

import { useMemo } from "react";
import type { IconFunctionComponent } from "@opal/types";
import { Button, LineItemButton, Text } from "@opal/components";
import { ContentAction } from "@opal/layouts";
import {
  SvgExternalLink,
  SvgFileText,
  SvgFolder,
  SvgPlusCircle,
} from "@opal/icons";
import { getSourceMetadata } from "@/lib/sources";
import type { ProjectConnectedKnowledge } from "@/lib/projects/types";
import type { ValidSources } from "@/lib/types";

interface SpaceConnectedSourcesSectionProps {
  knowledge: ProjectConnectedKnowledge;
  canEdit: boolean;
  compact?: boolean;
  onOpenPicker: () => void;
}

function totalSelections(knowledge: ProjectConnectedKnowledge): number {
  return knowledge.documents.length + knowledge.hierarchy_nodes.length;
}

export default function SpaceConnectedSourcesSection({
  knowledge,
  canEdit,
  compact = false,
  onOpenPicker,
}: SpaceConnectedSourcesSectionProps) {
  const grouped = useMemo(() => {
    const groups = new Map<
      ValidSources,
      {
        documents: number;
        folders: number;
        icon: IconFunctionComponent;
        label: string;
      }
    >();
    for (const node of knowledge.hierarchy_nodes) {
      const meta = getSourceMetadata(node.source);
      const current = groups.get(node.source) ?? {
        documents: 0,
        folders: 0,
        icon: meta.icon,
        label: meta.displayName,
      };
      current.folders += 1;
      groups.set(node.source, current);
    }
    for (const document of knowledge.documents) {
      if (!document.source) continue;
      const meta = getSourceMetadata(document.source);
      const current = groups.get(document.source) ?? {
        documents: 0,
        folders: 0,
        icon: meta.icon,
        label: meta.displayName,
      };
      current.documents += 1;
      groups.set(document.source, current);
    }
    return Array.from(groups.entries()).sort(([, left], [, right]) =>
      left.label.localeCompare(right.label),
    );
  }, [knowledge.documents, knowledge.hierarchy_nodes]);

  const count = totalSelections(knowledge);

  return (
    <div className="flex flex-col gap-2">
      <ContentAction
        icon={SvgFolder}
        sizePreset="main-ui"
        variant="section"
        title="Connected sources"
        description={
          compact
            ? undefined
            : "Attach indexed connector folders and documents without copying them."
        }
        padding="fit"
        center
        rightChildren={
          canEdit ? (
            <Button
              icon={SvgPlusCircle}
              prominence="tertiary"
              aria-label="Add connected source"
              tooltip={compact ? "Add connected source" : undefined}
              tooltipSide="bottom"
              onClick={onOpenPicker}
            >
              {compact ? undefined : "Add source"}
            </Button>
          ) : undefined
        }
      />

      {count === 0 ? (
        <div className="flex min-h-12 items-center rounded-12 border border-dashed border-border-01 px-3 py-2.5">
          <Text font="secondary-body" color="text-03">
            No connected sources yet. Add indexed SharePoint folders, sites, or
            documents.
          </Text>
        </div>
      ) : (
        <div className="flex flex-col gap-1.5">
          {grouped.map(([source, group]) => {
            const Icon = group.icon;
            const description = [
              group.folders ? `${group.folders} folder/site` : null,
              group.documents ? `${group.documents} document` : null,
            ]
              .filter(Boolean)
              .join(" · ");
            return (
              <LineItemButton
                key={source}
                icon={Icon}
                title={group.label}
                description={description}
                width="full"
                variant="section"
                onClick={onOpenPicker}
              />
            );
          })}
          {knowledge.hierarchy_nodes.slice(0, 3).map((node) => (
            <LineItemButton
              key={`node-${node.id}`}
              icon={SvgFolder}
              title={node.title}
              description={getSourceMetadata(node.source).displayName}
              width="full"
              variant="section"
              onClick={onOpenPicker}
            />
          ))}
          {knowledge.documents.slice(0, 3).map((document) => (
            <LineItemButton
              key={`document-${document.id}`}
              icon={SvgFileText}
              title={document.title}
              description={
                document.source
                  ? getSourceMetadata(document.source).displayName
                  : "Indexed document"
              }
              width="full"
              variant="section"
              onClick={onOpenPicker}
              rightChildren={
                document.link ? (
                  <Button
                    href={document.link}
                    target="_blank"
                    icon={SvgExternalLink}
                    prominence="tertiary"
                    size="xs"
                    tooltip="Open source document"
                  />
                ) : undefined
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
