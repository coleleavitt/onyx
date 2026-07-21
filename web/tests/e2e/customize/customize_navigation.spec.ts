import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";

test.describe("Customize navigation", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "admin");
    await page.addInitScript(() => {
      window.localStorage.setItem("sidebarIsToggled", "false");
      document.cookie = "sidebarIsToggled=false; path=/";
    });
  });

  test("keeps route tabs visible and sidebar group expanded for customize routes", async ({
    page,
  }) => {
    await page.goto("/app/customize/skills");

    const customizeSidebar = page.getByTestId("AppSidebar/customize");
    await expect(
      customizeSidebar.getByText("Customize", { exact: true }),
    ).toBeVisible();
    await expect(
      customizeSidebar.getByText("Skills", { exact: true }),
    ).toBeVisible();
    await expect(
      customizeSidebar.getByText("Workflows", { exact: true }),
    ).toBeVisible();
    await expect(
      customizeSidebar.getByText("Memory", { exact: true }),
    ).toBeVisible();

    await expect(
      page.getByRole("tab", { name: "Skills", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "Workflows", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "Memory", exact: true }),
    ).toBeVisible();

    await page.getByRole("tab", { name: "Workflows", exact: true }).click();
    await expect(page).toHaveURL(/\/app\/customize\/workflows$/);
    await expect(
      page.getByText("Workflows", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      customizeSidebar.getByText("Workflows", { exact: true }),
    ).toBeVisible();

    await page.getByRole("tab", { name: "Memory", exact: true }).click();
    await expect(page).toHaveURL(/\/app\/customize\/memory$/);
    await expect(
      page.getByText("Memory", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      customizeSidebar.getByText("Memory", { exact: true }),
    ).toBeVisible();
  });
});
