"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Modal from "@/refresh-components/Modal";
import * as TableLayouts from "@/layouts/table-layouts";
import useCCPairs from "@/hooks/useCCPairs";
import SourceHierarchyBrowser from "@/sections/knowledge/SourceHierarchyBrowser";
import { getSourceMetadata } from "@/lib/sources";
import type {
  ProjectConnectedDocument,
  ProjectConnectedHierarchyNode,
  ProjectConnectedKnowledge,
} from "@/lib/projects/types";
import type { AgentAttachedDocument } from "@/lib/agents/types";
import { ValidSources } from "@/lib/types";
import { Button, Divider, LineItemButton, Tabs, Text } from "@opal/components";
import { toast } from "@opal/layouts";
import { SvgFiles, SvgFolderOpen, SvgPlusCircle } from "@opal/icons";

interface SpaceConnectedKnowledgeModalProps {
  open: boolean;
  canEdit: boolean;
  knowledge: ProjectConnectedKnowledge;
  onClose: () => void;
  onSave: (documentIds: string[], hierarchyNodeIds: number[]) => Promise<void>;
  onUploadFiles: (files: File[]) => void;
}

function toAgentAttachedDocument(
  document: ProjectConnectedDocument,
): AgentAttachedDocument {
  return {
    id: document.id,
    title: document.title,
    link: document.link,
    parent_id: document.parent_hierarchy_node_id,
    last_modified: document.last_modified,
    last_synced: document.last_synced,
    source: document.source,
  };
}

function selectedSourceCounts(
  documents: ProjectConnectedDocument[],
  nodes: ProjectConnectedHierarchyNode[],
): Map<ValidSources, number> {
  const counts = new Map<ValidSources, number>();
  for (const document of documents) {
    if (!document.source) continue;
    counts.set(document.source, (counts.get(document.source) ?? 0) + 1);
  }
  for (const node of nodes) {
    counts.set(node.source, (counts.get(node.source) ?? 0) + 1);
  }
  return counts;
}

export default function SpaceConnectedKnowledgeModal({
  open,
  canEdit,
  knowledge,
  onClose,
  onSave,
  onUploadFiles,
}: SpaceConnectedKnowledgeModalProps) {
  const { ccPairs } = useCCPairs(open);
  const connectedSources = useMemo(() => {
    const sources = new Set<ValidSources>();
    ccPairs.forEach((pair) => sources.add(pair.source));
    return Array.from(sources);
  }, [ccPairs]);

  const initialSourceCounts = useMemo(
    () => selectedSourceCounts(knowledge.documents, knowledge.hierarchy_nodes),
    [knowledge.documents, knowledge.hierarchy_nodes],
  );
  const [activeSource, setActiveSource] = useState<ValidSources | null>(null);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [selectedHierarchyNodeIds, setSelectedHierarchyNodeIds] = useState<
    number[]
  >([]);
  const [sourceCounts, setSourceCounts] =
    useState<Map<ValidSources, number>>(initialSourceCounts);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSelectedDocumentIds(knowledge.documents.map((document) => document.id));
    setSelectedHierarchyNodeIds(
      knowledge.hierarchy_nodes.map((node) => node.id),
    );
    setSourceCounts(initialSourceCounts);
  }, [
    initialSourceCounts,
    knowledge.documents,
    knowledge.hierarchy_nodes,
    open,
  ]);

  useEffect(() => {
    if (!open || activeSource !== null || connectedSources.length === 0) return;
    const selectedSource = connectedSources.find(
      (source) => (initialSourceCounts.get(source) ?? 0) > 0,
    );
    setActiveSource(selectedSource ?? connectedSources[0] ?? null);
  }, [activeSource, connectedSources, initialSourceCounts, open]);

  const initialAttachedDocuments = useMemo(
    () => knowledge.documents.map(toAgentAttachedDocument),
    [knowledge.documents],
  );

  function openLocalUploadPicker({ directory }: { directory: boolean }) {
    const input = document.createElement("input") as HTMLInputElement & {
      webkitdirectory?: boolean;
      directory?: boolean;
    };
    input.type = "file";
    input.multiple = true;
    if (directory) {
      input.webkitdirectory = true;
      input.directory = true;
    }
    input.onchange = () => {
      const files = Array.from(input.files ?? []).map((file) => {
        const relativePath = file.webkitRelativePath;
        if (!directory || !relativePath) return file;
        return new File([file], relativePath, { type: file.type });
      });
      if (files.length > 0) onUploadFiles(files);
      input.value = "";
    };
    input.click();
  }

  async function handleSave() {
    setIsSaving(true);
    try {
      await onSave(selectedDocumentIds, selectedHierarchyNodeIds);
      onClose();
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to update connected sources.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  function handleToggleDocument(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((id) => id !== documentId)
        : [...current, documentId],
    );
  }

  function handleToggleFolder(folderId: number) {
    setSelectedHierarchyNodeIds((current) =>
      current.includes(folderId)
        ? current.filter((id) => id !== folderId)
        : [...current, folderId],
    );
  }

  const handleSelectionCountChange = useCallback(
    (source: ValidSources, count: number) => {
      setSourceCounts((current) => {
        if ((current.get(source) ?? 0) === count) return current;
        const next = new Map(current);
        if (count === 0) next.delete(source);
        else next.set(source, count);
        return next;
      });
    },
    [],
  );

  const selectedCount =
    selectedDocumentIds.length + selectedHierarchyNodeIds.length;

  return (
    <Modal open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <Modal.Content width="xl" height="full">
        <Modal.Header
          icon={SvgFolderOpen}
          title="Add knowledge to space"
          description="Upload local files separately from indexed connector folders and documents. Connector selections scope retrieval without granting new permissions."
          onClose={onClose}
        />
        <Modal.Body alignItems="stretch">
          <Tabs variant="pill" defaultValue="connected">
            <Tabs.List>
              <Tabs.Trigger value="connected">Connected sources</Tabs.Trigger>
              <Tabs.Trigger value="uploads">Uploaded files</Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="connected">
              {connectedSources.length === 0 ? (
                <div className="flex min-h-80 flex-col items-center justify-center gap-2 rounded-12 border border-dashed border-border-01 p-6 text-center">
                  <Text font="main-ui-body" color="text-04">
                    No indexed connector sources are available.
                  </Text>
                  <Text font="secondary-body" color="text-03">
                    Connect and index SharePoint or another intranet connector
                    in the admin panel first. This space can still use uploaded
                    files.
                  </Text>
                </div>
              ) : (
                <TableLayouts.TwoColumnLayout minHeight={28}>
                  <TableLayouts.SidebarLayout aria-label="space-connected-source-sidebar">
                    {connectedSources.map((source) => {
                      const metadata = getSourceMetadata(source);
                      const count = sourceCounts.get(source) ?? 0;
                      return (
                        <LineItemButton
                          key={source}
                          icon={metadata.icon}
                          title={
                            source === ValidSources.Sharepoint
                              ? "SharePoint intranets"
                              : metadata.displayName
                          }
                          description={
                            source === ValidSources.Sharepoint
                              ? "Browse Foundations and Magellan departments"
                              : undefined
                          }
                          width="full"
                          variant="section"
                          selectVariant="select-light"
                          state={activeSource === source ? "selected" : "empty"}
                          onClick={() => setActiveSource(source)}
                          rightChildren={
                            count > 0 ? (
                              <Text font="main-ui-action" color="text-04">
                                {String(count)}
                              </Text>
                            ) : undefined
                          }
                        />
                      );
                    })}
                  </TableLayouts.SidebarLayout>
                  <TableLayouts.ContentColumn>
                    {activeSource && (
                      <SourceHierarchyBrowser
                        source={activeSource}
                        selectedDocumentIds={selectedDocumentIds}
                        onToggleDocument={handleToggleDocument}
                        onSetDocumentIds={setSelectedDocumentIds}
                        selectedFolderIds={selectedHierarchyNodeIds}
                        onToggleFolder={handleToggleFolder}
                        onSetFolderIds={setSelectedHierarchyNodeIds}
                        onDeselectAllDocuments={() =>
                          setSelectedDocumentIds([])
                        }
                        onDeselectAllFolders={() =>
                          setSelectedHierarchyNodeIds([])
                        }
                        initialAttachedDocuments={initialAttachedDocuments}
                        onSelectionCountChange={handleSelectionCountChange}
                      />
                    )}
                  </TableLayouts.ContentColumn>
                </TableLayouts.TwoColumnLayout>
              )}
            </Tabs.Content>
            <Tabs.Content value="uploads">
              <div className="flex flex-col gap-4 rounded-12 border border-border-01 p-4">
                <div className="flex items-start gap-3">
                  <SvgFiles className="mt-0.5 h-5 w-5 shrink-0 stroke-text-03" />
                  <div className="flex flex-col gap-1">
                    <Text font="main-ui-action" color="text-05">
                      Uploaded files are copied into this space
                    </Text>
                    <Text font="secondary-body" color="text-03">
                      Use this for local files or folders. Use Connected sources
                      for already-indexed SharePoint sites, folders, and
                      documents.
                    </Text>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    icon={SvgPlusCircle}
                    disabled={!canEdit}
                    onClick={() => openLocalUploadPicker({ directory: false })}
                  >
                    Upload local files
                  </Button>
                  <Button
                    icon={SvgFolderOpen}
                    prominence="secondary"
                    disabled={!canEdit}
                    onClick={() => openLocalUploadPicker({ directory: true })}
                  >
                    Upload local folder
                  </Button>
                </div>
              </div>
            </Tabs.Content>
          </Tabs>
        </Modal.Body>
        <Modal.Footer>
          <div className="flex w-full items-center justify-between gap-3">
            <Text font="secondary-body" color="text-03">
              {selectedCount === 0
                ? "No connected-source selections"
                : `${selectedCount} connected-source selection${
                    selectedCount === 1 ? "" : "s"
                  }`}
            </Text>
            <div className="flex items-center gap-2">
              <Button prominence="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button
                disabled={!canEdit || isSaving}
                onClick={() => void handleSave()}
              >
                Save
              </Button>
            </div>
          </div>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
