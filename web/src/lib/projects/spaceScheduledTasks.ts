import type {
  ScheduledTaskListItem,
  ScheduledTaskStatus,
} from "@/app/craft/v1/tasks/interfaces";

/**
 * Space-scoped scheduled tasks.
 *
 * The scheduled-tasks backend does not (yet) store a project/space id on a
 * task, so — as recorded in the goal's Risks section — a task is associated
 * with a space via a stable, human-visible name tag: `[space:{id}]`. The
 * create affordance stamps this tag; these pure helpers detect and filter by
 * it, and strip it for display. Keeping this in a pure module makes the mapping
 * unit-testable without the DOM or the tasks API.
 */

const SPACE_TAG_RE = /\[space:(\d+)\]/i;

/** Build the name tag that scopes a scheduled task to a space. */
export function spaceTaskTag(projectId: number): string {
  return `[space:${projectId}]`;
}

/** Parse the space id out of a task name, or null when it carries no tag. */
export function spaceIdFromTaskName(name: string): number | null {
  const match = name.match(SPACE_TAG_RE);
  if (!match) return null;
  const id = Number.parseInt(match[1] ?? "", 10);
  return Number.isNaN(id) ? null : id;
}

/** Whether a task is scoped to the given space. */
export function isTaskForSpace(
  task: Pick<ScheduledTaskListItem, "name">,
  projectId: number
): boolean {
  return spaceIdFromTaskName(task.name) === projectId;
}

/** Remove the space tag (and tidy whitespace) for display. */
export function stripSpaceTag(name: string): string {
  return name.replace(SPACE_TAG_RE, "").replace(/\s{2,}/g, " ").trim();
}

/**
 * Stamp a task name with the space tag if it isn't already scoped. Existing
 * tags (even for a different space) are replaced with this space's tag.
 */
export function tagTaskNameForSpace(name: string, projectId: number): string {
  const base = stripSpaceTag(name).trim();
  const tag = spaceTaskTag(projectId);
  return base.length > 0 ? `${base} ${tag}` : tag;
}

/** Select only the tasks scoped to the given space. */
export function filterTasksForSpace<T extends { name: string }>(
  tasks: T[],
  projectId: number
): T[] {
  return tasks.filter((task) => spaceIdFromTaskName(task.name) === projectId);
}

export interface SpaceScheduledTaskGroups<T> {
  active: T[];
  paused: T[];
}

/**
 * Partition a space's scheduled tasks into active vs. paused, preserving order.
 */
export function partitionTasksByStatus<
  T extends { status: ScheduledTaskStatus },
>(tasks: T[]): SpaceScheduledTaskGroups<T> {
  const active: T[] = [];
  const paused: T[] = [];
  for (const task of tasks) {
    if (task.status === "PAUSED") {
      paused.push(task);
    } else {
      active.push(task);
    }
  }
  return { active, paused };
}
