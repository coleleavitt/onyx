import { expect, test, type Page } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";
import {
  openActionManagement,
  openSourceManagement,
  TOOL_IDS,
} from "@tests/e2e/utils/tools";
import { buildMockStream, mockChatEndpoint } from "@tests/e2e/utils/chatMock";

type SendChatMessagePayload = {
  forced_tool_id?: number | null;
  internal_search_filters?: {
    source_type?: string[] | null;
  };
};

async function ensureDefaultAssistantSearchTool(page: Page): Promise<number> {
  const toolsResponse = await page.request.get("/api/tool");
  expect(toolsResponse.ok()).toBeTruthy();
  const tools = (await toolsResponse.json()) as Array<{
    id: number;
    in_code_tool_id?: string | null;
  }>;
  const searchTool = tools.find((tool) => tool.in_code_tool_id === "SearchTool");
  expect(searchTool).toBeTruthy();

  const configResponse = await page.request.get(
    "/api/admin/default-assistant/configuration"
  );
  expect(configResponse.ok()).toBeTruthy();
  const config = (await configResponse.json()) as { tool_ids: number[] };
  if (!config.tool_ids.includes(searchTool!.id)) {
    const patchResponse = await page.request.patch("/api/admin/default-assistant", {
      data: { tool_ids: [...config.tool_ids, searchTool!.id] },
    });
    expect(patchResponse.ok()).toBeTruthy();
  }

  return searchTool!.id;
}

test.describe("Internal search source selection", () => {
  test("enabling SharePoint forces internal search for the next prompt", async ({
    page,
  }) => {
    await page.context().clearCookies();
    await loginAs(page, "admin");

    const indexedSources = await page.request.get("/api/manage/indexed-sources");
    expect(indexedSources.ok()).toBeTruthy();
    expect(((await indexedSources.json()) as { sources: string[] }).sources).toContain(
      "sharepoint"
    );

    const searchToolId = await ensureDefaultAssistantSearchTool(page);

    const chat = new ChatPage(page);
    await chat.goto();
    await mockChatEndpoint(page, buildMockStream("SharePoint search smoke response"));

    await openActionManagement(page);
    await expect(page.locator(TOOL_IDS.searchOption)).toBeVisible({ timeout: 10000 });
    await openSourceManagement(page);

    const sharePointToggle = page.locator('[aria-label="Toggle Sharepoint"]');
    await expect(sharePointToggle).toBeVisible({ timeout: 10000 });
    if ((await sharePointToggle.getAttribute("aria-checked")) === "true") {
      await sharePointToggle.click();
      await expect(sharePointToggle).toHaveAttribute("aria-checked", "false");
    }
    await sharePointToggle.click();
    await expect(sharePointToggle).toHaveAttribute("aria-checked", "true");

    await page.keyboard.press("Escape");
    await expect(page.locator(TOOL_IDS.options)).toBeHidden({ timeout: 5000 });

    const capturedPayloads: SendChatMessagePayload[] = [];
    await page.route("**/api/chat/send-chat-message", async (route) => {
      capturedPayloads.push(
        route.request().postDataJSON() as SendChatMessagePayload
      );
      await route.continue();
    });

    await chat.inputBar.fill("tell me about my company's next holiday");
    await chat.inputBar.clickSend();

    await expect.poll(() => capturedPayloads.length).toBeGreaterThan(0);
    const capturedPayload = capturedPayloads[0];
    expect(capturedPayload?.forced_tool_id).toBe(searchToolId);
    expect(capturedPayload?.internal_search_filters?.source_type).toContain(
      "sharepoint"
    );
  });
});
