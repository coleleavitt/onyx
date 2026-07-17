# Research: File-upload handling — Perplexity vs. Onyx (and how Claude/OpenAI do it)

Written before touching code, to decide how far to extend Onyx's chat file
attachments beyond the recent XLSX/tabular fix (pptx, upload prioritization, etc.).

Primary source mined: the July-10 Perplexity public bundle at
`~/VulnerabilityResearch/perplexity/refresh-2026-07-10-public-assets/`, chiefly the
attachment composer `beautified-js/ask-input-DivHuv_Y.js` (224 upload/attachment
hits; the densest file in the dump). Line numbers below are from that file.

---

## 1. How Perplexity handles uploads

### 1a. Accepted types (three separate allow-lists)

- **Google-Drive picker list** (`yu`, ~L3765): google-apps doc/slides/sheet, **docx,
  txt, pdf, csv, pptx, xlsx, markdown**.
- **Local-upload list** (`bu`, ~L3782): **txt, pdf, csv, markdown, png, jpeg, pptx,
  xlsx, docx**, plus the three google-apps types.
- **Audio/Video list** (`xu`, ~L3778) — gated behind `isAudioVideoFilesEnabled`:
  mp3, wav, aiff, ogg, flac, mp4, mpeg, mov, …

So Office formats (pptx/xlsx/docx) and pdf/csv/txt/md/png/jpeg are first-class; A/V is
a flag-gated superset.

### 1b. Token-budget preflight (the "priority" mechanism)

Feature flag `attachment-token-estimation-params` (`D_`, ~L12357) with defaults:

```
max_total_tokens: 500_000
type_bytes_per_token:        { text: 4, image: 500 }
type_subtype_bytes_per_token:{ application/pdf: 200, msword: 500,
                               xlsx(spreadsheetml): 500, pptx(presentationml): 500 }
default_bytes_per_token: 100
```

Estimator (`Te`, ~L12616): for every **successfully uploaded** file,
`bytesPerToken = subtype ?? topLevelType ?? default`, then
`estTokens = fileSize / bytesPerToken`, summed. If `sum > max_total_tokens` → **over
budget**.

What it does when over budget (`useEffect`, ~L12622): once all files are terminal, it
shows a **soft warning only** — *"Performance may be degraded for larger files."* It
does **not** hard-block, reject, or truncate. This is a cost heuristic, not a gate.

### 1c. Per-file validation / reject rules (`be`, ~L12530)

In order: `unsupported_type` → `too_large` (`size > maxAttachmentFileSizeMB * 1MiB`) →
`too_small` (`size < 10 bytes`) → `no_name`.

- `maxAttachmentFileSizeMB` default **50 MB**, overridable per source; the "ASI" source
  reads its own `max_attachment_file_size_mb_by_source.asi` (default 200, `N_`) (~L13134).

### 1d. Upload readiness = the real send-gate (the "priority" answer)

File status machine: `uploading` → `parsing` → `success` | `failed`.

`setUploadsReady` (`b`, ~L12446) is set true when
`files.every(status ∈ {parsing, success, failed})`. **Crucially `parsing` counts as
ready** — so the composer unlocks send once bytes have transferred, while server-side
parsing continues asynchronously. The input receives `isUploadingFile` and disables
submit while any file is still `uploading` (`Xg`, ~L11581). Net effect: **the send
waits for transfer, not for parsing.**

### 1e. Rate limits & concurrency

- `uploadRateLimit` = `500` for subscribers, `3` for free/visitor (`T = S ?? (w ? 500 : 3)`, ~L13102);
  enforced via `gateUploadFile` / `canUploadFile` (`Rs`/`Ls`, ~L1524–1581).
- Uploads run **in parallel** (`Promise.all` over the file list, ~L12649 / L12680) — no
  sequential queue; bounded only by the count limit.
- **Images are downscaled client-side** before upload (`ne(e)` resize, ~L12643) — the
  cheapest way to cut token/byte cost.

### 1f. Source pickers

Local file input, Google Drive, Microsoft, and Box pickers all feed the same pipeline
(`openMicrosoftPicker`, `refreshBoxCredentials`, drive scopes at ~L3746).

---

## 2. Onyx today (grounded in the current branch)

`backend/onyx/file_processing/file_types.py` → `OnyxMimeTypes`:

- **IMAGE**: jpg, jpeg, png, webp.
- **TABULAR**: csv, xlsx, xlsm (`+SPREADSHEET_MACRO`).
- **TEXT**: txt, markdown (+x-markdown), x-log, x-config, tsv, json, xml, yaml.
- **DOCUMENT**: **pdf, docx, pptx (presentationml), eml (rfc822), epub**.
- `ALLOWED_MIME_TYPES` = image ∪ text ∪ document ∪ tabular. Excluded images: bmp, tiff,
  gif, svg, avif.

`ChatFileType` (`backend/onyx/file_store/models.py`): IMAGE, DOC, PLAIN_TEXT, TABULAR.
`use_metadata_only()` → **TABULAR only**. `mime_type_to_chat_file_type()`
(`server/query_and_chat/chat_utils.py`) routes image → IMAGE, tabular → TABULAR,
document → DOC, else PLAIN_TEXT.

**Key implication for the "pptx?" question:** pptx/docx/pdf/epub/eml are **already
allowed** and ride the **DOC** path, which is parsed-to-text and injected into the
prompt (not metadata-only). The recent fix was narrowly about the **TABULAR**
metadata-only path — `build_file_context` now injects extracted tabular text when
available (`chat/chat_utils.py`), plus the `file_reader`→`read_file` tool-hint rename.
So pptx does **not** need the same fix.

**Confirmed:** Onyx already has a real pptx extractor —
`extract_file_text.py::pptx_to_text()` (markitdown `PptxConverter`) + `extract_pptx_images()`
for embedded images, dispatched on the `.pptx` extension (~L844/L996). So pptx is
supported end-to-end today; the only gap is a **test** locking it in (mirror the XLSX
tests). This makes recommendation #1 a **test-only** task.

What Onyx appears to **lack** vs. Perplexity:
- No client-side **token-budget preflight** / "performance may be degraded" warning.
- No explicit **bytes-per-token** cost model per type.
- No client-side **image downscaling** before upload.
- No **A/V** support (fine — likely out of scope).
- Send-gate semantics (transfer-vs-parse) not yet audited against the new attach UI.

---

## 3. How Claude & OpenAI do it (architecture patterns; exact limits evolve)

**Claude Code (this tool):** there is no "upload" — files are read from disk on demand
via the Read tool. Large text files are **truncated by line window** (read in ~2k-line
chunks with offset), images are read multimodally, and the model pulls more only when
needed. "Prioritization" is lazy/tool-driven: nothing enters context until a tool
fetches it. There is no pre-send token-budget popup; the agent self-limits by reading
incrementally.

**Claude API:** two lanes — (1) **inline content blocks**: images (png/jpeg/gif/webp)
and PDFs as `document` blocks, where PDFs are processed as **both extracted text and
page images** (visual understanding), with page/size caps; (2) **Files API** container
for reuse across turns / code execution. Cost knob = image resolution (downscale to
cut tokens), same instinct as Perplexity's client resize.

**OpenAI:** a clean **two-lane split** that mirrors Onyx's own IMAGE-vs-DOC split:
- **Vision (inline)**: png/jpeg/gif/webp with a `detail: low|high|auto` knob — `low` is
  a flat cheap cost, `high` tiles the image into 512px patches. This is the explicit
  "priority/cost" lever.
- **Retrieval / Code-Interpreter (uploaded to a store)**: broad document set
  (pdf, docx, pptx, xlsx, csv, md, txt, code…), accessed by a tool rather than dumped
  inline — large files are chunked/embedded, not fully injected.

**Common lesson:** everyone separates *small/visual → inline (token-costed)* from
*large/document → tool-or-retrieval (fetched on demand)*. Perplexity adds a **soft
pre-send token estimate** so the user is warned before a huge paste degrades quality.
Onyx already has the inline-vs-tool split (IMAGE vs DOC/TABULAR); the missing polish is
the **pre-send cost estimate + warning** and **client-side image downscaling**.

---

## 4. Recommendations (ordered by value/risk)

1. **Verify + test pptx (and docx/pdf) DOC-path extraction end-to-end.** Highest value,
   lowest risk. Confirms the "other formats, not just xlsx" concern is actually already
   covered, and locks it with a unit + E2E/TestSprite test (mirror the XLSX tests).
2. **Audit the attach send-gate** (`file_attach_ui.spec.ts` surface): does Onyx let you
   send while a file is still transferring? Decide Perplexity-style semantics (block on
   transfer, allow during parse).
3. **Add a client-side token-budget preflight + soft warning** (bytes-per-token map,
   configurable, "large files may degrade quality"). Non-blocking, matches Perplexity.
4. **Client-side image downscale before upload** (cheap byte/token win).
5. (Optional) per-type max-size + friendlier reject copy (`too_large`/`too_small`/
   `unsupported_type`), matching Perplexity's validation ladder.

Do **1** first — it directly answers "what about pptx" and is a test-only change if
extraction already works.

---

## 5. The "priority queue" question — grounded in Onyx's real code

Claims worth calibrating before building a pattern:

- **"Claude Code stages files into an ephemeral context window with priority slots,
  indexed before tool use, queued by content-type parsing."** — Not accurate. Claude
  Code has no upload pipeline; it reads files from the local filesystem on demand via a
  Read tool (large text truncated by line window, images read multimodally). Nothing is
  "staged/indexed/priority-slotted" ahead of tool use. Don't model a UI on this.
- **"OpenAI: POST /files → file_id → reference in a thread (upload → attach → use)."** —
  Accurate. It's a decoupled lifecycle: the file exists independently of any message and
  is referenced by id.

**Key finding — Onyx already implements the OpenAI-style decoupling.** The chat composer
uploads files and sends the message with **file descriptors / ids** (`ProjectFile` /
`FileDescriptor`), not parsed text. The **backend** loads bytes and extracts text at
message-processing time (`process_message.py` / `build_file_context`). So on the wire,
Onyx is already "upload → get id → reference by id".

**Onyx's two existing upload implementations:**

| | Chat (`useChatController` + `ProjectsContext.beginUpload`) | Craft (`UploadFilesContext`) |
|---|---|---|
| Status model | coarse: session-level `ChatState="uploading"` + `FileDescriptor.isUploading` | rich per-file: `PENDING → UPLOADING → PROCESSING → COMPLETED/FAILED` |
| Optimistic UI | yes — `createOptimisticFile` temp-ids, real upload resolves in background (`svcUploadFiles(...).then(...)`, not awaited) | yes |
| Send gate | **hard block**: on submit, `if ChatState=="uploading"` → toast *"Please wait for the content to upload"* + return | n/a (craft flushes PENDING once a session exists) |
| Sequencing | none | **`PENDING` = "waiting for a session to be created before uploading"**, auto-flushed when ready — this *is* an upload→attach→use queue |
| Limits | `userFileMaxUploadSizeMb` (server-config) | `MAX_FILE_SIZE=50MB`, `MAX_TOTAL=200MB`, `MAX_FILES=20` |

**So the real "pattern" is not an invention — it's unifying chat onto craft's per-file
machine**, and deciding the readiness gate. Because Onyx references files by id (backend
extracts), it does **not** need to block send on server-side parsing the way its coarse
chat gate implies; the true requirement is only "a real file id exists" (transfer +
record created). That's closer to Perplexity's "transfer done = ready".

**One caution to verify at implementation time:** `beginUpload` fires `svcUploadFiles`
**without awaiting** and returns optimistic temp-id descriptors, yet `useChatController`
`await`s it and wraps it in the `"uploading"` state. Confirm exactly when the temp-id →
real-id swap happens and whether a message sent with a temp-id would reach the backend
before the real `UserFile` exists (race). The gate must key off **"has real id"**, not a
timer or the coarse session state.
