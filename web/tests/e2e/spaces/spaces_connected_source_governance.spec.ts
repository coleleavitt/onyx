import { expect, test } from "@playwright/test";
import { SpaceDetailPage } from "@tests/e2e/pages/SpaceDetailPage";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

/**
 * Real-user smoke for governed Space connected sources.
 *
 * This test intentionally accepts an honest empty-state branch because local CI
 * environments may not have indexed SharePoint hierarchy rows. When governed
 * SharePoint rows exist, it drives the full user path: right rail -> connected
 * source modal -> tenant/department row -> hierarchy browser -> save -> reload.
 */
test.describe("Spaces connected-source governance", () => {
  test("lets an editor use governed SharePoint departments while keeping uploads and sharing separate", async ({
    page,
  }) => {
    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const spaceName = `E2E Governed Sources ${stamp}`;
    const projectId = await apiClient.createProject(
      spaceName,
      "Governed SharePoint source selection smoke",
    );

    try {
      await spaceDetail.goto({ spaceName, projectId });
      await spaceDetail.expectDetailSectionsVisible();

      await page.getByRole("button", { name: "Add connected source" }).first().click();
      const dialog = page.getByRole("dialog", { name: /Add knowledge to space/i });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole("tab", { name: "Connected sources" })).toBeVisible();
      await expect(dialog.getByRole("tab", { name: "Uploaded files" })).toBeVisible();

      await dialog.getByRole("tab", { name: "Uploaded files" }).click();
      await expect(dialog.getByRole("button", { name: "Upload local files" })).toBeVisible();
      await expect(dialog.getByRole("button", { name: "Upload local folder" })).toBeVisible();
      await dialog.getByRole("tab", { name: "Connected sources" }).click();

      await expect(dialog.getByText("TestSprite Tenant")).toBeVisible({
        timeout: 15_000,
      });
      const seededDepartment = dialog.getByText("TestSprite Advisor Services").first();
      await expect(seededDepartment).toBeVisible();
      await seededDepartment.click();
      await expect(dialog.locator(".content-column-layout")).toBeVisible();
      // Browsing must NOT auto-attach: the footer still shows no selections.
      await expect(
        dialog.getByText("No connected-source selections"),
      ).toBeVisible();
      // Attaching is an explicit checkbox action.
      await dialog
        .getByRole("checkbox", { name: "Attach TestSprite Advisor Services" })
        .click();
      await expect(
        dialog.getByText("1 connected-source selection", { exact: true }),
      ).toBeVisible();
      await dialog.getByRole("button", { name: "Save", exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await spaceDetail.reload();
      await expect(page.getByText("Connected sources", { exact: true }).first()).toBeVisible();
      await expect(page.getByText("TestSprite Advisor Services").first()).toBeVisible();
      console.log("governed source smoke: selected TestSprite Advisor Services");

      const shareDialog = await spaceDetail.openShareDialog();
      await expect(shareDialog.getByText("Invite by email")).toBeVisible();
      await expect(shareDialog.getByPlaceholder("teammate@example.com")).toBeVisible();
      await page.keyboard.press("Escape");
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });
});
