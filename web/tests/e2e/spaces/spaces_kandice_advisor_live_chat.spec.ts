import { expect, test, type APIRequestContext } from "@playwright/test";
import { SpaceDetailPage } from "@tests/e2e/pages/SpaceDetailPage";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";
import { apiLogin } from "@tests/e2e/utils/auth";

const KANDICE_EMAIL = "kandice.garcia@fiwealth.com";
const KANDICE_PASSWORD = "TestPassword123!";
const ADVISOR_NODE_ID = 627;
const QUESTION =
  "Using only the connected Advisor Services files, what do we have about TPMM vs SubAdvisors? Name the exact document if you find it.";

async function visibleSharePointNodeIds(
  request: APIRequestContext,
): Promise<Set<number>> {
  const response = await request.get("/api/hierarchy-nodes?source=sharepoint");
  expect(response.status()).toBe(200);
  const body = await response.json();
  return new Set(body.nodes.map((node: { id: number }) => node.id));
}

/**
 * Latest assistant message text for a chat session, or "" if none yet.
 * Uses the shipped get-chat-session endpoint so the assertion does not depend
 * on mid-stream UI navigation timing.
 */
async function latestAssistantAnswer(
  request: APIRequestContext,
  chatSessionId: string,
): Promise<string> {
  const response = await request.get(
    `/api/chat/get-chat-session/${chatSessionId}`,
  );
  if (!response.ok()) return "";
  const body = await response.json();
  const messages: Array<{ message: string; message_type: string }> =
    body.messages ?? [];
  const assistantMessages = messages.filter(
    (message) => message.message_type === "assistant",
  );
  return assistantMessages.at(-1)?.message ?? "";
}

test.describe("Kandice Advisor Services live Space chat", () => {
  test("logs in as Kandice and answers from Advisor Services internal files", async ({
    page,
  }) => {
    test.setTimeout(300_000);

    await page.context().clearCookies();
    await apiLogin(page, KANDICE_EMAIL, KANDICE_PASSWORD);

    // Governance: Kandice can see the real Advisor Services SharePoint site.
    const visibleNodes = await visibleSharePointNodeIds(page.request);
    expect(visibleNodes.has(ADVISOR_NODE_ID)).toBe(true);

    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const spaceName = `Kandice Advisor Live ${stamp}`;
    const projectId = await apiClient.createProject(
      spaceName,
      "Live LLM regression for Advisor Services connected source",
    );

    try {
      const attachResponse = await page.request.put(
        `/api/user/projects/${projectId}/connected-knowledge`,
        { data: { document_ids: [], hierarchy_node_ids: [ADVISOR_NODE_ID] } },
      );
      expect(attachResponse.status()).toBe(200);

      await spaceDetail.goto({ spaceName, projectId });
      await expect(
        page.getByText("Connected sources", { exact: true }).first(),
      ).toBeVisible();
      await expect(
        page.getByText("AdvisorServicesIntranet").first(),
      ).toBeVisible();

      // Capture the chat session id the composer creates on submit.
      const createSessionResponse = page.waitForResponse(
        (response) =>
          response.url().includes("/api/chat/create-chat-session") &&
          response.request().method() === "POST" &&
          response.status() === 200,
        { timeout: 30_000 },
      );

      await spaceDetail.inputBox.fill(QUESTION);
      await page.locator("#onyx-chat-input-send-button").click();

      const chatSessionId = (await (await createSessionResponse).json())
        .chat_session_id as string;
      expect(chatSessionId).toBeTruthy();

      // Regression: submitting from a Space must keep the composer on the Space
      // route and open the thread inline (Perplexity-style) rather than
      // navigating to /app and stranding the stream on "Thinking…". Wait for
      // the new chatId to attach, then assert the pathname is STILL the Space
      // route (the bug navigated to /app instead).
      await page.waitForURL(
        (url) => url.searchParams.get("chatId") === chatSessionId,
        { timeout: 30_000 },
      );
      expect(new URL(page.url()).pathname).toMatch(/^\/app\/spaces\//);

      // The answer renders inline in the Space thread — not stuck thinking.
      const latestAnswer = page.getByTestId("onyx-ai-message").last();
      await expect(latestAnswer).toContainText(/TPMM vs SubAdvisors/i, {
        timeout: 240_000,
      });
      await expect(latestAnswer).not.toContainText(
        /internal search is temporarily unavailable|search infrastructure error|no results found/i,
      );

      // And the persisted session carries the internal citation (governance +
      // internal semantic search + LLM answer, end to end).
      const finalAnswer = await latestAssistantAnswer(
        page.request,
        chatSessionId,
      );
      expect(finalAnswer).toMatch(
        /AdvisorServicesIntranet|Advisor Services|\.pdf/i,
      );
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });
});
