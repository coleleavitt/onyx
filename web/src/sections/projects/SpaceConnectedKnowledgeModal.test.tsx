import { render, screen, userEvent, waitFor } from "@tests/setup/test-utils";
import SpaceConnectedKnowledgeModal from "@/sections/projects/SpaceConnectedKnowledgeModal";
import SpaceConnectedSourcesSection from "@/sections/projects/SpaceConnectedSourcesSection";
import { ValidSources } from "@/lib/types";
import type { ProjectConnectedKnowledge } from "@/lib/projects/types";

const mockUseCCPairs = jest.fn();

jest.mock("@/hooks/useCCPairs", () => ({
  __esModule: true,
  default: (...args: unknown[]) => mockUseCCPairs(...args),
}));

jest.mock("@/sections/knowledge/SourceHierarchyBrowser", () => ({
  __esModule: true,
  default: ({
    onToggleDocument,
    onToggleFolder,
  }: {
    onToggleDocument: (id: string) => void;
    onToggleFolder: (id: number) => void;
  }) => (
    <div aria-label="mock hierarchy browser">
      <button type="button" onClick={() => onToggleDocument("doc-new")}>
        Toggle mock document
      </button>
      <button type="button" onClick={() => onToggleFolder(7)}>
        Toggle mock folder
      </button>
    </div>
  ),
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
  mockUseCCPairs.mockReturnValue({
    ccPairs: [{ id: 1, source: ValidSources.Sharepoint, name: "SharePoint" }],
    isLoading: false,
    error: undefined,
    refetch: jest.fn(),
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
    expect(onSave).toHaveBeenCalledWith(["doc-existing", "doc-new"], [3, 7]);
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
