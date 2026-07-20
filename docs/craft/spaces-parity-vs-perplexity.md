# Spaces — parity gap analysis vs. Perplexity

Reference: Perplexity's captured/beautified frontend bundles (July 10 capture,
`~/VulnerabilityResearch/perplexity/beautified-js-v3/`, the `spaces-redesign`
variant). Internally Perplexity calls Spaces "collections" and the agent
"Computer"; threads are "tasks".

Onyx side reviewed: `web/src/views/spaces/SpacesPage.tsx` (list),
`web/src/app/app/spaces/[slug]/page.tsx` → `AppPage` + `ProjectContextPanel.tsx`
(detail rail), `SpaceCard.tsx`, `CreateProjectModal`, `EditSpaceDetailsModal`.

Screenshots: `testsprite_tests/tmp/spaces_parity/` (list, detail, create modal).

## TL;DR — why it "doesn't look the same"

1. **The chat wallpaper bleeds through the whole Spaces experience.** The space
   detail route renders the full `AppPage` shell, so the user's `chat_background`
   preference paints behind the list, the detail rail, and the cards. Perplexity
   Spaces render on a plain `bg-base`/`bg-raised` surface. This single thing is
   most of the "not the same at all" feeling — text sits at ~1–2:1 contrast over
   an orange wireframe image.
2. **The individual Space page is the chat surface with a right rail, not a
   dedicated Space layout.** Perplexity's Space page is its own thing: breadcrumb
   header (Spaces › Name), large emoji + inline-editable title/description, and a
   **Threads / Customize** tab pair (or threads + persistent right rail ≥900px).
   Onyx shows the standard ask-input + a sessions list with the project panel
   docked on the right.
3. **No emoji identity.** Onyx uses a plain text input (`maxLength 8`) for the
   "icon"; Perplexity has a real emoji picker (`emoji-picker-react`) plus a
   dynamic per-emoji accent color (`oklch()` derived from the emoji's hue) that
   themes the SpacePill/SpaceIcon everywhere.

## Layout / structure gaps

| Area | Perplexity | Onyx today | Gap |
|---|---|---|---|
| Detail surface | Clean `bg-base`, dedicated layout | Full `AppPage` + chat wallpaper | Give Spaces their own clean surface; suppress `chat_background` on `/app/spaces/*` |
| Detail header | Breadcrumb "Spaces › {name}" that fades in on scroll | No breadcrumb | Add breadcrumb header |
| Space identity | Big emoji tile + inline-editable title (≤50) + description (≤1000) on the page | Edit only via modal; description capped at 255 | Inline editing on the page; raise description cap |
| Tabs | **Threads** / **Customize** (responsive → right rail ≥900px) | Sessions list + always-on right rail | Add the Threads/Customize model (or at least the labeled tabs) |
| List grouping | Invited / Pinned / Your spaces / Shared in your organization | Pinned / Your Spaces / Shared with you | Add **Invited** group + org-shared naming |
| List row: contributors | AvatarList (owner+contributors, "View all members") | Single owner avatar | Add contributor stack |
| Empty states | "No spaces yet" / "No matching spaces"; per-tab task empties | "No spaces yet/found" | Close; fine |

## Feature gaps (built elsewhere or missing)

- **Emoji picker + per-space accent color** — missing (plain text field). High
  visual impact; this is what makes Perplexity spaces feel distinct.
- **Space Memory** — `ProjectMemoryPanel.tsx` exists but is **orphaned** (not
  imported/rendered anywhere). Perplexity surfaces "Manage Memory" from the space
  `⋯` menu. Wire the existing panel in.
- **Links section** — Onyx shows "Link support is coming soon" placeholder;
  Perplexity has a working add-URL flow with "Added by {email}" + remove.
- **Skills/tools** — Onyx "Add Skills" just routes to the global skills hub; no
  per-space association persists. Perplexity persists per-space tool context.
- **Scheduled/recurring tasks per space** — Perplexity has a "Scheduled Tasks"
  section in the rail (active + paused groups). Onyx has scheduled tasks only in
  Craft, not wired to Spaces.
- **Paste-text-as-file** — Perplexity has a "Paste text" button
  (`SpacePasteTextFileModal`). Onyx Files section has upload/drag only.
- **Thread ↔ Space management** — Perplexity thread menu: Pin/Unpin, Rename,
  **Swap Space** (move thread between spaces), **Remove from Space**, Make
  private / Share with Space. Onyx has no move-thread-to-space.
- **Space-level pinned threads** — distinct from pinning the space itself.
- **Sharing depth** — Perplexity has a full access-level model (Owner only /
  Private / Shared in space / Organization / Public / Published / Specific
  people), invite-by-email with org restrictions and max contributors, roles
  (Owner/Member), copy-link. Verify Onyx `ShareProjectModal` covers these levels.
- **Invitations UX** — accept/decline contributor invite banner + "Invited"
  landing section. Onyx has neither.
- **Thread type filter** (All / Computer / Search) + task search in the threads
  list — not applicable 1:1, but the "filter + search within a space" affordance
  is missing.

## Where Onyx is already at or ahead

- **Create modal** collects Icon + Title + Description + **Instructions** up
  front; Perplexity's create modal is only Title + Description.
- **Instructions section** in the rail (add/edit/view, reader "View all",
  5-line clamp) closely mirrors Perplexity's.
- **Files section** (drag-drop, connector files, previews, "View all") is close.
- **Pin swap ⇄ overflow menu** on hover in the list row matches Perplexity's
  `pin-filled` → `⋯` pattern.

## Suggested priority order (highest visual parity per unit effort)

1. **Kill the wallpaper on Spaces** + give the detail page a clean surface. (Biggest
   perceived-parity win; likely a CSS/layout scope change.)
2. **Real emoji picker + per-emoji accent color** for SpaceIcon/SpaceCard/pill.
3. **Breadcrumb header + inline title/description editing** on the detail page.
4. **Wire the orphaned Space Memory panel** into the rail + `⋯` menu.
5. **Threads/Customize tab model** and contributor avatar stacks.
6. Fill the deeper features (Links, scheduled tasks, paste-text, thread-move,
   invitations) as follow-ups.

## Design tokens to match (from Perplexity CSS)

- Header height `56px` (`--header-height`). Card radius `rounded-lg` = 12px.
  Pills `rounded-full`. Surfaces `bg-base`/`bg-raised`/`bg-subtle`; borders
  `border-subtle`/`border-subtlest`; section-header bars `bg-subtle rounded-lg
  px-3 py-2`. Row actions reveal on `group-hover`. Spacing scale: `2xs 2 / xs 4 /
  sm 6 / md 8 / lg 12 / xl 16`.
- Per-space accent: `oklch()` derived from emoji hue — light bg
  `oklch(0.96 0.02 H)` / text `oklch(0.45 0.08 H)`; dark `oklch(0.25 0.025 H)` /
  `oklch(0.65 0.08 H)`.
