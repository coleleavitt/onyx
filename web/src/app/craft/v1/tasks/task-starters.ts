import type { BackendChatSession } from "@/app/app/interfaces";
import type {
  EditorMode,
  EditorPayload,
} from "@/app/craft/v1/tasks/interfaces";

export type ScheduledTaskTemplateCategory =
  | "Briefings"
  | "Knowledge"
  | "Operations"
  | "Risk";

export interface ScheduledTaskTemplate {
  id: string;
  name: string;
  description: string;
  category: ScheduledTaskTemplateCategory;
  prompt: string;
  mode: EditorMode;
  payload: EditorPayload;
}

export const SCHEDULED_TASK_TEMPLATES: readonly ScheduledTaskTemplate[] = [
  {
    id: "daily-briefing",
    name: "Daily company briefing",
    description: "Summarize important company updates every weekday morning.",
    category: "Briefings",
    prompt:
      "Create a concise company briefing from connected sources. Highlight new or materially changed information, decisions, deadlines, and blockers. Group the result by topic, link every factual claim to its source, and omit items that have not changed since the previous run.",
    mode: "daily_weekly",
    payload: { time_of_day: "08:00", weekdays: [1, 2, 3, 4, 5] },
  },
  {
    id: "sharepoint-change-digest",
    name: "SharePoint change digest",
    description: "Review recently changed knowledge and call out what matters.",
    category: "Knowledge",
    prompt:
      "Review SharePoint content added or materially changed since the previous run. Summarize the important changes, identify the owning site and document, call out conflicting or superseded guidance, and include direct source links. Ignore routine file churn with no meaningful content change.",
    mode: "daily_weekly",
    payload: { time_of_day: "09:00", weekdays: [1] },
  },
  {
    id: "weekly-status-review",
    name: "Weekly status review",
    description:
      "Turn project activity into decisions, risks, and next actions.",
    category: "Operations",
    prompt:
      "Prepare a weekly status review from connected project sources. List completed work, active work, blocked work, decisions needed, owners, and due dates. Separate confirmed facts from assumptions and cite the underlying source for each status item.",
    mode: "daily_weekly",
    payload: { time_of_day: "15:00", weekdays: [5] },
  },
  {
    id: "compliance-watch",
    name: "Compliance watch",
    description:
      "Surface policy changes and unresolved compliance obligations.",
    category: "Risk",
    prompt:
      "Review connected compliance and policy sources for new requirements, changed guidance, approaching deadlines, and unresolved action items. Prioritize by impact and urgency, name the affected team or owner when available, and include source links. Do not treat unchanged historical documents as new alerts.",
    mode: "daily_weekly",
    payload: { time_of_day: "08:30", weekdays: [1, 2, 3, 4, 5] },
  },
  {
    id: "operations-queue-review",
    name: "Operations queue review",
    description: "Check operational queues for stale, blocked, or urgent work.",
    category: "Operations",
    prompt:
      "Review connected operational queues and trackers. Report overdue, blocked, high-priority, and unassigned work; group findings by owner; and recommend the next concrete action. Include source links and suppress unchanged healthy items.",
    mode: "interval",
    payload: { unit: "hours", every: 4 },
  },
] as const;

const CHAT_CONTEXT_LIMIT = 11_000;
const TASK_NAME_LIMIT = 80;
const TASK_CONTEXT_MESSAGE_LIMIT = 20;
const CONVERSATION_MESSAGE_TYPES = new Set(["user", "assistant"]);

export function getScheduledTaskTemplate(
  templateId: string | null
): ScheduledTaskTemplate | undefined {
  if (!templateId) return undefined;
  return SCHEDULED_TASK_TEMPLATES.find(
    (template) => template.id === templateId
  );
}

function roleLabel(messageType: string): string {
  return messageType === "user" ? "User" : "Assistant";
}

export function buildChatTaskStarter(session: BackendChatSession): {
  name: string;
  prompt: string;
} {
  const transcript = session.messages
    .filter(
      (message) =>
        CONVERSATION_MESSAGE_TYPES.has(message.message_type) &&
        message.message.trim().length > 0
    )
    .slice(-TASK_CONTEXT_MESSAGE_LIMIT)
    .map(
      (message) =>
        `${roleLabel(message.message_type)}:\n${message.message.trim()}`
    )
    .join("\n\n");

  const boundedTranscript =
    transcript.length > CHAT_CONTEXT_LIMIT
      ? `[Earlier conversation omitted]\n${transcript.slice(-CHAT_CONTEXT_LIMIT)}`
      : transcript;
  const context = boundedTranscript || "No conversational messages were found.";
  const name =
    session.description.trim().slice(0, TASK_NAME_LIMIT) ||
    "Task from conversation";

  return {
    name,
    prompt: [
      "Run the recurring workflow described in the conversation below.",
      "Use current information from connected sources at run time, distinguish facts from assumptions, and include source links in the result.",
      "Review and edit this prompt before saving if the conversation does not define a clear recurring outcome.",
      "<conversation_context>",
      context,
      "</conversation_context>",
    ].join("\n\n"),
  };
}
