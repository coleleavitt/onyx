import { expect, test } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";

test.describe("Broken model visibility", () => {
  test("GPT-5.6 family is hidden from the end-user model picker", async ({
    page,
  }) => {
    await page.context().clearCookies();
    await loginAs(page, "admin");

    await page.goto("/admin/configuration/language-models");
    await page.waitForLoadState("networkidle");
    await expect(page.getByText("Language Models").first()).toBeVisible();
    await expect(page.getByText("Default Model")).toBeVisible();
    await expect(page.locator("button").filter({ hasText: "GPT-5.5" })).toBeVisible();

    const chat = new ChatPage(page);
    await chat.goto();

    const modelButton = page.getByTestId("model-selector").locator("button").last();
    await expect(modelButton).toContainText("GPT-5.5");

    await modelButton.click();
    await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
    const dialog = page.locator('[role="dialog"]');

    await dialog.getByPlaceholder("Search models...").fill("GPT-5.6");
    await expect(dialog.getByText("No models found")).toBeVisible();
    await expect(dialog.locator('[data-interactive-state]')).toHaveCount(0);

    await dialog.getByPlaceholder("Search models...").fill("GPT-5.5");
    await expect(
      dialog.locator('[data-interactive-state]').filter({ hasText: "GPT-5.5" })
    ).toHaveCount(1);
  });
});
