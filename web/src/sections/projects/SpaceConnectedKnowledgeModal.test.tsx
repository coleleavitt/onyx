import { render, screen, userEvent, waitFor } from "@tests/setup/test-utils";
import SpaceConnectedKnowledgeModal from "@/sections/projects/SpaceConnectedKnowledgeModal";
import SpaceConnectedSourcesSection from "@/sections/projects/SpaceConnectedSourcesSection";
import { ValidSources } from "@/lib/types";
import type { ProjectConnectedKnowledge } from "@/lib/projects/types";

const mockUseCCPairs = jest.fn();
const mockFetchHierarchyNodes = jest.fn();
const lastHierarchyBrowserProps: Record<string, unknown> = {};

jest.mock("@/lib/hierarchy/svc", () => ({
  fetchHierarchyNodes: (...args: unknown[]) => mockFetchHierarchyNodes(...args),
}));

jest.mock("@/hooks/useCCPairs", () => ({
  __esModule: true,
  default: (...args: unknown[]) => mockUseCCPairs(...args),
}));

jest.mock("@/sections/knowledge/SourceHierarchyBrowser", () => ({
  __esModule: true,
  default: (props: {
    onToggleDocument: (id: string) => void;
    onToggleFolder: (id: number) => void;
    initialNodeId?: number;
  }) => {
    Object.assign(lastHierarchyBrowserProps, props);
    return (
      <div aria-label="mock hierarchy browser">
        <div>initial-node:{props.initialNodeId ?? "root"}</div>
        <button type="button" onClick={() => props.onToggleDocument("doc-new")}>
          Toggle mock document
        </button>
        <button type="button" onClick={() => props.onToggleFolder(7)}>
          Toggle mock folder
        </button>
      </div>
    );
  },
}));

const baseKnowledge: ProjectConnectedKnowledge = {
  documents: [
    {
      id: "doc-existing",
      title: "Existing policy",
      link: "https://sharepoint.example/doc-existing",
      source: ValidSources.Sharepoint,
      parent_hierarchy_node_id: 3,
      last_modified: null,
      last_synced: null,
    },
  ],
  hierarchy_nodes: [
    {
      id: 3,
      title: "Policies folder",
      link: "https://sharepoint.example/policies",
      source: ValidSources.Sharepoint,
      parent_id: null,
    },
  ],
};

beforeEach(() => {
  for (const key of Object.keys(lastHierarchyBrowserProps)) {
    delete lastHierarchyBrowserProps[key];
  }
  mockUseCCPairs.mockReturnValue({
    ccPairs: [{ id: 1, source: ValidSources.Sharepoint, name: "SharePoint" }],
    isLoading: false,
    error: undefined,
    refetch: jest.fn(),
  });
  mockFetchHierarchyNodes.mockResolvedValue({
    nodes: [
      {
        id: 10,
        title: "AdvisorServicesIntranet",
        link: "https://fiwealth.sharepoint.com/sites/AdvisorServicesIntranet",
        parent_id: 1,
        governance: {
          curation_status: "DEFAULT_SAFE",
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
      },
    ],
  });
});

test("space knowledge modal keeps uploads distinct from connected source selections and saves hierarchy toggles", async () => {
  const user = userEvent.setup();
  const onSave = jest.fn().mockResolvedValue(undefined);
  render(
    <SpaceConnectedKnowledgeModal
      open
      canEdit
      knowledge={baseKnowledge}
      onClose={jest.fn()}
      onSave={onSave}
      onUploadFiles={jest.fn()}
    />,
  );

  expect(screen.getByRole("tab", { name: "Connected sources" })).toBeVisible();
  expect(await screen.findByText("Foundations")).toBeVisible();
  expect(screen.getByText("Advisor Services Intranet")).toBeVisible();
  await user.click(screen.getByText("Advisor Services Intranet"));
  expect(lastHierarchyBrowserProps.initialNodeId).toBe(10);
  await user.click(screen.getByRole("tab", { name: "Uploaded files" }));
  expect(
    screen.getByText("Uploaded files are copied into this space"),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Upload local files" }),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Upload local folder" }),
  ).toBeVisible();

  await user.click(screen.getByRole("tab", { name: "Connected sources" }));
  await user.click(
    screen.getByRole("button", { name: "Toggle mock document" }),
  );
  await user.click(screen.getByRole("button", { name: "Toggle mock folder" }));
  await user.click(screen.getByRole("button", { name: "Save" }));

  await waitFor(() => {
    expect(onSave).toHaveBeenCalledWith(["doc-existing", "doc-new"], [3, 10, 7]);
  });
});

test("space connected-source rail renders connector selections separately from uploaded files", () => {
  const onOpenPicker = jest.fn();
  render(
    <SpaceConnectedSourcesSection
      knowledge={baseKnowledge}
      canEdit
      compact={false}
      onOpenPicker={onOpenPicker}
    />,
  );

  expect(screen.getByText("Connected sources")).toBeVisible();
  expect(screen.getByText("Policies folder")).toBeVisible();
  expect(screen.getByText("Existing policy")).toBeVisible();
  expect(screen.queryByText("Space Files")).not.toBeInTheDocument();
});
