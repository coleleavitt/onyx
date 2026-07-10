"use client";

import { useMemo, useRef, useState } from "react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { Button, InputTypeIn, MessageCard, Tabs, Text } from "@opal/components";
import { IllustrationContent, SettingsLayouts } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import { SvgBlocks, SvgPlus, SvgSimpleLoader } from "@opal/icons";
import useOnMount from "@/hooks/useOnMount";
import useUserSkills from "@/hooks/useUserSkills";
import { useUser } from "@/providers/UserProvider";
import SkillCard, {
  type CustomSkillCardItem,
  type SkillCardItem,
} from "@/sections/cards/SkillCard";
import CreatePersonalSkillModal from "@/views/SkillsPage/CreatePersonalSkillModal";
import UploadSkillModal from "@/sections/modals/skills/UploadSkillModal";
import SkillPreviewModal from "@/sections/modals/SkillPreviewModal";
import type { BuiltinSkill, CustomSkill } from "@/lib/skills/types";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import { updateSkillUserSettings } from "@/lib/skills/api";
import { toast } from "@/hooks/useToast";

type SkillScope = "all" | "mine" | "shared" | "builtin";

export default function SkillsPage() {
  const router = useRouter();
  const { data, error, isLoading, refresh } = useUserSkills();
  const { isAdmin, isCurator } = useUser();
  const [searchQuery, setSearchQuery] = useState("");
  const [scope, setScope] = useState<SkillScope>("all");
  const [category, setCategory] = useState("All");
  const [busySkillId, setBusySkillId] = useState<string | null>(null);
  const [personalCreateOpen, setPersonalCreateOpen] = useState(false);
  const [orgUploadOpen, setOrgUploadOpen] = useState(false);
  const [previewTarget, setPreviewTarget] = useState<SkillCardItem | null>(
    null
  );
  const searchInputRef = useRef<HTMLInputElement>(null);

  useOnMount(() => searchInputRef.current?.focus());

  const canManageOrgSkills = isAdmin || isCurator;

  function handleCreateClick() {
    if (canManageOrgSkills) setOrgUploadOpen(true);
    else setPersonalCreateOpen(true);
  }

  function handleEdit(item: CustomSkillCardItem) {
    router.push(`/craft/v1/skills/edit/${item.id}` as Route);
  }

  const items = useMemo<SkillCardItem[]>(() => {
    if (!data) return [];
    const builtinItems: SkillCardItem[] = data.builtins
      .filter(
        (skill): skill is BuiltinSkill =>
          skill.source === "builtin" && skill.is_available !== null
      )
      .map((skill) => ({
        id: skill.id,
        name: skill.name,
        description: skill.description,
        category: skill.category,
        user_enabled: skill.user_enabled,
        source: "builtin",
        is_available: skill.is_available,
        unavailable_reason: skill.unavailable_reason,
      }));
    const customItems: SkillCardItem[] = data.customs
      .filter(
        (skill): skill is CustomSkill =>
          skill.source === "custom" && skill.enabled !== null
      )
      .map((skill) => ({
        id: skill.id,
        name: skill.name,
        description: skill.description,
        category: skill.category,
        user_enabled: skill.user_enabled,
        source: "custom",
        skill,
        author_email: skill.author_email,
        is_personal: skill.is_personal && skill.user_permission === "OWNER",
        enabled: skill.enabled,
      }));
    return [...builtinItems, ...customItems].sort((left, right) =>
      left.name.localeCompare(right.name, undefined, { sensitivity: "base" })
    );
  }, [data]);

  const categories = useMemo(
    () => [
      "All",
      ...Array.from(
        new Set(items.map((item) => item.category).filter(Boolean) as string[])
      ).sort(),
    ],
    [items]
  );
  const visibleItems = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return items.filter((item) => {
      const matchesScope =
        scope === "all" ||
        (scope === "builtin" && item.source === "builtin") ||
        (scope === "mine" &&
          item.source === "custom" &&
          item.skill.user_permission === "OWNER") ||
        (scope === "shared" &&
          item.source === "custom" &&
          item.skill.user_permission !== "OWNER" &&
          !item.skill.is_personal);
      const matchesCategory = category === "All" || item.category === category;
      const matchesQuery =
        !query ||
        item.name.toLowerCase().includes(query) ||
        item.description.toLowerCase().includes(query);
      return matchesScope && matchesCategory && matchesQuery;
    });
  }, [category, items, scope, searchQuery]);

  const previewUnavailableReason =
    previewTarget?.source === "builtin" && !previewTarget.is_available
      ? (previewTarget.unavailable_reason ??
        "This skill is currently unavailable.")
      : null;

  async function handleToggleEnabled(item: SkillCardItem, enabled: boolean) {
    setBusySkillId(item.id);
    try {
      await updateSkillUserSettings(item.id, enabled);
      await refresh();
      toast.success(enabled ? "Skill enabled." : "Skill disabled.");
    } catch (toggleError) {
      toast.error(
        toggleError instanceof Error
          ? toggleError.message
          : "Skill preference update failed."
      );
    } finally {
      setBusySkillId(null);
    }
  }

  return (
    <SettingsLayouts.Root width="full" data-testid="SkillsPage/container">
      <SettingsLayouts.Header
        icon={SvgBlocks}
        title="Skills"
        description="Reusable capability bundles available to your Craft agent."
        rightChildren={
          <div className="hidden sm:block">
            <Button icon={SvgPlus} onClick={handleCreateClick}>
              Create skill
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-2">
          <div className="sm:hidden">
            <Button icon={SvgPlus} onClick={handleCreateClick}>
              Create skill
            </Button>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="w-full shrink-0 sm:w-[32rem]">
              <Tabs
                value={scope}
                onValueChange={(value) => setScope(value as SkillScope)}
              >
                <Tabs.List>
                  <Tabs.Trigger value="all">All</Tabs.Trigger>
                  <Tabs.Trigger value="mine">My skills</Tabs.Trigger>
                  <Tabs.Trigger value="shared">Shared</Tabs.Trigger>
                  <Tabs.Trigger value="builtin">Built-in</Tabs.Trigger>
                </Tabs.List>
              </Tabs>
            </div>
            <div className="min-w-0 flex-1">
              <InputTypeIn
                ref={searchInputRef}
                clearButton
                placeholder="Search skills"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                searchIcon
              />
            </div>
            <div className="w-full sm:w-48">
              <InputSelect value={category} onValueChange={setCategory}>
                <InputSelect.Trigger>{category}</InputSelect.Trigger>
                <InputSelect.Content>
                  {categories.map((value) => (
                    <InputSelect.Item key={value} value={value}>
                      {value}
                    </InputSelect.Item>
                  ))}
                </InputSelect.Content>
              </InputSelect>
            </div>
          </div>
        </div>
      </SettingsLayouts.Header>

      <SettingsLayouts.Body>
        {isLoading ? (
          <div className="flex justify-center py-16">
            <SvgSimpleLoader className="h-6 w-6" />
          </div>
        ) : error ? (
          <MessageCard
            variant="error"
            title="Failed to load skills"
            description="Try refreshing the page."
          />
        ) : visibleItems.length === 0 ? (
          <IllustrationContent
            illustration={SvgNoResult}
            title={
              items.length === 0 ? "No skills available" : "No matching skills"
            }
            description={
              items.length === 0
                ? "Create a skill or ask an administrator to share one with you."
                : "Try a different scope, category, or search."
            }
          />
        ) : (
          <section className="flex w-full flex-col gap-3">
            <div className="flex items-baseline gap-2">
              <Text font="heading-h3" color="text-05">
                {scope === "all"
                  ? "All skills"
                  : scope === "mine"
                    ? "My skills"
                    : scope === "shared"
                      ? "Shared skills"
                      : "Built-in skills"}
              </Text>
              <Text font="secondary-body" color="text-03">
                {String(visibleItems.length)}
              </Text>
            </div>
            <div className="grid w-full grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {visibleItems.map((item) => (
                <SkillCard
                  key={item.id}
                  item={item}
                  onEdit={handleEdit}
                  onClick={setPreviewTarget}
                  onToggleEnabled={(target, enabled) =>
                    void handleToggleEnabled(target, enabled)
                  }
                  enableToggleDisabled={busySkillId === item.id}
                />
              ))}
            </div>
          </section>
        )}
      </SettingsLayouts.Body>

      <CreatePersonalSkillModal
        open={personalCreateOpen}
        onClose={() => setPersonalCreateOpen(false)}
        onCreated={refresh}
      />
      <UploadSkillModal
        open={orgUploadOpen}
        onClose={() => setOrgUploadOpen(false)}
        onUploaded={(created) => {
          void refresh();
          router.push(`/craft/v1/skills/edit/${created.id}` as Route);
        }}
      />
      <SkillPreviewModal
        open={previewTarget !== null}
        skillId={previewTarget?.id ?? null}
        fallbackTitle={previewTarget?.name}
        unavailableReason={previewUnavailableReason}
        onClose={() => setPreviewTarget(null)}
      />
    </SettingsLayouts.Root>
  );
}
