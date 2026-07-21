"use client";

import { useMemo, useState } from "react";
import { Button, Popover, Text } from "@opal/components";
import { InputTypeIn } from "@opal/components";
import { toast } from "@opal/layouts";
import { ContentAction } from "@opal/layouts";
import LineItem from "@/refresh-components/buttons/LineItem";
import { SvgCheck, SvgPlusCircle, SvgSparkle, SvgTrash } from "@opal/icons";
import useUserSkills from "@/hooks/useUserSkills";
import type { Skill } from "@/lib/skills/types";
import { useSpaceMeta } from "@/lib/projects/useSpaceMeta";
import { addSkillId, removeSkillId } from "@/lib/projects/spaceMetadata";

interface SpaceSkillsSectionProps {
  canEdit: boolean;
  compact?: boolean;
}

/**
 * Per-space Skills section: persists a per-space set of skill ids (through the
 * space-metadata channel) so the selection survives reload — not just a link to
 * the global Skills hub. Editors add/remove skills from a picker.
 */
export default function SpaceSkillsSection({
  canEdit,
  compact = false,
}: SpaceSkillsSectionProps) {
  const { meta, saveMeta } = useSpaceMeta();
  const { data: skillsList } = useUserSkills();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);

  const allSkills: Skill[] = useMemo(
    () => [...(skillsList?.builtins ?? []), ...(skillsList?.customs ?? [])],
    [skillsList],
  );
  const byId = useMemo(() => {
    const map = new Map<string, Skill>();
    for (const skill of allSkills) map.set(skill.id, skill);
    return map;
  }, [allSkills]);

  const selectedIds = meta.skillIds;
  const selectedSkills = selectedIds
    .map((id) => byId.get(id))
    .filter((skill): skill is Skill => skill !== undefined);

  const pickable = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return allSkills
      .filter((skill) => !selectedIds.includes(skill.id))
      .filter(
        (skill) =>
          normalizedQuery.length === 0 ||
          skill.name.toLowerCase().includes(normalizedQuery),
      );
  }, [allSkills, selectedIds, query]);

  async function add(skillId: string) {
    setBusy(true);
    try {
      await saveMeta({ ...meta, skillIds: addSkillId(selectedIds, skillId) });
      setQuery("");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to add skill.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(skillId: string) {
    setBusy(true);
    try {
      await saveMeta({
        ...meta,
        skillIds: removeSkillId(selectedIds, skillId),
      });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to remove skill.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <ContentAction
        sizePreset="main-ui"
        variant="section"
        title="Skills"
        description={
          compact ? undefined : "Give this space access to specific skills."
        }
        padding="fit"
        center
        rightChildren={
          canEdit ? (
            <Popover open={pickerOpen} onOpenChange={setPickerOpen}>
              <Popover.Trigger asChild>
                <Button
                  icon={SvgPlusCircle}
                  prominence="tertiary"
                  interaction={pickerOpen ? "active" : undefined}
                  aria-label="Add skills"
                  tooltip={compact ? "Add skills" : undefined}
                  tooltipSide="bottom"
                >
                  {compact ? undefined : "Add skills"}
                </Button>
              </Popover.Trigger>
              <Popover.Content align="end" width="sm">
                <div className="flex w-full flex-col gap-2 p-2">
                  <InputTypeIn
                    searchIcon
                    placeholder="Search skills"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                  />
                  <div className="flex max-h-64 flex-col gap-0.5 overflow-y-auto">
                    {pickable.length === 0 ? (
                      <Text font="secondary-body" color="text-03">
                        No skills to add
                      </Text>
                    ) : (
                      pickable.map((skill) => (
                        <LineItem
                          key={skill.id}
                          icon={SvgSparkle}
                          disabled={busy}
                          onClick={() => void add(skill.id)}
                        >
                          {skill.name}
                        </LineItem>
                      ))
                    )}
                  </div>
                </div>
              </Popover.Content>
            </Popover>
          ) : undefined
        }
      />

      {selectedSkills.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          {selectedSkills.map((skill) => (
            <div
              key={skill.id}
              className="flex items-center gap-2 rounded-12 border border-border-01 bg-background-tint-02 px-3 py-2"
            >
              <SvgSparkle className="h-4 w-4 shrink-0 stroke-text-03" />
              <div className="flex min-w-0 flex-1 flex-col">
                <Text font="main-ui-body" color="text-05" nowrap>
                  {skill.name}
                </Text>
                {skill.description ? (
                  <Text font="secondary-body" color="text-03" maxLines={1}>
                    {skill.description}
                  </Text>
                ) : null}
              </div>
              <SvgCheck className="h-4 w-4 shrink-0 stroke-status-success-05" />
              {canEdit ? (
                <Button
                  icon={SvgTrash}
                  prominence="tertiary"
                  size="xs"
                  disabled={busy}
                  aria-label={`Remove ${skill.name} from space`}
                  onClick={() => void remove(skill.id)}
                />
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <div className="flex min-h-12 items-center rounded-12 border border-dashed border-border-01 px-3 py-2.5">
          <Text as="p" font="secondary-body" color="text-03">
            {canEdit
              ? "No skills added to this space yet."
              : "No skills in this space yet."}
          </Text>
        </div>
      )}
    </div>
  );
}
