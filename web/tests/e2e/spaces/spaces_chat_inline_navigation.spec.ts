import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";
import { SpaceDetailPage } from "@tests/e2e/pages/SpaceDetailPage";
import {
  buildMockStream,
  mockChatEndpoint,
  resetTurnCounter,
} from "@tests/e2e/utils/chatMock";

// Deterministic (mocked-LLM) regression for the Space→chat navigation bug:
// submitting the first message from a Space route used to route to /chat
// (which Next redirects to /app), changing the pathname. That pathname change
// fired useChatController's unmount cleanup which aborted the in-flight stream,
// while skip-reload suppressed the resume fetch — so the answer never rendered
// and the composer sat on "Thinking…". The fix keeps the composer on the Space
// pathname and attaches ?chatId, so the thread opens inline.
test.describe("Spaces inline chat navigation", () => {
  test.beforeEach(() => {
    resetTurnCounter();
  });

  test("submitting from a Space opens the thread inline and keeps the Space route", async ({
    page,
  }) => {
    await loginAs(page, "admin2");
    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const spaceName = `E2E Inline Chat Space ${stamp}`;
    const projectId = await apiClient.createProject(
      spaceName,
      "Space inline chat navigation regression",
    );

    const answer = "Mocked Space answer visible inline.";
    await mockChatEndpoint(page, buildMockStream(answer));

    try {
      await spaceDetail.goto({ spaceName, projectId });
      await expect(spaceDetail.inputBox).toBeVisible();

      const createSessionResponse = page.waitForResponse(
        (response) =>
          response.url().includes("/api/chat/create-chat-session") &&
          response.request().method() === "POST" &&
          response.status() === 200,
      );

      await spaceDetail.inputBox.fill("Ask something in this Space");
      await page.locator("#onyx-chat-input-send-button").click();

      const chatSessionId = (await (await createSessionResponse).json())
        .chat_session_id as string;
      expect(chatSessionId).toBeTruthy();

      // Navigation stays on the Space route (bug navigated to /app).
      await page.waitForURL(
        (url) => url.searchParams.get("chatId") === chatSessionId,
        { timeout: 30_000 },
      );
      expect(new URL(page.url()).pathname).toMatch(/^\/app\/spaces\//);

      // The answer renders inline (not stuck "Thinking…").
      await expect(page.getByTestId("onyx-ai-message").last()).toContainText(
        answer,
        { timeout: 30_000 },
      );
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });
});
