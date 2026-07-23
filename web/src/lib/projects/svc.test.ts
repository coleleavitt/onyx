import { createProject, fetchConnectedKnowledgePresets } from "@/lib/projects/svc";

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
