"use client";

import { useState } from "react";
import type { Project } from "@/lib/projects/types";
import { spaceAccentFromEmoji } from "@/lib/projects/spaceAccent";
import { getUserInitials } from "@/lib/users/svc";
import { timeAgo } from "@opal/time";
import { Button, Popover, PopoverMenu, Text } from "@opal/components";
import LineItem from "@/refresh-components/buttons/LineItem";
import { cn } from "@opal/utils";
import {
  SvgEdit,
  SvgFolder,
  SvgGlobe,
  SvgLock,
  SvgMoreHorizontal,
  SvgPin,
  SvgPinned,
  SvgShare,
  SvgTrash,
} from "@opal/icons";

interface SpaceCardProps {
  project: Project;
  onOpen: (project: Project) => void;
  onShare: (project: Project) => void;
  onRename: (project: Project) => void;
  onDelete: (project: Project) => void;
  onTogglePin: (project: Project) => void;
}

interface Visibility {
  label: string;
  icon: typeof SvgLock;
}

function visibility(project: Project): Visibility {
  if (project.organization_permission) {
    return { label: "Organization", icon: SvgGlobe };
  }
  const shared =
    project.user_permission !== "OWNER" || project.is_personal === false;
  return shared
    ? { label: "Shared", icon: SvgShare }
    : { label: "Private", icon: SvgLock };
}

export default function SpaceCard({
  project,
  onOpen,
  onShare,
  onRename,
  onDelete,
  onTogglePin,
}: SpaceCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { label: visibilityLabel, icon: VisibilityIcon } = visibility(project);
  const updated = timeAgo(project.updated_at ?? project.created_at);
  const isOwner = project.user_permission === "OWNER";

  return (
    <div
      className={cn(
        "group flex w-full cursor-pointer items-center gap-3 rounded-08 px-3 py-2.5",
        "outline-none transition-colors hover:bg-background-tint-01 focus-visible:bg-background-tint-01",
      )}
      onClick={() => onOpen(project)}
      tabIndex={0}
      role="button"
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen(project);
        }
      }}
      aria-label={`Open space ${project.name}`}
    >
      <div
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-08 bg-background-tint-02"
        style={
          project.emoji
            ? {
                backgroundColor: spaceAccentFromEmoji(project.emoji)
                  .backgroundLight,
              }
            : undefined
        }
      >
        {project.emoji ? (
          <Text font="main-ui-body" color="text-05" nowrap>
            {project.emoji}
          </Text>
        ) : (
          <SvgFolder className="h-4 w-4 stroke-text-03" />
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <Text font="main-ui-body" color="text-05" nowrap>
          {project.name}
        </Text>
        {project.description ? (
          <Text font="secondary-body" color="text-03" nowrap>
            {project.description}
          </Text>
        ) : null}
      </div>

      {project.owner ? (
        <div
          role="img"
          aria-label={`${project.owner.email} avatar`}
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-background-neutral-inverted-00"
          title={project.owner.full_name || project.owner.email}
        >
          <Text font="secondary-body" color="text-inverted-05" nowrap>
            {getUserInitials(
              project.owner.full_name ?? null,
              project.owner.email,
            ) ?? project.owner.email.charAt(0).toUpperCase()}
          </Text>
        </div>
      ) : null}

      <div className="flex w-28 shrink-0 items-center justify-end gap-1.5 text-text-03">
        <VisibilityIcon className="h-3.5 w-3.5 stroke-current" />
        <Text font="secondary-body" color="inherit" nowrap>
          {visibilityLabel}
        </Text>
      </div>

      <div className="w-20 shrink-0 text-right">
        {updated ? (
          <Text font="secondary-body" color="text-03" nowrap>
            {updated}
          </Text>
        ) : null}
      </div>

      {/* Trailing cell: pin indicator ⇄ overflow menu (Perplexity-style swap) */}
      <div
        className="relative flex h-7 w-7 shrink-0 items-center justify-center"
        onClick={(event) => event.stopPropagation()}
      >
        {project.is_pinned ? (
          <SvgPinned
            className={cn(
              "pointer-events-none absolute h-3.5 w-3.5 stroke-text-03 transition-opacity",
              "group-hover:opacity-0",
              menuOpen && "opacity-0",
            )}
          />
        ) : null}
        <Popover open={menuOpen} onOpenChange={setMenuOpen}>
          <div
            className={cn(
              "transition-opacity",
              !menuOpen &&
                project.is_pinned &&
                "opacity-0 group-hover:opacity-100",
            )}
          >
            <Popover.Trigger asChild>
              <Button
                icon={SvgMoreHorizontal}
                prominence="tertiary"
                size="xs"
                aria-label={`Space actions for ${project.name}`}
              />
            </Popover.Trigger>
          </div>
          <Popover.Content align="end" width="sm">
            <PopoverMenu>
              {[
                <LineItem
                  key="pin"
                  icon={project.is_pinned ? SvgPin : SvgPinned}
                  onClick={() => {
                    setMenuOpen(false);
                    onTogglePin(project);
                  }}
                >
                  {project.is_pinned ? "Unpin space" : "Pin space"}
                </LineItem>,
                ...(isOwner
                  ? [
                      <LineItem
                        key="rename"
                        icon={SvgEdit}
                        onClick={() => {
                          setMenuOpen(false);
                          onRename(project);
                        }}
                      >
                        Rename
                      </LineItem>,
                      <LineItem
                        key="share"
                        icon={SvgShare}
                        onClick={() => {
                          setMenuOpen(false);
                          onShare(project);
                        }}
                      >
                        Share
                      </LineItem>,
                      <LineItem
                        key="delete"
                        danger
                        icon={SvgTrash}
                        onClick={() => {
                          setMenuOpen(false);
                          onDelete(project);
                        }}
                      >
                        Delete space
                      </LineItem>,
                    ]
                  : []),
              ]}
            </PopoverMenu>
          </Popover.Content>
        </Popover>
      </div>
    </div>
  );
}
