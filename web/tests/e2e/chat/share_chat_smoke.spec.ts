import { expect, test } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";
import {
  buildMockStream,
  mockChatEndpoint,
  resetTurnCounter,
} from "@tests/e2e/utils/chatMock";

test.describe("Share chat smoke", () => {
  test.beforeEach(async ({ page }) => {
    resetTurnCounter();
    await page.context().clearCookies();
    await loginAs(page, "admin");
  });

  test("user can create and remove a share link", async ({ page }) => {
    const chat = new ChatPage(page);
    await chat.goto();
    await mockChatEndpoint(page, buildMockStream("Share smoke response"));

    await chat.inputBar.fill("Hello for share smoke");
    await chat.inputBar.clickSend();
    await expect(chat.aiMessages).toHaveCount(1, { timeout: 30000 });
    await expect(page.locator('[aria-label="share-chat-button"]')).toBeVisible({
      timeout: 10000,
    });

    await page.locator('[aria-label="share-chat-button"]').click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('[aria-label="share-modal-submit"]')).toBeDisabled();

    let publicPatchBody: Record<string, unknown> | null = null;
    await page.route("**/api/chat/chat-session/*", async (route) => {
      if (route.request().method() === "PATCH") {
        publicPatchBody = JSON.parse(route.request().postData() ?? "{}");
      }
      await route.continue();
    });

    await dialog.locator('[aria-label="share-modal-option-public"]').click();
    await dialog.locator('[aria-label="share-modal-submit"]').click();
    await page.waitForResponse(
      (response) =>
        response.url().includes("/api/chat/chat-session/") &&
        response.request().method() === "PATCH",
      { timeout: 10000 }
    );

    expect(publicPatchBody).toEqual({ sharing_status: "public" });
    await expect(dialog.locator('[aria-label="share-modal-link-input"]')).toHaveValue(
      /\/app\/shared\//,
      { timeout: 5000 }
    );
    await expect(dialog.locator('[aria-label="share-modal-submit"]')).toHaveText(
      "Copy Link"
    );

    await page.unrouteAll({ behavior: "ignoreErrors" });
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden({ timeout: 5000 });

    let privatePatchBody: Record<string, unknown> | null = null;
    await page.route("**/api/chat/chat-session/*", async (route) => {
      if (route.request().method() === "PATCH") {
        privatePatchBody = JSON.parse(route.request().postData() ?? "{}");
      }
      await route.continue();
    });

    await page.locator('[aria-label="share-chat-button"]').click();
    await expect(dialog).toBeVisible();
    await dialog.locator('[aria-label="share-modal-option-private"]').click();
    await expect(dialog.locator('[aria-label="share-modal-submit"]')).toHaveText(
      "Make Private"
    );
    await dialog.locator('[aria-label="share-modal-submit"]').click();
    await page.waitForResponse(
      (response) =>
        response.url().includes("/api/chat/chat-session/") &&
        response.request().method() === "PATCH",
      { timeout: 10000 }
    );

    expect(privatePatchBody).toEqual({ sharing_status: "private" });
    await expect(dialog).toBeHidden({ timeout: 5000 });
    await page.unrouteAll({ behavior: "ignoreErrors" });
  });
});
