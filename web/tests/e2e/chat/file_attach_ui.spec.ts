import { expect, test, type Page } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";
import {
  openActionManagement,
  openSourceManagement,
  TOOL_IDS,
} from "@tests/e2e/utils/tools";

// End-user regression for the 2026-07-16 xlsx bug: a user attaches a
// spreadsheet through the chat input's paperclip menu and asks about it. The
// completed answer must contain the exact figure from the file and must NOT be
// the "I don't have a file_reader tool" apology that the regression produced.
// This exercises the real UI wiring (paperclip -> Upload Files -> file chooser)
// plus the live user_file_processing pipeline and a live LLM answer, so nothing
// here is mocked.

const FIXTURE_PATH =
  "/home/cole/WebstormProjects/forks/onyx/testsprite_tests/fixtures/foundations_2025_production.xlsx";
const FIXTURE_NAME = "foundations_2025_production.xlsx";
const QUESTION =
  "How much business did Stewart Willis write in 2025? Give the exact amount.";

// Accepts the figure with or without thousands separators (e.g. "40,216,752.33"
// or "40216752.33"), which is how a live model might format it.
const EXPECTED_FIGURE = /40,?216,?752\.33/;

interface UploadedUserFile {
  id: string;
  name: string;
  status: string;
}

interface UploadResponseBody {
  user_files: UploadedUserFile[];
  rejected_files: { file_name: string; reason: string }[];
}

interface FileStatusRow {
  id: string;
  status: string;
  chunk_count: number | null;
}

async function deleteUserFile(page: Page, fileId: string): Promise<void> {
  const res = await page.request.delete(
    `/api/user/projects/file/${encodeURIComponent(fileId)}`
  );
  if (!res.ok()) {
    console.warn(
      `cleanup: failed to delete user file ${fileId}: ${res.status()}`
    );
  }
}

async function deleteChatSession(page: Page, chatId: string): Promise<void> {
  const res = await page.request.delete(
    `/api/chat/delete-chat-session/${encodeURIComponent(chatId)}`
  );
  if (!res.ok()) {
    console.warn(
      `cleanup: failed to delete chat session ${chatId}: ${res.status()}`
    );
  }
}

/**
 * The default agent enables every indexed source (e.g. SharePoint) by default,
 * which scopes internal search to those sources — so a freshly attached file is
 * never reached (source_type is sent). A message-attached file is only findable
 * via an unscoped search, so turn every enabled source off first, making the
 * send payload's source_type null.
 */
async function clearInternalSearchSourceScope(page: Page): Promise<void> {
  await openActionManagement(page);
  await expect(page.locator(TOOL_IDS.searchOption)).toBeVisible({
    timeout: 10_000,
  });
  await openSourceManagement(page);

  const enabledToggleLabels = await page
    .locator('[aria-label^="Toggle "][aria-checked="true"]')
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("aria-label") ?? "")
    );
  for (const label of enabledToggleLabels) {
    if (!label) {
      continue;
    }
    const toggle = page.locator(`[aria-label="${label}"]`);
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-checked", "false");
  }

  await page.keyboard.press("Escape");
  await expect(page.locator(TOOL_IDS.options)).toBeHidden({ timeout: 5_000 });
}

test.describe("File attach via chat input UI", () => {
  test("attaching an xlsx via the paperclip and asking about it answers with the exact figure", async ({
    page,
  }) => {
    test.setTimeout(300_000);

    await page.context().clearCookies();
    await loginAs(page, "admin");

    const chat = new ChatPage(page);
    await chat.goto();

    let userFileId: string | null = null;
    let chatSessionId: string | null = null;

    try {
      // Ensure internal search isn't pinned to indexed sources, so the attached
      // file becomes findable (mirrors the API-level regression's conditions).
      await clearInternalSearchSourceScope(page);

      const inputBar = page.locator("#onyx-chat-input");

      // Register the upload listener before triggering the picker so the POST
      // that carries the new user_file id is never missed.
      const uploadResponsePromise = page.waitForResponse(
        (response) =>
          response.url().includes("/api/user/projects/file/upload") &&
          response.request().method() === "POST"
      );

      // Open the paperclip ("Attach Files") popover. It is the first popover
      // trigger inside the input bar; the tooltip is not exposed as an
      // accessible name, so target it by its popover-trigger role.
      const paperclip = inputBar.locator("button[aria-haspopup]").first();
      await expect(paperclip).toBeVisible({ timeout: 15_000 });
      await paperclip.click();

      // Choose "Upload Files", which opens the native file chooser via the
      // hidden <input type="file">. Scope to the visible popover item; an
      // identical label also lives in the (closed) Recent Files modal.
      const uploadFilesItem = page
        .getByRole("button", { name: /Upload Files/ })
        .filter({ visible: true });
      const fileChooserPromise = page.waitForEvent("filechooser");
      await uploadFilesItem.click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles(FIXTURE_PATH);

      const uploadResponse = await uploadResponsePromise;
      expect(uploadResponse.ok()).toBeTruthy();
      const uploaded = (await uploadResponse.json()) as UploadResponseBody;
      expect(uploaded.rejected_files).toHaveLength(0);
      const [uploadedFile] = uploaded.user_files;
      expect(uploadedFile).toBeDefined();
      userFileId = uploadedFile!.id;

      // The file chip renders in the input bar.
      await expect(inputBar.getByText(FIXTURE_NAME)).toBeVisible({
        timeout: 15_000,
      });

      // Wait for the user_file_processing worker to finish indexing. The chip
      // shows a spinner + "Processing..." until the file reaches COMPLETED, and
      // the send button stays disabled the whole time. Require chunk_count > 0
      // so the spreadsheet is actually readable/searchable before we ask.
      await expect
        .poll(
          async () => {
            const res = await page.request.post(
              "/api/user/projects/file/statuses",
              { data: { file_ids: [userFileId] } }
            );
            if (!res.ok()) {
              return `REQUEST_${res.status()}`;
            }
            const rows = (await res.json()) as FileStatusRow[];
            const row = rows[0];
            if (!row) {
              return "MISSING";
            }
            if (row.status === "COMPLETED" && (row.chunk_count ?? 0) > 0) {
              return "READY";
            }
            return row.status;
          },
          { timeout: 180_000, intervals: [2_000] }
        )
        .toBe("READY");

      // The chip's processing state must clear in the UI (frontend polls the
      // same statuses endpoint) before the send button becomes enabled.
      await expect(inputBar.getByText(/Processing|Uploading/)).toHaveCount(0, {
        timeout: 30_000,
      });

      // Ask about the file. clickSend auto-waits for the send button to leave
      // its disabled-while-processing state.
      await chat.inputBar.fill(QUESTION);
      await chat.inputBar.clickSend();

      await expect(chat.humanMessage(0)).toContainText("Stewart Willis");

      // Wait for the answer to finish streaming — the feedback toolbar only
      // mounts once the message is complete.
      const aiMessage = chat.aiMessage(0);
      await expect(aiMessage.getByTestId("AgentMessage/toolbar")).toBeVisible({
        timeout: 180_000,
      });

      // The regression produced a "no file_reader tool" apology instead of an
      // answer; the fix reads the spreadsheet and returns the exact figure.
      await expect(aiMessage).toContainText(EXPECTED_FIGURE);
      await expect(aiMessage).not.toContainText("file_reader");

      const chatIdMatch = page.url().match(/chatId=([0-9a-fA-F-]+)/);
      chatSessionId = chatIdMatch?.[1] ?? null;
    } finally {
      if (chatSessionId) {
        await deleteChatSession(page, chatSessionId);
      }
      if (userFileId) {
        await deleteUserFile(page, userFileId);
      }
    }
  });
});
