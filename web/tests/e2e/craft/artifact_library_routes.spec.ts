import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";

function artifact(name: string, id: string, updatedAt: string) {
  return {
    id,
    name,
    type: "pdf",
    is_pinned: false,
    published_at: null,
    created_at: updatedAt,
    updated_at: updatedAt,
    owner: {
      id: "00000000-0000-0000-0000-000000000001",
      email: "owner@example.com",
    },
    is_owner: true,
    latest_version: {
      id: `${id}-version`,
      version_number: 1,
      name: `${name}.pdf`,
      path: `artifacts/${name}.pdf`,
      mime_type: "application/pdf",
      size_bytes: 128,
      created_at: updatedAt,
    },
    versions: [],
    version_count: 1,
    user_shares: [],
    group_shares: [],
  };
}

test.describe("Artifact library browser behavior", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "admin");
  });

  test("shares the same library surface across route aliases", async ({
    page,
  }) => {
    await page.route("**/api/build/artifact-library/page?**", async (route) => {
      await route.fulfill({
        json: {
          items: [
            artifact(
              "Route Parity",
              "11111111-1111-4111-8111-111111111111",
              "2026-07-10T00:00:00Z"
            ),
          ],
          next_cursor: null,
        },
      });
    });

    for (const path of ["/app/artifacts", "/craft/v1/artifacts"]) {
      await page.goto(path);
      await expect(
        page.getByText(
          "Preview, organize, share, and revisit durable outputs from Craft."
        )
      ).toBeVisible();
      await expect(
        page.getByText("Route Parity", { exact: true })
      ).toBeVisible();
    }
  });

  test("loads cursor pages, deduplicates items, and resets on filter change", async ({
    page,
  }) => {
    const requests: string[] = [];
    await page.route("**/api/build/artifact-library/page?**", async (route) => {
      const url = new URL(route.request().url());
      requests.push(url.search);
      const cursor = url.searchParams.get("cursor");
      const scope = url.searchParams.get("scope");
      const query = url.searchParams.get("query");

      if (query === "report") {
        await route.fulfill({
          json: {
            items: [
              artifact(
                "Report Only",
                "33333333-3333-4333-8333-333333333333",
                "2026-07-08T00:00:00Z"
              ),
            ],
            next_cursor: null,
          },
        });
        return;
      }

      if (scope === "shared") {
        await route.fulfill({ json: { items: [], next_cursor: null } });
        return;
      }

      if (!cursor) {
        await route.fulfill({
          json: {
            items: [
              artifact(
                "First Page",
                "11111111-1111-4111-8111-111111111111",
                "2026-07-10T00:00:00Z"
              ),
            ],
            next_cursor: "cursor-2",
          },
        });
        return;
      }

      await route.fulfill({
        json: {
          items: [
            artifact(
              "First Page",
              "11111111-1111-4111-8111-111111111111",
              "2026-07-10T00:00:00Z"
            ),
            artifact(
              "Second Page",
              "22222222-2222-4222-8222-222222222222",
              "2026-07-09T00:00:00Z"
            ),
          ],
          next_cursor: null,
        },
      });
    });

    await page.goto("/app/artifacts");
    await expect(page.getByText("First Page", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: /load more/i }).click();
    await expect(page.getByText("Second Page", { exact: true })).toBeVisible();
    await expect(page.getByText("First Page", { exact: true })).toHaveCount(1);

    await page.getByPlaceholder("Search artifacts").fill("report");
    await expect(page.getByText("Report Only", { exact: true })).toBeVisible();
    await expect(page.getByText("Second Page", { exact: true })).toHaveCount(0);

    expect(requests.some((search) => search.includes("cursor=cursor-2"))).toBe(
      true
    );
    expect(requests.some((search) => search.includes("query=report"))).toBe(
      true
    );
  });
});
