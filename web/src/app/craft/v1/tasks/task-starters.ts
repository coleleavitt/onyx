import type { BackendChatSession } from "@/app/app/interfaces";
import type {
  EditorMode,
  EditorPayload,
} from "@/app/craft/v1/tasks/interfaces";

export type ScheduledTaskTemplateCategory =
  | "Briefings"
  | "Knowledge"
  | "Operations"
  | "Risk"
  | "Utility"
  | "Finance"
  | "Careers"
  | "Research"
  | "Legal"
  | "Productivity"
  | "Writing"
  | "Sales"
  | "Personal Finance"
  | "Creative"
  | "Marketing"
  | "Media"
  | "Recruiting"
  | "Health"
  | "Investments";

export interface ScheduledTaskTemplate {
  id: string;
  name: string;
  description: string;
  category: ScheduledTaskTemplateCategory;
  prompt: string;
  mode: EditorMode;
  payload: EditorPayload;
}

export type WorkflowDefinition = readonly [
  id: string,
  name: string,
  description: string,
  category: ScheduledTaskTemplateCategory,
];

export const WORKFLOW_DEFINITIONS: readonly WorkflowDefinition[] = [
  [
    "prompt-refinement",
    "Prompt refinement",
    "Improve any AI prompt with proven techniques for clarity, specificity, and effectiveness.",
    "Utility",
  ],
  [
    "billable-hours",
    "Billable hours",
    "Estimate billable hours for a work product with a detailed breakdown by task, role, and complexity.",
    "Utility",
  ],
  [
    "message-polish",
    "Message polish",
    "Refine drafts with adjustable tone, audience targeting, and custom instructions.",
    "Utility",
  ],
  [
    "background-removal",
    "Background removal",
    "Produce a clean image with the background removed and preserve edge detail.",
    "Utility",
  ],
  [
    "candidate-sourcing",
    "Candidate sourcing",
    "Build a hiring rubric, find candidates, verify evidence, and return a ranked shortlist.",
    "Recruiting",
  ],
  [
    "autonomous-candidate-sourcer",
    "Autonomous Candidates Sourcer",
    "Iteratively source, verify, score, and track candidates, then prepare review batches.",
    "Recruiting",
  ],
  [
    "final-pass",
    "Final pass",
    "Review a document page by page for errors, inconsistencies, unsupported claims, and release blockers.",
    "Finance",
  ],
  [
    "property-risk-review",
    "Property risk review",
    "Review commercial real estate diligence and produce a prioritized risk register and gap list.",
    "Finance",
  ],
  [
    "three-statement-model",
    "Three-statement model",
    "Build a linked financial model with editable assumptions, valuation outputs, and source support.",
    "Finance",
  ],
  [
    "credit-memo",
    "Credit memo",
    "Draft a credit committee memo covering borrower quality, structure, downside risk, and diligence.",
    "Finance",
  ],
  [
    "customer-cube-review",
    "Customer cube review",
    "Review financial, customer, contract, legal, and HR diligence files for risks and gaps.",
    "Finance",
  ],
  [
    "real-estate-ic-memo",
    "Real estate IC memo",
    "Turn underwriting and diligence into a decision-ready investment committee memo.",
    "Finance",
  ],
  [
    "internship-housing-finder",
    "Internship housing finder",
    "Find and rank short-term housing against budget, commute, dates, and constraints.",
    "Careers",
  ],
  [
    "job-finder",
    "Job finder",
    "Find relevant jobs and internships from a resume with match rationale and source links.",
    "Careers",
  ],
  [
    "interview-prep",
    "Interview prep",
    "Prepare company-specific technical, case, behavioral, and modeling interview practice.",
    "Careers",
  ],
  [
    "cover-letter-generator",
    "Cover letter generator",
    "Generate a tailored cover letter from a resume and job description.",
    "Careers",
  ],
  [
    "linkedin-headshot-generator",
    "LinkedIn headshot generator",
    "Turn a supplied photo into a natural professional headshot while preserving identity.",
    "Careers",
  ],
  [
    "scholarship-finder",
    "Scholarship and fellowship finder",
    "Find relevant scholarships and fellowships with deadlines and eligibility signals.",
    "Careers",
  ],
  [
    "compliance-monitor",
    "Compliance monitor",
    "Monitor regulatory sources and alert on material changes relevant to a compliance focus.",
    "Research",
  ],
  [
    "prospect-research",
    "Prospect research",
    "Identify decision-makers and build an evidence-backed prospect profile.",
    "Research",
  ],
  [
    "sourcing-screen",
    "Sourcing screen",
    "Build an investable target universe and monitor transaction-relevant company signals.",
    "Research",
  ],
  [
    "intelligence-monitor",
    "Intelligence monitor",
    "Monitor topics, entities, markets, or sectors and deliver scheduled evidence-backed updates.",
    "Research",
  ],
  [
    "property-analysis",
    "Property analysis",
    "Analyze a property using comparable sales, yields, demographics, and market trends.",
    "Research",
  ],
  [
    "key-driver-analysis",
    "Key driver analysis",
    "Identify the fundamentals, estimates, peers, macro factors, and guidance moving a stock.",
    "Research",
  ],
  [
    "contract-review",
    "Contract review",
    "Review a contract against a playbook with clause risks, redlines, and prioritized issues.",
    "Legal",
  ],
  [
    "litigation-prep",
    "Litigation prep",
    "Summarize pleadings, build counterarguments and defenses, and prepare deposition questions.",
    "Legal",
  ],
  [
    "due-diligence",
    "Due diligence",
    "Investigate a company across market, team, financial, customer, IP, and regulatory risk.",
    "Legal",
  ],
  [
    "slide-creation",
    "Slide creation",
    "Research a topic, distill the key insights, and produce a presentation-ready outline.",
    "Productivity",
  ],
  [
    "filetype-converter",
    "Filetype converter",
    "Convert an uploaded document into requested formats while preserving structure.",
    "Productivity",
  ],
  [
    "website-builder",
    "Website builder",
    "Turn a website brief into an implementation plan, build steps, and deployment checklist.",
    "Productivity",
  ],
  [
    "sales-prep",
    "Sales prep",
    "Research a company and produce a call-ready account profile and talking points.",
    "Productivity",
  ],
  [
    "memo-draft",
    "Memo draft",
    "Draft an investment memo from a target company, precedent structure, and current research.",
    "Productivity",
  ],
  [
    "document-summary",
    "Document summary",
    "Create an exportable summary with key metrics, findings, and takeaways.",
    "Writing",
  ],
  [
    "newsletter-creator",
    "Newsletter creator",
    "Turn topics, company updates, and curated links into a publication-ready newsletter.",
    "Writing",
  ],
  [
    "outreach-message",
    "Outreach message",
    "Generate personalized outreach for a list of people or companies and a defined objective.",
    "Sales",
  ],
  [
    "competitive-intelligence",
    "Competitive intelligence",
    "Monitor launches, pricing changes, and partnerships with material-change alerts.",
    "Sales",
  ],
  [
    "account-outreach",
    "Account outreach",
    "Research target accounts and generate personalized multistep outreach campaigns.",
    "Sales",
  ],
  [
    "customer-demo",
    "Customer demo",
    "Create customer-specific use cases, talking points, and a tailored demo script.",
    "Sales",
  ],
  [
    "account-profiles",
    "Account profiles",
    "Summarize an account using connected apps and public evidence for sales preparation.",
    "Sales",
  ],
  [
    "daily-personal-finance-digest",
    "Daily personal finance digest",
    "Summarize balances, recent spending, and notable account activity each day.",
    "Personal Finance",
  ],
  [
    "run-rate-dashboard",
    "Run Rate Dashboard",
    "Annualize spending pace for this week, month, and year from connected transactions.",
    "Personal Finance",
  ],
  [
    "cash-flow-forecast",
    "Cash flow forecast",
    "Forecast available cash after upcoming bills, expected income, and known transfers.",
    "Personal Finance",
  ],
  [
    "subscription-cleanup",
    "Subscription cleanup",
    "Identify recurring charges, flag forgotten subscriptions, and prioritize cancellations.",
    "Personal Finance",
  ],
  [
    "spending-review",
    "Spending review",
    "Explain where money went, what changed, and which categories drove the change.",
    "Personal Finance",
  ],
  [
    "net-worth-dashboard",
    "Net worth dashboard",
    "Track assets, debts, and cash in a concise source-backed summary.",
    "Personal Finance",
  ],
  [
    "brand-reputation",
    "Brand reputation",
    "Analyze brand sentiment across news, reviews, and social sources with competitor context.",
    "Marketing",
  ],
  [
    "store-optimizer",
    "Store optimizer",
    "Review a storefront and recommend listing, SEO, imagery, and positioning improvements.",
    "Marketing",
  ],
  [
    "product-teardown",
    "Product teardown",
    "Analyze product pricing, features, onboarding, and positioning with captured evidence.",
    "Marketing",
  ],
  [
    "brand-inspiration",
    "Brand inspiration",
    "Build an annotated reference set of competitor copy, calls to action, and creative patterns.",
    "Marketing",
  ],
  [
    "keyword-generator",
    "Keyword generator",
    "Analyze competitor advertising and produce a prioritized keyword strategy.",
    "Marketing",
  ],
  [
    "thumbnail-creator",
    "Thumbnail creator",
    "Create multiple thumbnail directions with distinct hooks, layouts, and text treatments.",
    "Media",
  ],
  [
    "product-photos",
    "Product photos",
    "Generate product-image directions across lighting, angle, and background variations.",
    "Media",
  ],
  [
    "creative-slide-creation",
    "Slide creation",
    "Research a topic, distill the key insights, and create a polished visual narrative.",
    "Creative",
  ],
  [
    "creative-website-builder",
    "Website builder",
    "Turn a website brief into a deliberate visual direction and an implementation-ready build plan.",
    "Creative",
  ],
  [
    "health-review",
    "Health review",
    "Organize supplied health information into questions, trends, and clinician discussion points.",
    "Health",
  ],
  [
    "nutrition-planner",
    "Nutrition planner",
    "Create a meal plan aligned with stated goals, constraints, and supplied lab context.",
    "Health",
  ],
  [
    "lab-results-interpreter",
    "Lab results interpreter",
    "Explain lab results, trends, and follow-up questions without replacing medical advice.",
    "Health",
  ],
  [
    "visit-prep-assistant",
    "Visit prep assistant",
    "Prepare a concise briefing and prioritized questions for an upcoming appointment.",
    "Health",
  ],
  [
    "fitness-coach",
    "Fitness coach",
    "Build a progressive workout plan around current activity, goals, and constraints.",
    "Health",
  ],
  [
    "sleep-recovery-coach",
    "Sleep & recovery coach",
    "Analyze sleep and recovery context and suggest measurable improvements.",
    "Health",
  ],
  [
    "etf-overlap",
    "ETF overlap",
    "Compare holdings and exposures to explain overlap, redundancy, and diversification.",
    "Investments",
  ],
];

export function buildWorkflowPrompt(
  name: string,
  description: string,
  category: ScheduledTaskTemplateCategory
): string {
  return [
    `Run the ${name} workflow.`,
    description,
    `Use current connected and public sources appropriate for ${category.toLowerCase()}. Separate verified facts from assumptions, preserve direct source links, call out missing inputs, and finish with concrete next actions.`,
  ].join("\n\n");
}

const CATALOG_AUTOMATION_SCHEDULES = new Map<
  string,
  { mode: EditorMode; payload: EditorPayload }
>([
  [
    "compliance-monitor",
    {
      mode: "daily_weekly",
      payload: { time_of_day: "08:30", weekdays: [1, 2, 3, 4, 5] },
    },
  ],
  [
    "intelligence-monitor",
    {
      mode: "daily_weekly",
      payload: { time_of_day: "08:30", weekdays: [1, 2, 3, 4, 5] },
    },
  ],
  [
    "competitive-intelligence",
    {
      mode: "daily_weekly",
      payload: { time_of_day: "09:00", weekdays: [1] },
    },
  ],
  [
    "sourcing-screen",
    {
      mode: "daily_weekly",
      payload: { time_of_day: "09:00", weekdays: [1] },
    },
  ],
  [
    "daily-personal-finance-digest",
    {
      mode: "daily_weekly",
      payload: { time_of_day: "08:00", weekdays: [1, 2, 3, 4, 5] },
    },
  ],
]);

const CATALOG_AUTOMATION_TEMPLATES: readonly ScheduledTaskTemplate[] =
  WORKFLOW_DEFINITIONS.flatMap(([id, name, description, category]) => {
    const schedule = CATALOG_AUTOMATION_SCHEDULES.get(id);
    return schedule
      ? [
          {
            id,
            name,
            description,
            category,
            prompt: buildWorkflowPrompt(name, description, category),
            ...schedule,
          },
        ]
      : [];
  });

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
  ...CATALOG_AUTOMATION_TEMPLATES,
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
