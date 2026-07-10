"use client";

import { useCallback, type MouseEvent } from "react";
import { Button, Switch, Tag, Tooltip } from "@opal/components";
import { Content } from "@opal/layouts";
import { SvgBlocks, SvgEdit, SvgUser } from "@opal/icons";
import { CardItemLayout } from "@/layouts/general-layouts";
import { Interactive } from "@opal/core";
import { Card } from "@/refresh-components/cards";
import { useSettings } from "@/lib/settings/hooks";
import type { CustomSkill } from "@/lib/skills/types";

export type SkillCardSource = "builtin" | "custom";

interface SkillCardItemBase {
  id: string;
  name: string;
  description: string;
  category?: string;
  user_enabled?: boolean;
}

export interface BuiltinSkillCardItem extends SkillCardItemBase {
  source: "builtin";
  is_available: boolean;
  unavailable_reason?: string | null;
}

export interface CustomSkillCardItem extends SkillCardItemBase {
  source: "custom";
  skill: CustomSkill;
  author_email?: string | null;
  /** True when the skill is a personal skill owned by the current user. */
  is_personal?: boolean;
  /** Disabled skills render greyed out; owners can re-enable via the toggle. */
  enabled?: boolean;
}

export type SkillCardItem = BuiltinSkillCardItem | CustomSkillCardItem;

export interface SkillCardProps {
  item: SkillCardItem;
  onClick?: (item: SkillCardItem) => void;
  onEdit?: (item: CustomSkillCardItem) => void;
  onToggleEnabled?: (item: SkillCardItem, enabled: boolean) => void;
  enableToggleDisabled?: boolean;
}

export default function SkillCard({
  item,
  onClick,
  onEdit,
  onToggleEnabled,
  enableToggleDisabled,
}: SkillCardProps) {
  const { appName } = useSettings();

  const handleClick = useCallback(() => {
    onClick?.(item);
  }, [onClick, item]);

  const authorTitle =
    item.source === "builtin" ? appName : item.author_email || appName;
  const footerTitle =
    item.source === "builtin"
      ? item.category || "Built-in capability"
      : authorTitle;
  const FooterIcon = item.source === "builtin" ? SvgBlocks : SvgUser;
  const isDisabled =
    item.user_enabled === false ||
    (item.source === "custom" && item.enabled === false);
  const isBuiltinUnavailable = item.source === "builtin" && !item.is_available;
  const isOrganizationDisabled =
    item.source === "custom" && item.enabled === false;
  const tooltip = isBuiltinUnavailable
    ? "Skill is currently unavailable. Click to view details."
    : undefined;
  const canEdit =
    item.source === "custom" &&
    (item.skill.user_permission === "OWNER" ||
      item.skill.user_permission === "EDITOR");

  const handleEditClick = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (item.source === "custom") {
      onEdit?.(item);
    }
  };

  return (
    <Tooltip tooltip={tooltip} side="top">
      <Interactive.Simple onClick={handleClick} group="group/SkillCard">
        <Card
          variant={isDisabled || isBuiltinUnavailable ? "disabled" : "primary"}
          padding={0}
          gap={0}
          height="full"
        >
          <div className="flex self-stretch h-24">
            <CardItemLayout
              icon={SvgBlocks}
              title={item.name}
              description={item.description}
              rightChildren={
                item.source === "custom" && canEdit ? (
                  <div className="opacity-0 transition-opacity group-hover/SkillCard:opacity-100 group-focus-within/SkillCard:opacity-100">
                    <Button
                      prominence="secondary"
                      size="sm"
                      icon={SvgEdit}
                      tooltip="Edit skill"
                      onClick={handleEditClick}
                    />
                  </div>
                ) : undefined
              }
            />
          </div>

          <div className="bg-background-tint-01 p-1 flex flex-row items-center justify-between w-full">
            <div className="py-1 px-2 min-w-0 flex-1">
              <Content
                icon={FooterIcon}
                title={footerTitle}
                sizePreset="secondary"
                variant="body"
                color="muted"
              />
            </div>
            <div className="p-0.5 pr-1.5 flex items-center gap-1">
              <Tooltip
                tooltip={
                  isOrganizationDisabled
                    ? "Disabled by your organization"
                    : undefined
                }
                side="top"
              >
                <div
                  className="mr-1 flex items-center"
                  onClick={(event) => event.stopPropagation()}
                  onPointerDown={(event) => event.stopPropagation()}
                >
                  <Switch
                    checked={
                      !isOrganizationDisabled &&
                      !isBuiltinUnavailable &&
                      item.user_enabled !== false
                    }
                    disabled={
                      enableToggleDisabled ||
                      isBuiltinUnavailable ||
                      isOrganizationDisabled
                    }
                    onCheckedChange={(checked) =>
                      onToggleEnabled?.(item, checked)
                    }
                  />
                </div>
              </Tooltip>
              {item.source === "builtin" ? (
                item.is_available ? (
                  <Tag title="Built-in" color="blue" />
                ) : (
                  <Tag
                    title="Unavailable - click to learn more"
                    color="amber"
                  />
                )
              ) : item.is_personal ? (
                <Tag title="Personal" color="purple" />
              ) : (
                <Tag title={item.category || "Shared"} color="gray" />
              )}
            </div>
          </div>
        </Card>
      </Interactive.Simple>
    </Tooltip>
  );
}
