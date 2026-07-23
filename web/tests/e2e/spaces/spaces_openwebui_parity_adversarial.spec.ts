import {
  expect,
  test,
  type APIRequestContext,
  type Browser,
  type BrowserContext,
  type Page,
} from "@playwright/test";
import { SpaceDetailPage } from "@tests/e2e/pages/SpaceDetailPage";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";
import { apiLogin } from "@tests/e2e/utils/auth";

/**
 * OpenWebUI-parity adversarial E2E.
 *
 * Recreates the production Open WebUI (chat-aws) setup inside Onyx:
 * - Users modeled on the real roster (Jessica, Jarrod, Josh) plus the admin.
 * - Spaces modeled on the real ones ("Intranet Test Space", "JF Folder
 *   Space") whose knowledge whitelisted Magellan HR SharePoint folders
 *   (Company Wide Files, JF, Medical/Dental/Vision/Policies).
 *
 * Requires seed-openwebui-parity-e2e.py to have governed:
 * - HumanResourcesIntranet (Magellan) as PUBLIC / recommended.
 * - ComplianceIntranet as RESTRICTED to a group nobody here belongs to
 *   (admins bypass that group gate; ordinary users do not).
 *
 * Adversarial posture: every ACL boundary is exercised from the outside —
 * non-members probing spaces, viewers attempting writes, editors attempting
 * governance bypasses via direct API calls with hidden/forged node ids.
 */

const PARITY_PASSWORD = "OpenWebUIParity123!";

interface ParityUser {
  readonly email: string;
  readonly displayName: string;
}

function parityUsers(stamp: number): Record<"jessica" | "jarrod" | "josh", ParityUser> {
  return {
    jessica: {
      email: `jessica.purnell+e2e${stamp}@example.com`,
      displayName: "Jessica Purnell",
    },
    jarrod: {
      email: `jflorence+e2e${stamp}@example.com`,
      displayName: "Jarrod Florence",
    },
    josh: {
      email: `josh+e2e${stamp}@example.com`,
      displayName: "Joshua Cooksey",
    },
  };
}

async function registerAndLogin(
  browser: Browser,
  user: ParityUser,
): Promise<{ context: BrowserContext; page: Page; api: OnyxApiClient }> {
  const context = await browser.newContext();
  const page = await context.newPage();
  const registerRes = await page.request.post("/api/auth/register", {
    data: { email: user.email, username: user.email, password: PARITY_PASSWORD },
  });
  if (!registerRes.ok() && registerRes.status() !== 400) {
    throw new Error(
      `register ${user.email}: ${registerRes.status()} ${await registerRes.text()}`,
    );
  }
  await apiLogin(page, user.email, PARITY_PASSWORD);
  await page.request.patch("/api/user/personalization", {
    data: { name: user.displayName },
  });
  return { context, page, api: new OnyxApiClient(page.request) };
}

async function hierarchyNodesBySource(
  request: APIRequestContext,
  source: string,
): Promise<
  {
    id: number;
    title: string;
    governance: {
      is_selectable: boolean;
      denial_reason: string | null;
      tenant_label: string | null;
    } | null;
  }[]
> {
  const response = await request.get(`/api/hierarchy-nodes?source=${source}`);
  expect(response.ok()).toBeTruthy();
  return (await response.json()).nodes;
}

async function putConnectedKnowledge(
  request: APIRequestContext,
  projectId: number,
  hierarchyNodeIds: number[],
): Promise<{ status: number; body: string }> {
  const response = await request.put(
    `/api/user/projects/${projectId}/connected-knowledge`,
    { data: { document_ids: [], hierarchy_node_ids: hierarchyNodeIds } },
  );
  return { status: response.status(), body: await response.text() };
}

test.describe("OpenWebUI parity: users, spaces, governance boundaries", () => {
  test("recreates OpenWebUI spaces for real-roster users and defends every boundary", async ({
    page,
    browser,
  }) => {
    test.setTimeout(300_000);
    const stamp = Date.now();
    const users = parityUsers(stamp);
    const adminApi = new OnyxApiClient(page.request);

    // === Discover the governed HR tree exactly like the modal would ===
    const adminNodes = await hierarchyNodesBySource(page.request, "sharepoint");
    const hrSite = adminNodes.find(
      (node) => node.governance?.tenant_label === "Magellan",
    );
    expect(hrSite, "seeded Magellan HR governed site must be visible").toBeTruthy();
    const byTitle = new Map(adminNodes.map((node) => [node.title, node]));
    const companyWide = byTitle.get("Company Wide Files");
    const jfFolder = byTitle.get("JF");
    const medical = byTitle.get("Medical");
    expect(companyWide && jfFolder && medical).toBeTruthy();

    // Admins have full connected-source access: RESTRICTED scopes are visible
    // to the admin picker feed even before any group membership exists.
    const complianceNode = byTitle.get("ComplianceIntranet");
    expect(complianceNode, "admin must see restricted ComplianceIntranet").toBeTruthy();
    const complianceSiteId = complianceNode!.id;

    const jessica = await registerAndLogin(browser, users.jessica);
    const jarrod = await registerAndLogin(browser, users.jarrod);
    const josh = await registerAndLogin(browser, users.josh);

    let intranetSpaceId: number | null = null;
    let jfSpaceId: number | null = null;
    try {
      // === Josh recreates "Intranet Test Space" (Company Wide Files + JF) ===
      const joshApi = josh.api;
      const intranetSpaceName = `Intranet Test Space ${stamp}`;
      intranetSpaceId = await joshApi.createProject(
        intranetSpaceName,
        "Parity of OpenWebUI Intranet Test Space",
      );
      const joshSave = await putConnectedKnowledge(
        josh.page.request,
        intranetSpaceId,
        [companyWide!.id, jfFolder!.id],
      );
      expect(joshSave.status).toBe(200);

      // === Jarrod recreates "JF Folder Space" through the real UI ===
      const jarrodApi = jarrod.api;
      const jfSpaceName = `JF Folder Space ${stamp}`;
      jfSpaceId = await jarrodApi.createProject(
        jfSpaceName,
        "Parity of OpenWebUI JF Folder Space",
      );
      const jarrodSpace = new SpaceDetailPage(jarrod.page);
      await jarrodSpace.goto({ spaceName: jfSpaceName, projectId: jfSpaceId });
      await jarrod.page
        .getByRole("button", { name: "Add connected source" })
        .first()
        .click();
      const dialog = jarrod.page.getByRole("dialog", {
        name: /Add knowledge to space/i,
      });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByText("Magellan", { exact: true })).toBeVisible({
        timeout: 15_000,
      });
      await dialog.getByText("Human Resources Intranet").first().click();
      // Browsing must not auto-attach; attach explicitly via the checkbox.
      await expect(
        dialog.getByText("No connected-source selections"),
      ).toBeVisible();
      await dialog
        .getByRole("checkbox", { name: "Attach Human Resources Intranet" })
        .click();
      await expect(
        dialog.getByText("1 connected-source selection", { exact: true }),
      ).toBeVisible();
      await dialog.getByRole("button", { name: "Save", exact: true }).click();
      await expect(dialog).toHaveCount(0);
      await jarrodSpace.reload();
      await expect(
        jarrod.page.getByText("Connected sources", { exact: true }).first(),
      ).toBeVisible();

      // === ADVERSARIAL 1: Jessica (no share) cannot read either space ===
      const jessicaProbe = await jessica.page.request.get(
        `/api/user/projects/${intranetSpaceId}/connected-knowledge`,
      );
      expect([403, 404]).toContain(jessicaProbe.status());
      const jessicaWrite = await putConnectedKnowledge(
        jessica.page.request,
        intranetSpaceId,
        [companyWide!.id],
      );
      expect([403, 404]).toContain(jessicaWrite.status);

      // === Josh shares Intranet Test Space: Jessica VIEWER, Jarrod EDITOR ===
      const jessicaId = (await adminApi.getUserByEmail(users.jessica.email))?.id;
      const jarrodId = (await adminApi.getUserByEmail(users.jarrod.email))?.id;
      expect(jessicaId && jarrodId).toBeTruthy();
      const shareRes = await josh.page.request.patch(
        `/api/user/projects/${intranetSpaceId}/sharing`,
        {
          data: {
            organization_permission: null,
            user_shares: [
              { user_id: jessicaId, permission: "VIEWER" },
              { user_id: jarrodId, permission: "EDITOR" },
            ],
            group_shares: [],
          },
        },
      );
      expect(shareRes.status()).toBe(200);

      // === ADVERSARIAL 2: viewer Jessica can read but still cannot write ===
      const jessicaRead = await jessica.page.request.get(
        `/api/user/projects/${intranetSpaceId}/connected-knowledge`,
      );
      expect(jessicaRead.status()).toBe(200);
      const readBody = await jessicaRead.json();
      const attachedTitles = readBody.hierarchy_nodes.map(
        (node: { title: string }) => node.title,
      );
      expect(attachedTitles).toContain("Company Wide Files");
      expect(attachedTitles).toContain("JF");
      const viewerWrite = await putConnectedKnowledge(
        jessica.page.request,
        intranetSpaceId,
        [companyWide!.id],
      );
      expect([403, 404]).toContain(viewerWrite.status);

      // Viewer sees the space in the UI with connected sources but no editor
      // affordance for adding connected sources.
      const jessicaSpace = new SpaceDetailPage(jessica.page);
      await jessicaSpace.goto({
        spaceName: intranetSpaceName,
        projectId: intranetSpaceId,
      });
      await expect(
        jessica.page.getByText("Company Wide Files").first(),
      ).toBeVisible({ timeout: 15_000 });
      await expect(
        jessica.page.getByRole("button", { name: "Add connected source" }),
      ).toHaveCount(0);

      // === ADVERSARIAL 3: editor Jarrod cannot smuggle restricted/hidden ids ===
      // Direct API attach of the RESTRICTED ComplianceIntranet site must fail
      // even though Jarrod legitimately holds EDIT on the space.
      const restrictedAttach = await putConnectedKnowledge(
        jarrod.page.request,
        intranetSpaceId,
        [companyWide!.id, complianceSiteId],
      );
      expect(restrictedAttach.status).toBe(403);
      expect(restrictedAttach.body).toContain("connected-source policy");

      // Source-root smuggling: SharePoint root is navigation_only.
      const rootNode = adminNodes.find((node) => node.title === "SharePoint");
      expect(rootNode?.governance?.denial_reason).toBe("navigation_only");
      const rootAttach = await putConnectedKnowledge(
        jarrod.page.request,
        intranetSpaceId,
        [rootNode!.id],
      );
      expect(rootAttach.status).toBe(403);

      // Nonexistent / forged id.
      const forgedAttach = await putConnectedKnowledge(
        jarrod.page.request,
        intranetSpaceId,
        [99_999_999],
      );
      expect([400, 403, 404]).toContain(forgedAttach.status);

      // A legitimate edit by the editor still works after the failed attacks
      // and failed writes did not corrupt the original selection.
      const legit = await putConnectedKnowledge(
        jarrod.page.request,
        intranetSpaceId,
        [companyWide!.id, jfFolder!.id, medical!.id],
      );
      expect(legit.status).toBe(200);
      const afterAttacks = await josh.page.request.get(
        `/api/user/projects/${intranetSpaceId}/connected-knowledge`,
      );
      const afterTitles = (await afterAttacks.json()).hierarchy_nodes.map(
        (node: { title: string }) => node.title,
      );
      expect(afterTitles.sort()).toEqual(
        ["Company Wide Files", "JF", "Medical"].sort(),
      );

      // === ADVERSARIAL 4: non-member picker feeds hide restricted scopes ===
      const jessicaNodes = await hierarchyNodesBySource(
        jessica.page.request,
        "sharepoint",
      );
      const jessicaTitles = new Set(jessicaNodes.map((node) => node.title));
      expect(jessicaTitles.has("ComplianceIntranet")).toBe(false);
      expect(jessicaTitles.has("Company Wide Files")).toBe(true);

      // === ADVERSARIAL 5: Jessica cannot touch Jarrod's unshared space ===
      const jfProbe = await jessica.page.request.get(
        `/api/user/projects/${jfSpaceId}/connected-knowledge`,
      );
      expect([403, 404]).toContain(jfProbe.status());
      const jfShareSteal = await jessica.page.request.patch(
        `/api/user/projects/${jfSpaceId}/sharing`,
        {
          data: {
            organization_permission: null,
            user_shares: [{ user_id: jessicaId, permission: "EDITOR" }],
            group_shares: [],
          },
        },
      );
      expect([403, 404]).toContain(jfShareSteal.status());

      // === POSITIVE COUNTERPART: restricted scope opens for group members ===
      // Deny-by-default alone doesn't prove the policy is group-based — add
      // Josh to the restricted compliance group and verify the gate opens for
      // him (and only him).
      const groups = await adminApi.getUserGroups();
      const restrictedGroup = groups.find(
        (group) => group.name === "OpenWebUI Parity Compliance Group",
      );
      expect(restrictedGroup, "seed must have created the restricted group").toBeTruthy();
      const joshId = (await adminApi.getUserByEmail(users.josh.email))?.id;
      expect(joshId).toBeTruthy();
      const addRes = await page.request.post(
        `/api/manage/admin/user-group/${restrictedGroup!.id}/add-users`,
        { data: { user_ids: [joshId] } },
      );
      expect(addRes.status()).toBe(200);
      try {
        const joshNodes = await hierarchyNodesBySource(
          josh.page.request,
          "sharepoint",
        );
        const complianceRow = joshNodes.find(
          (node) => node.id === complianceSiteId,
        );
        expect(
          complianceRow,
          "group member must now see the restricted ComplianceIntranet",
        ).toBeTruthy();
        expect(complianceRow!.governance?.is_selectable).toBe(true);
        const memberAttach = await putConnectedKnowledge(
          josh.page.request,
          intranetSpaceId,
          [companyWide!.id, complianceSiteId],
        );
        expect(memberAttach.status).toBe(200);

        // Non-members still locked out even while a member has it attached.
        const jarrodNodesAfter = await hierarchyNodesBySource(
          jarrod.page.request,
          "sharepoint",
        );
        expect(
          jarrodNodesAfter.some((node) => node.id === complianceSiteId),
        ).toBe(false);
        const jarrodAttachAfter = await putConnectedKnowledge(
          jarrod.page.request,
          intranetSpaceId,
          [companyWide!.id, complianceSiteId],
        );
        expect(jarrodAttachAfter.status).toBe(403);
      } finally {
        // Restore the group to empty so the seed stays reusable and other
        // suites keep their deny-by-default assumption.
        const restoreRes = await page.request.patch(
          `/api/manage/admin/user-group/${restrictedGroup!.id}`,
          { data: { user_ids: [], cc_pair_ids: [] } },
        );
        expect([200, 204]).toContain(restoreRes.status());
      }

      console.log(
        "openwebui parity adversarial: all governance and sharing boundaries held",
      );
    } finally {
      if (intranetSpaceId !== null) {
        await josh.api.deleteProject(intranetSpaceId);
      }
      if (jfSpaceId !== null) {
        await jarrod.api.deleteProject(jfSpaceId);
      }
      await jessica.context.close();
      await jarrod.context.close();
      await josh.context.close();
    }
  });
});
