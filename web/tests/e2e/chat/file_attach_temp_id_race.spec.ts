import { expect, test, type Page } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";

// Temp-id attachment race (2026-07-17): the chat composer's optimistic file
// descriptors carry a client-generated `temp_<uuid>` in BOTH `id` and
// `user_file_id` until the background upload resolves
// (ProjectsContext.createOptimisticFile -> projectsFileToFileDescriptor).
// The controller's "uploading" ChatState gate expires within milliseconds
// because beginUpload() resolves with the optimistic files WITHOUT awaiting
// svcUploadFiles. Component-local guards cover the send button and the Enter
// key, but the queued-message drain in AppInputBar calls onSubmit() with no
// upload guard at all — so a follow-up queued during streaming auto-fires
// while an attachment is still uploading, sending the temp_ ids verbatim.
// The backend then silently substitutes empty content (proven API-side by
// testsprite_tests/temp_id_race_smoke.py) — chip visible, LLM sees nothing.
//
// This spec instruments that flow end-to-end: it delays the real upload,
// queues a follow-up during a streaming answer, attaches a file, and captures
// the drained send-message payload. The final assertion states the CORRECT
// invariant — every file descriptor id in an outgoing message references a
// real uploaded file — so this test runs RED until the race is fixed.

const FIXTURE_PATH =
  "/home/cole/WebstormProjects/forks/onyx/testsprite_tests/fixtures/foundations_2025_production.xlsx";
const FIXTURE_NAME = "foundations_2025_production.xlsx";

const UPLOAD_DELAY_MS = 25_000;
const STREAM_HOLD_QUESTION =
  "Count from 1 to 40, one number per line. No other text.";
const QUEUED_QUESTION_MARKER = `Summarize the attached spreadsheet race-${Date.now()}`;

interface SendMessagePayload {
  message?: string;
  file_descriptors?: { id: string; user_file_id?: string | null }[];
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

async function deleteUserFileByName(page: Page, name: string): Promise<void> {
  // The delayed upload eventually completes in the background; find the real
  // record by name and delete it so reruns stay clean.
  const res = await page.request.get(`/api/user/files/recent`);
  if (!res.ok()) return;
  const files = (await res.json()) as { id: string; name: string }[];
  for (const file of files.filter((f) => f.name === name)) {
    await page.request.delete(
      `/api/user/projects/file/${encodeURIComponent(file.id)}`
    );
  }
}

test.describe("File attach temp-id race", () => {
  test("queued follow-up drained during an in-flight upload sends real file ids, not temp_ placeholders", async ({
    page,
  }) => {
    test.setTimeout(300_000);

    await page.context().clearCookies();
    await loginAs(page, "admin");

    // Instrument the network: hold the upload response open long enough that
    // the queued-message drain fires while the attachment is still optimistic.
    // route.continue() still reaches the real backend, so nothing is mocked —
    // this models a large file on a slow uplink.
    await page.route("**/api/user/projects/file/upload", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, UPLOAD_DELAY_MS));
      await route.continue();
    });

    const chat = new ChatPage(page);
    await chat.goto();

    let chatSessionId: string | null = null;

    try {
      // 1. Start a streaming answer to hold the composer in a non-input state.
      await chat.inputBar.fill(STREAM_HOLD_QUESTION);
      await chat.inputBar.clickSend();
      await expect(chat.humanMessage(0)).toContainText("Count from 1 to 40");

      // Register the capture BEFORE the queued message can possibly drain.
      // NOTE: the client posts to /api/chat/send-chat-message (send-message
      // is NOT a substring of it — the first run's capture missed for that).
      const drainedRequestPromise = page.waitForRequest(
        (request) =>
          request.url().includes("/api/chat/send-chat-message") &&
          request.method() === "POST" &&
          (request.postData() ?? "").includes(QUEUED_QUESTION_MARKER),
        { timeout: 180_000 }
      );

      // 2. While streaming, type the follow-up and press Enter — the composer
      // enqueues it (canSubmitNormally is false during streaming).
      await chat.inputBar.fill(QUEUED_QUESTION_MARKER);
      await page
        .locator("#onyx-chat-input-textbox")
        .press("Enter", { timeout: 10_000 });

      // 3. Still while streaming, attach the spreadsheet through the paperclip.
      // beginUpload inserts optimistic temp_ descriptors immediately; the real
      // upload is held open by the route delay above.
      const inputBar = page.locator("#onyx-chat-input");
      const paperclip = inputBar.locator("button[aria-haspopup]").first();
      await expect(paperclip).toBeVisible({ timeout: 15_000 });
      await paperclip.click();
      const uploadFilesItem = page
        .getByRole("button", { name: /Upload Files/ })
        .filter({ visible: true });
      const fileChooserPromise = page.waitForEvent("filechooser");
      await uploadFilesItem.click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles(FIXTURE_PATH);

      // The optimistic chip renders while the upload is still in flight.
      await expect(inputBar.getByText(FIXTURE_NAME)).toBeVisible({
        timeout: 15_000,
      });

      // 4. When the first answer finishes rendering, the queued-message drain
      // auto-fires onSubmit with whatever is in currentMessageFiles.
      const drainedRequest = await drainedRequestPromise;
      const payload = JSON.parse(
        drainedRequest.postData() ?? "{}"
      ) as SendMessagePayload;
      const descriptors = payload.file_descriptors ?? [];

      console.log(
        "drained send-message file_descriptors:",
        JSON.stringify(descriptors, null, 2)
      );

      const chatIdMatch = page.url().match(/chatId=([0-9a-fA-F-]+)/);
      chatSessionId = chatIdMatch?.[1] ?? null;

      // The drained follow-up must carry the attachment...
      expect(
        descriptors.length,
        "queued follow-up should carry the attached file"
      ).toBeGreaterThan(0);

      // ...and — THE INVARIANT UNDER TEST — every descriptor must reference a
      // real uploaded file id. Today the drain outraces the upload and this
      // captures `temp_...` ids, which the backend silently swallows
      // (empty content, no error). Red until the send gate keys off
      // "real id exists" instead of the coarse uploading state.
      const tempIds = descriptors
        .flatMap((d) => [d.id, d.user_file_id ?? ""])
        .filter((id) => id.startsWith("temp_"));
      expect(
        tempIds,
        `outgoing message must not reference client-side temp ids; got: ${tempIds.join(", ")}`
      ).toHaveLength(0);
    } finally {
      await page.unroute("**/api/user/projects/file/upload");
      if (chatSessionId) {
        await deleteChatSession(page, chatSessionId);
      }
      await deleteUserFileByName(page, FIXTURE_NAME);
    }
  });
});
