import { expect, test } from "@playwright/test";
import { apiLogin } from "@tests/e2e/utils/auth";

/**
 * Oversight scoping through the real admin UI, using the Compliance reporting
 * line seeded by seed-compliance-oversight.py:
 *
 *   Christopher Shin (Director)
 *   |-- Jeff Dow ------- Andy Joshu, McKenna Nigl
 *   `-- Kamara Gibson -- Jaime Duarte
 *
 * Two managers sit in one department, so the interesting assertion is the
 * negative one: neither may read the other's analyst.
 */

const PASSWORD = "TestPassword123!";
const DOW = "jeff.dow@fiwealth.com";
const GIBSON = "kamara.gibson@fiwealth.com";
const JOSHU = "andy.joshu@fiwealth.com";
const NIGL = "mckenna.nigl@fiwealth.com";
const DUARTE = "jaime.duarte@fiwealth.com";

const QUERY_HISTORY = "/admin/performance/query-history";

// These users are not the seeded admin, so start from a clean session.
test.use({ storageState: { cookies: [], origins: [] } });

async function visibleEmails(page: import("@playwright/test").Page) {
  const response = await page.request.get(
    "/api/admin/chat-session-history?page_num=0&page_size=200"
  );
  if (!response.ok())
    return { status: response.status(), emails: [] as string[] };
  const body = await response.json();
  const emails = (body.items ?? [])
    .map((item: { user_email?: string }) => item.user_email ?? "")
    .filter((email: string) => email.endsWith("@fiwealth.com"));
  return { status: response.status(), emails: [...new Set<string>(emails)] };
}

test("a manager reaches query history and sees only their own reports", async ({
  page,
}) => {
  await apiLogin(page, DOW, PASSWORD);
  await page.goto(QUERY_HISTORY);
  await page.waitForLoadState("networkidle");

  // The page renders for a delegated overseer, not just a full admin.
  await expect(page.getByText("Query History").first()).toBeVisible();
  await page.screenshot({ path: "artifacts/e2e-oversight-dow.png" });

  const { status, emails } = await visibleEmails(page);
  expect(status).toBe(200);
  expect(emails).toContain(JOSHU);
  expect(emails).toContain(NIGL);
  // The sibling manager's analyst must never appear.
  expect(emails).not.toContain(DUARTE);
});

test("the sibling manager sees their own report and not the other team", async ({
  page,
}) => {
  await apiLogin(page, GIBSON, PASSWORD);
  await page.goto(QUERY_HISTORY);
  await page.waitForLoadState("networkidle");

  const { status, emails } = await visibleEmails(page);
  expect(status).toBe(200);
  expect(emails).toContain(DUARTE);
  expect(emails).not.toContain(JOSHU);
  expect(emails).not.toContain(NIGL);
});

test("an analyst has no oversight at all", async ({ page }) => {
  await apiLogin(page, JOSHU, PASSWORD);
  await page.goto("/app");
  await page.waitForLoadState("networkidle");

  // No capability -> the API refuses outright.
  const { status } = await visibleEmails(page);
  expect(status).toBe(403);

  // And the admin surface is not offered to them.
  await page.goto(QUERY_HISTORY);
  await page.waitForLoadState("networkidle");
  await expect(page.getByText(DUARTE)).toHaveCount(0);
  await expect(page.getByText(NIGL)).toHaveCount(0);
  await page.screenshot({ path: "artifacts/e2e-oversight-analyst.png" });
});

test("a manager can administer the group they curate", async ({ page }) => {
  await apiLogin(page, DOW, PASSWORD);

  // A curator may list groups, and only sees the ones they curate.
  const response = await page.request.get("/api/manage/admin/user-group");
  expect(response.ok()).toBeTruthy();
  const groups = await response.json();
  const names = groups.map((group: { name: string }) => group.name);
  expect(names).toContain("Compliance — Jeff Dow");
  expect(names).not.toContain("Compliance — Kamara Gibson");
});

test("an admin can exclude a tier from oversight in the group UI", async ({
  page,
}) => {
  await apiLogin(page, "admin_user@example.com", PASSWORD);

  const listed = await page.request.get("/api/manage/admin/user-group");
  const groups = await listed.json();
  const target = groups.find(
    (group: { name: string }) => group.name === "Compliance Managers"
  );
  expect(target, "seed-compliance-oversight.py must have run").toBeTruthy();

  await page.goto(`/admin/groups/${target.id}`);
  await page.waitForLoadState("networkidle");

  const toggle = page.getByRole("switch", {
    name: "Exclude members from oversight",
  });
  await expect(toggle).toBeVisible();
  await expect(toggle).toHaveAttribute("aria-checked", "false");

  await toggle.click();
  await page.screenshot({ path: "artifacts/e2e-oversight-exclusion-on.png" });
  await page.getByRole("button", { name: "Save Changes" }).first().click();

  // The flag reaches the server, not just local component state.
  await expect
    .poll(async () => {
      const after = await page.request.get("/api/manage/admin/user-group");
      const groupsAfter = await after.json();
      return groupsAfter.find((group: { id: number }) => group.id === target.id)
        ?.excluded_from_oversight;
    })
    .toBe(true);

  // Leave the seeded fixture as it was.
  const reset = await page.request.put(
    `/api/manage/admin/user-group/${target.id}/oversight-exclusion`,
    { data: { excluded_from_oversight: false } }
  );
  expect(reset.ok()).toBeTruthy();
});
