import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

test.describe("Spaces lifecycle", () => {
  test("gates private Space details until access is approved", async ({
    browser,
    page,
  }) => {
    const suffix = Date.now().toString(36);
    const spaceName = `E2E Private Space ${suffix}`;
    const description = `Private collaboration context ${suffix}`;
    let projectId: number | null = null;

    await loginAs(page, "admin");
    const ownerClient = new OnyxApiClient(page.request);

    try {
      projectId = await ownerClient.createProject(spaceName, description);
      await page.goto(`/app?projectId=${projectId}`);
      await expect(
        page.getByText(spaceName, { exact: true }).first()
      ).toBeVisible();
      await expect(
        page.getByText(description, { exact: true }).first()
      ).toBeVisible();
      await expect(page.getByRole("button", { name: /share/i })).toBeVisible();

      const requesterContext = await browser.newContext();
      const requesterPage = await requesterContext.newPage();
      await loginAs(requesterPage, "admin2");

      try {
        await requesterPage.goto(`/app?projectId=${projectId}`);
        // Generic gate: no private metadata, no chat input, before approval.
        await expect(
          requesterPage.getByText("Request space access")
        ).toBeVisible();
        await expect(requesterPage.getByText(spaceName)).toHaveCount(0);
        await expect(requesterPage.getByText(description)).toHaveCount(0);
        await expect(
          requesterPage.getByRole("textbox", { name: /message input/i })
        ).toHaveCount(0);

        await requesterPage
          .getByRole("button", { name: "Request access" })
          .click();
        await expect(
          requesterPage.getByText("Access request pending")
        ).toBeVisible();
        await requesterPage
          .getByRole("button", { name: "Cancel request" })
          .click();
        await expect(
          requesterPage.getByText("Request space access")
        ).toBeVisible();
        await requesterPage
          .getByRole("button", { name: "Request access" })
          .click();
        await expect(
          requesterPage.getByText("Access request pending")
        ).toBeVisible();

        // Owner approves from the sharing dialog.
        await page.getByRole("button", { name: /share/i }).click();
        await expect(page.getByText(/access requests/i)).toBeVisible();
        await page
          .getByRole("button", { name: /approve access/i })
          .first()
          .click();
        await expect(page.getByText(/access requests/i)).toHaveCount(0);

        // Requester transitions into the authorized space with viewer limits.
        await requesterPage.getByRole("button", { name: "Refresh" }).click();
        await expect(
          requesterPage.getByText(spaceName, { exact: true }).first()
        ).toBeVisible();
        await expect(
          requesterPage.getByRole("button", { name: /^share$/i })
        ).toHaveCount(0);
        await expect(
          requesterPage.getByRole("button", { name: /edit details/i })
        ).toHaveCount(0);
      } finally {
        await requesterContext.close();
      }
    } finally {
      if (projectId !== null) {
        await ownerClient.deleteProject(projectId);
      }
    }
  });
});
