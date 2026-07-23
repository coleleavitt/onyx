import { render, screen, userEvent, waitFor } from "@tests/setup/test-utils";
import SourceHierarchyBrowser from "@/sections/knowledge/SourceHierarchyBrowser";
import { ValidSources } from "@/lib/types";
import type { HierarchyNodesResponse } from "@/lib/hierarchy/interfaces";

const mockFetchHierarchyNodes = jest.fn();
const mockFetchHierarchyNodeDocuments = jest.fn();

jest.mock("@/lib/hierarchy/svc", () => ({
  fetchHierarchyNodes: (...args: unknown[]) => mockFetchHierarchyNodes(...args),
  fetchHierarchyNodeDocuments: (...args: unknown[]) =>
    mockFetchHierarchyNodeDocuments(...args),
}));

const rootNode = {
  id: 1,
  title: "SharePoint",
  link: null,
  parent_id: null,
  governance: {
    curation_status: null,
    is_default: false,
    is_archived: false,
    is_hidden: false,
    is_diagnostic: false,
    is_selectable: true,
    denial_reason: null,
    display_label: null,
    tenant_label: null,
    department_label: null,
    sort_order: 0,
    size_bytes: null,
    document_count_estimate: null,
    indexed_document_count: 0,
    indexed_chunk_count: 0,
    indexing_status: null,
    last_synced_at: null,
    warning: null,
    allowed_group_ids: [],
    excluded_hierarchy_node_ids: [],
  },
};

const navigationOnlyNode = {
  id: 4,
  title: "Foundations",
  link: null,
  parent_id: 1,
  governance: {
    curation_status: null,
    is_default: false,
    is_archived: false,
    is_hidden: false,
    is_diagnostic: false,
    is_selectable: false,
    denial_reason: "navigation_only",
    display_label: "Foundations",
    tenant_label: "Foundations",
    department_label: null,
    sort_order: 0,
    size_bytes: null,
    document_count_estimate: null,
    indexed_document_count: 0,
    indexed_chunk_count: 0,
    indexing_status: null,
    last_synced_at: null,
    warning: null,
    allowed_group_ids: [],
    excluded_hierarchy_node_ids: [],
  },
};

const recommendedNode = {
  id: 2,
  title: "AdvisorServicesIntranet",
  link: "https://fiwealth.sharepoint.com/sites/AdvisorServicesIntranet",
  parent_id: 1,
  governance: {
    curation_status: "DEFAULT_SAFE" as const,
    is_default: true,
    is_archived: false,
    is_hidden: false,
    is_diagnostic: false,
    is_selectable: true,
    denial_reason: null,
    display_label: "Advisor Services Intranet",
    tenant_label: "Foundations",
    department_label: "Advisor Services",
    sort_order: 1,
    size_bytes: 18_000_000,
    document_count_estimate: 372,
    indexed_document_count: 373,
    indexed_chunk_count: 27186,
    indexing_status: "success",
    last_synced_at: "2026-07-23T16:00:00Z",
    warning: null,
    allowed_group_ids: [10],
    excluded_hierarchy_node_ids: [],
  },
};

const archiveNode = {
  id: 3,
  title: "BusinessDevelopmentIntranet",
  link: "https://fiwealth.sharepoint.com/sites/BusinessDevelopmentIntranet",
  parent_id: 1,
  governance: {
    curation_status: "ARCHIVE" as const,
    is_default: false,
    is_archived: true,
    is_hidden: false,
    is_diagnostic: false,
    is_selectable: true,
    denial_reason: null,
    display_label: "Business Development Archive",
    tenant_label: "Foundations",
    department_label: "Business Development",
    sort_order: 99,
    size_bytes: 94_000_000_000,
    document_count_estimate: 122763,
    indexed_document_count: 562,
    indexed_chunk_count: 35991,
    indexing_status: "canceled",
    last_synced_at: "2026-07-22T16:00:00Z",
    warning: "Large historical transition archive.",
    allowed_group_ids: [],
    excluded_hierarchy_node_ids: [],
  },
};

function response(includeArchive: boolean): HierarchyNodesResponse {
  return {
    nodes: includeArchive
      ? [rootNode, navigationOnlyNode, recommendedNode, archiveNode]
      : [rootNode, navigationOnlyNode, recommendedNode],
  };
}

test("hierarchy browser hides archive scopes until explicitly opted in and shows governance badges", async () => {
  const user = userEvent.setup();
  mockFetchHierarchyNodes.mockImplementation(
    (_source: ValidSources, options?: { includeArchived?: boolean }) =>
      Promise.resolve(response(Boolean(options?.includeArchived)))
  );
  mockFetchHierarchyNodeDocuments.mockResolvedValue({
    documents: [],
    next_cursor: null,
    page_size: 50,
    sort_field: "last_updated",
    sort_direction: "desc",
    folder_position: "on_top",
  });

  render(
    <SourceHierarchyBrowser
      source={ValidSources.Sharepoint}
      selectedDocumentIds={[]}
      onToggleDocument={jest.fn()}
      onSetDocumentIds={jest.fn()}
      selectedFolderIds={[]}
      onToggleFolder={jest.fn()}
      onSetFolderIds={jest.fn()}
      onDeselectAllDocuments={jest.fn()}
      onDeselectAllFolders={jest.fn()}
    />
  );

  const advisorLabels = await screen.findAllByText("Advisor Services Intranet");
  expect(advisorLabels.length).toBeGreaterThan(0);
  expect(screen.getAllByText(/Recommended/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/373 docs/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/Success/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/Synced/).length).toBeGreaterThan(0);
  expect(screen.queryByText("Business Development Archive")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Show archives" }));

  await waitFor(() => {
    expect(mockFetchHierarchyNodes).toHaveBeenLastCalledWith(
      ValidSources.Sharepoint,
      { includeArchived: true }
    );
  });
  const archiveLabels = await screen.findAllByText("Business Development Archive");
  expect(archiveLabels.length).toBeGreaterThan(0);
  expect(screen.getAllByText(/Archive/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/Large historical transition archive/).length).toBeGreaterThan(0);
});


test("hierarchy browser select-all ignores navigation-only folder scopes", async () => {
  const user = userEvent.setup();
  const onSetFolderIds = jest.fn();
  mockFetchHierarchyNodes.mockResolvedValue(response(false));
  mockFetchHierarchyNodeDocuments.mockResolvedValue({
    documents: [],
    next_cursor: null,
    page_size: 50,
    sort_field: "last_updated",
    sort_direction: "desc",
    folder_position: "on_top",
  });

  render(
    <SourceHierarchyBrowser
      source={ValidSources.Sharepoint}
      selectedDocumentIds={[]}
      onToggleDocument={jest.fn()}
      onSetDocumentIds={jest.fn()}
      selectedFolderIds={[]}
      onToggleFolder={jest.fn()}
      onSetFolderIds={onSetFolderIds}
      onDeselectAllDocuments={jest.fn()}
      onDeselectAllFolders={jest.fn()}
    />
  );

  await screen.findAllByText("Foundations");
  await user.click(screen.getAllByRole("checkbox")[0]);

  expect(onSetFolderIds).toHaveBeenCalledWith([recommendedNode.id]);
  expect(onSetFolderIds).not.toHaveBeenCalledWith(
    expect.arrayContaining([navigationOnlyNode.id])
  );
});
