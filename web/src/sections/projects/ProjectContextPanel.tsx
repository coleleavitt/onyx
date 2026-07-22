"use client";

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useProjectsContext } from "@/providers/ProjectsContext";
import FilePickerPopover from "@/refresh-components/popovers/FilePickerPopover";
import { UserFileStatus, type ProjectFile } from "@/lib/projects/types";
import { MinimalOnyxDocument } from "@/lib/search/interfaces";
import { Button, Divider, LineItemButton, Text } from "@opal/components";
import { timeAgo } from "@opal/time";
import { Content, ContentAction } from "@opal/layouts";
import AddInstructionModal from "@/sections/modals/AddInstructionModal";
import ViewInstructionsModal from "@/sections/modals/ViewInstructionsModal";
import EditSpaceDetailsModal from "@/sections/modals/EditSpaceDetailsModal";
import ShareProjectModal from "@/sections/modals/ShareProjectModal";
import UserFilesModal from "@/sections/modals/UserFilesModal";
import { useCreateModal } from "@/refresh-components/contexts/ModalContext";
import { FileCard } from "@/sections/cards/FileCard";
import SpaceDetailHeader from "@/sections/projects/SpaceDetailHeader";
import ProjectMemoryPanel from "@/sections/projects/ProjectMemoryPanel";
import SpaceLinksSection from "@/sections/projects/SpaceLinksSection";
import SpaceSkillsSection from "@/sections/projects/SpaceSkillsSection";
import SpaceScheduledTasksSection from "@/sections/projects/SpaceScheduledTasksSection";
import { parseSpaceInstructions } from "@/lib/projects/spaceMetadata";
import { hasNonImageFiles } from "@/lib/utils";
import { cn } from "@opal/utils";
import {
  SvgCalendar,
  SvgEdit,
  SvgFileText,
  SvgFiles,
  SvgFolderOpen,
  SvgPlusCircle,
  SvgSidebar,
  SvgSimpleLoader,
  SvgShare,
  SvgUser,
} from "@opal/icons";

export interface ProjectContextPanelProps {
  projectTokenCount?: number;
  availableContextTokens?: number;
  setPresentingDocument?: (document: MinimalOnyxDocument) => void;
  onCollapsePanel?: () => void;
  showIdentityHeader?: boolean;
  compact?: boolean;
}

interface SectionPlaceholderProps {
  children: string;
  dragActive?: boolean;
}

function SectionPlaceholder({
  children,
  dragActive = false,
}: SectionPlaceholderProps) {
  return (
    <div
      className={cn(
        "flex min-h-12 items-center rounded-12 border border-dashed px-3 py-2.5",
        dragActive
          ? "border-action-link-05 bg-action-link-01 text-action-link-05"
          : "border-border-01 text-text-03",
      )}
    >
      <Text as="p" font="secondary-body" color="inherit">
        {children}
      </Text>
    </div>
  );
}

export default function ProjectContextPanel({
  projectTokenCount = 0,
  availableContextTokens = 128_000,
  setPresentingDocument,
  onCollapsePanel,
  showIdentityHeader = true,
  compact = false,
}: ProjectContextPanelProps) {
  const addInstructionModal = useCreateModal();
  const editDetailsModal = useCreateModal();
  const projectFilesModal = useCreateModal();
  const shareProjectModal = useCreateModal();
  const [viewInstructionsOpen, setViewInstructionsOpen] = useState(false);
  // Convert ProjectFile to MinimalOnyxDocument format for viewing
  const handleOnView = useCallback(
    (file: ProjectFile) => {
      if (!setPresentingDocument) return;

      const documentForViewer: MinimalOnyxDocument = {
        document_id: `project_file__${file.file_id}`,
        semantic_identifier: file.name,
      };

      setPresentingDocument(documentForViewer);
    },
    [setPresentingDocument],
  );
  const {
    currentProjectDetails,
    currentProjectId,
    unlinkFileFromProject,
    linkFileToProject,
    allCurrentProjectFiles,
    isLoadingProjectDetails,
    beginUpload,
    projects,
    fetchProjects,
    refreshCurrentProjectDetails,
    updateProjectMetadata,
  } = useProjectsContext();
  const currentProject =
    currentProjectDetails?.project ??
    projects.find((project) => project.id === currentProjectId) ??
    null;
  const canEdit =
    currentProject !== null && currentProject.user_permission !== "VIEWER";
  const isOwner = currentProject?.user_permission === "OWNER";
  // Strip the machine-readable space-metadata block (links/skills) so only the
  // human-facing instructions are shown.
  const instructionsText = parseSpaceInstructions(
    currentProjectDetails?.project?.instructions,
  ).instructions;
  const handleUploadFiles = useCallback(
    async (files: File[]) => {
      if (!files || files.length === 0) return;
      beginUpload(Array.from(files), currentProjectId);
    },
    [currentProjectId, beginUpload],
  );

  const totalFiles = allCurrentProjectFiles.length;
  const displayFileCount = totalFiles > 100 ? "100+" : String(totalFiles);

  const handleUploadChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (!files || files.length === 0) return;
      await handleUploadFiles(Array.from(files));
      e.target.value = "";
    },
    [handleUploadFiles],
  );

  // Nested dropzone for drag-and-drop within ProjectContextPanel
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    disabled: !canEdit,
    noClick: true,
    noKeyboard: true,
    multiple: true,
    noDragEventsBubbling: true,
    onDrop: (acceptedFiles) => {
      void handleUploadFiles(acceptedFiles);
    },
  });

  const projectName = currentProject?.name || "Loading project...";

  if (!currentProjectId) return null; // no selection yet

  // Detect if there are any non-image files in the displayed files
  // to determine if images should be compact
  const displayedFiles = allCurrentProjectFiles.slice(0, 4);
  const shouldCompactImages = hasNonImageFiles(displayedFiles);

  return (
    <>
      <addInstructionModal.Provider>
        <AddInstructionModal />
      </addInstructionModal.Provider>

      <ShareProjectModal
        project={currentProject}
        open={shareProjectModal.isOpen}
        onClose={() => shareProjectModal.toggle(false)}
        onSaved={() => {
          void fetchProjects();
          void refreshCurrentProjectDetails();
        }}
      />
      <EditSpaceDetailsModal
        project={currentProject}
        open={editDetailsModal.isOpen}
        onClose={() => editDetailsModal.toggle(false)}
      />

      <ViewInstructionsModal
        open={viewInstructionsOpen}
        instructions={instructionsText}
        onClose={() => setViewInstructionsOpen(false)}
      />

      <projectFilesModal.Provider>
        <UserFilesModal
          title="Space Files"
          description="Sessions in this space can access the files here."
          recentFiles={[...allCurrentProjectFiles]}
          onView={handleOnView}
          handleUploadChange={handleUploadChange}
          onDelete={
            canEdit
              ? async (file: ProjectFile) => {
                  if (!currentProjectId) return;
                  await unlinkFileFromProject(currentProjectId, file.id);
                }
              : undefined
          }
        />
      </projectFilesModal.Provider>

      <div
        className={cn("w-full flex flex-col pb-6", compact ? "gap-5" : "gap-6")}
      >
        {showIdentityHeader && (
          <>
            <div className="flex w-full flex-col gap-3">
              <div className="flex w-full items-start justify-between gap-3">
                {currentProject ? (
                  <div className="min-w-0 flex-1">
                    <SpaceDetailHeader
                      project={currentProject}
                      canEdit={canEdit}
                      onUpdate={(metadata) =>
                        updateProjectMetadata(currentProject.id, metadata)
                      }
                    />
                  </div>
                ) : (
                  <Content icon={SvgFolderOpen} title={projectName} />
                )}
                {onCollapsePanel && (
                  <Button
                    icon={SvgSidebar}
                    aria-label="Hide space details"
                    prominence="tertiary"
                    tooltip="Hide space details"
                    tooltipSide="bottom"
                    onClick={onCollapsePanel}
                  />
                )}
              </div>
              {(canEdit || isOwner) && (
                <div className="flex flex-wrap items-center gap-2">
                  {canEdit && (
                    <Button
                      icon={SvgEdit}
                      interaction={
                        editDetailsModal.isOpen ? "active" : undefined
                      }
                      onClick={() => editDetailsModal.toggle(true)}
                      prominence="secondary"
                    >
                      Edit details
                    </Button>
                  )}
                  {isOwner && (
                    <Button
                      icon={SvgShare}
                      interaction={
                        shareProjectModal.isOpen ? "active" : undefined
                      }
                      onClick={() => shareProjectModal.toggle(true)}
                      prominence="secondary"
                    >
                      Share
                    </Button>
                  )}
                </div>
              )}
            </div>
            <div className="flex flex-wrap gap-2 text-text-03">
              {currentProject?.owner?.email && (
                <div className="flex items-center gap-1">
                  <SvgUser className="h-3.5 w-3.5 stroke-current" />
                  <Text font="secondary-body" color="inherit">
                    {`Owner: ${currentProject.owner.email}`}
                  </Text>
                </div>
              )}
              {currentProject?.created_at && (
                <div className="flex items-center gap-1">
                  <SvgCalendar className="h-3.5 w-3.5 stroke-current" />
                  <Text font="secondary-body" color="inherit">
                    {`Created ${timeAgo(currentProject.created_at) ?? new Date(currentProject.created_at).toLocaleDateString()}`}
                  </Text>
                </div>
              )}
              {currentProject && (
                <Text font="secondary-body" color="inherit">
                  {`Access: ${currentProject.user_permission.toLowerCase()}`}
                </Text>
              )}
            </div>

            <Divider paddingParallel="fit" paddingPerpendicular="fit" />
          </>
        )}

        {!showIdentityHeader && onCollapsePanel && (
          <div className="flex items-center justify-between gap-2">
            <Text font="secondary-action" color="text-03">
              Space details
            </Text>
            <Button
              icon={SvgSidebar}
              aria-label="Hide space details"
              prominence="tertiary"
              tooltip="Hide space details"
              tooltipSide="bottom"
              onClick={onCollapsePanel}
            />
          </div>
        )}

        <div className="flex flex-col gap-2">
          <ContentAction
            icon={SvgFileText}
            sizePreset="main-ui"
            variant="section"
            title="Instructions"
            description={
              compact
                ? undefined
                : "Give the agent instructions for how it should work in this space."
            }
            padding="fit"
            center
          />
          {isLoadingProjectDetails && !currentProjectDetails ? (
            <SvgSimpleLoader />
          ) : (
            <div className="overflow-hidden rounded-12 border border-border-01 bg-background-tint-02">
              {instructionsText ? (
                <>
                  <div className="whitespace-pre-wrap break-words px-3 py-2.5">
                    <Text
                      as="p"
                      font="secondary-body"
                      color="text-04"
                      maxLines={5}
                    >
                      {instructionsText}
                    </Text>
                  </div>
                  <div className="border-t border-border-01">
                    <LineItemButton
                      sizePreset="main-ui"
                      width="full"
                      icon={canEdit ? SvgEdit : SvgFileText}
                      title={canEdit ? "Edit instructions" : "View all"}
                      onClick={() =>
                        canEdit
                          ? addInstructionModal.toggle(true)
                          : setViewInstructionsOpen(true)
                      }
                    />
                  </div>
                </>
              ) : canEdit ? (
                <LineItemButton
                  sizePreset="main-ui"
                  width="full"
                  icon={SvgPlusCircle}
                  title="Add instructions..."
                  onClick={() => addInstructionModal.toggle(true)}
                />
              ) : (
                <div className="px-3 py-2.5">
                  <Text as="p" font="secondary-body" color="text-02">
                    No instructions yet
                  </Text>
                </div>
              )}
            </div>
          )}
        </div>

        <div
          className="flex flex-col gap-2 pb-2"
          {...getRootProps({ onClick: (e) => e.stopPropagation() })}
        >
          <ContentAction
            sizePreset="main-ui"
            variant="section"
            icon={SvgFiles}
            title="Files"
            description={
              compact
                ? undefined
                : "Chats in this space can access these files."
            }
            padding="fit"
            center
            rightChildren={
              canEdit ? (
                <FilePickerPopover
                  trigger={(open) => (
                    <Button
                      icon={SvgPlusCircle}
                      prominence="tertiary"
                      interaction={open ? "active" : undefined}
                      aria-label="Add files"
                      tooltip={compact ? "Add files" : undefined}
                      tooltipSide="bottom"
                    >
                      {compact ? undefined : "Add Files"}
                    </Button>
                  )}
                  onFileClick={handleOnView}
                  onPickRecent={async (file) => {
                    if (file.status === UserFileStatus.UPLOADING) return;
                    if (file.status === UserFileStatus.DELETING) return;
                    if (!currentProjectId) return;
                    if (!linkFileToProject) return;
                    linkFileToProject(currentProjectId, file);
                  }}
                  onUnpickRecent={async (file) => {
                    if (!currentProjectId) return;
                    await unlinkFileFromProject(currentProjectId, file.id);
                  }}
                  handleUploadChange={handleUploadChange}
                  selectedFileIds={(allCurrentProjectFiles || []).map(
                    (f) => f.id,
                  )}
                  compact={compact}
                />
              ) : undefined
            }
          />

          {/* Hidden input just to satisfy dropzone contract; we rely on FilePicker for clicks */}
          {canEdit && <input {...getInputProps()} />}

          {isLoadingProjectDetails && !currentProjectDetails ? (
            <SvgSimpleLoader />
          ) : allCurrentProjectFiles.length > 0 ? (
            <>
              {/* Mobile / small screens: just show a button to view files */}
              <div className="sm:hidden">
                <LineItemButton
                  sizePreset="main-ui"
                  variant="section"
                  title="View files"
                  description={`${displayFileCount} files`}
                  icon={SvgFiles}
                  width="full"
                  onClick={() => projectFilesModal.toggle(true)}
                />
              </div>

              {/* Desktop / larger screens: show previews with optional View All */}
              <div className="hidden sm:flex gap-1 relative items-center">
                {allCurrentProjectFiles.slice(0, 4).map((f) => (
                  <FileCard
                    key={f.id}
                    file={f}
                    removeFile={
                      canEdit
                        ? async (fileId: string) => {
                            if (!currentProjectId) return;
                            await unlinkFileFromProject(
                              currentProjectId,
                              fileId,
                            );
                          }
                        : undefined
                    }
                    onFileClick={handleOnView}
                    compactImages={shouldCompactImages}
                  />
                ))}

                {totalFiles > 4 && (
                  <LineItemButton
                    sizePreset="main-ui"
                    variant="section"
                    title="View All"
                    description={`${displayFileCount} files`}
                    rightChildren={
                      <SvgFiles className="h-5 w-5 stroke-text-02" />
                    }
                    onClick={() => projectFilesModal.toggle(true)}
                  />
                )}
                {isDragActive && (
                  <div className="pointer-events-none absolute inset-0 rounded-lg border-2 border-dashed border-action-link-05" />
                )}
              </div>

              {projectTokenCount > availableContextTokens && (
                <Text as="p" font="secondary-body" color="text-02">
                  This project exceeds the model&apos;s context limits. Sessions
                  will automatically search for relevant files first before
                  generating response.
                </Text>
              )}
            </>
          ) : (
            <SectionPlaceholder dragActive={isDragActive}>
              {isDragActive
                ? "Drop files here to add to this space"
                : canEdit
                  ? compact
                    ? "Drop files here, or use + to add."
                    : "Add documents, texts, or images to use in the space. Drag & drop supported."
                  : "No files have been added to this space."}
            </SectionPlaceholder>
          )}
        </div>

        {/* Space-scoped memory — real, backed by /api/memory?project_id=... */}
        {currentProjectId !== null && (
          <ProjectMemoryPanel
            projectId={currentProjectId}
            canEdit={canEdit}
            compact={compact}
          />
        )}

        {/* Per-space skills — persisted via the space-metadata channel. */}
        <SpaceSkillsSection canEdit={canEdit} compact={compact} />

        {/* Links — working add-URL flow persisted via the space-metadata channel. */}
        <SpaceLinksSection canEdit={canEdit} compact={compact} />

        {/* Scheduled tasks scoped to this space. */}
        {currentProjectId !== null && (
          <SpaceScheduledTasksSection
            projectId={currentProjectId}
            canEdit={canEdit}
            compact={compact}
          />
        )}

        {!showIdentityHeader && (canEdit || isOwner) && (
          <div className="flex flex-col gap-2">
            <ContentAction
              icon={SvgEdit}
              sizePreset="main-ui"
              variant="section"
              title="Settings"
              padding="fit"
              center
            />
            <div className="flex flex-col gap-1">
              {canEdit && (
                <LineItemButton
                  sizePreset="main-ui"
                  variant="section"
                  width="full"
                  icon={SvgEdit}
                  title="Edit details"
                  onClick={() => editDetailsModal.toggle(true)}
                />
              )}
              {isOwner && (
                <LineItemButton
                  sizePreset="main-ui"
                  variant="section"
                  width="full"
                  icon={SvgShare}
                  title="Share space"
                  onClick={() => shareProjectModal.toggle(true)}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
