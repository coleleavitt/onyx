import { test } from "@playwright/test";
import { SpaceDetailPage } from "@tests/e2e/pages/SpaceDetailPage";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

test.describe("Spaces right rail controls", () => {
  test("keeps add-files and edit-details controls compact and usable", async ({
    page,
  }) => {
    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const spaceName = `E2E Rail Space ${stamp}`;
    const projectId = await apiClient.createProject(spaceName);

    try {
      await spaceDetail.goto({ spaceName, projectId });
      await spaceDetail.expectDetailSectionsVisible();
      await spaceDetail.openAddFilesPopoverAndExpectCompact();

      const description = `Right rail description ${stamp}`;
      await spaceDetail.updateDetailsDescription(description);
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });
});
