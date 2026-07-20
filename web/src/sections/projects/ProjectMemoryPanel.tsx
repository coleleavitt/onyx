"use client";

import { useState } from "react";
import { useSWRConfig } from "swr";
import { Button, Text } from "@opal/components";
import { ContentAction } from "@opal/layouts";
import { toast } from "@opal/layouts";
import { SvgBookOpen, SvgPlusCircle } from "@opal/icons";
import Modal from "@/refresh-components/Modal";
import InputTextArea from "@/refresh-components/inputs/InputTextArea";
import { InputTypeIn } from "@opal/components";
import { createMemory } from "@/lib/memory/api";
import {
  MEMORY_LIST_KEY,
  spaceMemoryListKey,
  useSpaceMemories,
} from "@/lib/memory/hooks";

interface ProjectMemoryPanelProps {
  /** The space these memories are scoped to. */
  projectId: number;
  /** Whether the current user can add memories to this space. */
  canEdit: boolean;
}

/**
 * Space-scoped memory section for the Space detail rail. Lists the memories
 * attached to this space (`GET /api/memory?project_id=...`) and lets editors
 * add a new one scoped to the space (`POST /api/memory` with `project_id`).
 *
 * Previously this was orphaned "coming soon" dead code; it is now wired into
 * `ProjectContextPanel` and drives the real memory API.
 */
export default function ProjectMemoryPanel({
  projectId,
  canEdit,
}: ProjectMemoryPanelProps) {
  const { mutate } = useSWRConfig();
  const { memories, isLoading } = useSpaceMemories(projectId);
  const [addOpen, setAddOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    await mutate(spaceMemoryListKey(projectId));
    // Also refresh the global memory list so the library stays consistent.
    await mutate(MEMORY_LIST_KEY);
  }

  async function submit() {
    if (!content.trim()) return;
    setBusy(true);
    try {
      await createMemory({
        title: title.trim() || null,
        category: "notes",
        content: content.trim(),
        project_id: projectId,
      });
      toast.success("Memory added to this space.");
      setTitle("");
      setContent("");
      setAddOpen(false);
      await refresh();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to add memory."
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
        title="Memory"
        description="Notes the agent remembers and can reference in this space."
        padding="fit"
        center
        rightChildren={
          canEdit ? (
            <Button
              icon={SvgPlusCircle}
              prominence="tertiary"
              interaction={addOpen ? "active" : undefined}
              onClick={() => setAddOpen(true)}
            >
              Add memory
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <div className="flex min-h-12 items-center rounded-12 border border-dashed border-border-01 px-3 py-2.5">
          <Text as="p" font="secondary-body" color="text-03">
            Loading memories…
          </Text>
        </div>
      ) : memories.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          {memories.map((memory) => (
            <div
              key={memory.id}
              className="flex items-start gap-2 rounded-12 border border-border-01 bg-background-tint-02 px-3 py-2.5"
            >
              <SvgBookOpen className="mt-0.5 h-4 w-4 shrink-0 stroke-text-03" />
              <div className="flex min-w-0 flex-1 flex-col">
                <Text font="main-ui-body" color="text-05" maxLines={1}>
                  {memory.title}
                </Text>
                <Text font="secondary-body" color="text-03" maxLines={2}>
                  {memory.content}
                </Text>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex min-h-12 items-center rounded-12 border border-dashed border-border-01 px-3 py-2.5">
          <Text as="p" font="secondary-body" color="text-03">
            {canEdit
              ? "No memories yet. Add notes the agent should remember in this space."
              : "No memories in this space yet."}
          </Text>
        </div>
      )}

      <Modal
        open={addOpen}
        onOpenChange={(next) => {
          if (!next) setAddOpen(false);
        }}
      >
        <Modal.Content width="sm">
          <Modal.Header
            icon={SvgBookOpen}
            title="Add space memory"
            description="Save durable context the agent can use in this space's chats."
            onClose={() => setAddOpen(false)}
          />
          <Modal.Body>
            <div className="flex w-full flex-col gap-4">
              <label className="flex flex-col gap-1">
                <Text font="main-ui-action" color="text-05">
                  Title
                </Text>
                <InputTypeIn
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Short, recognizable title"
                />
              </label>
              <label className="flex flex-col gap-1">
                <Text font="main-ui-action" color="text-05">
                  Memory
                </Text>
                <InputTextArea
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  placeholder="What should the agent remember in this space?"
                  rows={6}
                />
              </label>
            </div>
          </Modal.Body>
          <Modal.Footer>
            <Button prominence="secondary" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={!content.trim() || busy}
              onClick={() => void submit()}
            >
              {busy ? "Adding…" : "Add memory"}
            </Button>
          </Modal.Footer>
        </Modal.Content>
      </Modal>
    </div>
  );
}
