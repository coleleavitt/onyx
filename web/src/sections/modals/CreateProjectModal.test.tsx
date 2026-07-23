import { fireEvent, render, screen, userEvent, waitFor } from "@tests/setup/test-utils";
import CreateProjectModal, {
  presetDetailLine,
} from "@/sections/modals/CreateProjectModal";
import { ValidSources } from "@/lib/types";
import type { ConnectedKnowledgePreset } from "@/lib/projects/types";

const mockCreateProject = jest.fn();
const mockFetchConnectedKnowledgePresets = jest.fn();
const mockRoute = jest.fn();
const mockToggle = jest.fn();

jest.mock("@/providers/ProjectsContext", () => ({
  useProjectsContext: () => ({ createProject: mockCreateProject }),
}));

jest.mock("@/hooks/appNavigation", () => ({
  useAppRouter: () => mockRoute,
}));

jest.mock("@/refresh-components/contexts/ModalContext", () => ({
  useModal: () => ({ isOpen: true, toggle: mockToggle }),
}));

jest.mock("@/lib/projects/svc", () => ({
  fetchConnectedKnowledgePresets: (...args: unknown[]) =>
    mockFetchConnectedKnowledgePresets(...args),
}));

beforeAll(() => {
  // Radix Select calls scrollIntoView when opening options; jsdom does not
  // implement it.
  window.HTMLElement.prototype.scrollIntoView = jest.fn();
});

const hrPreset: ConnectedKnowledgePreset = {
  id: 12,
  name: "Magellan HR starter",
  description: "Company Wide Files and JF from the Magellan HR intranet",
  emoji: "📁",
  instructions: null,
  is_default: true,
  is_archived: false,
  connected_knowledge: {
    documents: [],
    hierarchy_nodes: [
      {
        id: 599,
        title: "Company Wide Files",
        link: "https://sharepoint.example/company-wide",
        source: ValidSources.Sharepoint,
        parent_id: 598,
      },
      {
        id: 605,
        title: "JF",
        link: "https://sharepoint.example/jf",
        source: ValidSources.Sharepoint,
        parent_id: 598,
      },
    ],
  },
};

beforeEach(() => {
  mockCreateProject.mockResolvedValue({ id: 555, name: "HR research" });
  mockFetchConnectedKnowledgePresets.mockResolvedValue([hrPreset]);
  mockRoute.mockClear();
  mockToggle.mockClear();
});

test("space preset picker uses the Opal select, shows preset contents, and submits the preset id", async () => {
  const user = userEvent.setup();
  render(
    <CreateProjectModal terminology="space" initialProjectName="HR research" />,
  );
  const presetTrigger = await screen.findByRole("combobox");
  fireEvent.keyDown(presetTrigger, { key: "ArrowDown" });
  await user.click(await screen.findByRole("option", { name: /Magellan HR starter/ }));

  expect(
    screen.getByText(
      "Company Wide Files and JF from the Magellan HR intranet — Includes: Company Wide Files, JF",
    ),
  ).toBeVisible();
  expect(screen.getByRole("combobox")).toBeVisible();
  expect(document.querySelector("select[name='presetId']")).toBeNull();

  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Create Space" })).toBeEnabled(),
  );
  await user.click(screen.getByRole("button", { name: "Create Space" }));

  await waitFor(() => {
    expect(mockCreateProject).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "HR research",
        connected_knowledge_preset_id: 12,
      }),
    );
  });
});

test("preset fetch failures are logged instead of swallowed", async () => {
  const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
  mockFetchConnectedKnowledgePresets.mockRejectedValue(new Error("boom"));
  try {
    render(<CreateProjectModal terminology="space" />);
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to fetch connected knowledge presets",
        expect.any(Error),
      );
    });
  } finally {
    consoleSpy.mockRestore();
  }
});

test("preset detail helper summarizes descriptions and attached source names", () => {
  expect(presetDetailLine(hrPreset)).toBe(
    "Company Wide Files and JF from the Magellan HR intranet — Includes: Company Wide Files, JF",
  );
});
