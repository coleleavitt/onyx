import { expect, test } from "@playwright/test";
import { SpaceDetailPage } from "@tests/e2e/pages/SpaceDetailPage";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

// GUI coverage for the space controls whose APIs are proven server-side but
// whose rendered affordances were previously unverified: per-thread privacy,
// paste-text knowledge, and admin featuring.
test.describe("Space thread privacy and knowledge controls", () => {
  test("toggles a thread between private and shared from the thread menu", async ({
    page,
  }) => {
    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const spaceName = `E2E Privacy Space ${stamp}`;
    const threadName = `Privacy thread ${stamp}`;
    const projectId = await apiClient.createProject(spaceName);

    try {
      const created = await page.request.post("/api/chat/create-chat-session", {
        data: { persona_id: 0, description: threadName, project_id: projectId },
      });
      expect(created.ok()).toBeTruthy();

      await spaceDetail.goto({ spaceName, projectId });

      const threadRow = page.getByText(threadName, { exact: true }).first();
      await expect(threadRow).toBeVisible();
      await threadRow.hover();

      const threadActions = page.getByRole("button", {
        name: `Thread actions for ${threadName}`,
      });
      await threadActions.click();

      // A new thread defaults to private, so the menu offers sharing.
      const shareToSpace = page.getByText("Share to space", { exact: true });
      await expect(shareToSpace).toBeVisible();
      await page.screenshot({
        path: "artifacts/e2e-f1-thread-menu-private.png",
      });
      await shareToSpace.click();

      // Sharing is persisted, not just local state.
      const visibilityOf = async (): Promise<string | undefined> => {
        const details = await page.request.get(
          `/api/user/projects/${projectId}/details`,
        );
        const payload = await details.json();
        const thread = payload.project.chat_sessions.find(
          (session: { name: string }) => session.name === threadName,
        );
        return thread?.project_visibility;
      };
      await expect.poll(visibilityOf).toBe("shared");

      // Reload so the menu re-renders from server state, then confirm the
      // control reflects the flipped state and can flip it back.
      await spaceDetail.goto({ spaceName, projectId });
      await page.getByText(threadName, { exact: true }).first().hover();
      await threadActions.click();
      const makePrivate = page.getByText("Make private", { exact: true });
      await expect(makePrivate).toBeVisible();
      await page.screenshot({
        path: "artifacts/e2e-f1-thread-menu-shared.png",
      });
      await makePrivate.click();
      await expect.poll(visibilityOf).toBe("private");
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });

  test("saves pasted text as a space file", async ({ page }) => {
    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const spaceName = `E2E Paste Space ${stamp}`;
    const fileName = `Pasted note ${stamp}`;
    const projectId = await apiClient.createProject(spaceName);

    try {
      await spaceDetail.goto({ spaceName, projectId });

      await page.getByRole("button", { name: "Add plaintext" }).click();
      const dialog = page.getByRole("dialog", { name: /Add plaintext/i });
      await expect(dialog).toBeVisible();

      await dialog.locator('input[name="name"]').fill(fileName);
      await dialog
        .locator('textarea[name="content"]')
        .fill("Stewart Willis 2025 production 40216752.33");
      await page.screenshot({ path: "artifacts/e2e-f4-paste-modal.png" });
      await dialog.getByRole("button", { name: "Save" }).click();

      await expect(dialog).toHaveCount(0);

      // The pasted text became a real file rendered in the space.
      await expect(
        page.getByText(`${fileName}.txt`, { exact: true }).first(),
      ).toBeVisible({ timeout: 15_000 });
      await page.screenshot({ path: "artifacts/e2e-f4-file-in-space.png" });
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });

  test("lets an admin feature a space from the space page", async ({
    page,
  }) => {
    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const spaceName = `E2E Feature Space ${stamp}`;
    const projectId = await apiClient.createProject(spaceName);

    try {
      await spaceDetail.goto({ spaceName, projectId });

      await page.getByRole("button", { name: "Feature space" }).click();
      const dialog = page.getByRole("dialog", { name: /Feature this space/i });
      await expect(dialog).toBeVisible();

      await dialog.locator('input[type="checkbox"]').check();
      await page.screenshot({ path: "artifacts/e2e-f2-feature-modal.png" });
      await dialog.getByRole("button", { name: "Save" }).click();

      await expect(dialog).toHaveCount(0);
      await expect(page.getByText("Featuring updated.")).toBeVisible();
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });
});
