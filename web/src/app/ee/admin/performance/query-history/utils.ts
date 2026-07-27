import { DateRange } from "../../../../../components/dateRangeSelectors/AdminDateRangeSelector";
import { START_QUERY_HISTORY_EXPORT_URL } from "./constants";

export const withRequestId = (url: string, requestId: string): string =>
  `${url}?request_id=${requestId}`;

/**
 * Flatten an assistant message into one line of readable preview text.
 *
 * Stored messages are markdown with inline citations, so rendering them raw
 * puts `**bold**`, `[[3]](https://…%20…)` and hard newlines straight into a
 * table cell. Mirrors opal's `toPlainString`, which can't be reused here
 * because it short-circuits on anything that isn't a `RichStr`.
 */
export const toPreviewText = (value: string | null | undefined): string => {
  if (!value) return "";
  return value
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/(?<!\w)__([^_]+)__(?!\w)/g, "$1")
    .replace(/~~([^~]+)~~/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/(?<!\w)_([^_]+)_(?!\w)/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/^\s{0,3}>\s?/gm, "")
    .replace(/\s*\n\s*/g, " ")
    .replace(/\s{2,}/g, " ")
    .trim();
};

export const withDateRange = (dateRange: DateRange): string => {
  if (!dateRange) {
    return START_QUERY_HISTORY_EXPORT_URL;
  }

  const { from, to } = dateRange;

  const fromString = from.toISOString();
  const toString = to.toISOString();

  return `${START_QUERY_HISTORY_EXPORT_URL}?start=${fromString}&end=${toString}`;
};
