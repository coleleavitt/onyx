"use client";

import { useMemo, useState } from "react";
import { Button, Popover, Text } from "@opal/components";
import { InputTypeIn } from "@opal/components";
import { cn } from "@opal/utils";
import { SvgFolder, SvgX } from "@opal/icons";
import { spaceAccentFromEmoji } from "@/lib/projects/spaceAccent";

/**
 * A small, self-contained emoji picker (no external emoji-picker dependency).
 *
 * The trigger renders the currently selected emoji on an accent-tinted tile
 * (accent derived from the emoji via `spaceAccentFromEmoji`), or a neutral
 * smiley placeholder when empty. Clicking opens a popover with a searchable
 * curated grid plus a "Remove" affordance.
 */

interface EmojiGroup {
  label: string;
  emojis: string[];
}

// A curated, dependency-free emoji set covering the categories users reach for
// when labeling a Space. Kept compact so the popover stays fast and scannable.
const EMOJI_GROUPS: EmojiGroup[] = [
  {
    label: "Smileys & People",
    emojis: [
      "😀", "😅", "😊", "😍", "🤓", "😎", "🤔", "🥳",
      "🤖", "👋", "👍", "🙌", "🧠", "👀", "💪", "🫶",
    ],
  },
  {
    label: "Work & Objects",
    emojis: [
      "📁", "📂", "📌", "📎", "📝", "📚", "📊", "📈",
      "💼", "🗂️", "🔖", "🗃️", "📅", "🧾", "🖇️", "📋",
    ],
  },
  {
    label: "Tech & Science",
    emojis: [
      "💻", "🖥️", "⚙️", "🔧", "🧪", "🔬", "🛰️", "🚀",
      "🛸", "🔭", "🧬", "⚛️", "🔋", "💡", "🧫", "📡",
    ],
  },
  {
    label: "Symbols & Nature",
    emojis: [
      "⭐", "🔥", "✨", "🌟", "💎", "🎯", "🏆", "🎨",
      "🌈", "🌍", "🌱", "🍀", "🌸", "⚡", "❤️", "🧭",
    ],
  },
];

export interface EmojiPickerProps {
  /** Currently selected emoji, or empty/null for none. */
  value: string | null | undefined;
  /** Called with the chosen emoji, or `null` when cleared. */
  onChange: (emoji: string | null) => void;
  /** Accessible label for the trigger. */
  ariaLabel?: string;
  /** Optional trigger-size override. */
  size?: "md" | "lg";
  disabled?: boolean;
}

export default function EmojiPicker({
  value,
  onChange,
  ariaLabel = "Pick an emoji",
  size = "md",
  disabled = false,
}: EmojiPickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const trimmed = value?.trim() ?? "";
  const hasEmoji = trimmed.length > 0;
  const accent = useMemo(() => spaceAccentFromEmoji(trimmed), [trimmed]);

  const tileSize = size === "lg" ? "h-12 w-12 text-2xl" : "h-9 w-9 text-lg";

  const filteredGroups = useMemo(() => {
    const q = query.trim();
    if (!q) return EMOJI_GROUPS;
    // Match against the raw emoji glyph (covers direct emoji paste/search).
    return EMOJI_GROUPS.map((group) => ({
      label: group.label,
      emojis: group.emojis.filter((emoji) => emoji.includes(q)),
    })).filter((group) => group.emojis.length > 0);
  }, [query]);

  function pick(emoji: string) {
    onChange(emoji);
    setOpen(false);
    setQuery("");
  }

  return (
    <Popover open={open} onOpenChange={disabled ? undefined : setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          disabled={disabled}
          aria-label={ariaLabel}
          className={cn(
            "flex shrink-0 items-center justify-center rounded-08 border border-border-01 transition-colors",
            tileSize,
            disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer"
          )}
          style={
            hasEmoji
              ? {
                  backgroundColor: accent.backgroundLight,
                  borderColor: accent.foregroundLight,
                }
              : undefined
          }
        >
          {hasEmoji ? (
            <span aria-hidden>{trimmed}</span>
          ) : (
            <SvgFolder className="h-5 w-5 stroke-text-03" />
          )}
        </button>
      </Popover.Trigger>
      <Popover.Content align="start" width="sm">
        <div className="flex w-full flex-col gap-2 p-2">
          <div className="flex items-center gap-2">
            <div className="min-w-0 flex-1">
              <InputTypeIn
                searchIcon
                placeholder="Search emoji"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            {hasEmoji ? (
              <Button
                icon={SvgX}
                prominence="tertiary"
                size="xs"
                aria-label="Remove emoji"
                onClick={() => {
                  onChange(null);
                  setOpen(false);
                }}
              />
            ) : null}
          </div>
          <div className="max-h-64 overflow-y-auto">
            {filteredGroups.length === 0 ? (
              <Text font="secondary-body" color="text-03">
                No emoji found
              </Text>
            ) : (
              filteredGroups.map((group) => (
                <div key={group.label} className="mb-2 flex flex-col gap-1">
                  <Text font="secondary-body" color="text-03">
                    {group.label}
                  </Text>
                  <div className="grid grid-cols-8 gap-1">
                    {group.emojis.map((emoji) => (
                      <button
                        key={emoji}
                        type="button"
                        aria-label={`Select ${emoji}`}
                        onClick={() => pick(emoji)}
                        className={cn(
                          "flex h-8 w-8 items-center justify-center rounded-08 text-lg transition-colors hover:bg-background-tint-01",
                          emoji === trimmed && "bg-background-tint-02"
                        )}
                      >
                        <span aria-hidden>{emoji}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </Popover.Content>
    </Popover>
  );
}
