/**
 * E2E + UX coverage for the connector-detail page
 * (`/admin/connector/[ccPairId]`, rendered by `page.tsx` + `ConfigDisplay`,
 * `IndexAttemptsTable`, `EditPropertyModal`, and the "Manage" dropdown).
 *
 * This is the "like-for-like with the connectors" instrumentation of the
 * SharePoint connector detail view at `/admin/connector/4`: it drives the same
 * surfaces a real admin uses — the header, the Indexing summary card, the
 * Connector Configuration table, the Manage dropdown, and the Advanced section —
 * asserting concrete, observable outcomes and capturing screenshots along the
 * way.
 *
 * Two connectors are used:
 *
 * 1. **Real file cc-pair** (created via `OnyxApiClient`) — proves the page
 *    renders end-to-end against a live backend: header, status card, and the
 *    Advanced → "Indexing Attempts" table. Mirrors `inlineFileManagement.spec`
 *    and `permission-sync-tabs.spec`.
 *
 * 2. **Route-mocked SharePoint cc-pair** — reproduces the exact config shape of
 *    connector 4 (empty `excluded_paths` / `excluded_sites` /
 *    `microsoft_search_queries` arrays) without needing real SharePoint OAuth.
 *    This locks in the `ConfigDisplay` fix: empty-array config rows must render
 *    the "-" placeholder, never a blank/valueless row. It also exercises the
 *    Microsoft Search Region edit-modal validation.
 */

import { test, expect } from "@playwright/test";
import type { Page, Route } from "@playwright/test";

import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";
import { expectScreenshot } from "@tests/e2e/utils/visualRegression";

const MOCK_SP_CC_PAIR_ID = 98765;
const MOCK_SP_SOURCE = "sharepoint";

function jsonResponse(data: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  };
}

/**
 * Minimal `CCPairFullInfo` for a SharePoint connector whose config mirrors the
 * real connector 4: several empty list-valued fields alongside populated
 * scalars and a `microsoft_search_region` (the one inline-editable text field).
 */
function sharepointCCPairFixture() {
  const now = new Date().toISOString();
  return {
    id: MOCK_SP_CC_PAIR_ID,
    name: "sharepoint-hr",
    status: "ACTIVE",
    in_repeated_error_state: false,
    num_docs_indexed: 719,
    connector: {
      id: 4321,
      name: "sharepoint-hr",
      source: MOCK_SP_SOURCE,
      input_type: "poll",
      connector_specific_config: {
        sites: ["https://contoso.sharepoint.com/sites/HumanResources"],
        include_lists: true,
        authority_host: "https://login.microsoftonline.com",
        excluded_paths: [],
        excluded_sites: [],
        graph_api_host: "https://graph.microsoft.com",
        include_site_pages: true,
        microsoft_search_region: "NAM",
        microsoft_search_queries: [],
        sharepoint_domain_suffix: "sharepoint.com",
      },
      refresh_freq: 1800,
      prune_freq: 604800,
      indexing_start: null,
      access_type: "public",
      credential_ids: [11],
      time_created: now,
      time_updated: now,
    },
    credential: {
      id: 11,
      name: "Credential #1",
      credential_json: {},
      admin_public: true,
      time_created: now,
      time_updated: now,
      source: MOCK_SP_SOURCE,
      user_id: null,
      curator_public: true,
    },
    number_of_index_attempts: 1,
    last_index_attempt_status: "success",
    latest_deletion_attempt: null,
    access_type: "public",
    is_editable_for_current_user: true,
    deletion_failure_message: null,
    indexing: false,
    creator: null,
    creator_email: "cole@unwrap.rs",
    last_indexed: now,
    last_pruned: null,
    last_full_permission_sync: null,
    overall_indexing_speed: null,
    latest_checkpoint_description: null,
    last_permission_sync_attempt_status: null,
    permission_syncing: false,
    last_permission_sync_attempt_finished: null,
    last_permission_sync_attempt_error_message: null,
    groups: [],
    supports_targeted_reindex: false,
  };
}

/**
 * Wire up the endpoints the connector-detail page fetches for the mocked
 * SharePoint cc-pair. Everything else (auth, settings, llm providers) hits the
 * real backend. Routes are registered parent-first; Playwright matches LIFO, so
 * the `index-attempts` / `errors` sub-routes win over the bare cc-pair route.
 */
async function mockSharepointConnector(page: Page): Promise<void> {
  const base = `**/api/manage/admin/cc-pair/${MOCK_SP_CC_PAIR_ID}`;

  await page.route(`${base}/index-attempts*`, async (route: Route) => {
    await route.fulfill(
      jsonResponse({
        items: [
          {
            id: 7001,
            status: "success",
            new_docs_indexed: 0,
            total_docs_indexed: 0,
            docs_removed_from_index: 0,
            error_msg: null,
            full_exception_trace: null,
            from_beginning: false,
            time_started: new Date().toISOString(),
            time_updated: new Date().toISOString(),
          },
        ],
        total_items: 1,
      })
    );
  });

  await page.route(`${base}/errors*`, async (route: Route) => {
    await route.fulfill(jsonResponse({ items: [], total_items: 0 }));
  });

  await page.route(base, async (route: Route) => {
    if (route.request().method() === "GET") {
      await route.fulfill(jsonResponse(sharepointCCPairFixture()));
      return;
    }
    await route.continue();
  });
}

/**
 * Read the rendered value of a config row by its label.
 *
 * Each `ConfigItem` row renders as `<row><labelWrapper>label</labelWrapper>
 * <valueWrapper>value…</valueWrapper></row>`. We grab the row (the label's
 * grandparent), read its full text, and strip the leading label — leaving the
 * rendered value (e.g. "True", "-", or a comma-joined list).
 */
async function configRowValue(page: Page, label: string): Promise<string> {
  const labelNode = page.getByText(label, { exact: true }).first();
  const row = labelNode.locator("xpath=../..");
  const full = (await row.textContent()) ?? "";
  return full.slice(label.length).trim();
}

test.describe("Connector detail — real file connector", () => {
  let ccPairId: number | null = null;

  test.beforeEach(async ({ page }) => {
    // Auth comes from the admin project's `storageState`; don't clear cookies.
    const apiClient = new OnyxApiClient(page.request);
    ccPairId = await apiClient.createFileConnector(
      `E2E ConnectorDetail ${Date.now()}`
    );
  });

  test.afterEach(async ({ page }) => {
    if (ccPairId !== null) {
      const apiClient = new OnyxApiClient(page.request);
      try {
        await apiClient.deleteCCPair(ccPairId);
      } catch (error) {
        console.warn(`Failed to delete test connector ${ccPairId}: ${error}`);
      }
      ccPairId = null;
    }
  });

  test("renders header, indexing summary, and Advanced indexing-attempts table", async ({
    page,
  }) => {
    await page.goto(`/admin/connector/${ccPairId}`);
    await page.waitForLoadState("networkidle");

    // Header: editable connector name + Manage control.
    await expect(page.getByRole("button", { name: "Manage" })).toBeVisible();

    // Indexing summary card labels.
    await expect(page.getByText("Documents Indexed")).toBeVisible();
    await expect(page.getByText("Last Indexed")).toBeVisible();

    // Manage dropdown exposes the three lifecycle actions.
    await page.getByRole("button", { name: "Manage" }).click();
    await expect(
      page.getByRole("menuitem", { name: /Re-Index/i })
    ).toBeVisible();
    await expect(
      page.getByRole("menuitem", { name: /Pause|Resume/i })
    ).toBeVisible();
    await expect(page.getByRole("menuitem", { name: /Delete/i })).toBeVisible();
    await page.keyboard.press("Escape");

    // Advanced reveals the Indexing Attempts table for a non-sync connector.
    await page.getByRole("button", { name: "Advanced" }).click();
    await expect(
      page.getByRole("heading", { name: "Indexing Attempts" })
    ).toBeVisible();
    await expect(
      page.getByRole("columnheader", { name: "Total Docs" })
    ).toBeVisible();
  });
});

test.describe("Connector detail — SharePoint config rendering (mocked)", () => {
  test("empty-array config fields render a '-' placeholder, never a blank row", async ({
    page,
  }) => {
    await mockSharepointConnector(page);

    await page.goto(`/admin/connector/${MOCK_SP_CC_PAIR_ID}`);
    await page.waitForLoadState("networkidle");

    await expect(
      page.getByRole("heading", { name: "Connector Configuration" })
    ).toBeVisible();

    // Populated scalar still shows its value.
    expect(await configRowValue(page, "include_lists")).toContain("True");

    // Regression: empty-array fields must show the same "-" placeholder used
    // for empty scalars — not an empty, valueless row that reads as "failed to
    // load" to an admin.
    for (const field of [
      "excluded_paths",
      "excluded_sites",
      "microsoft_search_queries",
    ]) {
      expect(await configRowValue(page, field)).toBe("-");
    }

    await expectScreenshot(page, { name: "connector-detail-sharepoint-config" });
  });

  test("Microsoft Search Region edit modal validates a three-letter code", async ({
    page,
  }) => {
    await mockSharepointConnector(page);

    await page.goto(`/admin/connector/${MOCK_SP_CC_PAIR_ID}`);
    await page.waitForLoadState("networkidle");

    // The region row is the one inline-editable config field for SharePoint.
    const regionRow = page
      .getByText("microsoft_search_region", { exact: true })
      .locator("xpath=../..");
    await regionRow.getByRole("button").last().click();

    const dialog = page.getByRole("dialog", {
      name: "Edit Microsoft Search Region",
    });
    await expect(dialog).toBeVisible();

    const input = dialog.getByRole("textbox");

    // Invalid: too short. The submit button must stay disabled and an inline
    // validation message must surface on blur.
    await input.fill("XX");
    await input.blur();
    await expect(
      dialog.getByText(/three-letter region code/i)
    ).toBeVisible();
    await expect(
      dialog.getByRole("button", { name: /Update property/i })
    ).toBeDisabled();

    // Valid: a fresh three-letter code re-enables submit.
    await input.fill("EUR");
    await expect(
      dialog.getByRole("button", { name: /Update property/i })
    ).toBeEnabled();
  });
});
