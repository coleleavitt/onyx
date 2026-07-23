import { expect, test, type APIRequestContext } from "@playwright/test";
import { SpaceDetailPage } from "@tests/e2e/pages/SpaceDetailPage";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

async function connectedTitles(
  pageRequest: APIRequestContext,
  projectId: number,
): Promise<string[]> {
  const response = await pageRequest.get(
    `/api/user/projects/${projectId}/connected-knowledge`,
  );
  expect(response.status()).toBe(200);
  const body = await response.json();
  return body.hierarchy_nodes.map((node: { title: string }) => node.title).sort();
}

test.describe("Space presets and deep SharePoint folder browse", () => {
  test("creates a space with the Magellan HR preset from the create-space modal", async ({
    page,
  }) => {
    const apiClient = new OnyxApiClient(page.request);
    const stamp = Date.now();
    const name = `Preset Space ${stamp}`;
    let projectId: number | null = null;

    try {
      await page.goto("/app/spaces");
      await page.getByRole("button", { name: "New space" }).click();
      const dialog = page.getByRole("dialog", { name: /Create a new Space/i });
      await expect(dialog).toBeVisible();
      await dialog.getByPlaceholder("Name this Space").fill(name);
      await dialog.getByRole("combobox").click();
      await page.getByRole("option", { name: /Magellan HR starter/ }).click();
      await expect(
        dialog.getByText(
          "Company Wide Files and JF from the Magellan HR intranet — Includes: Company Wide Files, JF",
        ),
      ).toBeVisible();
      await dialog.getByRole("button", { name: "Create Space" }).click();
      await page.waitForURL(/\/app\/spaces\/.*-\d+$/);
      const match = page.url().match(/-(\d+)$/);
      expect(match).toBeTruthy();
      projectId = Number(match![1]);
      await expect(page.getByText("Connected sources", { exact: true }).first()).toBeVisible();
      await expect(page.getByText("Company Wide Files").first()).toBeVisible();
      await expect(page.getByText("JF").first()).toBeVisible();
      await expect.poll(() => connectedTitles(page.request, projectId!)).toEqual([
        "Company Wide Files",
        "JF",
      ]);
    } finally {
      if (projectId !== null) await apiClient.deleteProject(projectId);
    }
  });

  test("browses department children and attaches exactly one child folder, not the whole site", async ({
    page,
  }) => {
    test.setTimeout(180_000);
    const apiClient = new OnyxApiClient(page.request);
    const spaceDetail = new SpaceDetailPage(page);
    const stamp = Date.now();
    const name = `Deep Browse Space ${stamp}`;
    const projectId = await apiClient.createProject(
      name,
      "Deep folder browse regression",
    );

    try {
      await spaceDetail.goto({ spaceName: name, projectId });
      await page.getByRole("button", { name: "Add connected source" }).first().click();
      const dialog = page.getByRole("dialog", { name: /Add knowledge to space/i });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByText("Magellan", { exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await dialog.getByText("Human Resources Intranet").first().click();
      await expect(dialog.getByText("No connected-source selections")).toBeVisible();

      await dialog.getByRole("button", { name: "Open Shared Documents" }).click();
      await dialog.getByRole("button", { name: "Open Company Wide Files" }).click();
      await dialog.getByLabel("Toggle Medical").click();
      await expect(
        dialog.getByText("1 connected-source selection", { exact: true }),
      ).toBeVisible();
      await dialog.getByRole("button", { name: "Save", exact: true }).click();
      await expect(dialog).toHaveCount(0);

      await expect.poll(() => connectedTitles(page.request, projectId)).toEqual([
        "Medical",
      ]);
      await spaceDetail.reload();
      await expect(page.getByText("Medical", { exact: true }).first()).toBeVisible();
    } finally {
      await apiClient.deleteProject(projectId);
    }
  });
});
