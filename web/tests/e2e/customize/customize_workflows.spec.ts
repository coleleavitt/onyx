import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";

test.describe("Customize Workflows", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "admin");
  });

  test("supports search, pinning, and scheduled template handoff without execution", async ({
    page,
  }) => {
    let pinnedIds: string[] = [];
    await page.route("**/api/build/workflow-catalog/pins**", async (route) => {
      const method = route.request().method();
      const url = new URL(route.request().url());
      const match = url.pathname.match(/\/pins\/([^/]+)$/);
      if (method === "GET") {
        await route.fulfill({ json: { workflow_ids: pinnedIds } });
        return;
      }
      if (method === "PUT" && match) {
        const id = decodeURIComponent(match[1] ?? "");
        pinnedIds = Array.from(new Set([...pinnedIds, id]));
        await route.fulfill({ json: { workflow_ids: pinnedIds } });
        return;
      }
      if (method === "DELETE" && match) {
        const id = decodeURIComponent(match[1] ?? "");
        pinnedIds = pinnedIds.filter((candidate) => candidate !== id);
        await route.fulfill({ json: { workflow_ids: pinnedIds } });
        return;
      }
      await route.fallback();
    });

    await page.goto("/app/customize/workflows");
    await expect(
      page.getByText(
        "Start guided work or schedule recurring, reviewable automations."
      )
    ).toBeVisible();

    await page.getByPlaceholder("Search workflows").fill("compliance");
    const complianceCard = page
      .locator("article")
      .filter({ hasText: /compliance/i })
      .first();
    await expect(complianceCard).toBeVisible();
    await complianceCard.getByRole("button", { name: /pin workflow/i }).click();

    await page.getByRole("tab", { name: "Pinned" }).click();
    await expect(
      page
        .locator("article")
        .filter({ hasText: /compliance/i })
        .first()
    ).toBeVisible();

    await page.getByRole("tab", { name: "Browse" }).click();
    await page.getByPlaceholder("Search workflows").fill("status");
    const scheduledCard = page
      .locator("article")
      .filter({ hasText: /status/i })
      .first();
    await expect(scheduledCard).toBeVisible();
    await scheduledCard.getByRole("link", { name: /schedule/i }).click();
    await expect(page).toHaveURL(/\/craft\/v1\/tasks\/new\?template=/);
    await expect(page.getByTestId("task-prompt-input")).toBeVisible();
    await expect(page.getByTestId("save-and-run-now")).toBeVisible();
  });
});
