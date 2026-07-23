import { createProject, fetchConnectedKnowledgePresets } from "@/lib/projects/svc";
import { updateConnectedSourceScopeGroupSharing } from "@/views/admin/GroupsPage/svc";

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ id: 12, name: "Advisor Space" }),
  }) as unknown as typeof fetch;
});

afterEach(() => {
  jest.restoreAllMocks();
});

test("createProject sends connected knowledge preset id to the create endpoint", async () => {
  await createProject({
    name: "Advisor Space",
    emoji: "📁",
    description: "Advisor Services default",
    instructions: "Use Advisor Services sources.",
    connected_knowledge_preset_id: 44,
  });

  expect(global.fetch).toHaveBeenCalledTimes(1);
  const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
  expect(String(url)).toContain("/api/user/projects/create?");
  expect(String(url)).toContain("connected_knowledge_preset_id=44");
  expect(String(url)).toContain("name=Advisor+Space");
  expect(init).toMatchObject({ method: "POST" });
});

test("fetchConnectedKnowledgePresets uses the shipped presets endpoint", async () => {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    json: async () => [],
  });

  await expect(fetchConnectedKnowledgePresets()).resolves.toEqual([]);
  expect(global.fetch).toHaveBeenCalledWith(
    "/api/user/projects/connected-knowledge-presets"
  );
});


test("removing the last group from a connected source scope keeps it restricted", async () => {
  (global.fetch as jest.Mock)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          id: 1,
          hierarchy_node_id: 44,
          title: "Advisor Services Intranet",
          source: "sharepoint",
          link: null,
          parent_id: null,
          access_type: "RESTRICTED",
          curation_status: "DEFAULT_SAFE",
          display_label: "Advisor Services Intranet",
          tenant_label: "Foundations",
          department_label: "Advisor Services",
          sort_order: 0,
          size_bytes: null,
          document_count_estimate: null,
          warning: null,
          group_ids: [7],
          excluded_hierarchy_node_ids: [],
        },
      ],
    })
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1 }),
    });

  await updateConnectedSourceScopeGroupSharing(7, [1], []);

  expect(global.fetch).toHaveBeenCalledTimes(2);
  const [url, init] = (global.fetch as jest.Mock).mock.calls[1];
  expect(url).toBe("/api/user/projects/connected-source-scopes/44");
  expect(init).toMatchObject({ method: "PUT" });
  expect(JSON.parse(init.body)).toMatchObject({
    access_type: "RESTRICTED",
    group_ids: [],
  });
});
