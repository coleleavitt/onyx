import { expect, test, type Locator, type Page } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";

// End-user lifecycle of a chat session as it appears in the sidebar "Recents":
// send a live message to create it, watch it auto-name, rename it via the row's
// kebab menu, then delete it via that same menu. A unique suffix keeps the
// message/name from colliding with concurrent runs or leftovers.
const UNIQUE = `sidebarlifecycle-${Date.now()}`;
const PROMPT = `Reply with exactly: OK — lifecycle ${UNIQUE}`;
const RENAMED_NAME = `Renamed ${UNIQUE}`;
const PLACEHOLDER_NAME = "New Chat";

// The Recents row is a SidebarTab: an absolutely-positioned overlay <a> (whose
// href carries the chatId) plus a kebab <button>, both children of the same
// container div. The visible name lives in that container as sibling text.
function sidebarChatLink(page: Page, chatId: string): Locator {
  return page.locator(`a[href="/app?chatId=${chatId}"]`);
}

function sidebarChatRow(page: Page, chatId: string): Locator {
  return sidebarChatLink(page, chatId).locator("xpath=..");
}

async function rowText(row: Locator): Promise<string> {
  return (await row.textContent())?.trim() ?? "";
}

test.describe("Chat session sidebar lifecycle", () => {
  // Tracked so the afterEach safety net can remove the session even if the test
  // is aborted (a hard test-timeout skips inline finally blocks, so cleanup
  // must live in a hook).
  let createdChatId: string | null = null;

  test.afterEach(async ({ page }) => {
    if (!createdChatId) return;
    await page.request
      .delete(`/api/chat/delete-chat-session/${createdChatId}`)
      .catch(() => {
        /* already deleted or never persisted — nothing to clean up */
      });
    createdChatId = null;
  });

  test("create, rename, and delete a chat from the sidebar Recents", async ({
    page,
  }) => {
    test.setTimeout(300_000);

    await page.context().clearCookies();
    await loginAs(page, "admin");

    const chat = new ChatPage(page);
    await chat.goto();

    // 1. Send a short live prompt from a new chat.
    await chat.inputBar.fill(PROMPT);
    await chat.inputBar.clickSend();

    await chat.expectHumanMessage(UNIQUE);

    // Sending the first message navigates to /app?chatId=<id> before streaming.
    await page.waitForURL(/chatId=/, { timeout: 60_000 });
    const chatId = new URL(page.url()).searchParams.get("chatId");
    expect(chatId).toBeTruthy();
    if (!chatId) throw new Error("chatId missing from URL after first message");
    createdChatId = chatId;

    // Let the assistant finish responding (auto-naming fires on completion).
    await expect(chat.aiMessage(0)).toContainText("OK", { timeout: 180_000 });

    // 2. The chat shows up in the sidebar Recents.
    const row = sidebarChatRow(page, chatId);
    await expect(sidebarChatLink(page, chatId)).toBeVisible({
      timeout: 30_000,
    });

    // Its title is LLM-generated, so assert only that a non-empty name
    // eventually replaces the "New Chat" placeholder. Waiting for auto-naming
    // to settle here also prevents it from racing our manual rename below.
    await expect
      .poll(() => rowText(row), { timeout: 120_000 })
      .not.toBe(PLACEHOLDER_NAME);
    expect(await rowText(row)).not.toBe("");

    // 3. Rename the chat via the sidebar kebab menu.
    await row.hover();
    const kebabButton = row.locator("button");
    await expect(kebabButton).toBeVisible({ timeout: 10_000 });
    await kebabButton.click();

    const renameItem = page.getByRole("button", {
      name: "Rename",
      exact: true,
    });
    await expect(renameItem).toBeVisible({ timeout: 10_000 });
    await renameItem.click();

    // The row swaps its title text for an inline rename <input>. Drive it via
    // the keyboard once focused so we don't fight per-element actionability.
    const renameInput = row.locator("input");
    await expect(renameInput).toBeFocused({ timeout: 10_000 });
    await renameInput.focus();
    await page.keyboard.press("ControlOrMeta+a");
    await page.keyboard.type(RENAMED_NAME);
    await page.keyboard.press("Enter");

    // 4. The new unique name is reflected in the sidebar.
    await expect(row).toContainText(RENAMED_NAME, { timeout: 30_000 });

    // 5. Delete the chat via the sidebar kebab menu.
    await row.hover();
    await expect(kebabButton).toBeVisible({ timeout: 10_000 });
    await kebabButton.click();

    const deleteItem = page.getByRole("button", {
      name: "Delete",
      exact: true,
    });
    await expect(deleteItem).toBeVisible({ timeout: 10_000 });
    await deleteItem.click();

    const confirmDialog = page
      .getByRole("dialog")
      .filter({ hasText: "Delete Chat" });
    await expect(confirmDialog).toBeVisible({ timeout: 10_000 });
    await confirmDialog
      .getByRole("button", { name: "Delete", exact: true })
      .click();

    // 6. The entry disappears from the sidebar.
    await expect(sidebarChatLink(page, chatId)).toHaveCount(0, {
      timeout: 30_000,
    });
  });
});
