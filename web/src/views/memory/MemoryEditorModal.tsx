"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { Button, Divider, InputTypeIn, Tabs, Text } from "@opal/components";
import { SvgBookOpen, SvgFolder, SvgHistory, SvgTrash } from "@opal/icons";
import Modal from "@/refresh-components/Modal";
import InputTextArea from "@/refresh-components/inputs/InputTextArea";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import MemoryRelatedPages from "@/views/memory/MemoryRelatedPages";
import MemorySources from "@/views/memory/MemorySources";

import { errorHandlingFetcher } from "@/lib/fetcher";
import {
  createMemory,
  deleteMemory,
  restoreMemoryRevision,
  updateMemory,
} from "@/lib/memory/api";
import type {
  MemoryCategory,
  MemoryItem,
  MemoryRevision,
} from "@/lib/memory/types";
import { toast } from "@opal/layouts";

const CATEGORY_LABELS: Record<MemoryCategory, string> = {
  notes: "Notes",
  concepts: "Concepts",
  entities: "Entities",
  workstreams: "Workstreams",
};

interface MemoryEditorModalProps {
  open: boolean;
  memory: MemoryItem | null;
  canCreateUpdateRestore: boolean;
  canDelete: boolean;
  onClose: () => void;
  onChanged: () => void;
}

export default function MemoryEditorModal({
  open,
  memory,
  canCreateUpdateRestore,
  canDelete,
  onClose,
  onChanged,
}: MemoryEditorModalProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState<MemoryCategory>("notes");
  const [tab, setTab] = useState<"details" | "history">("details");
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const historyKey = open && memory ? `/api/memory/${memory.id}/history` : null;
  const { data: history, mutate: refreshHistory } = useSWR<MemoryRevision[]>(
    historyKey,
    errorHandlingFetcher,
    { revalidateOnFocus: false }
  );

  useEffect(() => {
    setTitle(memory?.title ?? "");
    setContent(memory?.content ?? "");
    setCategory(memory?.category ?? "notes");
    setTab("details");
    setConfirmDelete(false);
  }, [memory, open]);

  const hasChanges = useMemo(
    () =>
      !memory ||
      title.trim() !== memory.title ||
      content.trim() !== memory.content ||
      category !== memory.category,
    [category, content, memory, title]
  );

  async function save() {
    if (!content.trim() || !canCreateUpdateRestore) return;
    setBusy(true);
    try {
      if (memory) {
        await updateMemory(memory.id, {
          title: title.trim() || null,
          category,
          content: content.trim(),
        });
        toast.success("Memory updated.");
      } else {
        await createMemory({
          title: title.trim() || null,
          category,
          content: content.trim(),
        });
        toast.success("Memory added.");
      }
      onChanged();
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Memory save failed."
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!memory || !canDelete) return;
    setBusy(true);
    try {
      await deleteMemory(memory.id);
      toast.success("Memory deleted.");
      onChanged();
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Memory deletion failed."
      );
    } finally {
      setBusy(false);
    }
  }

  async function restore(revision: MemoryRevision) {
    if (!memory || !canCreateUpdateRestore) return;
    setBusy(true);
    try {
      const restored = await restoreMemoryRevision(memory.id, revision.id);
      setTitle(restored.title);
      setContent(restored.content);
      setCategory(restored.category);
      await refreshHistory();
      onChanged();
      toast.success("Memory version restored.");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Version restore failed."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Modal.Content width="lg" height="lg">
        <Modal.Header
          icon={memory ? SvgBookOpen : undefined}
          title={memory ? memory.title : "Add memory"}
          description={
            memory
              ? "Edit what Onyx remembers or restore an earlier version."
              : "Save durable context that Onyx can use in future work."
          }
          onClose={onClose}
        >
          {memory ? (
            <Tabs
              value={tab}
              onValueChange={(value) => setTab(value as typeof tab)}
            >
              <Tabs.List>
                <Tabs.Trigger value="details">Details</Tabs.Trigger>
                <Tabs.Trigger value="history">History</Tabs.Trigger>
              </Tabs.List>
            </Tabs>
          ) : null}
        </Modal.Header>
        <Modal.Body>
          {tab === "details" ? (
            <div className="flex w-full flex-col gap-4">
              <label className="flex flex-col gap-1">
                <Text font="main-ui-action" color="text-05">
                  Title
                </Text>
                <InputTypeIn
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="Short, recognizable title"
                  variant={canCreateUpdateRestore ? "primary" : "disabled"}
                />
              </label>
              <label className="flex flex-col gap-1">
                <Text font="main-ui-action" color="text-05">
                  Category
                </Text>
                <InputSelect
                  value={category}
                  onValueChange={(value) =>
                    setCategory(value as MemoryCategory)
                  }
                  disabled={!canCreateUpdateRestore}
                >
                  <InputSelect.Trigger>
                    {CATEGORY_LABELS[category]}
                  </InputSelect.Trigger>
                  <InputSelect.Content>
                    {(Object.keys(CATEGORY_LABELS) as MemoryCategory[]).map(
                      (value) => (
                        <InputSelect.Item key={value} value={value}>
                          {CATEGORY_LABELS[value]}
                        </InputSelect.Item>
                      )
                    )}
                  </InputSelect.Content>
                </InputSelect>
              </label>
              <label className="flex flex-col gap-1">
                <Text font="main-ui-action" color="text-05">
                  Memory
                </Text>
                <InputTextArea
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  placeholder="What should Onyx remember?"
                  rows={10}
                  variant={canCreateUpdateRestore ? "primary" : "disabled"}
                />
              </label>
              {memory ? (
                <div className="flex w-full flex-col gap-4">
                  {memory.project_name ? (
                    <div className="flex items-center gap-2">
                      <SvgFolder className="h-4 w-4 shrink-0 stroke-text-03" />
                      <Text font="secondary-body" color="text-03">
                        {`Scoped to the "${memory.project_name}" space — only recalled in that space's chats.`}
                      </Text>
                    </div>
                  ) : null}
                  <MemoryRelatedPages memoryId={memory.id} />
                  <MemorySources memoryId={memory.id} />
                </div>
              ) : null}
            </div>
          ) : (
            <div className="flex w-full flex-col gap-2">
              {history?.map((revision, index) => (
                <div key={revision.id}>
                  <div className="flex items-start justify-between gap-4 py-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <SvgHistory className="h-4 w-4 shrink-0 stroke-text-03" />
                        <Text font="main-ui-body" color="text-05">
                          {index === 0
                            ? "Current version"
                            : `Version ${history.length - index}`}
                        </Text>
                      </div>
                      <Text font="secondary-body" color="text-03" maxLines={3}>
                        {revision.content}
                      </Text>
                      <Text font="secondary-body" color="text-02">
                        {`${formatDistanceToNow(new Date(revision.created_at), {
                          addSuffix: true,
                        })} · ${revision.source}`}
                      </Text>
                    </div>
                    {index > 0 ? (
                      <Button
                        prominence="secondary"
                        size="sm"
                        disabled={busy || !canCreateUpdateRestore}
                        onClick={() => void restore(revision)}
                      >
                        Restore
                      </Button>
                    ) : null}
                  </div>
                  {index < (history?.length ?? 0) - 1 ? <Divider /> : null}
                </div>
              ))}
              {history?.length === 0 ? (
                <Text font="main-ui-body" color="text-03">
                  No revision history is available yet.
                </Text>
              ) : null}
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          {memory && tab === "details" ? (
            <div className="mr-auto">
              {confirmDelete ? (
                <div className="flex items-center gap-2">
                  <Text font="secondary-body" color="status-error-05">
                    Delete permanently?
                  </Text>
                  <Button
                    icon={SvgTrash}
                    variant="danger"
                    prominence="primary"
                    size="sm"
                    disabled={busy}
                    onClick={() => void remove()}
                  >
                    Delete
                  </Button>
                  <Button
                    prominence="tertiary"
                    size="sm"
                    onClick={() => setConfirmDelete(false)}
                  >
                    Keep
                  </Button>
                </div>
              ) : (
                <Button
                  icon={SvgTrash}
                  prominence="tertiary"
                  size="sm"
                  disabled={!canDelete}
                  onClick={() => setConfirmDelete(true)}
                >
                  Delete
                </Button>
              )}
            </div>
          ) : null}
          <Button prominence="secondary" onClick={onClose}>
            Cancel
          </Button>
          {tab === "details" ? (
            <Button
              disabled={
                !canCreateUpdateRestore ||
                !content.trim() ||
                !hasChanges ||
                busy
              }
              onClick={() => void save()}
            >
              {memory ? "Save" : "Add memory"}
            </Button>
          ) : null}
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
