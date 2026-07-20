import { render, screen, within } from "@tests/setup/test-utils";
import { ConfigDisplay } from "./ConfigDisplay";

/**
 * Regression coverage for the connector-detail "Connector Configuration" table.
 *
 * A SharePoint (and several other) connector configs contain list-valued fields
 * that are frequently empty — e.g. `excluded_paths`, `excluded_sites`,
 * `microsoft_search_queries`. The table must render a visible placeholder for
 * these, exactly like it does for empty scalar values, so an admin can tell the
 * field is "unset" rather than wondering whether the value failed to load.
 */
describe("ConfigDisplay", () => {
  /** Find the value cell for a given config label row. */
  function valueTextForLabel(label: string): string {
    const labelNode = screen.getByText(label);
    // Row = label's flex container two levels up (label wrapper -> row).
    const row = labelNode.closest("div")?.parentElement as HTMLElement;
    // The row text minus the leading label is the rendered value.
    return (row.textContent ?? "").slice(label.length).trim();
  }

  test("renders a placeholder for empty-array config values", () => {
    render(
      <ConfigDisplay
        configEntries={
          {
            include_lists: true,
            excluded_paths: [],
            excluded_sites: [],
            microsoft_search_queries: [],
          } as any
        }
      />
    );

    // Sanity: a populated boolean still shows its value.
    expect(valueTextForLabel("include_lists")).toBe("True");

    // The bug: empty-array rows rendered as blank (label only, no value).
    // Each empty list field should show the same "-" placeholder used for
    // empty scalars, so the row is never visually empty.
    expect(valueTextForLabel("excluded_paths")).toBe("-");
    expect(valueTextForLabel("excluded_sites")).toBe("-");
    expect(valueTextForLabel("microsoft_search_queries")).toBe("-");
  });

  test("still renders populated array values as a comma-joined list", () => {
    render(
      <ConfigDisplay
        configEntries={
          {
            excluded_paths: ["/private", "/drafts"],
          } as any
        }
      />
    );

    const labelNode = screen.getByText("excluded_paths");
    const row = labelNode.closest("div")?.parentElement as HTMLElement;
    expect(within(row).getByText("/private, /drafts")).toBeInTheDocument();
  });
});
