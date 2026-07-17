import { expect, test } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";

// Live end-user regression for the "stop generation, then regenerate" flow.
// The send button morphs into a stop affordance while the answer streams
// (SvgStop renders this exact path). Clicking it must cancel generation and
// return the composer to a sendable state; the assistant message toolbar must
// then let the user regenerate a fresh, completed answer. Runs against a live
// LLM — a partial first answer is expected and its content is not asserted.
const STOP_ICON_PATH = 'path[d="M12 4H4V12H12V4Z"]';
const STOP_ICON = `#onyx-chat-input-send-button ${STOP_ICON_PATH}`;

test.describe("Stop generation and regenerate", () => {
  test("user stops a streaming answer then regenerates a fresh one", async ({
    page,
  }) => {
    test.setTimeout(300_000);

    await page.context().clearCookies();
    await loginAs(page, "admin");

    const chat = new ChatPage(page);
    await chat.goto();

    const marker = `stopregen-${Date.now()}`;
    const stopIcon = page.locator(STOP_ICON);
    const createdChatIds = new Set<string>();

    function currentChatId(): string | null {
      return new URL(page.url()).searchParams.get("chatId");
    }

    // The latest assistant message. The `onyx-ai-message` testid is only
    // present once the message is complete (including after a user stop, once
    // the STOP packet lands), so this also gates on completion.
    function latestAiMessage() {
      return page.getByTestId("onyx-ai-message").last();
    }

    try {
      // The streaming answer content of the latest assistant message. This div
      // is empty during the pre-answer "thinking" phase and only fills once
      // answer display-groups render.
      const streamingAnswer = page.locator(".select-text").last();

      // Send a prompt that streams long enough to interrupt, then click stop
      // once the answer has begun rendering. Returns false if the answer never
      // started or finished before we could interrupt (retry with a longer
      // prompt). Stopping mid-answer (rather than mid-thinking) is required so
      // the stopped message becomes "complete" and exposes its toolbar.
      async function sendLongPromptAndStop(prompt: string): Promise<boolean> {
        await chat.inputBar.fill(prompt);
        await chat.inputBar.clickSend();

        // The session id lands in the URL as soon as the turn is submitted;
        // capture it for cleanup regardless of whether the stop succeeds.
        await page
          .waitForFunction(() => window.location.href.includes("chatId="), null, {
            timeout: 20_000,
          })
          .catch(() => {});
        const id = currentChatId();
        if (id) createdChatIds.add(id);

        try {
          await stopIcon.waitFor({ state: "visible", timeout: 30_000 });
        } catch {
          return false;
        }

        // Wait until the answer text actually begins streaming before stopping.
        try {
          await expect
            .poll(
              async () => ((await streamingAnswer.textContent()) ?? "").trim().length,
              { timeout: 90_000, intervals: [400] }
            )
            .toBeGreaterThan(0);
        } catch {
          return false;
        }

        // Only a genuine interruption counts: the stream must still be running.
        if (!(await stopIcon.isVisible())) {
          return false;
        }

        // Interrupt now — well before a 200+ line count could finish.
        await chat.inputBar.sendButton.click();

        // A genuine stop flips the chat state back to input near-instantly, so
        // the stop affordance disappears.
        await expect(stopIcon).toBeHidden({ timeout: 20_000 });
        return true;
      }

      let stopped = await sendLongPromptAndStop(
        `Count from 1 to 200 slowly, one number per line, and after each ` +
          `number add a short descriptive note (marker ${marker}).`
      );
      if (!stopped) {
        // Response finished before we could interrupt; retry once in a fresh
        // chat with a longer prompt.
        await chat.goto();
        stopped = await sendLongPromptAndStop(
          `Count from 1 to 500 slowly, one number on its own line, adding a ` +
            `full descriptive sentence after every number (marker ${marker}).`
        );
      }
      expect(stopped, "expected to interrupt a streaming response").toBeTruthy();

      // --- Composer is back to a sendable state, with no error toast. ---
      await expect(chat.inputBar.textbox).toBeEditable();
      await expect(
        page
          .getByTestId("toast-container")
          .getByText(/error|failed|went wrong/i)
      ).toHaveCount(0);

      // The stopped assistant message settles (partial content is fine).
      const stoppedMessage = latestAiMessage();
      await expect(stoppedMessage).toBeVisible({ timeout: 30_000 });

      // --- Regenerate a fresh answer from the assistant toolbar. ---
      await stoppedMessage.hover();
      const regenerate = stoppedMessage.getByTestId("AgentMessage/regenerate");
      await expect(regenerate).toBeVisible({ timeout: 15_000 });
      await regenerate.click();

      const dialog = page.locator('[role="dialog"]');
      await expect(dialog).toBeVisible({ timeout: 10_000 });

      // Re-select the currently active (default) model so protected model state
      // is untouched; re-selecting still triggers a fresh regeneration. Fall
      // back to any available model if the selected one can't be resolved.
      const selectedModel = dialog.locator('[data-interactive-state="selected"]');
      const modelToClick =
        (await selectedModel.count()) > 0
          ? selectedModel.first()
          : dialog.locator('[data-interactive-state="empty"]').first();
      await expect(modelToClick).toBeVisible({ timeout: 10_000 });
      await modelToClick.click();
      await expect(dialog).toBeHidden({ timeout: 10_000 });

      // Regeneration restarts streaming (stop affordance reappears)...
      await expect(stopIcon).toBeVisible({ timeout: 45_000 });
      // ...and this time we let it run to completion.
      await expect(stopIcon).toBeHidden({ timeout: 240_000 });

      // A fresh, completed answer with non-empty content and a finished stream.
      const regenerated = latestAiMessage();
      await expect(regenerated).toBeVisible({ timeout: 240_000 });
      await expect(
        regenerated.getByTestId("AgentMessage/copy-button")
      ).toBeVisible({ timeout: 240_000 });
      await expect(regenerated.locator(".select-text").first()).not.toBeEmpty();
    } finally {
      for (const id of createdChatIds) {
        await page.request
          .delete(`/api/chat/delete-chat-session/${id}?hard_delete=true`)
          .catch(() => {});
      }
    }
  });
});
