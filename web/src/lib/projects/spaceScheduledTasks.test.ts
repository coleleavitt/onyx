import {
  filterTasksForSpace,
  isTaskForSpace,
  partitionTasksByStatus,
  spaceIdFromTaskName,
  spaceTaskTag,
  stripSpaceTag,
  tagTaskNameForSpace,
} from "@/lib/projects/spaceScheduledTasks";
import type {
  ScheduledTaskListItem,
  ScheduledTaskStatus,
} from "@/app/craft/v1/tasks/interfaces";

/** Minimal scheduled-task factory (only the fields the helpers read). */
function task(
  name: string,
  status: ScheduledTaskStatus = "ACTIVE"
): ScheduledTaskListItem {
  return {
    id: name,
    name,
    human_readable_schedule: "Every day",
    cron_expression: "0 9 * * *",
    editor_mode: "daily_weekly",
    status,
    next_run_at: null,
    last_run: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
  };
}

describe("space scheduled-task tagging", () => {
  it("builds and parses the space tag", () => {
    expect(spaceTaskTag(42)).toBe("[space:42]");
    expect(spaceIdFromTaskName("Weekly report [space:42]")).toBe(42);
    expect(spaceIdFromTaskName("Untagged task")).toBeNull();
  });

  it("detects membership for a specific space", () => {
    expect(isTaskForSpace(task("Report [space:1]"), 1)).toBe(true);
    expect(isTaskForSpace(task("Report [space:1]"), 2)).toBe(false);
    expect(isTaskForSpace(task("Report"), 1)).toBe(false);
  });

  it("strips the tag for display", () => {
    expect(stripSpaceTag("Weekly report [space:42]")).toBe("Weekly report");
    expect(stripSpaceTag("[space:42]")).toBe("");
  });

  it("tags a fresh name and replaces a stale tag", () => {
    expect(tagTaskNameForSpace("Weekly report", 42)).toBe(
      "Weekly report [space:42]"
    );
    // Re-tag to a different space: old tag removed, new applied.
    expect(tagTaskNameForSpace("Weekly report [space:9]", 42)).toBe(
      "Weekly report [space:42]"
    );
  });

  it("filters a mixed list down to the space's tasks only", () => {
    const tasks = [
      task("A [space:1]"),
      task("B [space:2]"),
      task("C"),
      task("D [space:1]"),
    ];
    expect(filterTasksForSpace(tasks, 1).map((t) => t.name)).toEqual([
      "A [space:1]",
      "D [space:1]",
    ]);
  });

  it("partitions into active vs paused preserving order", () => {
    const groups = partitionTasksByStatus([
      task("A", "ACTIVE"),
      task("B", "PAUSED"),
      task("C", "ACTIVE"),
    ]);
    expect(groups.active.map((t) => t.name)).toEqual(["A", "C"]);
    expect(groups.paused.map((t) => t.name)).toEqual(["B"]);
  });
});
