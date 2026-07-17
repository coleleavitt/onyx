import { expect, test } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";
import {
  selectModelFromInputPopover,
  verifyCurrentModel,
} from "@tests/e2e/utils/chatActions";

type StreamPacket = {
  obj?: {
    type?: string;
    content?: string;
  };
};

function streamedAnswerText(body: string): string {
  return body
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as StreamPacket)
    .filter((packet) => packet.obj?.type === "message_delta")
    .map((packet) => packet.obj?.content ?? "")
    .join("");
}

test.describe("Live LLM model picker", () => {
  test.skip(
    process.env.LIVE_LLM_E2E !== "true",
    "Set LIVE_LLM_E2E=true to spend live LLM credits."
  );

  test("selected visible model returns a real streamed response", async ({
    page,
  }) => {
    await page.context().clearCookies();
    await loginAs(page, "admin");

    const chat = new ChatPage(page);
    await chat.goto();

    const requestedModel = process.env.LIVE_LLM_MODEL ?? "GPT-5.5";
    const selectedModel = await selectModelFromInputPopover(page, [
      requestedModel,
    ]);
    expect(selectedModel).toContain(requestedModel);
    await verifyCurrentModel(page, selectedModel);

    const expectedText = "onyx-live-smoke";
    const prompt = `Reply with exactly this text and no markdown: ${expectedText}`;

    const existingMessageCount = await chat.aiMessages.count();
    const responsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().includes("/api/chat/send-chat-message"),
      { timeout: 120000 }
    );

    await chat.inputBar.textbox.fill(prompt);
    await page.locator("#onyx-chat-input-send-button").click();

    const response = await responsePromise;
    expect(response.ok()).toBeTruthy();

    const body = await response.text();
    const streamedText = streamedAnswerText(body);
    expect(streamedText.toLowerCase()).toContain(expectedText);

    await expect(chat.aiMessages).toHaveCount(existingMessageCount + 1, {
      timeout: 30000,
    });
    await expect(chat.aiMessages.last()).toContainText(expectedText, {
      timeout: 30000,
    });
    await expect(page.getByText("There was an error with the response")).toHaveCount(
      0
    );
  });
});
