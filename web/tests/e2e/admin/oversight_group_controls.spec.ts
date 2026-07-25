import { expect, test } from "@playwright/test";
import { apiLogin } from "@tests/e2e/utils/auth";

/**
 * The whole oversight setup has to be reachable from the admin UI, otherwise
 * running it by hand means calling the API directly. This drives the two
 * controls that turn it on: granting the capability to a group, and marking a
 * member as curator.
 */

const PASSWORD = "TestPassword123!";
const ADMIN = "admin_user@example.com";
const GROUP = "Compliance — Jeff Dow";
const CURATOR_EMAIL = "jeff.dow@fiwealth.com";

test.use({ storageState: { cookies: [], origins: [] } });

async function groupByName(
  page: import("@playwright/test").Page,
  name: string,
) {
  const response = await page.request.get("/api/manage/admin/user-group");
  expect(response.ok()).toBeTruthy();
  const groups = await response.json();
  const match = groups.find((group: { name: string }) => group.name === name);
  expect(
    match,
    `${name} must exist (seed-compliance-oversight.py)`,
  ).toBeTruthy();
  return match;
}

async function permissionsOf(
  page: import("@playwright/test").Page,
  groupId: number,
): Promise<string[]> {
  const response = await page.request.get(
    `/api/manage/admin/user-group/${groupId}/permissions`,
  );
  expect(response.ok()).toBeTruthy();
  return await response.json();
}

test("an admin grants and revokes oversight from the group page", async ({
  page,
}) => {
  await apiLogin(page, ADMIN, PASSWORD);
  const group = await groupByName(page, GROUP);

  // Start from a known state so the assertion is about the UI, not the seed.
  await page.request.put(
    `/api/manage/admin/user-group/${group.id}/permissions`,
    { data: { permission: "read:query_history", enabled: false } },
  );

  await page.goto(`/admin/groups/${group.id}`);
  await page.waitForLoadState("networkidle");

  const grant = page.getByRole("switch", { name: "Grant oversight" });
  await expect(grant).toBeVisible();
  await expect(grant).toHaveAttribute("aria-checked", "false");

  await grant.click();
  await page.screenshot({ path: "artifacts/e2e-oversight-grant.png" });
  await page.getByRole("button", { name: "Save Changes" }).first().click();

  await expect
    .poll(async () =>
      (await permissionsOf(page, group.id)).includes("read:query_history"),
    )
    .toBe(true);

  // And it comes back off, so the control is a real toggle rather than a latch.
  await page.reload();
  await page.waitForLoadState("networkidle");
  const grantAfter = page.getByRole("switch", { name: "Grant oversight" });
  await expect(grantAfter).toHaveAttribute("aria-checked", "true");
  await grantAfter.click();
  await page.getByRole("button", { name: "Save Changes" }).first().click();

  await expect
    .poll(async () =>
      (await permissionsOf(page, group.id)).includes("read:query_history"),
    )
    .toBe(false);

  // Leave the seeded fixture as it was: the capability lives on the managers
  // group, never on a reporting-line group, which also holds the analysts.
  await page.request.put(
    `/api/manage/admin/user-group/${group.id}/permissions`,
    { data: { permission: "read:query_history", enabled: false } },
  );
});

test("an admin promotes and demotes a curator from the members table", async ({
  page,
}) => {
  await apiLogin(page, ADMIN, PASSWORD);
  const group = await groupByName(page, GROUP);
  const curator = group.users.find(
    (user: { email: string }) => user.email === CURATOR_EMAIL,
  );
  expect(curator).toBeTruthy();

  await page.goto(`/admin/groups/${group.id}`);
  await page.waitForLoadState("networkidle");

  // The seed already made this member a curator, so the row reflects it.
  const row = page.getByRole("row", { name: new RegExp(CURATOR_EMAIL) });
  const toggle = row.getByRole("switch", { name: "Curator" });
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-checked", "true");
  await page.screenshot({ path: "artifacts/e2e-oversight-curator.png" });

  // Demote, save, and confirm it reached the server.
  await toggle.click();
  await page.getByRole("button", { name: "Save Changes" }).first().click();
  await expect
    .poll(async () => {
      const refreshed = await groupByName(page, GROUP);
      return refreshed.curator_ids.includes(curator.id);
    })
    .toBe(false);

  // Restore, so the seeded reporting line still works afterwards.
  await page.reload();
  await page.waitForLoadState("networkidle");
  await page
    .getByRole("row", { name: new RegExp(CURATOR_EMAIL) })
    .getByRole("switch", { name: "Curator" })
    .click();
  await page.getByRole("button", { name: "Save Changes" }).first().click();
  await expect
    .poll(async () => {
      const refreshed = await groupByName(page, GROUP);
      return refreshed.curator_ids.includes(curator.id);
    })
    .toBe(true);
});
