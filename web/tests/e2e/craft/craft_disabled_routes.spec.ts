import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";

const CRAFT_DISABLED = process.env.ONYX_CRAFT_DISABLED_E2E === "true";

test.describe("Craft-disabled route guards", () => {
  test.skip(
    !CRAFT_DISABLED,
    "Requires a per-user Craft-disabled browser capability."
  );

  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
    await loginAs(page, "admin");
  });

  for (const path of ["/craft", "/app/artifacts", "/app/customize/workflows"]) {
    test(`redirects ${path} before mounting Craft content`, async ({
      page,
    }) => {
      const buildRequests: string[] = [];
      page.on("request", (request) => {
        if (request.url().includes("/api/build/")) {
          buildRequests.push(request.url());
        }
      });

      await page.goto(path);
      await expect(page).toHaveURL(/\/app(?:\?.*)?$/);
      expect(buildRequests).toEqual([]);
    });
  }

  test("hides Craft-only sidebar navigation and skips background fetches", async ({
    page,
  }) => {
    const buildRequests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/build/")) {
        buildRequests.push(request.url());
      }
    });

    await page.goto("/app");
    await expect(page.getByText("Artifacts", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Workflows", { exact: true })).toHaveCount(0);
    expect(buildRequests).toEqual([]);
  });
});
