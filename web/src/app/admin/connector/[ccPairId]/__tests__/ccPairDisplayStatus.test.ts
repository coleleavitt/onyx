import {
  ConnectorCredentialPairStatus,
  resolveCCPairDisplayStatus,
} from "../types";

describe("resolveCCPairDisplayStatus", () => {
  it("keeps PAUSED while a secondary-index run is mid-flight", () => {
    // The exact production case: an embedding switchover indexes paused
    // connectors on purpose, so the newest attempt is in_progress and has
    // never finished. The list must still agree with the detail page.
    expect(
      resolveCCPairDisplayStatus(
        ConnectorCredentialPairStatus.PAUSED,
        null,
        "in_progress"
      )
    ).toBe(ConnectorCredentialPairStatus.PAUSED);
  });

  it("keeps PAUSED when an attempt is queued but unstarted", () => {
    expect(
      resolveCCPairDisplayStatus(
        ConnectorCredentialPairStatus.PAUSED,
        null,
        "not_started"
      )
    ).toBe(ConnectorCredentialPairStatus.PAUSED);
  });

  it.each([
    ConnectorCredentialPairStatus.INVALID,
    ConnectorCredentialPairStatus.DELETING,
  ])("never masks an explicit %s", (status) => {
    expect(resolveCCPairDisplayStatus(status, null, "in_progress")).toBe(
      status
    );
  });

  it("reports SCHEDULED for a fresh connector whose first attempt is queued", () => {
    expect(
      resolveCCPairDisplayStatus(
        ConnectorCredentialPairStatus.ACTIVE,
        null,
        "not_started"
      )
    ).toBe(ConnectorCredentialPairStatus.SCHEDULED);
  });

  it("reports INITIAL_INDEXING while the first attempt runs", () => {
    expect(
      resolveCCPairDisplayStatus(
        ConnectorCredentialPairStatus.ACTIVE,
        null,
        "in_progress"
      )
    ).toBe(ConnectorCredentialPairStatus.INITIAL_INDEXING);
  });

  it("defers to the real status once any attempt has finished", () => {
    expect(
      resolveCCPairDisplayStatus(
        ConnectorCredentialPairStatus.ACTIVE,
        "success",
        "in_progress"
      )
    ).toBe(ConnectorCredentialPairStatus.ACTIVE);
  });

  it("treats a never-attempted connector as scheduled, not indexing", () => {
    expect(
      resolveCCPairDisplayStatus(
        ConnectorCredentialPairStatus.SCHEDULED,
        null,
        null
      )
    ).toBe(ConnectorCredentialPairStatus.INITIAL_INDEXING);
  });
});
