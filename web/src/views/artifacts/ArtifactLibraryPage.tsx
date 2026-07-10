"use client";

import { useEffect, useMemo, useState } from "react";
import type { Route } from "next";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import { useSWRConfig } from "swr";
import { errorHandlingFetcher } from "@/lib/fetcher";
import { toast } from "@/hooks/useToast";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import ConfirmationModalLayout from "@/refresh-components/layouts/ConfirmationModalLayout";
import ArtifactPreviewModal from "@/app/craft/v1/artifacts/ArtifactPreviewModal";
import ArtifactShareModal from "@/app/craft/v1/artifacts/ArtifactShareModal";
import ArtifactVersionsModal from "@/app/craft/v1/artifacts/ArtifactVersionsModal";
import {
  artifactVersionDownloadUrl,
  bulkUpdateArtifactLibrary,
  removeSharedArtifact,
  PINNED_ARTIFACTS_URL,
  setArtifactLibraryPin,
} from "@/app/craft/v1/artifacts/api";
import { groupArtifactLibraryItems } from "@/app/craft/v1/artifacts/grouping";
import type {
  ArtifactLibraryBulkAction,
  ArtifactLibraryItem,
  ArtifactLibraryScope,
  ArtifactLibraryType,
} from "@/app/craft/v1/artifacts/types";
import {
  Button,
  Checkbox,
  InputTypeIn,
  Tabs,
  Tag,
  Text,
} from "@opal/components";
import { IllustrationContent, SettingsLayouts } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import type { IconFunctionComponent } from "@opal/types";
import {
  SvgCode,
  SvgDashboard,
  SvgDocFile,
  SvgDownload,
  SvgFile,
  SvgFileText,
  SvgFiles,
  SvgGlobe,
  SvgHistory,
  SvgImage,
  SvgMenu,
  SvgPin,
  SvgPinned,
  SvgShare,
  SvgSimpleLoader,
  SvgSlidesFile,
  SvgSpreadsheetFile,
  SvgTrash,
  SvgX,
} from "@opal/icons";

type ViewMode = "grid" | "list";

const VIEW_MODE_KEY = "onyx.artifact-library.view-mode.v1";

export const TYPE_LABELS: Record<ArtifactLibraryType, string> = {
  web_app: "Web app",
  pptx: "Presentation",
  docx: "Document",
  pdf: "PDF",
  image: "Image",
  markdown: "Markdown",
  excel: "Spreadsheet",
  csv: "CSV",
  other: "File",
};

const TYPE_ICONS: Record<ArtifactLibraryType, IconFunctionComponent> = {
  web_app: SvgCode,
  pptx: SvgSlidesFile,
  docx: SvgDocFile,
  pdf: SvgFileText,
  image: SvgImage,
  markdown: SvgFileText,
  excel: SvgSpreadsheetFile,
  csv: SvgSpreadsheetFile,
  other: SvgFile,
};

function formatSize(bytes: number | null): string {
  if (bytes === null) return "Unknown size";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatUpdated(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year:
      new Date(value).getFullYear() === new Date().getFullYear()
        ? undefined
        : "numeric",
  }).format(new Date(value));
}

interface ArtifactItemViewProps {
  item: ArtifactLibraryItem;
  selected: boolean;
  viewMode: ViewMode;
  onOpen: () => void;
  onSelect: (selected: boolean) => void;
  onPin: () => void;
  onHistory: () => void;
  onShare: () => void;
  onRemoveShared: () => void;
}

function ArtifactItemView({
  item,
  selected,
  viewMode,
  onOpen,
  onSelect,
  onPin,
  onHistory,
  onShare,
  onRemoveShared,
}: ArtifactItemViewProps) {
  const Icon = TYPE_ICONS[item.type];
  const controls = (
    <div
      className="flex shrink-0 items-center gap-0.5"
      onClick={(event) => event.stopPropagation()}
    >
      <Button
        icon={item.is_pinned ? SvgPinned : SvgPin}
        prominence="tertiary"
        size="xs"
        tooltip={item.is_pinned ? "Unpin" : "Pin"}
        onClick={onPin}
      />
      <Button
        icon={SvgHistory}
        prominence="tertiary"
        size="xs"
        tooltip="Version history"
        onClick={onHistory}
      />
      {item.is_owner ? (
        <Button
          icon={SvgShare}
          prominence="tertiary"
          size="xs"
          tooltip="Share"
          onClick={onShare}
        />
      ) : (
        <Button
          icon={SvgX}
          prominence="tertiary"
          size="xs"
          tooltip="Remove from my library"
          onClick={onRemoveShared}
        />
      )}
      <Button
        href={artifactVersionDownloadUrl(
          item.id,
          item.latest_version.version_number
        )}
        icon={SvgDownload}
        prominence="tertiary"
        size="xs"
        tooltip="Download latest"
      />
    </div>
  );

  const selection = (
    <div className="shrink-0" onClick={(event) => event.stopPropagation()}>
      <Checkbox
        aria-label={`Select ${item.name}`}
        checked={selected}
        onCheckedChange={onSelect}
      />
    </div>
  );

  if (viewMode === "list") {
    return (
      <div
        role="button"
        tabIndex={0}
        onClick={onOpen}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onOpen();
          }
        }}
        className="group flex min-h-16 w-full cursor-pointer items-center gap-3 border-b border-border-01 px-2 py-3 outline-none transition-colors last:border-b-0 hover:bg-background-tint-01 focus-visible:bg-background-tint-01"
      >
        {selection}
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-08 bg-background-tint-02">
          <Icon className="h-5 w-5 stroke-text-03" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-1.5">
            <Text font="main-ui-body" color="text-05" maxLines={1}>
              {item.name}
            </Text>
            {item.is_pinned ? (
              <SvgPinned className="h-3.5 w-3.5 shrink-0 stroke-text-03" />
            ) : null}
          </div>
          <Text font="secondary-body" color="text-03" maxLines={1}>
            {`${TYPE_LABELS[item.type]} · v${item.latest_version.version_number} · ${formatSize(item.latest_version.size_bytes)} · Updated ${formatUpdated(item.updated_at)}`}
          </Text>
        </div>
        <div className="hidden items-center gap-1 md:flex">
          {item.published_at ? <Tag color="blue" title="Organization" /> : null}
          {!item.is_owner ? <Tag color="gray" title="Shared" /> : null}
        </div>
        {controls}
      </div>
    );
  }

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpen();
        }
      }}
      className="group flex min-h-48 cursor-pointer flex-col rounded-08 border border-border-01 bg-background-01 p-4 outline-none transition-colors hover:bg-background-tint-01 focus-visible:bg-background-tint-01"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-08 bg-background-tint-02">
          <Icon className="h-5 w-5 stroke-text-03" />
        </div>
        {selection}
      </div>
      <div className="mt-5 min-w-0 flex-1">
        <div className="flex min-w-0 items-center gap-1.5">
          <Text font="main-ui-body" color="text-05" maxLines={2}>
            {item.name}
          </Text>
          {item.is_pinned ? (
            <SvgPinned className="h-3.5 w-3.5 shrink-0 stroke-text-03" />
          ) : null}
        </div>
        <Text font="secondary-body" color="text-03" maxLines={1}>
          {item.is_owner ? "Created by you" : `Shared by ${item.owner.email}`}
        </Text>
      </div>
      <div className="mt-3 flex items-end justify-between gap-2">
        <div className="flex min-w-0 flex-col">
          <Text font="secondary-body" color="text-03" maxLines={1}>
            {`${TYPE_LABELS[item.type]} · v${item.latest_version.version_number} · ${formatSize(item.latest_version.size_bytes)}`}
          </Text>
          <Text font="secondary-body" color="text-02" maxLines={1}>
            {`Updated ${formatUpdated(item.updated_at)}`}
          </Text>
        </div>
        {controls}
      </div>
    </article>
  );
}

export default function ArtifactLibraryPage() {
  const { mutate: mutateGlobal } = useSWRConfig();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const selectedArtifactId = searchParams.get("artifactId");
  const [scope, setScope] = useState<ArtifactLibraryScope>("all");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<ArtifactLibraryType | "all">(
    "all"
  );
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [sharingItem, setSharingItem] = useState<ArtifactLibraryItem | null>(
    null
  );
  const [versionsItem, setVersionsItem] = useState<ArtifactLibraryItem | null>(
    null
  );
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(VIEW_MODE_KEY);
    if (stored === "grid" || stored === "list") setViewMode(stored);
  }, []);

  function updateViewMode(nextMode: ViewMode) {
    setViewMode(nextMode);
    window.localStorage.setItem(VIEW_MODE_KEY, nextMode);
  }

  const url = useMemo(() => {
    const params = new URLSearchParams({ scope });
    if (query.trim()) params.set("query", query.trim());
    if (typeFilter !== "all") params.set("artifact_type", typeFilter);
    params.set("limit", "200");
    return `/api/build/artifact-library?${params.toString()}`;
  }, [query, scope, typeFilter]);
  const {
    data = [],
    error,
    isLoading,
    mutate,
  } = useSWR<ArtifactLibraryItem[]>(url, errorHandlingFetcher, {
    keepPreviousData: true,
  });
  const listedPreviewItem = data.find((item) => item.id === selectedArtifactId);
  const { data: fetchedPreviewItem, mutate: mutatePreviewItem } =
    useSWR<ArtifactLibraryItem>(
      selectedArtifactId && !listedPreviewItem
        ? `/api/build/artifact-library/${selectedArtifactId}`
        : null,
      errorHandlingFetcher
    );
  const previewItem = listedPreviewItem ?? fetchedPreviewItem ?? null;
  const groups = useMemo(() => groupArtifactLibraryItems(data), [data]);
  const selectedItems = useMemo(
    () => data.filter((item) => selectedIds.has(item.id)),
    [data, selectedIds]
  );
  const ownedSelected = selectedItems.filter((item) => item.is_owner);
  const sharedSelected = selectedItems.filter((item) => !item.is_owner);
  const allVisibleSelected =
    data.length > 0 && selectedIds.size === data.length;

  function updatePreviewQuery(itemId: string | null) {
    const next = new URLSearchParams(searchParams.toString());
    if (itemId) next.set("artifactId", itemId);
    else next.delete("artifactId");
    const queryString = next.toString();
    router.replace(
      (queryString ? `${pathname}?${queryString}` : pathname) as Route,
      { scroll: false }
    );
  }

  function toggleSelection(itemId: string, selected: boolean) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (selected) next.add(itemId);
      else next.delete(itemId);
      return next;
    });
  }

  async function refreshLibrary() {
    await Promise.all([
      mutate(),
      mutatePreviewItem(),
      mutateGlobal(PINNED_ARTIFACTS_URL),
    ]);
  }

  async function togglePin(item: ArtifactLibraryItem) {
    try {
      await setArtifactLibraryPin(item.id, !item.is_pinned);
      await refreshLibrary();
    } catch (pinError) {
      toast.error(
        pinError instanceof Error ? pinError.message : "Failed to update pin"
      );
    }
  }

  async function removeShared(item: ArtifactLibraryItem) {
    try {
      await removeSharedArtifact(item.id);
      setSelectedIds((current) => {
        const next = new Set(current);
        next.delete(item.id);
        return next;
      });
      if (selectedArtifactId === item.id) updatePreviewQuery(null);
      await refreshLibrary();
      toast.success(`Removed "${item.name}" from your library.`);
    } catch (removeError) {
      toast.error(
        removeError instanceof Error
          ? removeError.message
          : "Failed to remove shared artifact"
      );
    }
  }

  async function runBulk(
    action: ArtifactLibraryBulkAction,
    items: ArtifactLibraryItem[]
  ) {
    if (items.length === 0) return;
    setBulkBusy(true);
    try {
      await bulkUpdateArtifactLibrary(
        items.map((item) => item.id),
        action
      );
      setSelectedIds(new Set());
      setConfirmDelete(false);
      await refreshLibrary();
      toast.success(
        `${items.length} artifact${items.length === 1 ? "" : "s"} updated.`
      );
    } catch (bulkError) {
      toast.error(
        bulkError instanceof Error
          ? bulkError.message
          : "Failed to update artifacts"
      );
    } finally {
      setBulkBusy(false);
    }
  }

  async function downloadSelected() {
    if (selectedItems.length === 0) return;
    setBulkBusy(true);
    let failures = 0;
    for (const item of selectedItems) {
      try {
        const response = await fetch(
          artifactVersionDownloadUrl(
            item.id,
            item.latest_version.version_number
          )
        );
        if (!response.ok) throw new Error("Download failed");
        const objectUrl = URL.createObjectURL(await response.blob());
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = item.latest_version.name;
        anchor.click();
        URL.revokeObjectURL(objectUrl);
      } catch {
        failures += 1;
      }
    }
    setBulkBusy(false);
    if (failures > 0) {
      toast.error(
        `${failures} artifact download${failures === 1 ? "" : "s"} failed.`
      );
    }
  }

  const emptyDescription =
    scope === "shared"
      ? "Artifacts shared with you will appear here."
      : scope === "created"
        ? "Save an output from a Craft session to add it here."
        : "Save or receive an artifact to build your library.";

  return (
    <SettingsLayouts.Root width="lg">
      <SettingsLayouts.Header
        icon={SvgFiles}
        title="Artifacts"
        description="Preview, organize, share, and revisit durable outputs from Craft."
      >
        <div className="flex w-full flex-col gap-3">
          <div className="flex w-full items-center gap-2">
            <div className="min-w-0 flex-1">
              <Tabs
                value={scope}
                onValueChange={(value) => {
                  setScope(value as ArtifactLibraryScope);
                  setSelectedIds(new Set());
                }}
              >
                <Tabs.List>
                  <Tabs.Trigger value="all">All</Tabs.Trigger>
                  <Tabs.Trigger value="created">Created</Tabs.Trigger>
                  <Tabs.Trigger value="shared">Shared</Tabs.Trigger>
                </Tabs.List>
              </Tabs>
            </div>
            <div className="flex shrink-0 items-center rounded-08 border border-border-01 p-0.5">
              <Button
                icon={SvgDashboard}
                prominence={viewMode === "grid" ? "secondary" : "tertiary"}
                size="sm"
                tooltip="Grid view"
                onClick={() => updateViewMode("grid")}
              />
              <Button
                icon={SvgMenu}
                prominence={viewMode === "list" ? "secondary" : "tertiary"}
                size="sm"
                tooltip="List view"
                onClick={() => updateViewMode("list")}
              />
            </div>
          </div>
          <div className="flex w-full flex-col gap-2 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <InputTypeIn
                clearButton
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search artifacts"
                searchIcon
                value={query}
              />
            </div>
            <div className="min-w-40 sm:w-48 sm:shrink-0">
              <InputSelect
                value={typeFilter}
                onValueChange={(value) =>
                  setTypeFilter(value as ArtifactLibraryType | "all")
                }
              >
                <InputSelect.Trigger />
                <InputSelect.Content>
                  <InputSelect.Item value="all">All types</InputSelect.Item>
                  {Object.entries(TYPE_LABELS).map(([value, label]) => (
                    <InputSelect.Item key={value} value={value}>
                      {label}
                    </InputSelect.Item>
                  ))}
                </InputSelect.Content>
              </InputSelect>
            </div>
          </div>
          {data.length > 0 ? (
            <div className="flex items-center gap-2">
              <Checkbox
                aria-label="Select all visible artifacts"
                checked={allVisibleSelected}
                indeterminate={selectedIds.size > 0 && !allVisibleSelected}
                onCheckedChange={(checked) =>
                  setSelectedIds(
                    checked ? new Set(data.map((item) => item.id)) : new Set()
                  )
                }
              />
              <Text font="secondary-body" color="text-03">
                {selectedIds.size > 0
                  ? `${selectedIds.size} selected`
                  : `${data.length} artifact${data.length === 1 ? "" : "s"}`}
              </Text>
            </div>
          ) : null}
        </div>
      </SettingsLayouts.Header>
      <SettingsLayouts.Body>
        {selectedItems.length > 0 ? (
          <div className="sticky top-0 z-10 flex w-full flex-col gap-2 rounded-08 border border-border-01 bg-background-01 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
            <Text color="text-03" font="main-ui-body">
              {`${selectedItems.length} selected`}
            </Text>
            <div className="flex flex-wrap items-center gap-1">
              <Button
                icon={SvgPin}
                prominence="tertiary"
                onClick={() => void runBulk("pin", selectedItems)}
                disabled={bulkBusy}
              >
                Pin
              </Button>
              {selectedItems.some((item) => item.is_pinned) ? (
                <Button
                  icon={SvgPinned}
                  prominence="tertiary"
                  onClick={() => void runBulk("unpin", selectedItems)}
                  disabled={bulkBusy}
                >
                  Unpin
                </Button>
              ) : null}
              <Button
                icon={SvgDownload}
                prominence="tertiary"
                onClick={() => void downloadSelected()}
                disabled={bulkBusy}
              >
                Download
              </Button>
              {ownedSelected.length > 0 ? (
                <Button
                  icon={SvgGlobe}
                  prominence="tertiary"
                  onClick={() => void runBulk("publish", ownedSelected)}
                  disabled={bulkBusy}
                >
                  Publish
                </Button>
              ) : null}
              {sharedSelected.length > 0 ? (
                <Button
                  icon={SvgX}
                  prominence="tertiary"
                  onClick={() => void runBulk("remove_shared", sharedSelected)}
                  disabled={bulkBusy}
                >
                  Remove shared
                </Button>
              ) : null}
              {ownedSelected.length > 0 ? (
                <Button
                  icon={SvgTrash}
                  variant="danger"
                  prominence="tertiary"
                  onClick={() => setConfirmDelete(true)}
                  disabled={bulkBusy}
                >
                  Delete
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}

        {isLoading && data.length === 0 ? (
          <div className="flex w-full items-center justify-center gap-2 py-16">
            <SvgSimpleLoader className="h-5 w-5" />
            <Text color="text-03" font="main-ui-body">
              Loading artifacts...
            </Text>
          </div>
        ) : error ? (
          <Text color="status-error-05" font="main-ui-body">
            Artifacts could not be loaded.
          </Text>
        ) : groups.length === 0 ? (
          <IllustrationContent
            illustration={SvgNoResult}
            title="No artifacts found"
            description={emptyDescription}
          />
        ) : (
          <div className="flex w-full flex-col gap-8 pb-8">
            {groups.map((group) => (
              <section key={group.key} className="flex w-full flex-col gap-3">
                <div className="flex items-baseline gap-2">
                  <Text font="heading-h3" color="text-05">
                    {group.title}
                  </Text>
                  <Text font="secondary-body" color="text-03">
                    {String(group.items.length)}
                  </Text>
                </div>
                <div
                  className={
                    viewMode === "grid"
                      ? "grid w-full grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3"
                      : "w-full overflow-hidden rounded-08 border border-border-01"
                  }
                >
                  {group.items.map((item) => (
                    <ArtifactItemView
                      key={item.id}
                      item={item}
                      selected={selectedIds.has(item.id)}
                      viewMode={viewMode}
                      onOpen={() => updatePreviewQuery(item.id)}
                      onSelect={(checked) => toggleSelection(item.id, checked)}
                      onPin={() => void togglePin(item)}
                      onHistory={() => setVersionsItem(item)}
                      onShare={() => setSharingItem(item)}
                      onRemoveShared={() => void removeShared(item)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}
      </SettingsLayouts.Body>

      {previewItem ? (
        <ArtifactPreviewModal
          item={previewItem}
          onClose={() => updatePreviewQuery(null)}
          onHistory={() => {
            updatePreviewQuery(null);
            setVersionsItem(previewItem);
          }}
          onShare={() => {
            updatePreviewQuery(null);
            setSharingItem(previewItem);
          }}
        />
      ) : null}
      {sharingItem ? (
        <ArtifactShareModal
          item={sharingItem}
          onClose={() => setSharingItem(null)}
          onSaved={(item) => {
            setSharingItem(item);
            void refreshLibrary();
          }}
        />
      ) : null}
      {versionsItem ? (
        <ArtifactVersionsModal
          item={versionsItem}
          onClose={() => setVersionsItem(null)}
        />
      ) : null}
      {confirmDelete ? (
        <ConfirmationModalLayout
          icon={SvgTrash}
          title={`Delete ${ownedSelected.length} artifact${ownedSelected.length === 1 ? "" : "s"}?`}
          description="Every saved version will be permanently removed."
          onClose={() => setConfirmDelete(false)}
          submit={
            <Button
              variant="danger"
              onClick={() => void runBulk("delete", ownedSelected)}
              disabled={bulkBusy}
            >
              {bulkBusy ? "Deleting..." : "Delete"}
            </Button>
          }
        />
      ) : null}
    </SettingsLayouts.Root>
  );
}
