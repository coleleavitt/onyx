import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";

const USER_SETTINGS_PAGES = [
  { path: "/app/settings/general", title: "Profile" },
  { path: "/app/settings/chat-preferences", title: "Chats" },
  { path: "/app/settings/accounts-access", title: "Accounts" },
];

const ADMIN_SETTINGS_PAGES = [
  { path: "/admin/configuration/language-models", title: "Language Models" },
  { path: "/admin/security", title: "Security & Hardening" },
  { path: "/admin/users", title: "Users" },
];

test.describe("Settings navigation smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
    await loginAs(page, "admin");
  });

  for (const pageInfo of USER_SETTINGS_PAGES) {
    test(`user settings page renders: ${pageInfo.title}`, async ({ page }) => {
      await page.goto(pageInfo.path);
      await page.waitForLoadState("networkidle");

      await expect(page).toHaveURL(new RegExp(pageInfo.path.replaceAll("/", "\\/")));
      await expect(
        page
          .locator(".opal-content-md-header")
          .filter({ hasText: pageInfo.title })
          .first()
      ).toBeVisible();
      await expect(page.locator("body")).not.toContainText("Application error");
      await expect(page.locator("body")).not.toContainText("Internal Server Error");
    });
  }

  for (const pageInfo of ADMIN_SETTINGS_PAGES) {
    test(`admin settings page renders: ${pageInfo.title}`, async ({ page }) => {
      await page.goto(pageInfo.path);
      await page.waitForLoadState("networkidle");

      await expect(page).toHaveURL(new RegExp(pageInfo.path.replaceAll("/", "\\/")));
      await expect(page.getByText(pageInfo.title).first()).toBeVisible();
      await expect(page.locator("body")).not.toContainText("Application error");
      await expect(page.locator("body")).not.toContainText("Internal Server Error");
    });
  }
});
