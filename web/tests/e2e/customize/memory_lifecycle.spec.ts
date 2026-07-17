import { expect, test } from "@playwright/test";
import { loginAs } from "@tests/e2e/utils/auth";

// UI proof of the memory lifecycle at /app/customize/memory: add a memory, see
// it render, confirm it survives a reload, edit it, and delete it. The org
// memory-creation policy is enabled by default, so the Add button is active.
test.describe("Memory customize page", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, "admin");
  });

  test("add, persist across reload, edit, and delete a memory", async ({
    page,
  }) => {
    const stamp = Date.now();
    const title = `E2E memory ${stamp}`;
    const content = `The user's e2e marker is ${stamp}.`;
    const editedContent = `The user's updated e2e marker is ${stamp}.`;

    await page.goto("/app/customize/memory");
    const addButton = page.getByRole("button", { name: "Add memory" });
    await expect(addButton).toBeVisible();

    // --- Create ---
    await addButton.click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByPlaceholder("Short, recognizable title").fill(title);
    await dialog.getByPlaceholder("What should Onyx remember?").fill(content);
    await dialog.getByRole("button", { name: "Add memory" }).click();
    await expect(dialog).toBeHidden();

    // The new memory renders as a card.
    await expect(page.getByText(title)).toBeVisible();

    // --- Persists across reload ---
    await page.reload();
    await expect(page.getByText(title)).toBeVisible();

    // --- Edit ---
    await page.getByText(title).click();
    const editDialog = page.getByRole("dialog");
    await expect(editDialog).toBeVisible();
    const contentField = editDialog.getByPlaceholder(
      "What should Onyx remember?"
    );
    await contentField.fill(editedContent);
    await editDialog.getByRole("button", { name: "Save" }).click();
    await expect(editDialog).toBeHidden();
    await expect(page.getByText(editedContent)).toBeVisible();

    // --- Delete ---
    await page.getByText(title).click();
    const deleteDialog = page.getByRole("dialog");
    await deleteDialog.getByRole("button", { name: "Delete" }).click();
    await expect(deleteDialog.getByText("Delete permanently?")).toBeVisible();
    await deleteDialog.getByRole("button", { name: "Delete" }).click();
    await expect(deleteDialog).toBeHidden();

    // The memory is gone.
    await expect(page.getByText(title)).toHaveCount(0);
  });
});
