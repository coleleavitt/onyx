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

// Beyond this the list stops being a summary and starts being a file browser —
// the picker is the file browser.
const MAX_VISIBLE_ITEMS = 5;

interface ConnectedItem {
  key: string;
  title: string;
  icon: IconFunctionComponent;
  description?: string;
  link?: string | null;
}

function totalSelections(knowledge: ProjectConnectedKnowledge): number {
  return knowledge.documents.length + knowledge.hierarchy_nodes.length;
}

function countLabel(count: number, singular: string): string {
  return `${count} ${count === 1 ? singular : `${singular}s`}`;
}

/** Distinct sources across every selection, used to decide if rows need a source label. */
function distinctSources(
  knowledge: ProjectConnectedKnowledge
): Set<ValidSources> {
  const sources = new Set<ValidSources>();
  for (const node of knowledge.hierarchy_nodes) sources.add(node.source);
  for (const document of knowledge.documents) {
    if (document.source) sources.add(document.source);
  }
  return sources;
}

export default function SpaceConnectedSourcesSection({
  knowledge,
  canEdit,
  compact = false,
  onOpenPicker,
}: SpaceConnectedSourcesSectionProps) {
  // One row per thing actually connected. The previous shape also rendered a
  // per-source summary row above the items, so a single connected folder
  // produced two rows naming the same source twice.
  const items = useMemo<ConnectedItem[]>(() => {
    // With one source the name is already implied by the section and the icon;
    // it only earns a row's description line when sources are mixed.
    const labelSources = distinctSources(knowledge).size > 1;

    const folders = knowledge.hierarchy_nodes.map((node) => ({
      key: `node-${node.id}`,
      title: node.title,
      icon: getSourceMetadata(node.source).icon,
      description: labelSources
        ? getSourceMetadata(node.source).displayName
        : undefined,
    }));

    const documents = knowledge.documents.map((document) => ({
      key: `document-${document.id}`,
      title: document.title,
      icon: document.source
        ? getSourceMetadata(document.source).icon
        : SvgFileText,
      description:
        labelSources && document.source
          ? getSourceMetadata(document.source).displayName
          : undefined,
      link: document.link,
    }));

    return [...folders, ...documents];
  }, [knowledge]);

  const count = totalSelections(knowledge);
  const overflow = items.length - MAX_VISIBLE_ITEMS;

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
          {items.slice(0, MAX_VISIBLE_ITEMS).map((item) => (
            <LineItemButton
              key={item.key}
              icon={item.icon}
              title={item.title}
              description={item.description}
              width="full"
              sizePreset="main-ui"
              variant="section"
              titleMaxLines={1}
              onClick={onOpenPicker}
              rightChildren={
                item.link ? (
                  <Button
                    href={item.link}
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
          {overflow > 0 && (
            <LineItemButton
              icon={SvgFolder}
              title={`${overflow} more`}
              description={[
                knowledge.hierarchy_nodes.length
                  ? countLabel(knowledge.hierarchy_nodes.length, "folder")
                  : null,
                knowledge.documents.length
                  ? countLabel(knowledge.documents.length, "document")
                  : null,
              ]
                .filter(Boolean)
                .join(" · ")}
              width="full"
              sizePreset="main-ui"
              variant="section"
              titleMaxLines={1}
              onClick={onOpenPicker}
            />
          )}
        </div>
      )}
    </div>
  );
}
