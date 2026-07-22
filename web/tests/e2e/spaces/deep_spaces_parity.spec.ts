import { expect, test } from "@playwright/test";
import { SpaceDetailPage } from "@tests/e2e/pages/SpaceDetailPage";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

test.describe("Deep Spaces parity", () => {
  test("space detail keeps details in the right panel with functional links, skills, scheduled tasks, and sharing invite UI", async ({
    page,
  }) => {
    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const spaceName = `E2E Deep Space ${stamp}`;
    const projectId = await apiClient.createProject(spaceName);

    await spaceDetail.setChatBackground("mountains");

    try {
      await spaceDetail.goto({ spaceName, projectId });
      await spaceDetail.expectWallpaperVisible();
      await spaceDetail.expectMainColumnWithoutDuplicateTabs();
      await spaceDetail.collapseAndExpandDetailsPanel();
      await spaceDetail.expectDetailSectionsVisible();

      // Functional Links flow: add, persist through reload, then remove.
      const linkUrl = `example-${stamp}.com`;
      const normalizedLinkUrl = `https://${linkUrl}`;
      await spaceDetail.addLink(linkUrl);
      await spaceDetail.expectLinkVisible(normalizedLinkUrl);
      await spaceDetail.expectAddedByVisible();

      await spaceDetail.reload();
      await spaceDetail.expectLinkVisible(normalizedLinkUrl);

      await spaceDetail.removeLink(normalizedLinkUrl);
      await spaceDetail.expectLinkGone(normalizedLinkUrl);
      await spaceDetail.expectAddControlsEnabled();

      // Sharing surface: access model + invite-by-email affordance + pending request section container.
      const dialog = await spaceDetail.openShareDialog();
      await expect(dialog.getByText("Invite by email")).toBeVisible();
      await expect(
        dialog.getByPlaceholder("teammate@example.com"),
      ).toBeVisible();
      await expect(
        dialog.getByText("People with access", { exact: true }),
      ).toBeVisible();
      await expect(
        dialog.getByText("General access", { exact: true }),
      ).toBeVisible();
    } finally {
      await spaceDetail.setChatBackground(null);
      await apiClient.deleteProject(projectId);
    }
  });
});
