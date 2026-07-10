import type { BackendChatSession, BackendMessage } from "@/app/app/interfaces";
import { ChatSessionSharedStatus } from "@/app/app/interfaces";
import {
  buildChatTaskStarter,
  getScheduledTaskTemplate,
} from "@/app/craft/v1/tasks/task-starters";

function message(
  messageType: string,
  value: string,
  messageId: number
): BackendMessage {
  return {
    message_id: messageId,
    message_type: messageType,
    research_type: null,
    parent_message: null,
    latest_child_message: null,
    message: value,
    rephrased_query: null,
    context_docs: null,
    time_sent: "2026-07-10T12:00:00Z",
    overridden_model: "",
    alternate_assistant_id: null,
    chat_session_id: "session-1",
    citations: null,
    files: [],
    tool_call: null,
    current_feedback: null,
    sub_questions: [],
    comments: null,
    parentMessageId: null,
    refined_answer_improvement: null,
    is_agentic: null,
    preferred_response_id: null,
    model_display_name: null,
    error: null,
  };
}

function session(messages: BackendMessage[]): BackendChatSession {
  return {
    chat_session_id: "session-1",
    description: "Weekly customer escalation review",
    persona_id: 1,
    persona_name: "Onyx",
    messages,
    time_created: "2026-07-10T12:00:00Z",
    time_updated: "2026-07-10T12:00:00Z",
    shared_status: ChatSessionSharedStatus.Private,
    current_temperature_override: null,
    owner_name: "owner@example.com",
    packets: [],
  };
}

describe("scheduled task starters", () => {
  it("builds an editable task prompt from user and assistant turns", () => {
    const result = buildChatTaskStarter(
      session([
        message("system", "internal instructions", 1),
        message("user", "Review unresolved escalations each Friday.", 2),
        message("assistant", "I will group them by owner and severity.", 3),
        message("tool", "private tool output", 4),
      ])
    );

    expect(result.name).toBe("Weekly customer escalation review");
    expect(result.prompt).toContain(
      "User:\nReview unresolved escalations each Friday."
    );
    expect(result.prompt).toContain(
      "Assistant:\nI will group them by owner and severity."
    );
    expect(result.prompt).not.toContain("internal instructions");
    expect(result.prompt).not.toContain("private tool output");
  });

  it("bounds conversation context while retaining the latest request", () => {
    const result = buildChatTaskStarter(
      session([
        message("user", "old ".repeat(4_000), 1),
        message("assistant", "middle ".repeat(2_000), 2),
        message("user", "LATEST REQUEST MUST REMAIN", 3),
      ])
    );

    expect(result.prompt.length).toBeLessThan(13_000);
    expect(result.prompt).toContain("LATEST REQUEST MUST REMAIN");
    expect(result.prompt).toContain("Earlier conversation omitted");
  });

  it("looks up only known templates", () => {
    expect(getScheduledTaskTemplate("daily-briefing")?.name).toBe(
      "Daily company briefing"
    );
    expect(getScheduledTaskTemplate("does-not-exist")).toBeUndefined();
  });
});
