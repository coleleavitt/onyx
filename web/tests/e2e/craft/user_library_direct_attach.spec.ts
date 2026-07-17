import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";

async function craftEnabled(
  page: import("@playwright/test").Page
): Promise<boolean> {
  const response = await page.request.get("/api/settings");
  if (!response.ok()) return false;
  const settings = await response.json();
  return (
    settings?.onyx_craft_enabled === true ||
    settings?.settings?.onyx_craft_enabled === true
  );
}

/**
 * Seed the `build_user_persona` cookie so the Craft onboarding modal doesn't
 * intercept the composer on first navigation (same approach the scheduled-tasks
 * POM uses). Shape matches `BuildUserPersona`.
 */
async function skipCraftOnboarding(
  page: import("@playwright/test").Page
): Promise<void> {
  await page.goto("/");
  const domain = new URL(page.url()).hostname || "localhost";
  const expires = Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 365;
  await page.context().addCookies([
    {
      name: "build_user_persona",
      value: encodeURIComponent(
        JSON.stringify({ workArea: "engineering", level: "ic" })
      ),
      domain,
      path: "/",
      expires,
    },
    // Skips the intro/demo carousel that otherwise overlays the composer.
    { name: "craft_onboarding_seen", value: "1", domain, path: "/", expires },
  ]);
}

test.describe("Craft user library direct attachment", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "admin");
    test.skip(!(await craftEnabled(page)), "Craft is disabled");
  });

  test("attaches a named Library file without opening management for that row", async ({
    page,
  }) => {
    const suffix = Date.now().toString(36);
    const fileName = `library-direct-${suffix}.txt`;
    const documentId = `CRAFT_FILE__00000000-0000-0000-0000-000000000001__${suffix}`;
    await page.route("**/api/build/user-library/tree", async (route) => {
      await route.fulfill({
        json: [
          {
            id: documentId,
            name: fileName,
            path: `user_library/${fileName}`,
            is_directory: false,
            file_size: 12,
            mime_type: "text/plain",
            sync_enabled: true,
            created_at: "2026-07-10T00:00:00Z",
          },
        ],
      });
    });
    await page.route(
      "**/api/build/user-library/files/*/attach",
      async (route) => {
        await route.fulfill({
          json: {
            filename: fileName,
            path: `attachments/${fileName}`,
            size_bytes: 12,
          },
        });
      }
    );
    await page.route("**/api/build/sessions/*/files**", async (route) => {
      await route.fulfill({ json: { entries: [] } });
    });

    await skipCraftOnboarding(page);
    await page.goto("/craft/v1");
    // Opening the + menu; the Library flyout expands on hover, and file rows
    // attach directly instead of opening the management modal.
    await page.getByRole("button", { name: "Open add menu" }).click();
    await page.getByRole("button", { name: "Library", exact: true }).hover();
    await page.getByRole("button", { name: fileName }).first().click();

    // The attached (or queued) file appears as a composer chip.
    await expect(
      page.getByText(fileName, { exact: true }).first()
    ).toBeVisible();
    // The named row attaches directly — it must NOT open the Your Files modal.
    await expect(page.getByRole("dialog", { name: /your files/i })).toHaveCount(
      0
    );
  });
});
