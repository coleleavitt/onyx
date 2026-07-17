"use client";

import { useEffect, useMemo, useState } from "react";
import type { IconFunctionComponent } from "@opal/types";
import {
  Button,
  InputTypeIn,
  MessageCard,
  SidebarTab,
  Switch,
  Text,
} from "@opal/components";
import { IllustrationContent, SettingsLayouts } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import {
  SvgBlocks,
  SvgBookOpen,
  SvgFolder,
  SvgLightbulbSimple,
  SvgMenu,
  SvgNetworkGraph,
  SvgPlus,
  SvgSettings,
  SvgShield,
  SvgSimpleLoader,
  SvgUsers,
} from "@opal/icons";
import Modal from "@/refresh-components/Modal";
import useUserPersonalization from "@/hooks/useUserPersonalization";
import { useUser } from "@/providers/UserProvider";
import { toast } from "@opal/layouts";
import { getMemoryCapabilities } from "@/lib/memory/capabilities";
import { useMemoryLibrary } from "@/lib/memory/hooks";
import type { MemoryCategory, MemoryItem } from "@/lib/memory/types";
import MemoryEditorModal from "@/views/memory/MemoryEditorModal";
import MemoryGraphView from "@/views/memory/MemoryGraphView";
import BrainSettingsModal from "@/views/memory/BrainSettingsModal";
import MemoryCard from "@/sections/cards/MemoryCard";

type CategoryFilter = "all" | MemoryCategory;
type ViewMode = "grid" | "list" | "graph";

interface CategoryDefinition {
  value: CategoryFilter;
  label: string;
  icon: IconFunctionComponent;
}

const CATEGORIES: readonly CategoryDefinition[] = [
  {
    value: "all",
    label: "All",
    icon: SvgBookOpen,
  },
  {
    value: "concepts",
    label: "Concepts",
    icon: SvgLightbulbSimple,
  },
  {
    value: "entities",
    label: "Entities",
    icon: SvgUsers,
  },
  {
    value: "workstreams",
    label: "Workstreams",
    icon: SvgFolder,
  },
  {
    value: "notes",
    label: "Notes",
    icon: SvgMenu,
  },
] as const;

interface MemorySettingsModalProps {
  open: boolean;
  onClose: () => void;
}

function MemorySettingsModal({ open, onClose }: MemorySettingsModalProps) {
  const { user, updateUserPersonalization } = useUser();
  const {
    personalizationValues,
    toggleUseMemories,
    toggleEnableMemoryTool,
    handleSavePersonalization,
    isSavingPersonalization,
  } = useUserPersonalization(user, updateUserPersonalization, {
    onError: () => toast.error("Memory preference update failed."),
  });
  const memoryPolicyLoaded = user?.personalization !== undefined;
  const organizationMemoriesEnabled =
    memoryPolicyLoaded && personalizationValues.organization_memories_enabled;
  const organizationCreationEnabled =
    memoryPolicyLoaded &&
    personalizationValues.organization_memory_creation_enabled;

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Modal.Content width="md">
        <Modal.Header
          icon={SvgSettings}
          title="Memory settings"
          description="Control when Onyx can reference or update saved context."
          onClose={onClose}
        />
        <Modal.Body>
          <div className="flex w-full flex-col gap-3">
            <div className="flex items-center justify-between gap-4 rounded-08 border border-border-01 bg-background-tint-02 p-4">
              <div className="min-w-0">
                <Text font="main-ui-body" color="text-05">
                  Reference stored memories
                </Text>
                <Text font="secondary-body" color="text-03">
                  Use saved context when answering you.
                </Text>
              </div>
              <Switch
                checked={
                  organizationMemoriesEnabled &&
                  personalizationValues.use_memories
                }
                disabled={
                  isSavingPersonalization || !organizationMemoriesEnabled
                }
                onCheckedChange={(checked) => {
                  toggleUseMemories(checked);
                  void handleSavePersonalization({ use_memories: checked });
                }}
              />
            </div>
            <div className="flex items-center justify-between gap-4 rounded-08 border border-border-01 bg-background-tint-02 p-4">
              <div className="min-w-0">
                <Text font="main-ui-body" color="text-05">
                  Allow memory updates
                </Text>
                <Text font="secondary-body" color="text-03">
                  Let Onyx learn and refine context from conversations.
                </Text>
              </div>
              <Switch
                checked={
                  organizationCreationEnabled &&
                  personalizationValues.enable_memory_tool
                }
                disabled={
                  isSavingPersonalization || !organizationCreationEnabled
                }
                onCheckedChange={(checked) => {
                  toggleEnableMemoryTool(checked);
                  void handleSavePersonalization({
                    enable_memory_tool: checked,
                  });
                }}
              />
            </div>
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button onClick={onClose}>Done</Button>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}

export default function MemoryPage() {
  const { isAdmin, user } = useUser();
  const { data, memories, error, isLoading, mutate } = useMemoryLibrary();
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ViewMode>("grid");
  const [editorOpen, setEditorOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [brainOpen, setBrainOpen] = useState(false);
  const [selectedMemory, setSelectedMemory] = useState<MemoryItem | null>(null);
  const { canCreateUpdateRestore, canDelete } = getMemoryCapabilities(
    user?.personalization
  );

  useEffect(() => {
    const stored = window.localStorage.getItem("onyx-memory-view");
    if (stored === "grid" || stored === "list" || stored === "graph") {
      setView(stored);
    }
  }, []);

  const visibleMemories = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return memories.filter((memory) => {
      const matchesCategory =
        category === "all" || memory.category === category;
      const matchesQuery =
        !normalized ||
        memory.title.toLowerCase().includes(normalized) ||
        memory.content.toLowerCase().includes(normalized);
      return matchesCategory && matchesQuery;
    });
  }, [category, memories, query]);

  function setViewMode(nextView: ViewMode) {
    setView(nextView);
    window.localStorage.setItem("onyx-memory-view", nextView);
  }

  function openMemory(memory: MemoryItem | null) {
    setSelectedMemory(memory);
    setEditorOpen(true);
  }

  function openMemoryById(memoryId: number) {
    const match = memories.find((memory) => memory.id === memoryId);
    if (match) openMemory(match);
  }

  function countFor(filter: CategoryFilter): number {
    if (filter === "all") return data?.total ?? 0;
    return data?.category_counts[filter] ?? 0;
  }

  const headerActions = (
    <div className="flex items-center gap-2">
      {isAdmin ? (
        <Button
          href="/admin/memory-governance"
          icon={SvgShield}
          prominence="tertiary"
          tooltip="Organization memory governance"
        />
      ) : null}
      <Button
        icon={SvgNetworkGraph}
        prominence="secondary"
        onClick={() => setBrainOpen(true)}
      >
        Brain
      </Button>
      <Button
        icon={SvgSettings}
        prominence="secondary"
        onClick={() => setSettingsOpen(true)}
      >
        Settings
      </Button>
      <Button
        icon={SvgPlus}
        disabled={!canCreateUpdateRestore}
        onClick={() => openMemory(null)}
      >
        Add memory
      </Button>
    </div>
  );

  return (
    <SettingsLayouts.Root width="full">
      <SettingsLayouts.Header
        icon={SvgBookOpen}
        title="Memory"
        description="View and manage what Onyx has learned about you."
        density="compact"
        rightChildren={<div className="hidden sm:block">{headerActions}</div>}
      >
        <div className="flex w-full flex-col gap-2">
          <div className="sm:hidden">{headerActions}</div>
          <div className="flex w-full items-center gap-2">
            <div className="min-w-0 flex-1">
              <InputTypeIn
                clearButton
                placeholder="Search memory"
                searchIcon
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
            <div className="flex shrink-0 rounded-08 border border-border-01 bg-background-tint-02 p-0.5">
              <Button
                icon={SvgBlocks}
                prominence={view === "grid" ? "secondary" : "tertiary"}
                size="sm"
                tooltip="Grid view"
                onClick={() => setViewMode("grid")}
              />
              <Button
                icon={SvgMenu}
                prominence={view === "list" ? "secondary" : "tertiary"}
                size="sm"
                tooltip="List view"
                onClick={() => setViewMode("list")}
              />
              <Button
                icon={SvgNetworkGraph}
                prominence={view === "graph" ? "secondary" : "tertiary"}
                size="sm"
                tooltip="Graph view"
                onClick={() => setViewMode("graph")}
              />
            </div>
          </div>
        </div>
      </SettingsLayouts.Header>
      <SettingsLayouts.Body density="compact">
        <div className="flex w-full flex-col gap-5 md:flex-row md:items-start">
          <div className="flex w-full gap-1 overflow-x-auto pb-1 md:sticky md:top-4 md:w-56 md:shrink-0 md:flex-col md:overflow-visible">
            {CATEGORIES.map((item) => {
              const Icon = item.icon;
              const active = category === item.value;

              return (
                <SidebarTab
                  key={item.value}
                  icon={Icon}
                  selected={active}
                  variant="sidebar-light"
                  type="button"
                  onClick={() => setCategory(item.value)}
                  rightChildren={
                    <Text font="secondary-body" color="text-03">
                      {String(countFor(item.value))}
                    </Text>
                  }
                >
                  {item.label}
                </SidebarTab>
              );
            })}
          </div>

          <section className="min-w-0 flex-1">
            {view === "graph" ? (
              <>
                <div className="mb-3 flex items-baseline gap-2">
                  <Text font="heading-h3" color="text-05">
                    Context graph
                  </Text>
                  <Text font="secondary-body" color="text-03">
                    Explore how your memories connect.
                  </Text>
                </div>
                <MemoryGraphView onSelectMemory={openMemoryById} />
              </>
            ) : (
              <>
                <div className="mb-3 flex items-baseline gap-2">
                  <Text font="heading-h3" color="text-05">
                    {CATEGORIES.find((item) => item.value === category)?.label}
                  </Text>
                  <Text font="secondary-body" color="text-03">
                    {`${visibleMemories.length} ${visibleMemories.length === 1 ? "memory" : "memories"}`}
                  </Text>
                </div>

                {isLoading ? (
                  <div className="flex justify-center py-16">
                    <SvgSimpleLoader className="h-6 w-6" />
                  </div>
                ) : error ? (
                  <MessageCard
                    variant="error"
                    title="Memory could not be loaded"
                    description="Try refreshing the page."
                  />
                ) : visibleMemories.length === 0 ? (
                  <IllustrationContent
                    illustration={SvgNoResult}
                    title={
                      memories.length === 0
                        ? "No memories yet"
                        : "No memories found"
                    }
                    description={
                      memories.length === 0
                        ? "Add durable context or let Onyx learn useful details from conversations."
                        : "Try a different category or search."
                    }
                  />
                ) : view === "grid" ? (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {visibleMemories.map((memory) => (
                      <MemoryCard
                        key={memory.id}
                        memory={memory}
                        view="grid"
                        onClick={openMemory}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col divide-y divide-border-01 border-y border-border-01">
                    {visibleMemories.map((memory) => (
                      <MemoryCard
                        key={memory.id}
                        memory={memory}
                        view="list"
                        onClick={openMemory}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </SettingsLayouts.Body>

      <MemoryEditorModal
        open={editorOpen}
        memory={selectedMemory}
        canCreateUpdateRestore={canCreateUpdateRestore}
        canDelete={canDelete}
        onClose={() => setEditorOpen(false)}
        onChanged={() => void mutate()}
      />
      <MemorySettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
      <BrainSettingsModal
        open={brainOpen}
        onClose={() => setBrainOpen(false)}
      />
    </SettingsLayouts.Root>
  );
}
