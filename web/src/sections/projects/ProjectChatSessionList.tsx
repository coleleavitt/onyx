"use client";

import React, { useCallback, useMemo, useState } from "react";
import { deleteChatSession } from "@/app/app/services/lib";
import {
  moveChatSession as moveChatSessionService,
  removeChatSessionFromProject as removeChatSessionFromProjectService,
} from "@/lib/projects/svc";
import { useProjectsContext } from "@/providers/ProjectsContext";
import { useUser } from "@/providers/UserProvider";
import { ChatSession } from "@/app/app/interfaces";
import AgentAvatar from "@/refresh-components/avatars/AgentAvatar";
import { useAgents } from "@/lib/agents/hooks";
import useChatSessions from "@/hooks/useChatSessions";
import {
  Button,
  Card,
  InputTypeIn,
  LineItemButton,
  Popover,
  PopoverMenu,
  Tabs,
  Text,
} from "@opal/components";
import { Hoverable } from "@opal/core";
import { DEFAULT_AGENT_ID, UNNAMED_CHAT } from "@/lib/constants";
import {
  SvgBubbleText,
  SvgFolder,
  SvgFolderIn,
  SvgMoreHorizontal,
  SvgSimpleLoader,
  SvgTrash,
} from "@opal/icons";
import { timeAgo } from "@opal/time";
import type { IconFunctionComponent } from "@opal/types";
import { noProp } from "@/lib/utils";
import MoveCustomAgentChatModal from "@/sections/modals/MoveCustomAgentChatModal";
import ConfirmationModalLayout from "@/refresh-components/layouts/ConfirmationModalLayout";
import { PopoverSearchInput } from "@/sections/sidebar/ChatButton";
import SpaceDetailHeader from "@/sections/projects/SpaceDetailHeader";

const LS_HIDE_MOVE_CUSTOM_AGENT_MODAL_KEY = "onyx:hideMoveCustomAgentModal";

type SessionOwnerFilter = "all" | "mine";

// Project chat sessions don't currently carry an owner id in their serialized
// shape, so this reads one defensively and returns undefined when absent.
function getChatOwnerId(chat: ChatSession): string | undefined {
  const ownerId = (chat as { user_id?: unknown }).user_id;
  return typeof ownerId === "string" ? ownerId : undefined;
}

interface ProjectChatItemProps {
  chat: ChatSession;
  projectId: number;
  icon: IconFunctionComponent;
  afterRefresh: () => void;
}

function ProjectChatItem({
  chat,
  projectId,
  icon,
  afterRefresh,
}: ProjectChatItemProps) {
  const [popoverOpen, setPopoverOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [pendingMoveProjectId, setPendingMoveProjectId] = useState<
    number | null
  >(null);
  const [showMoveCustomAgentModal, setShowMoveCustomAgentModal] =
    useState(false);
  const [showMoveOptions, setShowMoveOptions] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");

  const lastUpdateTime = useMemo(
    () => timeAgo(chat.time_updated),
    [chat.time_updated],
  );

  const { refreshChatSessions, removeSession } = useChatSessions();
  const { fetchProjects, projects } = useProjectsContext();

  const isChatUsingDefaultAgent = chat.persona_id === DEFAULT_AGENT_ID;

  const filteredProjects = projects.filter((project) =>
    project.name.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  const handleConfirmDelete = useCallback(
    async (e: React.MouseEvent<HTMLButtonElement>) => {
      e.stopPropagation();
      await deleteChatSession(chat.id);
      removeSession(chat.id);
      await refreshChatSessions();
      await fetchProjects();
      setIsDeleteModalOpen(false);
      setPopoverOpen(false);
      afterRefresh();
    },
    [chat, refreshChatSessions, removeSession, fetchProjects, afterRefresh],
  );

  const performMove = useCallback(
    async (targetProjectId: number) => {
      await moveChatSessionService(targetProjectId, chat.id);
      await fetchProjects();
      await refreshChatSessions();
      setPopoverOpen(false);
      afterRefresh();
    },
    [chat.id, fetchProjects, refreshChatSessions, afterRefresh],
  );

  const handleMoveChatSession = useCallback(
    async (item: { id: number; label: string }) => {
      const hideModal =
        typeof window !== "undefined" &&
        window.localStorage.getItem(LS_HIDE_MOVE_CUSTOM_AGENT_MODAL_KEY) ===
          "true";

      if (!isChatUsingDefaultAgent && !hideModal) {
        setPendingMoveProjectId(item.id);
        setShowMoveCustomAgentModal(true);
        return;
      }

      await performMove(item.id);
    },
    [isChatUsingDefaultAgent, performMove],
  );

  const handleRemoveFromProject = useCallback(async () => {
    await removeChatSessionFromProjectService(chat.id);
    await fetchProjects();
    await refreshChatSessions();
    afterRefresh();
    setPopoverOpen(false);
  }, [chat.id, fetchProjects, refreshChatSessions, afterRefresh]);

  const popoverItems = useMemo(() => {
    if (!showMoveOptions) {
      return [
        <LineItemButton
          key="move"
          sizePreset="main-ui"
          rounding="sm"
          icon={SvgFolderIn}
          title="Move to space"
          onClick={noProp(() => setShowMoveOptions(true))}
        />,
        <LineItemButton
          key="remove"
          sizePreset="main-ui"
          rounding="sm"
          icon={SvgFolder}
          title={`Remove from ${projects.find((p) => p.id === projectId)?.name ?? "space"}`}
          onClick={noProp(handleRemoveFromProject)}
        />,
        null,
        <LineItemButton
          key="delete"
          sizePreset="main-ui"
          rounding="sm"
          color="danger"
          icon={SvgTrash}
          title="Delete"
          onClick={noProp(() => setIsDeleteModalOpen(true))}
        />,
      ];
    }
    return [
      <PopoverSearchInput
        key="search"
        setShowMoveOptions={setShowMoveOptions}
        onSearch={setSearchTerm}
      />,
      ...filteredProjects
        .filter((candidate) => candidate.id !== projectId)
        .map((target) => (
          <LineItemButton
            key={target.id}
            sizePreset="main-ui"
            rounding="sm"
            icon={SvgFolder}
            title={target.name}
            onClick={noProp(() =>
              handleMoveChatSession({ id: target.id, label: target.name }),
            )}
          />
        )),
    ];
  }, [
    showMoveOptions,
    projects,
    projectId,
    filteredProjects,
    handleMoveChatSession,
    handleRemoveFromProject,
  ]);

  return (
    <>
      {isDeleteModalOpen && (
        <ConfirmationModalLayout
          title="Delete Chat"
          icon={SvgTrash}
          onClose={() => setIsDeleteModalOpen(false)}
          submit={
            <Button variant="danger" onClick={handleConfirmDelete}>
              Delete
            </Button>
          }
        >
          Are you sure you want to delete this chat? This action cannot be
          undone.
        </ConfirmationModalLayout>
      )}

      {showMoveCustomAgentModal && (
        <MoveCustomAgentChatModal
          onCancel={() => {
            setShowMoveCustomAgentModal(false);
            setPendingMoveProjectId(null);
          }}
          onConfirm={async (doNotShowAgain) => {
            if (doNotShowAgain && typeof window !== "undefined") {
              window.localStorage.setItem(
                LS_HIDE_MOVE_CUSTOM_AGENT_MODAL_KEY,
                "true",
              );
            }
            const target = pendingMoveProjectId;
            setShowMoveCustomAgentModal(false);
            setPendingMoveProjectId(null);
            if (target != null) await performMove(target);
          }}
        />
      )}

      <Hoverable.Root group={chat.id} width="full">
        <LineItemButton
          href={`/app?chatId=${chat.id}`}
          group={chat.id}
          icon={icon}
          title={chat.name || UNNAMED_CHAT}
          description={
            lastUpdateTime ? `Last message ${lastUpdateTime}` : undefined
          }
          sizePreset="main-ui"
          interaction={popoverOpen ? "active" : undefined}
          rightChildren={
            <Hoverable.Item group={chat.id} variant="appear-on-hover">
              <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
                <Popover.Trigger
                  asChild
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    setPopoverOpen(!popoverOpen);
                  }}
                >
                  <Button
                    icon={SvgMoreHorizontal}
                    size="sm"
                    prominence="tertiary"
                  />
                </Popover.Trigger>
                <Popover.Content
                  align="end"
                  side="right"
                  avoidCollisions
                  sideOffset={8}
                >
                  <PopoverMenu>{popoverItems}</PopoverMenu>
                </Popover.Content>
              </Popover>
            </Hoverable.Item>
          }
        />
      </Hoverable.Root>
    </>
  );
}

interface ProjectChatSessionListProps {
  showIdentityHeader?: boolean;
}

export default function ProjectChatSessionList({
  showIdentityHeader = true,
}: ProjectChatSessionListProps) {
  const {
    currentProjectDetails,
    currentProjectId,
    refreshCurrentProjectDetails,
    isLoadingProjectDetails,
    updateProjectMetadata,
  } = useProjectsContext();
  const { agents } = useAgents();
  const { user } = useUser();
  const currentUserId = user?.id ?? null;
  const [query, setQuery] = useState("");
  const [sessionFilter, setSessionFilter] = useState<SessionOwnerFilter>("all");

  const projectChats: ChatSession[] = useMemo(() => {
    const sessions = currentProjectDetails?.project?.chat_sessions || [];
    return [...sessions].sort(
      (a, b) =>
        new Date(b.time_updated).getTime() - new Date(a.time_updated).getTime(),
    );
  }, [currentProjectDetails?.project?.chat_sessions]);

  const filteredChats: ChatSession[] = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    const bySearch = normalized
      ? projectChats.filter((chat) =>
          (chat.name || UNNAMED_CHAT).toLowerCase().includes(normalized),
        )
      : projectChats;

    if (sessionFilter !== "mine" || !currentUserId) return bySearch;

    // Fall back to showing all when no chat exposes an owner id, so the
    // "Your sessions" filter stays no-op-safe until that data is available.
    const hasOwnerInfo = bySearch.some(
      (chat) => getChatOwnerId(chat) !== undefined,
    );
    if (!hasOwnerInfo) return bySearch;

    return bySearch.filter((chat) => getChatOwnerId(chat) === currentUserId);
  }, [projectChats, query, sessionFilter, currentUserId]);

  if (!currentProjectId) return null;

  const currentProject = currentProjectDetails?.project ?? null;
  const canEdit =
    currentProject !== null && currentProject.user_permission !== "VIEWER";

  return (
    <div className="mx-auto flex flex-col gap-5 pt-5">
      {showIdentityHeader && currentProject ? (
        <div className="px-3 pb-2">
          <SpaceDetailHeader
            project={currentProject}
            canEdit={canEdit}
            onUpdate={(metadata) =>
              updateProjectMetadata(currentProject.id, metadata)
            }
          />
        </div>
      ) : null}

      <div>
        {projectChats.length > 0 && (
          <div className="px-3 pb-1">
            <Tabs
              variant="pill"
              value={sessionFilter}
              onValueChange={(value) =>
                setSessionFilter(value === "mine" ? "mine" : "all")
              }
            >
              <Tabs.List>
                <Tabs.Trigger value="all">All</Tabs.Trigger>
                <Tabs.Trigger value="mine">Your sessions</Tabs.Trigger>
              </Tabs.List>
            </Tabs>
          </div>
        )}

        <div className="flex items-center justify-between gap-2 px-3 py-2">
          <Text as="p" font="secondary-action" color="text-03">
            Recent chats
          </Text>
          {projectChats.length > 0 && (
            <div className="w-48 shrink-0">
              <InputTypeIn
                clearButton
                searchIcon
                placeholder="Search chats"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </div>
          )}
        </div>

        {isLoadingProjectDetails && !currentProjectDetails ? (
          <SvgSimpleLoader className="mx-4" />
        ) : projectChats.length === 0 ? (
          <Card rounding="md" border="dashed" background="none" padding="sm">
            <div className="p-1">
              <Text as="p" font="secondary-body" color="text-03">
                No chats yet.
              </Text>
            </div>
          </Card>
        ) : filteredChats.length === 0 ? (
          <Card rounding="md" border="dashed" background="none" padding="sm">
            <div className="p-1">
              <Text as="p" font="secondary-body" color="text-03">
                No chats match your search.
              </Text>
            </div>
          </Card>
        ) : (
          filteredChats.map((chat) => {
            const personaIdToFeatured =
              currentProjectDetails?.persona_id_to_is_featured || {};
            const isFeatured = personaIdToFeatured[chat.persona_id];
            const agent =
              isFeatured === false
                ? agents.find((a) => a.id === chat.persona_id)
                : undefined;
            const icon: IconFunctionComponent = agent
              ? ((() => (
                  <AgentAvatar agent={agent} size={18} />
                )) as IconFunctionComponent)
              : SvgBubbleText;

            return (
              <div key={chat.id} className="px-1">
                <ProjectChatItem
                  chat={chat}
                  projectId={currentProjectId}
                  icon={icon}
                  afterRefresh={refreshCurrentProjectDetails}
                />
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
