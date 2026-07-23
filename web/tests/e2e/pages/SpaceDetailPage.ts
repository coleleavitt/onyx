import { expect, type Locator, type Page } from "@playwright/test";

interface SpaceRoute {
  readonly projectId: number;
  readonly spaceName: string;
}

const CHAT_BACKGROUND_API = "/api/user/chat-background";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export class SpaceDetailPage {
  readonly page: Page;
  readonly inputBox: Locator;

  constructor(page: Page) {
    this.page = page;
    this.inputBox = page.locator("#onyx-chat-input-textbox");
  }

  async setChatBackground(chatBackground: string | null): Promise<void> {
    const response = await this.page.request.patch(CHAT_BACKGROUND_API, {
      data: { chat_background: chatBackground },
    });
    expect(response.ok()).toBeTruthy();
  }

  async goto(route: SpaceRoute): Promise<void> {
    await this.page.goto(
      `/app/spaces/${slugify(route.spaceName)}-${route.projectId}`,
    );
    await this.page.waitForLoadState("networkidle");
  }

  async reload(): Promise<void> {
    await this.page.reload();
    await this.page.waitForLoadState("networkidle");
  }

  async expectWallpaperVisible(): Promise<void> {
    await expect
      .poll(async () => await this.wallpaperElementCount())
      .toBeGreaterThan(0);
  }

  async expectMainColumnWithoutDuplicateTabs(): Promise<void> {
    await expect(this.page.getByRole("tab", { name: "Threads" })).toHaveCount(
      0,
    );
    await expect(this.page.getByRole("tab", { name: "Customize" })).toHaveCount(
      0,
    );
    await expect(this.inputBox).toBeVisible();
  }

  async collapseAndExpandDetailsPanel(): Promise<void> {
    const hideDetails = this.page.getByRole("button", {
      name: "Hide space details",
    });
    await expect(hideDetails).toBeVisible();
    await hideDetails.click();

    const showDetails = this.page.getByRole("button", {
      name: "Show space details",
    });
    await expect(showDetails).toBeVisible();
    await expect(
      this.page.getByText("Instructions", { exact: true }),
    ).toHaveCount(0);

    await showDetails.click();
    await expect(
      this.page.getByText("Instructions", { exact: true }).first(),
    ).toBeVisible();
  }

  async expectDetailSectionsVisible(): Promise<void> {
    await expect(
      this.page.getByText("Connected sources", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      this.page.getByText("Links", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      this.page.getByText("Skills", { exact: true }).first(),
    ).toBeVisible();
    await expect(
      this.page.getByText("Scheduled Tasks", { exact: true }).first(),
    ).toBeVisible();
  }

  async addLink(inputUrl: string): Promise<void> {
    await this.page.getByRole("button", { name: "Add link" }).first().click();
    await this.page
      .getByPlaceholder("Paste a website URL")
      .first()
      .fill(inputUrl);
    await this.page.getByRole("button", { name: /^Add$/ }).first().click();
  }

  async expectLinkVisible(url: string): Promise<void> {
    await expect(this.page.getByText(url).first()).toBeVisible({
      timeout: 10_000,
    });
  }

  async expectAddedByVisible(): Promise<void> {
    await expect(this.page.getByText(/Added by/i).first()).toBeVisible();
  }

  async removeLink(url: string): Promise<void> {
    const linkActions = this.page
      .getByRole("button", {
        name: new RegExp(`^Link actions for ${escapeRegExp(url)}$`),
      })
      .first();
    await linkActions.click();
    await this.page
      .getByRole("button", { name: "Remove link" })
      .first()
      .click();
  }

  async expectLinkGone(url: string): Promise<void> {
    await expect(this.page.getByText(url)).toHaveCount(0);
  }

  async expectAddControlsEnabled(): Promise<void> {
    await expect(
      this.page.getByRole("button", { name: "Add skills" }).first(),
    ).toBeEnabled();
    await expect(
      this.page.getByRole("button", { name: "Create scheduled task" }).first(),
    ).toBeEnabled();
    await expect(
      this.page.getByText("Link support is coming soon"),
    ).toHaveCount(0);
  }

  async openConnectedSourcesPickerAndExpectRealState(): Promise<void> {
    await this.page
      .getByRole("button", { name: "Add connected source" })
      .first()
      .click();

    const dialog = this.page.getByRole("dialog", {
      name: /Add knowledge to space/i,
    });
    await expect(dialog).toBeVisible();
    await expect(
      dialog.getByRole("tab", { name: "Connected sources" }),
    ).toBeVisible();
    await expect(
      dialog.getByRole("tab", { name: "Uploaded files" }),
    ).toBeVisible();

    const emptyState = dialog.getByText(
      "No indexed connector sources are available.",
    );
    const sourceSidebar = dialog.locator(
      '[aria-label="space-connected-source-sidebar"]',
    );
    const rows = dialog.locator(".content-column-layout .table-row-layout");
    const emptyBrowserText = dialog.getByText(
      /No items in this folder|Select a folder to browse documents/i,
    );
    const branchState: { value: "empty" | "browser" | "loading" } = {
      value: "loading",
    };
    await expect
      .poll(async () => {
        if (await emptyState.isVisible().catch(() => false)) {
          branchState.value = "empty";
        } else if ((await rows.count()) > 1) {
          branchState.value = "browser";
        } else if (
          (await sourceSidebar.isVisible().catch(() => false)) &&
          (await emptyBrowserText.isVisible().catch(() => false))
        ) {
          branchState.value = "empty";
        } else {
          branchState.value = "loading";
        }
        return branchState.value;
      })
      .not.toBe("loading");

    await dialog.getByRole("tab", { name: "Uploaded files" }).click();
    await expect(
      dialog.getByRole("button", { name: "Upload local files" }),
    ).toBeVisible();
    await expect(
      dialog.getByRole("button", { name: "Upload local folder" }),
    ).toBeVisible();

    if (branchState.value === "empty") {
      console.log("space connected sources smoke: empty-state");
      await this.page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      return;
    }

    await dialog.getByRole("tab", { name: "Connected sources" }).click();
    await expect.poll(async () => await rows.count()).toBeGreaterThan(1);
    const selectableCount = await rows.count();
    expect(selectableCount).toBeGreaterThan(1);
    const firstSelectable = rows.nth(1);
    const selectedLabel = (await firstSelectable.innerText())
      .split("\n")
      .map((part) => part.trim())
      .find((part) => part && part !== "—");
    expect(selectedLabel).toBeTruthy();
    await firstSelectable.click();
    await expect(dialog.getByText(/items? selected/)).toBeVisible();
    await dialog.getByRole("button", { name: "Save" }).click();
    await expect(dialog).toHaveCount(0);

    await this.reload();
    await expect(
      this.page.getByText("Connected sources", { exact: true }).first(),
    ).toBeVisible();
    await expect(this.page.getByText(selectedLabel!).first()).toBeVisible();
    console.log(`space connected sources smoke: selected ${selectedLabel}`);
  }

  async openAddFilesPopoverAndExpectCompact(): Promise<void> {
    await this.page.getByRole("button", { name: "Add files" }).first().click();

    const popover = this.page
      .locator("[data-radix-popper-content-wrapper]")
      .filter({ hasText: "Upload Files" })
      .first();
    await expect(
      popover.getByText("Upload Files", { exact: true }).first(),
    ).toBeVisible();

    const popoverWidth = await popover.evaluate(
      (element) => element.getBoundingClientRect().width,
    );
    expect(popoverWidth).toBeLessThanOrEqual(224);

    await this.page.keyboard.press("Escape");
    await expect(popover).toHaveCount(0);
  }

  async updateDetailsDescription(description: string): Promise<void> {
    await this.page.getByRole("button", { name: "Edit details" }).click();

    const dialog = this.page.getByRole("dialog", {
      name: /Edit space details/i,
    });
    await expect(dialog).toBeVisible();

    const dialogWidth = await dialog.evaluate(
      (element) => element.getBoundingClientRect().width,
    );
    expect(dialogWidth).toBeGreaterThanOrEqual(560);

    const descriptionInput = dialog.locator('textarea[name="description"]');
    await expect(descriptionInput).toBeVisible();
    const descriptionHeight = await descriptionInput.evaluate(
      (element) => element.getBoundingClientRect().height,
    );
    expect(descriptionHeight).toBeGreaterThanOrEqual(90);
    const descriptionWidth = await descriptionInput.evaluate(
      (element) => element.getBoundingClientRect().width,
    );
    expect(descriptionWidth).toBeGreaterThanOrEqual(500);

    await descriptionInput.fill(description);
    await dialog.getByRole("button", { name: "Save" }).click();
    await expect(dialog).toHaveCount(0);
    await expect(this.page.getByText(description).first()).toBeVisible();
  }

  async openShareDialog(): Promise<Locator> {
    const shareSpaceButton = this.page
      .getByRole("button", { name: "Share space" })
      .first();
    if (await shareSpaceButton.isVisible().catch(() => false)) {
      await shareSpaceButton.click();
    } else {
      await this.page.getByRole("button", { name: "Share" }).first().click();
    }
    const dialog = this.page.getByRole("dialog", { name: /Share space/i });
    await expect(dialog).toBeVisible();
    return dialog;
  }

  private async wallpaperElementCount(): Promise<number> {
    try {
      return await this.page
        .locator("[data-main-container] *")
        .evaluateAll(
          (elements) =>
            elements.filter((element) =>
              getComputedStyle(element).backgroundImage.includes("url("),
            ).length,
        );
    } catch {
      // The space route can still be hydrating/navigating when the poll starts.
      // Treat that poll iteration as "not visible yet" rather than failing the
      // whole smoke before the route settles.
      return 0;
    }
  }
}
