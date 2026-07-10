"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { toast } from "@/hooks/useToast";
import { errorHandlingFetcher } from "@/lib/fetcher";
import InputSelect from "@/refresh-components/inputs/InputSelect";
import ConfirmationModalLayout from "@/refresh-components/layouts/ConfirmationModalLayout";
import ArtifactShareModal from "@/app/craft/v1/artifacts/ArtifactShareModal";
import ArtifactVersionsModal from "@/app/craft/v1/artifacts/ArtifactVersionsModal";
import {
  artifactVersionDownloadUrl,
  bulkUpdateArtifactLibrary,
  updateArtifactLibraryItem,
} from "@/app/craft/v1/artifacts/api";
import type {
  ArtifactLibraryBulkAction,
  ArtifactLibraryItem,
  ArtifactLibraryScope,
  ArtifactLibraryType,
} from "@/app/craft/v1/artifacts/types";
import {
  Button,
  InputTypeIn,
  Table,
  Tabs,
  Tag,
  Text,
  createTableColumns,
} from "@opal/components";
import { IllustrationContent, SettingsLayouts } from "@opal/layouts";
import SvgNoResult from "@opal/illustrations/no-result";
import {
  SvgDownload,
  SvgFiles,
  SvgGlobe,
  SvgHistory,
  SvgPin,
  SvgPinned,
  SvgShare,
  SvgTrash,
} from "@opal/icons";

const TYPE_LABELS: Record<ArtifactLibraryType, string> = {
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

const tc = createTableColumns<ArtifactLibraryItem>();

function formatSize(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface RowActionsProps {
  onHistory: (item: ArtifactLibraryItem) => void;
  onMutate: () => Promise<unknown>;
  onShare: (item: ArtifactLibraryItem) => void;
}

function buildColumns({ onHistory, onMutate, onShare }: RowActionsProps) {
  return [
    tc.column("name", {
      header: "Artifact",
      weight: 34,
      cell: (name, item) => (
        <div className="flex min-w-0 flex-col">
          <div className="flex min-w-0 items-center gap-1.5">
            <Text color="text-05" font="main-ui-body" maxLines={1}>
              {name}
            </Text>
            {item.is_pinned ? (
              <SvgPinned className="h-3.5 w-3.5 shrink-0 stroke-text-03" />
            ) : null}
          </div>
          <Text color="text-03" font="secondary-body" maxLines={1}>
            {item.is_owner ? "Created by you" : `Shared by ${item.owner.email}`}
          </Text>
        </div>
      ),
    }),
    tc.column("type", {
      header: "Type",
      weight: 13,
      cell: (type) => (
        <Text color="text-03" font="main-ui-body" nowrap>
          {TYPE_LABELS[type]}
        </Text>
      ),
    }),
    tc.displayColumn({
      id: "version",
      header: "Version",
      width: { weight: 12 },
      cell: (item) => (
        <div className="flex flex-col">
          <Text color="text-04" font="main-ui-body" nowrap>
            {`v${item.latest_version.version_number}`}
          </Text>
          <Text color="text-03" font="secondary-body" nowrap>
            {formatSize(item.latest_version.size_bytes)}
          </Text>
        </div>
      ),
    }),
    tc.displayColumn({
      id: "access",
      header: "Access",
      width: { weight: 16 },
      cell: (item) => (
        <div className="flex flex-wrap gap-1">
          {item.published_at ? <Tag color="blue" title="Organization" /> : null}
          {item.user_shares.length + item.group_shares.length > 0 ? (
            <Tag
              color="gray"
              title={`${item.user_shares.length + item.group_shares.length} shared`}
            />
          ) : null}
          {!item.published_at &&
          item.user_shares.length + item.group_shares.length === 0 ? (
            <Tag color="gray" title="Private" />
          ) : null}
        </div>
      ),
    }),
    tc.column("updated_at", {
      header: "Updated",
      weight: 15,
      cell: (updatedAt) => (
        <Text color="text-03" font="main-ui-body" nowrap>
          {new Date(updatedAt).toLocaleDateString()}
        </Text>
      ),
    }),
    tc.actions({
      showColumnVisibility: false,
      showSorting: false,
      cell: (item) => (
        <div
          className="flex items-center gap-0.5"
          onClick={(event) => event.stopPropagation()}
        >
          {item.is_owner ? (
            <>
              <Button
                icon={item.is_pinned ? SvgPinned : SvgPin}
                prominence="tertiary"
                size="xs"
                tooltip={item.is_pinned ? "Unpin" : "Pin"}
                onClick={async () => {
                  await updateArtifactLibraryItem(item.id, {
                    is_pinned: !item.is_pinned,
                  });
                  await onMutate();
                }}
              />
              <Button
                icon={SvgGlobe}
                prominence="tertiary"
                size="xs"
                tooltip={
                  item.published_at
                    ? "Remove organization access"
                    : "Publish to organization"
                }
                onClick={async () => {
                  await updateArtifactLibraryItem(item.id, {
                    published: !item.published_at,
                  });
                  await onMutate();
                }}
              />
              <Button
                icon={SvgShare}
                prominence="tertiary"
                size="xs"
                tooltip="Share"
                onClick={() => onShare(item)}
              />
            </>
          ) : null}
          <Button
            icon={SvgHistory}
            prominence="tertiary"
            size="xs"
            tooltip="Version history"
            onClick={() => onHistory(item)}
          />
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
      ),
    }),
  ];
}

export default function ArtifactLibraryPage() {
  const [scope, setScope] = useState<ArtifactLibraryScope>("all");
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<ArtifactLibraryType | "all">(
    "all"
  );
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectionEpoch, setSelectionEpoch] = useState(0);
  const [sharingItem, setSharingItem] = useState<ArtifactLibraryItem | null>(
    null
  );
  const [versionsItem, setVersionsItem] = useState<ArtifactLibraryItem | null>(
    null
  );
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [bulkBusy, setBulkBusy] = useState(false);

  const url = useMemo(() => {
    const params = new URLSearchParams({ scope });
    if (query.trim()) params.set("query", query.trim());
    if (typeFilter !== "all") params.set("artifact_type", typeFilter);
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

  const ownedSelectedIds = useMemo(() => {
    const ownerIds = new Set(
      data.filter((item) => item.is_owner).map((item) => item.id)
    );
    return selectedIds.filter((id) => ownerIds.has(id));
  }, [data, selectedIds]);

  const columns = useMemo(
    () =>
      buildColumns({
        onHistory: setVersionsItem,
        onShare: setSharingItem,
        onMutate: mutate,
      }),
    [mutate]
  );

  async function runBulk(action: ArtifactLibraryBulkAction) {
    if (ownedSelectedIds.length === 0) return;
    setBulkBusy(true);
    try {
      await bulkUpdateArtifactLibrary(ownedSelectedIds, action);
      toast.success(
        `${ownedSelectedIds.length} artifact${ownedSelectedIds.length === 1 ? "" : "s"} updated.`
      );
      setSelectedIds([]);
      setSelectionEpoch((current) => current + 1);
      setConfirmDelete(false);
      await mutate();
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

  return (
    <SettingsLayouts.Root width="lg">
      <SettingsLayouts.Header
        icon={SvgFiles}
        title="Artifacts"
        description="Find, share, publish, and revisit durable outputs from Craft."
      >
        <div className="flex w-full flex-wrap items-center gap-2">
          <Tabs
            value={scope}
            onValueChange={(value) => {
              setScope(value as ArtifactLibraryScope);
              setSelectedIds([]);
              setSelectionEpoch((current) => current + 1);
            }}
          >
            <Tabs.List>
              <Tabs.Trigger value="all">All</Tabs.Trigger>
              <Tabs.Trigger value="created">Created</Tabs.Trigger>
              <Tabs.Trigger value="shared">Shared</Tabs.Trigger>
            </Tabs.List>
          </Tabs>
          <div className="min-w-52 flex-1">
            <InputTypeIn
              clearButton
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search artifacts"
              searchIcon
              value={query}
            />
          </div>
          <div className="w-44">
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
      </SettingsLayouts.Header>
      <SettingsLayouts.Body>
        {ownedSelectedIds.length > 0 ? (
          <div className="flex w-full items-center justify-between gap-3 rounded-08 bg-background-tint-01 px-3 py-2">
            <Text color="text-03" font="main-ui-body">
              {`${ownedSelectedIds.length} owned selected`}
            </Text>
            <div className="flex items-center gap-1">
              <Button
                icon={SvgPin}
                prominence="tertiary"
                onClick={() => void runBulk("pin")}
                disabled={bulkBusy}
              >
                Pin
              </Button>
              <Button
                icon={SvgGlobe}
                prominence="tertiary"
                onClick={() => void runBulk("publish")}
                disabled={bulkBusy}
              >
                Publish
              </Button>
              <Button
                icon={SvgTrash}
                variant="danger"
                prominence="tertiary"
                onClick={() => setConfirmDelete(true)}
                disabled={bulkBusy}
              >
                Delete
              </Button>
            </div>
          </div>
        ) : null}

        {isLoading && data.length === 0 ? (
          <Text color="text-03" font="main-ui-body">
            Loading artifacts...
          </Text>
        ) : error ? (
          <Text color="status-error-05" font="main-ui-body">
            Artifacts could not be loaded.
          </Text>
        ) : (
          <Table
            key={`${url}-${selectionEpoch}`}
            data={data}
            columns={columns}
            getRowId={(item) => item.id}
            onRowClick={setVersionsItem}
            onSelectionChange={setSelectedIds}
            pageSize={20}
            selectionBehavior="multi-select"
            emptyState={
              <IllustrationContent
                illustration={SvgNoResult}
                title="No artifacts found"
                description="Save an output from a Craft session to add it here."
              />
            }
            footer={{ units: "artifacts" }}
          />
        )}
      </SettingsLayouts.Body>

      {sharingItem ? (
        <ArtifactShareModal
          item={sharingItem}
          onClose={() => setSharingItem(null)}
          onSaved={(item) => {
            setSharingItem(item);
            void mutate();
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
          title={`Delete ${ownedSelectedIds.length} artifact${ownedSelectedIds.length === 1 ? "" : "s"}?`}
          description="Every saved version will be permanently removed."
          onClose={() => setConfirmDelete(false)}
          submit={
            <Button
              variant="danger"
              onClick={() => void runBulk("delete")}
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
