"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useProjects } from "@/lib/projects/hooks";
import { spacePath } from "@/lib/projects/slug";
import type { Project } from "@/lib/projects/types";
import { deleteProject, setProjectPinned } from "@/lib/projects/svc";
import { groupSpaces } from "@/lib/projects/spaceGrouping";
import { useInvitedSpaceIds } from "@/lib/projects/useInvitedSpaceIds";
import { useCreateModal } from "@/refresh-components/contexts/ModalContext";
import { toast } from "@opal/layouts";
import SpaceCard from "@/sections/cards/SpaceCard";
import CreateProjectModal from "@/sections/modals/CreateProjectModal";
import EditSpaceDetailsModal from "@/sections/modals/EditSpaceDetailsModal";
import ShareProjectModal from "@/sections/modals/ShareProjectModal";
import ConfirmationModalLayout from "@/refresh-components/layouts/ConfirmationModalLayout";
import { Button, InputTypeIn, Text } from "@opal/components";
import { IllustrationContent, SettingsLayouts } from "@opal/layouts";
import { cn } from "@opal/utils";
import SvgNoResult from "@opal/illustrations/no-result";
import {
  SvgChevronRight,
  SvgFolder,
  SvgFolderPlus,
  SvgSimpleLoader,
  SvgTrash,
} from "@opal/icons";

const SECTION_EXPANDED_KEY = "onyx:spaces:section-expanded";

export default function SpacesPage() {
  const router = useRouter();
  const createSpaceModal = useCreateModal();
  const { projects, isLoading, error, refreshProjects } = useProjects();
  const [query, setQuery] = useState("");
  const [sharingProject, setSharingProject] = useState<Project | null>(null);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(SECTION_EXPANDED_KEY);
      if (stored) setCollapsed(JSON.parse(stored) as Record<string, boolean>);
    } catch {
      // ignore malformed persisted state
    }
  }, []);

  function toggleCollapsed(key: string) {
    setCollapsed((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      window.localStorage.setItem(SECTION_EXPANDED_KEY, JSON.stringify(next));
      return next;
    });
  }

  async function togglePin(project: Project) {
    try {
      await setProjectPinned(project.id, !project.is_pinned);
      await refreshProjects();
    } catch (pinError) {
      toast.error(
        pinError instanceof Error ? pinError.message : "Failed to update pin.",
      );
    }
  }

  async function confirmDelete() {
    if (!deletingProject) return;
    setDeleting(true);
    try {
      await deleteProject(deletingProject.id);
      await refreshProjects();
      toast.success("Space deleted.");
      setDeletingProject(null);
    } catch (deleteError) {
      toast.error(
        deleteError instanceof Error
          ? deleteError.message
          : "Failed to delete space.",
      );
    } finally {
      setDeleting(false);
    }
  }

  const visibleProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return projects;
    return projects.filter(
      (project) =>
        project.name.toLowerCase().includes(normalizedQuery) ||
        (project.description ?? "").toLowerCase().includes(normalizedQuery),
    );
  }, [projects, query]);

  const invitedProjectIds = useInvitedSpaceIds(projects);

  const spaceGroups = useMemo(
    () => groupSpaces(visibleProjects, { invitedProjectIds }),
    [visibleProjects, invitedProjectIds],
  );

  return (
    <SettingsLayouts.Root width="lg">
      <div className="sticky top-0 z-settings-header flex flex-wrap items-start justify-between gap-3 bg-background-neutral-00 px-4 py-4">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex items-center gap-2">
            <SvgFolder className="h-4 w-4 shrink-0 stroke-text-03" />
            <Text as="h1" font="heading-h3" color="text-05" nowrap>
              Spaces
            </Text>
            {!isLoading && projects.length > 0 ? (
              <Text font="secondary-body" color="text-02" nowrap>
                {String(projects.length)}
              </Text>
            ) : null}
          </div>
          <Text as="p" font="secondary-body" color="text-03">
            Organize chats, files, links, instructions, and collaborators by
            workspace.
          </Text>
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:flex-none">
          <div className="min-w-0 flex-1 sm:w-64 sm:flex-none">
            <InputTypeIn
              clearButton
              placeholder="Search spaces"
              searchIcon
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <Button
            icon={SvgFolderPlus}
            onClick={() => createSpaceModal.toggle(true)}
          >
            New space
          </Button>
        </div>
      </div>
      <SettingsLayouts.Body density="compact">
        {isLoading ? (
          <div className="flex w-full items-center justify-center gap-2 py-16">
            <SvgSimpleLoader className="h-5 w-5" />
            <Text color="text-03" font="main-ui-body">
              Loading spaces...
            </Text>
          </div>
        ) : error ? (
          <Text color="status-error-05" font="main-ui-body">
            Spaces could not be loaded.
          </Text>
        ) : visibleProjects.length === 0 ? (
          <IllustrationContent
            illustration={SvgNoResult}
            title={projects.length === 0 ? "No spaces yet" : "No spaces found"}
            description={
              projects.length === 0
                ? "Create a space to organize related work and invite collaborators."
                : "Try a different search or scope."
            }
          />
        ) : (
          <div className="flex w-full flex-col gap-5">
            {spaceGroups.map((group) => {
              const isCollapsed = collapsed[group.key] === true;
              return (
                <section key={group.key} className="flex w-full flex-col gap-2">
                  <button
                    type="button"
                    aria-expanded={!isCollapsed}
                    onClick={() => toggleCollapsed(group.key)}
                    className="flex w-full items-center gap-2 rounded-08 px-2 py-1 text-left transition-colors hover:bg-background-tint-01"
                  >
                    <SvgChevronRight
                      className={cn(
                        "h-3.5 w-3.5 shrink-0 stroke-text-03 transition-transform duration-150",
                        !isCollapsed && "rotate-90",
                      )}
                    />
                    <Text color="text-03" font="secondary-action">
                      {group.title}
                    </Text>
                    <Text color="text-02" font="secondary-body">
                      {String(group.items.length)}
                    </Text>
                  </button>
                  {!isCollapsed ? (
                    <div className="flex w-full flex-col rounded-16 border border-border-01 bg-background-neutral-00 p-1 shadow-box-01">
                      {group.items.map((project) => (
                        <SpaceCard
                          key={project.id}
                          project={project}
                          onOpen={(space) =>
                            router.push(spacePath(space.id, space.name))
                          }
                          onShare={setSharingProject}
                          onRename={setEditingProject}
                          onDelete={setDeletingProject}
                          onTogglePin={(space) => void togglePin(space)}
                        />
                      ))}
                    </div>
                  ) : null}
                </section>
              );
            })}
          </div>
        )}
      </SettingsLayouts.Body>

      <createSpaceModal.Provider>
        <CreateProjectModal terminology="space" />
      </createSpaceModal.Provider>
      <ShareProjectModal
        project={sharingProject}
        open={sharingProject !== null}
        onClose={() => setSharingProject(null)}
        onSaved={() => void refreshProjects()}
      />
      <EditSpaceDetailsModal
        project={editingProject}
        open={editingProject !== null}
        onClose={() => {
          setEditingProject(null);
          void refreshProjects();
        }}
      />
      {deletingProject ? (
        <ConfirmationModalLayout
          icon={SvgTrash}
          title={`Delete ${deletingProject.name}?`}
          description="This permanently removes the space. Chats and files are unlinked, not deleted."
          onClose={() => setDeletingProject(null)}
          submit={
            <Button
              variant="danger"
              disabled={deleting}
              onClick={() => void confirmDelete()}
            >
              {deleting ? "Deleting..." : "Delete space"}
            </Button>
          }
        />
      ) : null}
    </SettingsLayouts.Root>
  );
}
