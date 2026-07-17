import { expect, test } from "@playwright/test";
import { ChatPage } from "@tests/e2e/chat/ChatPage";
import { AgentEditorPage } from "@tests/e2e/pages/AgentEditorPage";
import { loginAs } from "@tests/e2e/utils/auth";
import { OnyxApiClient } from "@tests/e2e/utils/onyxApiClient";

// End-to-end coverage for the core "create a custom agent through the UI and
// chat with it" flow. It clicks through the Agents sidebar into the editor,
// fills the basics (name, description, system prompt), creates the agent, then
// exercises a LIVE chat turn to prove the system prompt is actually wired into
// the model call: the prompt forces the answer to contain the word PINEAPPLE,
// so a passing run confirms both the UI creation path and prompt plumbing.
test.describe("Create a custom agent through the UI", () => {
  test("creates an agent and its system prompt drives the live answer", async ({
    page,
  }) => {
    test.setTimeout(240_000);

    // Distinctive, unique suffix so concurrent runs / leftovers never collide.
    const unique = `agent-create-ui-${Date.now()}`;
    const agentName = `QA Smoke Agent ${unique}`;
    const agentDescription = `Smoke-test agent for ${unique}`;
    const systemPrompt =
      "Always reply with the word PINEAPPLE somewhere in your answer.";

    let agentId: number | null = null;
    let chatId: string | null = null;

    await page.context().clearCookies();
    await loginAs(page, "admin");

    const chat = new ChatPage(page);
    const editor = new AgentEditorPage(page);

    try {
      // Land on the app so the sidebar is available, then click through the
      // Agents surface into the create editor (the real end-user path).
      await chat.goto();
      await editor.openFromSidebar();

      // Fill only the basics; skip tools, knowledge, and labels.
      await editor.fill({
        name: agentName,
        description: agentDescription,
        instructions: systemPrompt,
      });

      // Create; the app immediately opens a chat scoped to the new agent.
      // Read the new agent's id from the create POST response rather than the
      // resulting URL: the response resolves before the client-side redirect,
      // so the id is recorded for cleanup even if the SPA navigation to
      // /app?agentId= is slow to land (or never lands) under a loaded web tier.
      const personaResponsePromise = page.waitForResponse(
        (response) =>
          response.request().method() === "POST" &&
          new URL(response.url()).pathname === "/api/persona",
        { timeout: 60_000 }
      );

      const navigation = editor.create();

      const personaResponse = await personaResponsePromise;
      expect(personaResponse.ok()).toBeTruthy();
      agentId = ((await personaResponse.json()) as { id: number }).id;
      expect(agentId).toBeGreaterThan(0);

      // Now that the id is safely recorded for cleanup, require the navigation
      // to land on the freshly created agent's chat.
      await navigation;

      // The agent's page shows its name — proves navigation landed on the
      // freshly created agent rather than the default assistant.
      const nameDisplay = page.getByTestId("agent-name-display");
      await expect(nameDisplay).toBeVisible({ timeout: 15_000 });
      await expect(nameDisplay).toContainText(agentName);

      // Start the chat: send a neutral prompt and let the live LLM answer.
      await chat.inputBar.textbox.waitFor({ state: "visible", timeout: 15_000 });
      await chat.inputBar.fill("Say hello.");
      await chat.inputBar.clickSend();

      // A persisted chat session appears in the URL once the turn starts;
      // capture it for cleanup.
      await page.waitForURL(/chatId=/, { timeout: 30_000 });
      chatId = new URL(page.url()).searchParams.get("chatId");
      expect(chatId).not.toBeNull();

      // The onyx-ai-message test id is only attached once the message is
      // complete, so this assertion waits for the full streamed answer. The
      // system prompt forces PINEAPPLE into every reply — its presence proves
      // the prompt was applied to the live model call.
      await expect(chat.aiMessage(0)).toContainText(/pineapple/i, {
        timeout: 180_000,
      });
    } finally {
      const cleanup = new OnyxApiClient(page.request);
      if (chatId !== null) {
        await cleanup.deleteChatSession(chatId);
      }
      // Fall back to a name lookup if the id was never captured (e.g. the
      // create POST response was missed) so a created agent is never orphaned.
      if (agentId === null) {
        const orphan = (await cleanup.findAgentByName(agentName)) as {
          id: number;
        } | null;
        if (orphan) {
          agentId = orphan.id;
        }
      }
      if (agentId !== null) {
        await cleanup.deleteAgent(agentId);
      }
    }
  });
});
