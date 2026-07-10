"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import Modal from "@/refresh-components/Modal";
import {
  fetchHierarchyNodeDocuments,
  fetchHierarchyNodes,
} from "@/lib/hierarchy/svc";
import type {
  DocumentPageCursor,
  DocumentSummary,
  HierarchyNodeSummary,
  HierarchyNodesResponse,
} from "@/lib/hierarchy/interfaces";
import { ValidSources } from "@/lib/types";
import {
  Button,
  Checkbox,
  InputTypeIn,
  LineItemButton,
  Text,
} from "@opal/components";
import {
  SvgChevronRight,
  SvgExternalLink,
  SvgFileText,
  SvgFolder,
  SvgRefreshCw,
  SvgSimpleLoader,
} from "@opal/icons";
import { SvgSharepoint } from "@opal/logos";

const MAX_SELECTED_FILES = 20;

interface SharePointFilePickerModalProps {
  initialSelection: DocumentSummary[];
  onAttach: (documents: DocumentSummary[]) => void;
  onClose: () => void;
}

function hierarchyPath(
  node: HierarchyNodeSummary,
  nodesById: Map<number, HierarchyNodeSummary>,
  sourceRootId: number | null
): HierarchyNodeSummary[] {
  const path: HierarchyNodeSummary[] = [];
  let current: HierarchyNodeSummary | undefined = node;
  while (current && current.id !== sourceRootId) {
    path.unshift(current);
    current =
      current.parent_id === null ? undefined : nodesById.get(current.parent_id);
  }
  return path;
}

export default function SharePointFilePickerModal({
  initialSelection,
  onAttach,
  onClose,
}: SharePointFilePickerModalProps) {
  const {
    data,
    error: nodesError,
    isLoading,
  } = useSWR<HierarchyNodesResponse>(
    "sharepoint-file-picker-hierarchy",
    () => fetchHierarchyNodes(ValidSources.Sharepoint),
    { revalidateOnFocus: false }
  );
  const nodes = data?.nodes ?? [];
  const nodesById = useMemo(
    () => new Map(nodes.map((node) => [node.id, node])),
    [nodes]
  );
  const sourceRoot = useMemo(
    () => nodes.find((node) => node.parent_id === null) ?? null,
    [nodes]
  );
  const sites = useMemo(
    () =>
      nodes
        .filter((node) => node.parent_id === sourceRoot?.id)
        .sort((left, right) => left.title.localeCompare(right.title)),
    [nodes, sourceRoot?.id]
  );
  const [currentNodeId, setCurrentNodeId] = useState<number | null>(null);
  const [siteQuery, setSiteQuery] = useState("");
  const [itemQuery, setItemQuery] = useState("");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [nextCursor, setNextCursor] = useState<DocumentPageCursor | null>(null);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [documentsError, setDocumentsError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Map<string, DocumentSummary>>(
    () => new Map(initialSelection.map((document) => [document.id, document]))
  );

  useEffect(() => {
    if (currentNodeId === null && sites[0]) setCurrentNodeId(sites[0].id);
  }, [currentNodeId, sites]);

  const loadDocuments = useCallback(
    async (
      nodeId: number,
      cursor: DocumentPageCursor | null,
      append: boolean
    ) => {
      setLoadingDocuments(true);
      setDocumentsError(null);
      try {
        const response = await fetchHierarchyNodeDocuments({
          parent_hierarchy_node_id: nodeId,
          cursor,
          sort_field: "name",
          sort_direction: "asc",
        });
        setDocuments((current) =>
          append ? [...current, ...response.documents] : response.documents
        );
        setNextCursor(response.next_cursor);
      } catch (loadError) {
        setDocumentsError(
          loadError instanceof Error
            ? loadError.message
            : "Files could not be loaded"
        );
      } finally {
        setLoadingDocuments(false);
      }
    },
    []
  );

  useEffect(() => {
    if (currentNodeId === null) return;
    setDocuments([]);
    setNextCursor(null);
    setItemQuery("");
    void loadDocuments(currentNodeId, null, false);
  }, [currentNodeId, loadDocuments]);

  const currentNode =
    currentNodeId === null ? null : (nodesById.get(currentNodeId) ?? null);
  const path = useMemo(
    () =>
      currentNode
        ? hierarchyPath(currentNode, nodesById, sourceRoot?.id ?? null)
        : [],
    [currentNode, nodesById, sourceRoot?.id]
  );
  const childFolders = useMemo(
    () =>
      nodes
        .filter((node) => node.parent_id === currentNodeId)
        .sort((left, right) => left.title.localeCompare(right.title)),
    [currentNodeId, nodes]
  );
  const normalizedItemQuery = itemQuery.trim().toLocaleLowerCase();
  const visibleFolders = childFolders.filter((folder) =>
    folder.title.toLocaleLowerCase().includes(normalizedItemQuery)
  );
  const visibleDocuments = documents.filter((document) =>
    document.title.toLocaleLowerCase().includes(normalizedItemQuery)
  );
  const visibleSites = sites.filter((site) =>
    `${site.title} ${site.link ?? ""}`
      .toLocaleLowerCase()
      .includes(siteQuery.trim().toLocaleLowerCase())
  );

  function toggleDocument(document: DocumentSummary, checked: boolean) {
    setSelected((current) => {
      const next = new Map(current);
      if (checked) {
        if (next.size >= MAX_SELECTED_FILES) return current;
        next.set(document.id, document);
      } else {
        next.delete(document.id);
      }
      return next;
    });
  }

  return (
    <Modal open onOpenChange={(open) => !open && onClose()}>
      <Modal.Content width="xl" height="full">
        <Modal.Header
          icon={SvgSharepoint}
          title="Attach SharePoint files"
          description="Choose indexed files you can access. Retrieval will be limited to these files."
        />
        <Modal.Body>
          {isLoading ? (
            <div className="flex min-h-80 w-full items-center justify-center gap-2">
              <SvgSimpleLoader className="h-5 w-5" />
              <Text color="text-03" font="main-ui-body">
                Loading SharePoint sites
              </Text>
            </div>
          ) : nodesError ? (
            <div className="flex min-h-80 w-full flex-col items-center justify-center gap-2">
              <Text color="status-error-05" font="main-ui-body">
                SharePoint files could not be loaded.
              </Text>
              <Text color="text-03" font="secondary-body">
                The picker only shows files available in the indexed SharePoint
                hierarchy.
              </Text>
            </div>
          ) : sites.length === 0 ? (
            <div className="flex min-h-80 w-full items-center justify-center">
              <Text color="text-03" font="main-ui-body">
                No accessible SharePoint sites are indexed.
              </Text>
            </div>
          ) : (
            <div className="grid min-h-[32rem] w-full grid-cols-[15rem_minmax(0,1fr)] overflow-hidden rounded-08 border border-border-01">
              <div className="flex min-w-0 flex-col border-r border-border-01 bg-background-tint-01">
                <div className="border-b border-border-01 p-2">
                  <InputTypeIn
                    clearButton
                    onChange={(event) => setSiteQuery(event.target.value)}
                    placeholder="Search sites"
                    searchIcon
                    value={siteQuery}
                  />
                </div>
                <div className="flex-1 overflow-y-auto p-1">
                  {visibleSites.map((site) => (
                    <LineItemButton
                      key={site.id}
                      icon={SvgSharepoint}
                      onClick={() => setCurrentNodeId(site.id)}
                      rounding="sm"
                      selectVariant="select-heavy"
                      sizePreset="main-ui"
                      state={path[0]?.id === site.id ? "selected" : "empty"}
                      title={site.title}
                      variant="section"
                      width="full"
                    />
                  ))}
                </div>
              </div>

              <div className="flex min-w-0 flex-col bg-background-tint-00">
                <div className="flex min-h-12 items-center gap-1 border-b border-border-01 px-3">
                  {path.map((node, index) => (
                    <div
                      className="flex min-w-0 items-center gap-1"
                      key={node.id}
                    >
                      {index > 0 ? (
                        <SvgChevronRight className="h-3.5 w-3.5 shrink-0 stroke-text-02" />
                      ) : null}
                      <Button
                        prominence="tertiary"
                        size="sm"
                        onClick={() => setCurrentNodeId(node.id)}
                      >
                        {node.title}
                      </Button>
                    </div>
                  ))}
                </div>
                <div className="border-b border-border-01 p-2">
                  <InputTypeIn
                    clearButton
                    onChange={(event) => setItemQuery(event.target.value)}
                    placeholder="Filter this folder"
                    searchIcon
                    value={itemQuery}
                  />
                </div>
                <div className="flex-1 overflow-y-auto">
                  {visibleFolders.map((folder) => (
                    <LineItemButton
                      key={folder.id}
                      description="Folder"
                      icon={SvgFolder}
                      onClick={() => setCurrentNodeId(folder.id)}
                      rightChildren={
                        <SvgChevronRight className="h-4 w-4 stroke-text-02" />
                      }
                      selectVariant="select-light"
                      sizePreset="main-ui"
                      state="empty"
                      title={folder.title}
                      variant="section"
                      width="full"
                    />
                  ))}
                  {visibleDocuments.map((document) => {
                    const checked = selected.has(document.id);
                    const disabled =
                      !checked && selected.size >= MAX_SELECTED_FILES;
                    return (
                      <div
                        className="flex min-h-12 items-center gap-2 border-t border-border-01 px-3 py-2 first:border-t-0"
                        key={document.id}
                      >
                        <Checkbox
                          aria-label={`Select ${document.title}`}
                          checked={checked}
                          disabled={disabled}
                          onCheckedChange={(value) =>
                            toggleDocument(document, value)
                          }
                        />
                        <SvgFileText className="h-5 w-5 shrink-0 stroke-text-02" />
                        <div className="min-w-0 flex-1">
                          <Text
                            color="text-04"
                            font="main-ui-body"
                            maxLines={1}
                          >
                            {document.title}
                          </Text>
                          <Text color="text-02" font="secondary-body">
                            {document.last_modified
                              ? `Updated ${new Date(document.last_modified).toLocaleDateString()}`
                              : "SharePoint file"}
                          </Text>
                        </div>
                        {document.link ? (
                          <Button
                            href={document.link}
                            icon={SvgExternalLink}
                            prominence="tertiary"
                            size="xs"
                            target="_blank"
                            tooltip="Open in SharePoint"
                          />
                        ) : null}
                      </div>
                    );
                  })}
                  {loadingDocuments ? (
                    <div className="flex min-h-16 items-center justify-center gap-2">
                      <SvgSimpleLoader className="h-4 w-4" />
                      <Text color="text-03" font="secondary-body">
                        Loading files
                      </Text>
                    </div>
                  ) : documentsError ? (
                    <div className="flex min-h-20 items-center justify-center gap-2">
                      <Text color="status-error-05" font="secondary-body">
                        {documentsError}
                      </Text>
                      {currentNodeId !== null ? (
                        <Button
                          icon={SvgRefreshCw}
                          prominence="tertiary"
                          size="sm"
                          onClick={() =>
                            void loadDocuments(currentNodeId, null, false)
                          }
                        >
                          Retry
                        </Button>
                      ) : null}
                    </div>
                  ) : nextCursor ? (
                    <div className="flex justify-center p-2">
                      <Button
                        prominence="secondary"
                        onClick={() =>
                          currentNodeId !== null &&
                          void loadDocuments(currentNodeId, nextCursor, true)
                        }
                      >
                        Load more
                      </Button>
                    </div>
                  ) : visibleFolders.length === 0 &&
                    visibleDocuments.length === 0 ? (
                    <div className="flex min-h-28 items-center justify-center">
                      <Text color="text-03" font="main-ui-body">
                        No files or folders here.
                      </Text>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          )}
        </Modal.Body>
        <Modal.Footer>
          <div className="flex w-full items-center justify-between gap-3">
            <Text color="text-03" font="secondary-body">
              {`${selected.size} of ${MAX_SELECTED_FILES} files selected`}
            </Text>
            <div className="flex items-center gap-2">
              <Button prominence="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button
                disabled={selected.size === 0}
                onClick={() => onAttach(Array.from(selected.values()))}
              >
                Attach files
              </Button>
            </div>
          </div>
        </Modal.Footer>
      </Modal.Content>
    </Modal>
  );
}
