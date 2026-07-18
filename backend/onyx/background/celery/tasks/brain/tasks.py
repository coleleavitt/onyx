"""Brain self-improvement run.

A scheduled task that, once per day, organizes each brain-enabled user's recent
chat activity into a linked graph of memory "pages": it extracts durable facts,
categorizes them (entities / concepts / workstreams / notes), links related
pages, and cites the specific sessions (and, when the user enables connectors,
the documents) that produced them. This is the engine behind the
"self-improving memory" surface.
"""

import datetime
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session

from onyx.background.celery.apps.app_base import task_logger
from onyx.configs.constants import MessageType
from onyx.configs.constants import OnyxCeleryTask
from onyx.db.brain import add_memory_relation
from onyx.db.brain import add_memory_source
from onyx.db.brain import get_memory_sources
from onyx.db.brain import list_brain_enabled_user_ids
from onyx.db.brain import mark_brain_run_complete
from onyx.db.chat import get_chat_messages_by_sessions
from onyx.db.chat import get_chat_sessions_by_user
from onyx.db.engine.sql_engine import get_session_with_current_tenant
from onyx.db.enums import MemoryCategory
from onyx.db.enums import MemorySourceType
from onyx.db.memory import create_memory_item
from onyx.db.memory import is_memory_creation_allowed
from onyx.db.memory import list_memory_items_for_user
from onyx.db.memory import memory_title_for_content
from onyx.db.memory import update_memory_item
from onyx.db.models import ChatMessage
from onyx.db.models import ChatSession
from onyx.db.models import Memory
from onyx.db.models import SearchDoc
from onyx.db.models import User
from onyx.llm.factory import get_default_llm
from onyx.llm.interfaces import LLM
from onyx.llm.models import ReasoningEffort
from onyx.llm.models import UserMessage
from onyx.tracing.flows import LLMFlow
from onyx.tracing.llm_utils import llm_generation_span
from onyx.tracing.llm_utils import record_llm_response
from onyx.utils.text_processing import parse_llm_json_response

# Bounds keep a single scheduled run cheap and predictable.
BRAIN_MAX_USERS_PER_RUN = 100
BRAIN_MAX_SESSIONS_PER_USER = 25
BRAIN_MAX_MESSAGES_PER_SESSION = 20
BRAIN_MAX_CHARS_PER_MESSAGE = 800
BRAIN_MAX_TRANSCRIPT_CHARS = 24_000
BRAIN_MAX_DOCS = 20
BRAIN_MAX_PAGES_PER_RUN = 12
BRAIN_MAX_SOURCES_PER_PAGE = 4
BRAIN_LOOKBACK_DAYS = 14
BRAIN_SOURCE = "brain"

_CATEGORY_BY_VALUE = {category.value: category for category in MemoryCategory}


@dataclass
class _SourceRef:
    """A citation the LLM can reference by its short `ref` id (e.g. "S1", "D2")
    and that maps to a concrete source row when applied to a memory."""

    ref: str
    source_type: MemorySourceType
    label: str
    source_id: str
    url: str | None = None
    # For chat-session refs: the project (space) the session belongs to, used
    # to scope pages derived entirely from one space's conversations.
    project_id: int | None = None


@dataclass
class _BrainPage:
    title: str
    category: MemoryCategory
    content: str
    related: list[str]
    sources: list[str]


_BRAIN_EXTRACT_PROMPT = """\
You maintain a user's long-term "Brain": a small, curated graph of durable \
memory pages derived from their work. Read the recent source material and \
produce the memory pages worth keeping for future tasks.

Rules:
- Only keep durable, reusable facts, decisions, preferences, entities, and \
ongoing initiatives. Ignore one-off chatter and transient details.
- Each page has a category:
  - "entities": people, organizations, products, or systems (e.g. "Acme Corp").
  - "concepts": reusable ideas, artifacts, or definitions (e.g. "Brand Kit").
  - "workstreams": ongoing initiatives or projects (e.g. "Product Launches").
  - "notes": simple durable details that do not fit the above.
- Prefer updating an existing page (reuse its exact title) over creating a \
near-duplicate. Existing page titles are listed below.
- "related" lists the titles of other pages (from this response or the existing \
list) that this page is meaningfully connected to.
- "sources" lists the source ids (the bracketed [S#]/[D#] tags below) that this \
specific page was actually derived from. Only cite sources you used.
{focus}
Existing pages (titles):
{existing_titles}

Source material:
{transcript}

Respond with ONLY a JSON object of the form:
{{"pages": [{{"title": "...", "category": "entities|concepts|workstreams|notes", \
"content": "one short paragraph", "related": ["Other Title", ...], \
"sources": ["S1", "D2", ...]}}]}}
Return at most {max_pages} pages. If nothing is worth keeping, return \
{{"pages": []}}.
"""


def _recent_sessions(db_session: Session, user: User) -> list[ChatSession]:
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=BRAIN_LOOKBACK_DAYS)
    if user.brain_last_run_at is not None and user.brain_last_run_at > cutoff:
        cutoff = user.brain_last_run_at
    sessions = get_chat_sessions_by_user(
        user_id=user.id,
        deleted=False,
        db_session=db_session,
        limit=BRAIN_MAX_SESSIONS_PER_USER,
    )
    return [
        session
        for session in sessions
        if session.time_updated is not None and session.time_updated >= cutoff
    ]


def _collect_cited_documents(
    messages: list[ChatMessage],
) -> dict[str, SearchDoc]:
    """Unique documents cited across the processed messages, keyed by
    document_id (kept to a bounded count for prompt size)."""
    docs: dict[str, SearchDoc] = {}
    for message in messages:
        for doc in message.search_docs:
            if doc.is_internet or not doc.document_id:
                continue
            if doc.document_id not in docs:
                docs[doc.document_id] = doc
            if len(docs) >= BRAIN_MAX_DOCS:
                return docs
    return docs


def _build_context(
    db_session: Session, user: User, sessions: list[ChatSession]
) -> tuple[str, dict[str, _SourceRef]]:
    """Build the LLM source material and a ref->source map. Sessions are labeled
    [S1], [S2], ...; cited documents (only when the user enabled connectors) are
    labeled [D1], [D2], ... so the LLM can attribute each page to real sources.
    """
    session_refs = {
        session.id: f"S{index + 1}" for index, session in enumerate(sessions)
    }
    source_map: dict[str, _SourceRef] = {
        session_refs[session.id]: _SourceRef(
            ref=session_refs[session.id],
            source_type=MemorySourceType.CHAT_SESSION,
            label=session.description or "Chat session",
            source_id=str(session.id),
            # Conversation-history citations deep-link back into the app.
            url=f"/app?chatId={session.id}",
            project_id=session.project_id,
        )
        for session in sessions
    }

    messages = list(
        get_chat_messages_by_sessions(
            chat_session_ids=[session.id for session in sessions],
            user_id=user.id,
            db_session=db_session,
            skip_permission_check=True,
        )
    )
    # Order chronologically within each session and budget per session so no
    # single session starves the others.
    by_session: dict[object, list[ChatMessage]] = defaultdict(list)
    for message in messages:
        by_session[message.chat_session_id].append(message)

    parts: list[str] = []
    total = 0
    for session in sessions:
        ref = session_refs[session.id]
        session_messages = sorted(by_session.get(session.id, []), key=lambda m: m.id)
        kept = 0
        for message in session_messages:
            if kept >= BRAIN_MAX_MESSAGES_PER_SESSION:
                break
            if message.message_type not in (MessageType.USER, MessageType.ASSISTANT):
                continue
            text = (message.message or "").strip()
            if not text:
                continue
            role = "User" if message.message_type == MessageType.USER else "Assistant"
            line = f"[{ref}] {role}: {text[:BRAIN_MAX_CHARS_PER_MESSAGE]}\n"
            if total + len(line) > BRAIN_MAX_TRANSCRIPT_CHARS:
                break
            parts.append(line)
            total += len(line)
            kept += 1

    if user.brain_use_connectors:
        cited = _collect_cited_documents(messages)
        if cited:
            parts.append("\nCited documents:\n")
            for index, doc in enumerate(cited.values()):
                ref = f"D{index + 1}"
                source_map[ref] = _SourceRef(
                    ref=ref,
                    source_type=MemorySourceType.DOCUMENT,
                    label=doc.semantic_id or doc.document_id,
                    source_id=doc.document_id,
                    url=doc.link,
                )
                blurb = (doc.blurb or "").strip()[:300]
                line = f"[{ref}] {doc.semantic_id or doc.document_id}: {blurb}\n"
                if total + len(line) > BRAIN_MAX_TRANSCRIPT_CHARS:
                    break
                parts.append(line)
                total += len(line)

    return "".join(parts).strip(), source_map


def _extract_pages(
    llm: LLM, transcript: str, existing_titles: list[str], focus: str | None
) -> list[_BrainPage]:
    focus_block = (
        f"- User focus for this run: {focus.strip()}\n"
        if focus and focus.strip()
        else ""
    )
    existing_block = (
        "\n".join(f"- {title}" for title in existing_titles) or "(none yet)"
    )
    prompt = _BRAIN_EXTRACT_PROMPT.format(
        focus=focus_block,
        existing_titles=existing_block,
        transcript=transcript,
        max_pages=BRAIN_MAX_PAGES_PER_RUN,
    )
    prompt_msg = UserMessage(content=prompt)
    try:
        with llm_generation_span(
            llm=llm, flow=LLMFlow.BRAIN_MEMORY_EXTRACT, input_messages=[prompt_msg]
        ) as span:
            response = llm.invoke(
                prompt=prompt_msg, reasoning_effort=ReasoningEffort.OFF
            )
            record_llm_response(span, response)
            content = response.choice.message.content
    except SoftTimeLimitExceeded:
        raise
    except Exception as exc:
        task_logger.warning("Brain extraction LLM call failed: %s", exc)
        return []

    if not content:
        return []
    parsed = parse_llm_json_response(content)
    if not isinstance(parsed, dict):
        return []
    raw_pages = parsed.get("pages")
    if not isinstance(raw_pages, list):
        return []

    pages: list[_BrainPage] = []
    for raw in raw_pages[:BRAIN_MAX_PAGES_PER_RUN]:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        content_text = str(raw.get("content") or "").strip()
        if not title or not content_text:
            continue
        category = _CATEGORY_BY_VALUE.get(
            str(raw.get("category") or "").strip().lower(), MemoryCategory.NOTES
        )
        related = _string_list(raw.get("related"))
        sources = _string_list(raw.get("sources"))
        pages.append(
            _BrainPage(
                title=title,
                category=category,
                content=content_text,
                related=related,
                sources=sources,
            )
        )
    return pages


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_source_ref(ref: str) -> str:
    """Normalize an LLM-supplied source ref (e.g. "[s1]") to a source_map key
    ("S1"), hardening provenance against bracket-echo and case drift."""
    return ref.strip().strip("[]").strip().upper()


def _attach_sources(
    db_session: Session, memory_id: int, refs: list[_SourceRef]
) -> None:
    if not refs:
        return
    existing = {
        source.source_id for source in get_memory_sources(db_session, memory_id)
    }
    added = False
    for ref in refs[:BRAIN_MAX_SOURCES_PER_PAGE]:
        if ref.source_id in existing:
            continue
        add_memory_source(
            db_session,
            memory_id,
            source_type=ref.source_type,
            label=ref.label,
            source_id=ref.source_id,
            url=ref.url,
            commit=False,
        )
        existing.add(ref.source_id)
        added = True
    if added:
        db_session.commit()


def _page_project_id(
    refs: list[_SourceRef],
) -> int | None:
    """A page derived exclusively from one space's chat sessions is scoped to
    that space; anything mixed (multiple spaces, global sessions, documents)
    stays global."""
    if not refs:
        return None
    project_ids = {
        ref.project_id
        for ref in refs
        if ref.source_type == MemorySourceType.CHAT_SESSION
    }
    if len(project_ids) != 1:
        return None
    only = project_ids.pop()
    # Document refs alongside a space's sessions still describe that space's
    # work, so they don't break the attribution.
    return only


def _apply_pages(
    db_session: Session,
    user: User,
    pages: list[_BrainPage],
    source_map: dict[str, _SourceRef],
) -> int:
    existing = list_memory_items_for_user(user.id, db_session=db_session)
    by_title: dict[str, Memory] = {
        (memory.title or "").strip().lower(): memory for memory in existing
    }

    applied: dict[str, int] = {}
    for page in pages:
        page_refs = [
            source_map[ref_key]
            for ref_key in (_normalize_source_ref(ref) for ref in page.sources)
            if ref_key in source_map
        ]
        # Match the stored (normalized) title so re-runs update rather than
        # duplicate a near-identical page.
        key = memory_title_for_content(page.content, page.title).strip().lower()
        current = by_title.get(key)
        if current is not None:
            # Updates keep the page's existing scope: a page that graduated to
            # global (or was created inside a space) stays where it is.
            memory = update_memory_item(
                current,
                memory_text=page.content,
                title=page.title,
                category=page.category,
                source=BRAIN_SOURCE,
                db_session=db_session,
            )
        else:
            memory = create_memory_item(
                user_id=user.id,
                memory_text=page.content,
                title=page.title,
                category=page.category,
                source=BRAIN_SOURCE,
                db_session=db_session,
                project_id=_page_project_id(page_refs),
            )
        if memory is None:
            continue
        by_title[key] = memory
        applied[key] = memory.id

        _attach_sources(db_session, memory.id, page_refs)

    # Link related pages once every page has an id.
    for page in pages:
        source_key = memory_title_for_content(page.content, page.title).strip().lower()
        source_id = applied.get(source_key)
        if source_id is None:
            continue
        for related_title in page.related:
            related_key = related_title.strip().lower()
            target = by_title.get(related_key)
            if target is not None and target.id != source_id:
                add_memory_relation(db_session, user.id, source_id, target.id)

    return len(applied)


def _run_for_user(db_session: Session, user: User, llm: LLM) -> bool:
    sessions = _recent_sessions(db_session, user)
    now = datetime.datetime.now(datetime.timezone.utc)
    if not sessions:
        mark_brain_run_complete(db_session, user.id, run_at=now)
        return False

    transcript, source_map = _build_context(db_session, user, sessions)
    if not transcript:
        mark_brain_run_complete(db_session, user.id, run_at=now)
        return False

    existing_titles = [
        memory.title or "Untitled memory"
        for memory in list_memory_items_for_user(user.id, db_session=db_session)
    ]
    pages = _extract_pages(
        llm, transcript, existing_titles, user.brain_focus_instructions
    )
    if pages:
        _apply_pages(db_session, user, pages, source_map)

    mark_brain_run_complete(db_session, user.id, run_at=now)
    return bool(pages)


@shared_task(
    name=OnyxCeleryTask.BRAIN_SELF_IMPROVEMENT,
    ignore_result=True,
    soft_time_limit=60 * 30,
    bind=False,
)
def brain_self_improvement() -> int:
    """Daily self-improvement run for every brain-enabled user in the tenant."""
    with get_session_with_current_tenant() as db_session:
        if not is_memory_creation_allowed(db_session):
            return 0
        user_ids = list_brain_enabled_user_ids(db_session)

    if not user_ids:
        return 0

    try:
        llm = get_default_llm()
    except ValueError:
        task_logger.info("Brain run skipped: no default LLM configured.")
        return 0

    processed = 0
    for user_id in user_ids[:BRAIN_MAX_USERS_PER_RUN]:
        try:
            with get_session_with_current_tenant() as db_session:
                user = db_session.get(User, user_id)
                if user is None or not user.brain_enabled:
                    continue
                if _run_for_user(db_session, user, llm):
                    processed += 1
        except SoftTimeLimitExceeded:
            task_logger.warning(
                "Brain run hit soft time limit after %s user(s)", processed
            )
            raise
        except Exception as exc:
            task_logger.warning("Brain run failed for user %s: %s", user_id, exc)

    if processed:
        task_logger.info("Brain self-improvement updated %s user(s)", processed)
    return processed


@shared_task(
    name=OnyxCeleryTask.BRAIN_SELF_IMPROVEMENT_USER,
    ignore_result=True,
    soft_time_limit=60 * 10,
    bind=False,
)
def brain_self_improvement_user(
    *,
    user_id: str,
    tenant_id: str | None = None,  # noqa: ARG001 — consumed by the task base
) -> bool:
    """On-demand brain run for a single user, triggered from the API.

    Same pipeline as the nightly run, but for one user so a manual "refresh
    now" doesn't wait for (or repeat) the whole-tenant sweep. `tenant_id` is
    consumed by the task base to select the tenant schema.
    """
    with get_session_with_current_tenant() as db_session:
        if not is_memory_creation_allowed(db_session):
            return False
        user = db_session.get(User, UUID(user_id))
        if user is None or not user.brain_enabled:
            return False

        try:
            llm = get_default_llm()
        except ValueError:
            task_logger.info("Manual brain run skipped: no default LLM configured.")
            return False

        return _run_for_user(db_session, user, llm)
