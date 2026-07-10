"use client";

import { useMemo, useState } from "react";
import type { Route } from "next";
import { useRouter } from "next/navigation";
import { useProjects } from "@/lib/projects/hooks";
import type { Project } from "@/lib/projects/types";
import { useCreateModal } from "@/refresh-components/contexts/ModalContext";
import CreateProjectModal from "@/sections/modals/CreateProjectModal";
import ShareProjectModal from "@/sections/modals/ShareProjectModal";
import { Button, InputTypeIn, Tabs, Tag, Text } from "@opal/components";
import { IllustrationContent, SettingsLayouts } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import {
  SvgFolder,
  SvgFolderPlus,
  SvgOrganization,
  SvgShare,
  SvgSimpleLoader,
  SvgUsers,
} from "@opal/icons";

type SpaceScope = "all" | "created" | "shared";

function accessLabel(project: Project): string {
  if (project.user_permission === "OWNER") return "Owner";
  if (project.user_permission === "EDITOR") return "Editor";
  return "Viewer";
}

export default function SpacesPage() {
  const router = useRouter();
  const createSpaceModal = useCreateModal();
  const { projects, isLoading, error, refreshProjects } = useProjects();
  const [scope, setScope] = useState<SpaceScope>("all");
  const [query, setQuery] = useState("");
  const [sharingProject, setSharingProject] = useState<Project | null>(null);

  const visibleProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return projects.filter((project) => {
      const matchesScope =
        scope === "all" ||
        (scope === "created" && project.user_permission === "OWNER") ||
        (scope === "shared" && project.user_permission !== "OWNER");
      const matchesQuery =
        !normalizedQuery ||
        project.name.toLowerCase().includes(normalizedQuery) ||
        (project.description ?? "").toLowerCase().includes(normalizedQuery);
      return matchesScope && matchesQuery;
    });
  }, [projects, query, scope]);

  return (
    <SettingsLayouts.Root width="lg">
      <SettingsLayouts.Header
        icon={SvgFolder}
        title="Spaces"
        description="Shared workspaces for conversations, files, instructions, and collaborators."
        rightChildren={
          <Button
            icon={SvgFolderPlus}
            onClick={() => createSpaceModal.toggle(true)}
          >
            New space
          </Button>
        }
      >
        <div className="flex w-full flex-col gap-2">
          <Tabs
            value={scope}
            onValueChange={(value) => setScope(value as SpaceScope)}
          >
            <Tabs.List>
              <Tabs.Trigger value="all">All</Tabs.Trigger>
              <Tabs.Trigger value="created">Created</Tabs.Trigger>
              <Tabs.Trigger value="shared">Shared</Tabs.Trigger>
            </Tabs.List>
          </Tabs>
          <div className="min-w-0 flex-1">
            <InputTypeIn
              clearButton
              placeholder="Search spaces"
              searchIcon
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>
      </SettingsLayouts.Header>
      <SettingsLayouts.Body>
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
          <div className="grid w-full grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visibleProjects.map((project) => (
              <article
                key={project.id}
                className="flex min-h-52 flex-col rounded-08 border border-border-01 bg-background-01 p-4 transition-colors hover:bg-background-tint-01"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-08 bg-background-tint-02">
                    <SvgFolder className="h-5 w-5 stroke-text-03" />
                  </div>
                  <div className="flex items-center gap-1">
                    {project.organization_permission ? (
                      <SvgOrganization
                        aria-label={`Organization can ${project.organization_permission.toLowerCase()}`}
                        className="h-4 w-4 stroke-text-03"
                      />
                    ) : null}
                    {project.user_permission === "OWNER" ? (
                      <Button
                        icon={SvgShare}
                        prominence="tertiary"
                        size="xs"
                        tooltip="Share space"
                        onClick={() => setSharingProject(project)}
                      />
                    ) : null}
                  </div>
                </div>
                <div className="mt-5 min-w-0 flex-1">
                  <Text font="heading-h3" color="text-05" maxLines={2}>
                    {project.name}
                  </Text>
                  <Text font="secondary-body" color="text-03" maxLines={3}>
                    {project.description ||
                      "Keep conversations, files, and instructions together."}
                  </Text>
                </div>
                <div className="mt-4 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-1.5">
                    <Tag color="gray" title={accessLabel(project)} />
                    <div className="flex items-center gap-1">
                      <SvgUsers className="h-3.5 w-3.5 stroke-text-03" />
                      <Text font="secondary-body" color="text-03">
                        {`${project.chat_sessions.length} chat${project.chat_sessions.length === 1 ? "" : "s"}`}
                      </Text>
                    </div>
                  </div>
                  <Button
                    prominence="secondary"
                    size="sm"
                    onClick={() =>
                      router.push(`/app?projectId=${project.id}` as Route)
                    }
                  >
                    Open
                  </Button>
                </div>
              </article>
            ))}
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
    </SettingsLayouts.Root>
  );
}
