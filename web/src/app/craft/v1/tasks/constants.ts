/**
 * Constants for the Scheduled Tasks UI.
 */

import type { Route } from "next";

export const TASKS_PATH = "/craft/v1/tasks" as Route;
export const NEW_TASK_PATH = `${TASKS_PATH}/new` as Route;
export const TASK_TEMPLATES_PATH = `${TASKS_PATH}/templates` as Route;

export function newTaskFromTemplatePath(templateId: string): Route {
  return `${NEW_TASK_PATH}?template=${encodeURIComponent(templateId)}` as Route;
}

export function newTaskFromChatPath(chatSessionId: string): Route {
  return `${NEW_TASK_PATH}?source_chat_id=${encodeURIComponent(chatSessionId)}` as Route;
}

export function taskDetailPath(taskId: string): Route {
  return `${TASKS_PATH}/${taskId}` as Route;
}

export function taskEditPath(taskId: string): Route {
  return `${TASKS_PATH}/${taskId}/edit` as Route;
}

export function buildSessionPath(sessionId: string): Route {
  return `/craft/v1?sessionId=${sessionId}` as Route;
}

// Default page size for the scheduled task list.
export const TASKS_PAGE_SIZE = 20;

// Default page size for run history.
export const RUNS_PAGE_SIZE = 50;
