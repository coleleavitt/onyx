import { expect, Page, test } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { loginAs } from "@tests/e2e/utils/auth";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

type SendChatMessagePayload = {
  llm_override?: {
    model_provider?: string | null;
    model_version?: string | null;
  } | null;
  llm_overrides?: Array<{
    model_provider?: string | null;
    model_version?: string | null;
    display_name?: string | null;
  }> | null;
};

function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function mockSingleModelStream(): string {
  return [
    { user_message_id: 501, reserved_assistant_message_id: 502 },
    {
      placement: { turn_index: 0, tab_index: 0, model_index: 0 },
      obj: {
        type: "message_start",
        id: "mock-502",
        content: "",
        final_documents: null,
      },
    },
    {
      placement: { turn_index: 0, tab_index: 0, model_index: 0 },
      obj: { type: "message_delta", content: "mock multi-model response" },
    },
    {
      placement: { turn_index: 0, tab_index: 0, model_index: null },
      obj: { type: "stop", stop_reason: "finished" },
    },
  ]
    .map((packet) => JSON.stringify(packet))
    .join("\n");
}

async function createPublicProvider(
  page: Page,
  providerName: string,
  modelName: string
): Promise<number> {
  const response = await page.request.put(
    "/api/admin/llm/provider?is_creation=true",
    {
      data: {
        name: providerName,
        provider: "openai",
        api_key: "e2e-placeholder-api-key-not-used",
        default_model_name: modelName,
        is_public: true,
        groups: [],
        personas: [],
        model_configurations: [{ name: modelName, is_visible: true }],
      },
    }
  );
  expect(response.ok()).toBeTruthy();
  const body = (await response.json()) as { id: number };
  return body.id;
}

async function waitForVisibleModel(page: Page, modelName: string): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await page.request.get("/api/llm/provider");
        if (!response.ok()) return false;
        const data = (await response.json()) as {
          providers: Array<{
            model_configurations: Array<{ name: string; is_visible: boolean }>;
          }>;
        };
        return data.providers.some((provider) =>
          provider.model_configurations.some(
            (model) => model.name === modelName && model.is_visible
          )
        );
      },
      { timeout: 30000 }
    )
    .toBe(true);
}

async function openModelPicker(page: Page): Promise<void> {
  await page.getByTestId("model-selector").getByRole("button").first().click();
  await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
}

test.describe("Multi-model picker", () => {
  let providerId: number | null = null;

  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
    await loginAs(page, "admin");
  });

  test.afterEach(async ({ page }) => {
    if (providerId !== null) {
      await loginAs(page, "admin");
      await new OnyxApiClient(page.request).deleteProvider(providerId, {
        force: true,
      });
      providerId = null;
    }
  });

  test("adding a second model sends multi-model overrides", async ({ page }) => {
    const providerName = uniqueName("PW Multi Picker Provider");
    const extraModelName = uniqueName("pw-multi-picker-model");
    providerId = await createPublicProvider(page, providerName, extraModelName);
    await waitForVisibleModel(page, extraModelName);

    const chat = new ChatPage(page);
    await chat.goto();

    await openModelPicker(page);
    const dialog = page.locator('[role="dialog"]');
    await dialog.getByPlaceholder("Search models...").fill(extraModelName);
    const extraOption = dialog.locator('[data-interactive-state="empty"]').first();
    await expect(extraOption).toBeVisible({ timeout: 15000 });
    await extraOption.click();

    await expect(page.getByTestId("model-selector")).toContainText("GPT-5.5");
    await page.keyboard.press("Escape");
    await page.waitForSelector('[role="dialog"]', { state: "hidden" });

    const capturedPayloads: SendChatMessagePayload[] = [];
    await page.route("**/api/chat/send-chat-message", async (route) => {
      capturedPayloads.push(
        route.request().postDataJSON() as SendChatMessagePayload
      );
      await route.fulfill({
        status: 200,
        contentType: "text/plain",
        body: mockSingleModelStream(),
      });
    });

    await chat.inputBar.fill("Compare these two models.");
    await chat.inputBar.clickSend();

    await expect.poll(() => capturedPayloads.length).toBeGreaterThan(0);
    const capturedPayload = capturedPayloads[0];
    expect(capturedPayload?.llm_override ?? null).toBeNull();
    expect(capturedPayload?.llm_overrides).toHaveLength(2);
    expect(
      capturedPayload?.llm_overrides?.map((override) => override.model_version)
    ).toEqual(expect.arrayContaining(["gpt-5.5", extraModelName]));
  });
});
