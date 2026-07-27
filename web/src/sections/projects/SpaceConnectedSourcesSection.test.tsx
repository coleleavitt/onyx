import { render, screen } from "@tests/setup/test-utils";
import SpaceConnectedSourcesSection from "@/sections/projects/SpaceConnectedSourcesSection";
import { ValidSources } from "@/lib/types";
import type { ProjectConnectedKnowledge } from "@/lib/projects/types";

function folder(
  id: number,
  title: string,
  source: ValidSources = ValidSources.Sharepoint
) {
  return { id, title, link: null, source, parent_id: null };
}

function doc(id: string, title: string, source: ValidSources | null) {
  return {
    id,
    title,
    link: null,
    source,
    parent_hierarchy_node_id: null,
    last_modified: null,
    last_synced: null,
  };
}

function renderSection(knowledge: ProjectConnectedKnowledge) {
  render(
    <SpaceConnectedSourcesSection
      knowledge={knowledge}
      canEdit
      compact={false}
      onOpenPicker={jest.fn()}
    />
  );
}

test("a single connected folder renders one row, not a summary plus a duplicate", () => {
  renderSection({
    documents: [],
    hierarchy_nodes: [folder(1, "AdvisorServicesIntranet")],
  });

  expect(screen.getByText("AdvisorServicesIntranet")).toBeVisible();
  // The old shape emitted a "Sharepoint" summary row above the item and
  // repeated the source as the item's description — the same fact three times.
  expect(screen.queryByText("Sharepoint")).not.toBeInTheDocument();
});

test("rows carry a source label only once more than one source is connected", () => {
  renderSection({
    documents: [doc("d1", "Quarterly deck", ValidSources.GoogleDrive)],
    hierarchy_nodes: [folder(1, "AdvisorServicesIntranet")],
  });

  expect(screen.getByText("AdvisorServicesIntranet")).toBeVisible();
  expect(screen.getByText("Quarterly deck")).toBeVisible();
  // Now the label disambiguates rather than repeating.
  expect(screen.getByText("Sharepoint")).toBeVisible();
  expect(screen.getByText("Google Drive")).toBeVisible();
});

test("overflow beyond the cap is stated instead of silently dropped", () => {
  renderSection({
    documents: [],
    hierarchy_nodes: Array.from({ length: 8 }, (_, i) =>
      folder(i + 1, `Folder ${i + 1}`)
    ),
  });

  expect(screen.getByText("Folder 5")).toBeVisible();
  // The old shape sliced to 3 with no indication the rest existed.
  expect(screen.queryByText("Folder 6")).not.toBeInTheDocument();
  expect(screen.getByText("3 more")).toBeVisible();
  expect(screen.getByText("8 folders")).toBeVisible();
});

test("counts are pluralized", () => {
  renderSection({
    documents: [doc("d1", "Only doc", ValidSources.Sharepoint)],
    hierarchy_nodes: Array.from({ length: 5 }, (_, i) =>
      folder(i + 1, `Folder ${i + 1}`)
    ),
  });

  // The old shape hardcoded the singular: "5 folder/site", "1 document".
  expect(screen.getByText("5 folders · 1 document")).toBeVisible();
});

test("an empty selection shows the placeholder, not an empty list", () => {
  renderSection({ documents: [], hierarchy_nodes: [] });

  expect(screen.getByText(/No connected sources yet/)).toBeVisible();
});
