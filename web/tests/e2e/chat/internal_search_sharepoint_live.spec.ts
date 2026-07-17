import { expect, test } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";
import {
  openActionManagement,
  openSourceManagement,
  TOOL_IDS,
} from "@tests/e2e/utils/tools";

// Live regression for the "SharePoint search shows No results found" outage:
// the search tool ran but the query-embedding model server (port 9000) was
// down, so retrieval silently returned nothing and the answer was guessed
// from public knowledge. This test runs the real end-user flow (live LLM,
// live retrieval) and fails whenever internal search produces no documents.
test.describe("Internal search SharePoint live retrieval", () => {
  test("holiday prompt retrieves SharePoint documents and cites them", async ({
    page,
  }) => {
    test.setTimeout(240_000);

    await page.context().clearCookies();
    await loginAs(page, "admin");

    const indexedSources = await page.request.get("/api/manage/indexed-sources");
    expect(indexedSources.ok()).toBeTruthy();
    expect(
      ((await indexedSources.json()) as { sources: string[] }).sources
    ).toContain("sharepoint");

    const chat = new ChatPage(page);
    await chat.goto();

    await openActionManagement(page);
    await expect(page.locator(TOOL_IDS.searchOption)).toBeVisible({
      timeout: 10000,
    });
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

    // Capture the streamed chat response so retrieval can be asserted at the
    // packet level, independent of how the UI renders it.
    let streamBody = "";
    await page.route("**/api/chat/send-chat-message", async (route) => {
      const response = await route.fetch();
      streamBody = await response.text();
      await route.fulfill({ response, body: streamBody });
    });

    await chat.inputBar.fill("what is my next company holiday?");
    await chat.inputBar.clickSend();

    // The stream must contain retrieved sharepoint documents.
    await expect
      .poll(() => streamBody.length > 0, { timeout: 180_000 })
      .toBeTruthy();
    expect(streamBody).toContain('"sharepoint"');
    expect(streamBody).not.toContain('"results": []');

    // End-user rendering: a cited answer with sources, not "No results found".
    await expect(
      page
        .getByTestId("AgentMessage/toolbar")
        .getByRole("button", { name: "Sources" })
    ).toBeVisible({ timeout: 180_000 });
    await expect(page.getByText("No results found")).toBeHidden();
  });
});
