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
      `/app/spaces/${slugify(route.spaceName)}-${route.projectId}`
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
      0
    );
    await expect(this.page.getByRole("tab", { name: "Customize" })).toHaveCount(
      0
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
      this.page.getByText("Instructions", { exact: true })
    ).toHaveCount(0);

    await showDetails.click();
    await expect(
      this.page.getByText("Instructions", { exact: true }).first()
    ).toBeVisible();
  }

  async expectDetailSectionsVisible(): Promise<void> {
    await expect(
      this.page.getByText("Links", { exact: true }).first()
    ).toBeVisible();
    await expect(
      this.page.getByText("Skills", { exact: true }).first()
    ).toBeVisible();
    await expect(
      this.page.getByText("Scheduled Tasks", { exact: true }).first()
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
      this.page.getByRole("button", { name: "Add skills" }).first()
    ).toBeEnabled();
    await expect(
      this.page.getByRole("button", { name: "Create scheduled task" }).first()
    ).toBeEnabled();
    await expect(
      this.page.getByText("Link support is coming soon")
    ).toHaveCount(0);
  }

  async openShareDialog(): Promise<Locator> {
    await this.page.getByRole("button", { name: "Share" }).first().click();
    const dialog = this.page.getByRole("dialog", { name: /Share space/i });
    await expect(dialog).toBeVisible();
    return dialog;
  }

  private async wallpaperElementCount(): Promise<number> {
    return await this.page
      .locator("[data-main-container] *")
      .evaluateAll(
        (elements) =>
          elements.filter((element) =>
            getComputedStyle(element).backgroundImage.includes("url(")
          ).length
      );
  }
}
