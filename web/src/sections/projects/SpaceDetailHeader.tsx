"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import { Text } from "@opal/components";
import { toast } from "@opal/layouts";
import { cn } from "@opal/utils";
import { SvgChevronRight } from "@opal/icons";
import type { Project } from "@/lib/projects/types";
import type { ProjectMetadataUpdate } from "@/lib/projects/types";
import { SPACE_DESCRIPTION_MAX_LENGTH } from "@/lib/projects/constants";
import { spaceAccentFromEmoji } from "@/lib/projects/spaceAccent";
import EmojiPicker from "@/refresh-components/inputs/EmojiPicker";

interface SpaceDetailHeaderProps {
  project: Project;
  canEdit: boolean;
  onUpdate: (metadata: ProjectMetadataUpdate) => Promise<unknown>;
}

const DESCRIPTION_PLACEHOLDER = "Describe your project, goals, subject, etc…";

/**
 * The Space detail identity block, Perplexity-style: a breadcrumb ancestor link
 * back to Spaces, an emoji tile (picker for editors), and inline-editable title
 * + description that save on blur / Enter. Read-only viewers see static text.
 */
export default function SpaceDetailHeader({
  project,
  canEdit,
  onUpdate,
}: SpaceDetailHeaderProps) {
  const router = useRouter();

  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const descriptionRef = useRef<HTMLTextAreaElement>(null);

  // Keep local edit state in sync when the underlying project changes
  // (e.g. after a refresh or switching spaces).
  useEffect(() => {
    setName(project.name);
  }, [project.id, project.name]);
  useEffect(() => {
    setDescription(project.description ?? "");
  }, [project.id, project.description]);

  // Auto-grow the description textarea to fit its content.
  useEffect(() => {
    const el = descriptionRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [description]);

  const accent = spaceAccentFromEmoji(project.emoji);

  async function commitName() {
    const trimmed = name.trim();
    if (trimmed.length === 0) {
      setName(project.name); // revert empty
      return;
    }
    if (trimmed === project.name) return;
    try {
      await onUpdate({ name: trimmed });
    } catch (error) {
      setName(project.name);
      toast.error(
        error instanceof Error ? error.message : "Failed to rename space."
      );
    }
  }

  async function commitDescription() {
    const next = description.trim();
    if (next === (project.description ?? "").trim()) return;
    try {
      await onUpdate({ description: next || null });
    } catch (error) {
      setDescription(project.description ?? "");
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to update description."
      );
    }
  }

  async function commitEmoji(emoji: string | null) {
    try {
      await onUpdate({ emoji });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to update emoji."
      );
    }
  }

  return (
    <div className="flex w-full flex-col gap-3">
      {/* Breadcrumb: Spaces › {name} */}
      <nav aria-label="Breadcrumb" className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => router.push("/app/spaces" as Route)}
          className="text-text-03 transition-colors hover:text-text-05"
        >
          <Text font="secondary-body" color="inherit" nowrap>
            Spaces
          </Text>
        </button>
        <SvgChevronRight className="h-3.5 w-3.5 stroke-text-03" />
        <Text font="secondary-body" color="text-04" nowrap>
          {project.name}
        </Text>
      </nav>

      <div className="flex items-start gap-3">
        {canEdit ? (
          <EmojiPicker
            value={project.emoji}
            onChange={(emoji) => void commitEmoji(emoji)}
            ariaLabel="Pick an emoji for this space"
            size="lg"
          />
        ) : (
          <div
            aria-hidden
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-08 border border-border-01 bg-background-tint-02 text-2xl"
            style={
              project.emoji
                ? {
                    backgroundColor: accent.backgroundLight,
                    borderColor: accent.foregroundLight,
                  }
                : undefined
            }
          >
            {project.emoji ?? ""}
          </div>
        )}

        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {canEdit ? (
            <input
              aria-label="Space name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              onBlur={() => void commitName()}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  event.currentTarget.blur();
                }
              }}
              placeholder="New space"
              className="w-full border-none bg-transparent p-0 text-xl font-semibold text-text-05 outline-none placeholder:text-text-03"
            />
          ) : (
            <Text as="h1" font="heading-h3" color="text-05">
              {project.name}
            </Text>
          )}

          {canEdit ? (
            <textarea
              ref={descriptionRef}
              aria-label="Space description"
              value={description}
              maxLength={SPACE_DESCRIPTION_MAX_LENGTH}
              onChange={(event) => setDescription(event.target.value)}
              onBlur={() => void commitDescription()}
              placeholder={DESCRIPTION_PLACEHOLDER}
              rows={1}
              className={cn(
                "w-full resize-none border-none bg-transparent p-0 text-sm text-text-03 outline-none",
                "placeholder:text-text-03"
              )}
            />
          ) : project.description ? (
            <Text as="p" font="secondary-body" color="text-03">
              {project.description}
            </Text>
          ) : null}
        </div>
      </div>
    </div>
  );
}
