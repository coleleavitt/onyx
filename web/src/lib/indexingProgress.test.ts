import { getIndexingProgress } from "@/lib/indexingProgress";
import { IndexAttemptSnapshot } from "@/lib/types";

function makeAttempt(
  overrides: Partial<IndexAttemptSnapshot>
): IndexAttemptSnapshot {
  return {
    id: 9,
    status: "in_progress",
    from_beginning: true,
    new_docs_indexed: 0,
    docs_removed_from_index: 0,
    total_docs_indexed: 0,
    error_msg: null,
    error_count: 0,
    full_exception_trace: null,
    time_started: "2026-07-09T19:00:00Z",
    time_updated: "2026-07-09T19:05:00Z",
    source_docs_discovered: 0,
    source_docs_estimated: null,
    source_doc_estimate_method: null,
    source_doc_estimate_time: null,
    source_progress_label: null,
    total_batches: null,
    completed_batches: 0,
    last_heartbeat_time: null,
    ...overrides,
  };
}

test("reports approximate progress while the source is being discovered", () => {
  const progress = getIndexingProgress(
    makeAttempt({
      source_docs_discovered: 175,
      source_docs_estimated: 700,
    })
  );

  expect(progress).toEqual({
    phase: "discovering",
    ratio: 0.25,
    completed: 175,
    total: 700,
    approximate: true,
  });
});

test("switches to exact batch progress after source discovery", () => {
  const progress = getIndexingProgress(
    makeAttempt({
      source_docs_discovered: 715,
      source_docs_estimated: 700,
      total_batches: 20,
      completed_batches: 8,
    })
  );

  expect(progress).toEqual({
    phase: "processing",
    ratio: 0.4,
    completed: 8,
    total: 20,
    approximate: false,
  });
});

test("reports an empty extracted run as complete", () => {
  expect(
    getIndexingProgress(makeAttempt({ total_batches: 0, completed_batches: 0 }))
  ).toEqual({
    phase: "processing",
    ratio: 1,
    completed: 0,
    total: 0,
    approximate: false,
  });
});

test("keeps discovery indeterminate when no source estimate is available", () => {
  const progress = getIndexingProgress(
    makeAttempt({ source_docs_discovered: 42 })
  );

  expect(progress).toEqual({
    phase: "discovering",
    ratio: null,
    completed: 42,
    total: null,
    approximate: false,
  });
});

test("uses processed documents while the next source checkpoint is pending", () => {
  const progress = getIndexingProgress(
    makeAttempt({
      source_docs_discovered: 0,
      source_docs_estimated: 715,
      total_docs_indexed: 16,
    })
  );

  expect(progress?.completed).toBe(16);
  expect(progress?.ratio).toBeCloseTo(16 / 715);
});

test("does not compare a file estimate with pages and list items", () => {
  const progress = getIndexingProgress(
    makeAttempt({
      source_docs_discovered: 500,
      source_docs_estimated: 700,
    }),
    false
  );

  expect(progress).toEqual({
    phase: "discovering",
    ratio: null,
    completed: 500,
    total: 700,
    approximate: false,
  });
});

test("supports API responses from before progress fields were added", () => {
  const attempt = makeAttempt({});
  delete attempt.source_docs_discovered;
  delete attempt.source_docs_estimated;
  delete attempt.total_batches;
  delete attempt.completed_batches;

  expect(getIndexingProgress(attempt)).toEqual({
    phase: "discovering",
    ratio: null,
    completed: 0,
    total: null,
    approximate: false,
  });
});

test("does not report progress for a finished attempt", () => {
  expect(getIndexingProgress(makeAttempt({ status: "success" }))).toBeNull();
});
