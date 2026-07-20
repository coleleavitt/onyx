"use client";

import { useState } from "react";
import { Button, Popover, Text } from "@opal/components";
import { InputTypeIn } from "@opal/components";
import { toast } from "@opal/layouts";
import { ContentAction } from "@opal/layouts";
import LineItem from "@/refresh-components/buttons/LineItem";
import {
  SvgExternalLink,
  SvgLink,
  SvgMoreHorizontal,
  SvgPlusCircle,
  SvgTrash,
} from "@opal/icons";
import { useUser } from "@/providers/UserProvider";
import { useSpaceMeta } from "@/lib/projects/useSpaceMeta";
import { addLink, isValidLinkUrl, removeLink } from "@/lib/projects/spaceMetadata";

interface SpaceLinksSectionProps {
  canEdit: boolean;
}

/**
 * Working "Links" section for the Space rail: an editor pastes a URL, it's
 * added with "Added by …" attribution and persists (via the space-metadata
 * channel), and can be removed. Replaces the previous "coming soon" placeholder.
 */
export default function SpaceLinksSection({ canEdit }: SpaceLinksSectionProps) {
  const { user } = useUser();
  const { meta, saveMeta } = useSpaceMeta();
  const [adding, setAdding] = useState(false);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);

  const links = meta.links;
  const canSubmit = isValidLinkUrl(url);

  async function submit() {
    if (!canSubmit) return;
    const next = addLink(links, url, { addedByEmail: user?.email });
    if (next === links) {
      toast.error("That link is invalid or already added.");
      return;
    }
    setBusy(true);
    try {
      await saveMeta({ ...meta, links: next });
      setUrl("");
      setAdding(false);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to add link."
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setBusy(true);
    try {
      await saveMeta({ ...meta, links: removeLink(links, id) });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to remove link."
      );
    } finally {
      setBusy(false);
      setMenuOpenId(null);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <ContentAction
        sizePreset="main-ui"
        variant="section"
        title="Links"
        description="Add websites this space should prioritize when running tasks."
        padding="fit"
        center
        rightChildren={
          canEdit ? (
            <Button
              icon={SvgPlusCircle}
              prominence="tertiary"
              interaction={adding ? "active" : undefined}
              onClick={() => setAdding((prev) => !prev)}
            >
              Add link
            </Button>
          ) : undefined
        }
      />

      {adding && canEdit ? (
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <InputTypeIn
              autoFocus
              placeholder="Paste a website URL"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void submit();
                }
              }}
            />
          </div>
          <Button disabled={!canSubmit || busy} onClick={() => void submit()}>
            Add
          </Button>
        </div>
      ) : null}

      {links.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          {links.map((link) => (
            <div
              key={link.id}
              className="flex items-center gap-2 rounded-12 border border-border-01 bg-background-tint-02 px-3 py-2"
            >
              <SvgLink className="h-4 w-4 shrink-0 stroke-text-03" />
              <a
                href={link.url}
                target="_blank"
                rel="noreferrer"
                className="flex min-w-0 flex-1 flex-col"
              >
                <Text font="main-ui-body" color="text-05" nowrap>
                  {link.label ?? link.url}
                </Text>
                {link.addedByEmail ? (
                  <Text font="secondary-body" color="text-03" nowrap>
                    {`Added by ${link.addedByEmail}`}
                  </Text>
                ) : null}
              </a>
              <SvgExternalLink className="h-3.5 w-3.5 shrink-0 stroke-text-03" />
              {canEdit ? (
                <Popover
                  open={menuOpenId === link.id}
                  onOpenChange={(open) =>
                    setMenuOpenId(open ? link.id : null)
                  }
                >
                  <Popover.Trigger asChild>
                    <Button
                      icon={SvgMoreHorizontal}
                      prominence="tertiary"
                      size="xs"
                      aria-label={`Link actions for ${link.url}`}
                    />
                  </Popover.Trigger>
                  <Popover.Content align="end" width="sm">
                    <LineItem
                      icon={SvgTrash}
                      danger
                      onClick={() => void remove(link.id)}
                    >
                      Remove link
                    </LineItem>
                  </Popover.Content>
                </Popover>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="flex min-h-12 items-center rounded-12 border border-dashed border-border-01 px-3 py-2.5">
          <Text as="p" font="secondary-body" color="text-03">
            {canEdit
              ? "No links yet. Add websites this space should reference."
              : "No links in this space yet."}
          </Text>
        </div>
      )}
    </div>
  );
}
