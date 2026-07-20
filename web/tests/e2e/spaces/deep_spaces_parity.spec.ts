import { expect, test } from "@playwright/test";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

test.describe("Deep Spaces parity", () => {
  test("space detail exposes Threads/Customize, functional links, skills, scheduled tasks, and sharing invite UI", async ({
    page,
  }) => {
    const apiClient = new OnyxApiClient(page.request);
    const stamp = Date.now();
    const spaceName = `E2E Deep Space ${stamp}`;
    const projectId = await apiClient.createProject(spaceName);

    try {
      await page.goto(`/app/spaces/${slugify(spaceName)}-${projectId}`);
      await page.waitForLoadState("networkidle");

      // Space routes should not inherit the user's chat wallpaper.
      const backgroundUrls = await page.evaluate(() =>
        Array.from(document.querySelectorAll("[data-main-container] *")).filter(
          (element) => getComputedStyle(element).backgroundImage.includes("url(")
        ).length
      );
      expect(backgroundUrls).toBe(0);

      const threadsTab = page.getByRole("tab", { name: "Threads" });
      const customizeTab = page.getByRole("tab", { name: "Customize" });
      await expect(threadsTab).toBeVisible();
      await expect(customizeTab).toBeVisible();

      await customizeTab.click();
      await expect(customizeTab).toHaveAttribute("data-state", "active");
      await expect(page.getByText("Links", { exact: true }).first()).toBeVisible();
      await expect(page.getByText("Skills", { exact: true }).first()).toBeVisible();
      await expect(
        page.getByText("Scheduled Tasks", { exact: true }).first()
      ).toBeVisible();

      // Functional Links flow: add, persist through reload, then remove.
      const linkUrl = `example-${stamp}.com`;
      await page.getByRole("button", { name: "Add link" }).first().click();
      await page.getByPlaceholder("Paste a website URL").first().fill(linkUrl);
      await page.getByRole("button", { name: /^Add$/ }).first().click();
      await expect(page.getByText(`https://${linkUrl}`).first()).toBeVisible({
        timeout: 10_000,
      });
      await expect(page.getByText(/Added by/i).first()).toBeVisible();

      await page.reload();
      await page.waitForLoadState("networkidle");
      await expect(page.getByText(`https://${linkUrl}`).first()).toBeVisible({
        timeout: 10_000,
      });

      const linkActions = page
        .getByRole("button", { name: new RegExp(`Link actions for https://${linkUrl}`) })
        .first();
      await linkActions.click();
      await page.getByRole("button", { name: "Remove link" }).first().click();
      await expect(page.getByText(`https://${linkUrl}`)).toHaveCount(0);

      // Add controls are real controls, not disabled coming-soon placeholders.
      await expect(page.getByRole("button", { name: "Add skills" }).first()).toBeEnabled();
      await expect(
        page.getByRole("button", { name: "Create scheduled task" }).first()
      ).toBeEnabled();
      await expect(page.getByText("Link support is coming soon")).toHaveCount(0);

      // Sharing surface: access model + invite-by-email affordance + pending request section container.
      await page.getByRole("button", { name: "Share" }).first().click();
      const dialog = page.getByRole("dialog", { name: /Share space/i });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByText("Invite by email")).toBeVisible();
      await expect(dialog.getByPlaceholder("teammate@example.com")).toBeVisible();
      await expect(
        dialog.getByText("People with access", { exact: true })
      ).toBeVisible();
      await expect(
        dialog.getByText("General access", { exact: true })
      ).toBeVisible();
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });
});
