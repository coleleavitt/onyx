"use client";

import { useMemo, useRef, useState } from "react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import {
  Button,
  InputTypeIn,
  MessageCard,
  Popover,
  Tabs,
  Text,
} from "@opal/components";
import { IllustrationContent, SettingsLayouts, toast } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import {
  SvgBlocks,
  SvgEdit,
  SvgPlus,
  SvgSimpleLoader,
  SvgUploadCloud,
} from "@opal/icons";
import useOnMount from "@/hooks/useOnMount";
import useUserSkills from "@/hooks/useUserSkills";
import SkillCard, {
  type CustomSkillCardItem,
  type SkillCardItem,
} from "@/sections/cards/SkillCard";
import CreateSkillModal from "@/sections/modals/skills/CreateSkillModal";
import SkillPreviewModal from "@/sections/modals/SkillPreviewModal";
import type { BuiltinSkill, CustomSkill } from "@/lib/skills/types";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import LineItem from "@/refresh-components/buttons/LineItem";
import { setSkillEnabled } from "@/lib/skills/api";

type SkillScope = "all" | "mine" | "shared" | "builtin";

interface CreateSkillMenuProps {
  onStartFromScratch: () => void;
  onUpload: () => void;
}

function CreateSkillMenu({ onStartFromScratch, onUpload }: CreateSkillMenuProps) {
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button icon={SvgPlus}>Create skill</Button>
      </Popover.Trigger>
      <Popover.Content align="end" sideOffset={4} width="xl">
        <Popover.Menu>
          <LineItem
            icon={SvgEdit}
            description="Write the instructions and add supporting files in Onyx."
            wrapDescription
            onClick={() => {
              setOpen(false);
              onStartFromScratch();
            }}
          >
            Start from scratch
          </LineItem>
          <LineItem
            icon={SvgUploadCloud}
            description="Import a SKILL.md file, ZIP file, or skill folder."
            wrapDescription
            onClick={() => {
              setOpen(false);
              onUpload();
            }}
          >
            Upload a skill
          </LineItem>
        </Popover.Menu>
      </Popover.Content>
    </Popover>
  );
}

export default function SkillsPage() {
  const router = useRouter();
  const { data, error, isLoading, refresh } = useUserSkills();
  const [searchQuery, setSearchQuery] = useState("");
  const [scope, setScope] = useState<SkillScope>("all");
  const [category, setCategory] = useState("All");
  const [createOpen, setCreateOpen] = useState(false);
  const [previewTarget, setPreviewTarget] = useState<SkillCardItem | null>(
    null
  );
  const [pendingSkillIds, setPendingSkillIds] = useState<Set<string>>(
    new Set()
  );
  const [optimisticEnabledById, setOptimisticEnabledById] = useState<
    Map<string, boolean>
  >(new Map());
  const searchInputRef = useRef<HTMLInputElement>(null);

  useOnMount(() => searchInputRef.current?.focus());

  function handleStartFromScratch() {
    router.push("/craft/v1/skills/new" as Route);
  }

  function handleEdit(item: CustomSkillCardItem) {
    router.push(`/craft/v1/skills/edit/${item.id}` as Route);
  }

  async function handleEnabledChange(item: SkillCardItem, enabled: boolean) {
    setPendingSkillIds((current) => new Set(current).add(item.id));
    setOptimisticEnabledById((current) =>
      new Map(current).set(item.id, enabled)
    );
    try {
      const updatedSkill = await setSkillEnabled(item.id, enabled);
      await refresh(
        (current) => {
          if (!current) return current;
          const key =
            updatedSkill.source === "builtin" ? "builtins" : "customs";
          return {
            ...current,
            [key]: current[key].map((skill) =>
              skill.id === updatedSkill.id ? updatedSkill : skill
            ),
          };
        },
        { revalidate: false }
      );
      void refresh().catch(() => {
        toast.error(
          `${item.name} was updated, but the skill list could not be refreshed.`
        );
      });
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : `Failed to ${enabled ? "enable" : "disable"} ${item.name}`
      );
    } finally {
      setOptimisticEnabledById((current) => {
        const next = new Map(current);
        next.delete(item.id);
        return next;
      });
      setPendingSkillIds((current) => {
        const next = new Set(current);
        next.delete(item.id);
        return next;
      });
    }
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
        enabled: optimisticEnabledById.get(skill.id) ?? skill.enabled,
        can_toggle: skill.can_toggle,
        is_available: skill.is_available,
        unavailable_reason: skill.unavailable_reason,
      }));
    const customItems: SkillCardItem[] = data.customs
      .filter((skill): skill is CustomSkill => skill.source === "custom")
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
        enabled: optimisticEnabledById.get(skill.id) ?? skill.enabled,
        can_toggle: skill.can_toggle,
      }));
    return [...builtinItems, ...customItems].sort((left, right) =>
      left.name.localeCompare(right.name, undefined, { sensitivity: "base" })
    );
  }, [data, optimisticEnabledById]);

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

  return (
    <SettingsLayouts.Root width="full" data-testid="SkillsPage/container">
      <SettingsLayouts.Header
        icon={SvgBlocks}
        title="Skills"
        description="Choose the reusable capabilities available to your agents."
        density="compact"
        rightChildren={
          <div className="hidden sm:block">
            <CreateSkillMenu
              onStartFromScratch={handleStartFromScratch}
              onUpload={() => setCreateOpen(true)}
            />
          </div>
        }
      >
        <div className="flex flex-col gap-2">
          <div className="sm:hidden">
            <CreateSkillMenu
              onStartFromScratch={handleStartFromScratch}
              onUpload={() => setCreateOpen(true)}
            />
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="w-full shrink-0 sm:w-[22rem]">
              <Tabs
                variant="underline"
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

      <SettingsLayouts.Body density="compact">
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
                  onEnabledChange={handleEnabledChange}
                  enablementPending={pendingSkillIds.has(item.id)}
                />
              ))}
            </div>
          </section>
        )}
      </SettingsLayouts.Body>

      <CreateSkillModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(created) => {
          refresh();
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
