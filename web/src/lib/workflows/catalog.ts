import {
  buildWorkflowPrompt,
  SCHEDULED_TASK_TEMPLATES,
  WORKFLOW_DEFINITIONS,
  type ScheduledTaskTemplateCategory,
} from "@/app/craft/v1/tasks/task-starters";

export type WorkflowExecution = "guided" | "scheduled";

export interface WorkflowCatalogItem {
  id: string;
  name: string;
  description: string;
  category: ScheduledTaskTemplateCategory;
  prompt: string;
  execution: WorkflowExecution;
}

const scheduledItems: readonly WorkflowCatalogItem[] =
  SCHEDULED_TASK_TEMPLATES.map((template) => ({
    id: template.id,
    name: template.name,
    description: template.description,
    category: template.category,
    prompt: template.prompt,
    execution: "scheduled",
  }));

const scheduledIds = new Set(scheduledItems.map((item) => item.id));

const guidedItems: readonly WorkflowCatalogItem[] = WORKFLOW_DEFINITIONS.filter(
  ([id]) => !scheduledIds.has(id)
).map(([id, name, description, category]) => ({
  id,
  name,
  description,
  category,
  prompt: buildWorkflowPrompt(name, description, category),
  execution: "guided",
}));

export const WORKFLOW_CATALOG: readonly WorkflowCatalogItem[] = [
  ...scheduledItems,
  ...guidedItems,
];
