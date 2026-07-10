import { ValidSources } from "@/lib/types";
import type { OnyxDocument } from "@/lib/search/interfaces";
import {
  getSourceAuthority,
  getSourceAuthorityReason,
  partitionSourceEvidence,
} from "@/sections/document-sidebar/sourceEvidence";

function document(
  documentId: string,
  score: number,
  metadata: Record<string, string> = {}
): OnyxDocument {
  return {
    document_id: documentId,
    semantic_identifier: documentId,
    link: "",
    source_type: ValidSources.Sharepoint,
    blurb: "",
    boost: 0,
    hidden: false,
    score,
    chunk_ind: 0,
    match_highlights: [],
    metadata,
    updated_at: null,
    is_internet: false,
  };
}

describe("partitionSourceEvidence", () => {
  test("keeps cited documents in citation order regardless of score", () => {
    const result = partitionSourceEvidence(
      [document("a", 0.1), document("b", 0.9), document("c", 0.8)],
      new Set(["a", "c"]),
      new Map([
        ["c", 0],
        ["a", 1],
      ])
    );

    expect(result.citedDocuments.map((item) => item.document_id)).toEqual([
      "c",
      "a",
    ]);
    expect(result.reviewedDocuments.map((item) => item.document_id)).toEqual([
      "b",
    ]);
  });

  test("separates lower-relevance results from reviewed results", () => {
    const result = partitionSourceEvidence(
      [document("high", 1), document("medium", 0.4), document("low", 0.2)],
      new Set(),
      new Map()
    );

    expect(result.reviewedDocuments.map((item) => item.document_id)).toEqual([
      "high",
      "medium",
    ]);
    expect(
      result.lowerRelevanceDocuments.map((item) => item.document_id)
    ).toEqual(["low"]);
  });

  test("does not discard non-positive result sets", () => {
    const result = partitionSourceEvidence(
      [document("zero", 0), document("negative", -1)],
      new Set(),
      new Map()
    );

    expect(result.reviewedDocuments).toHaveLength(2);
    expect(result.lowerRelevanceDocuments).toHaveLength(0);
  });
});

describe("source authority metadata", () => {
  test.each([
    ["3", "authoritative"],
    ["trusted", "trusted"],
    ["1", "credible"],
  ] as const)("maps %s to %s", (rawValue, expected) => {
    expect(
      getSourceAuthority(document("doc", 1, { trust_level: rawValue }))
    ).toBe(expected);
  });

  test("returns authority reason without inventing one", () => {
    const source = document("doc", 1, {
      source_authority_reason: "Published HR policy",
    });

    expect(getSourceAuthorityReason(source)).toBe("Published HR policy");
    expect(getSourceAuthority(document("other", 1))).toBeNull();
  });
});
