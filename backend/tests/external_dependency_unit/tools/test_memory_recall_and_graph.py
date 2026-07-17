"""Deterministic proof that stored memories are recalled into chat context and
that the brain "related pages" graph (edges + source citations) is built
correctly. No LLM is involved — this exercises the DB/context layer directly so
it stays fast and non-flaky.

Recall in Onyx is eager and recency-based (top ``MAX_CONTEXT_MEMORIES`` ordered
by ``updated_at``), not semantic, so these assertions check presence + recency
ordering rather than relevance ranking.
"""

from sqlalchemy.orm import Session

from onyx.db.brain import add_memory_relation
from onyx.db.brain import add_memory_source
from onyx.db.brain import get_memory_graph
from onyx.db.brain import get_memory_sources
from onyx.db.brain import get_related_memories
from onyx.db.enums import MemoryCategory
from onyx.db.enums import MemorySourceType
from onyx.db.memory import create_memory_item
from onyx.db.memory import get_memories
from onyx.db.models import User
from tests.external_dependency_unit.conftest import create_test_user


def _create(
    db_session: Session,
    user: User,
    *,
    title: str,
    category: MemoryCategory,
    text: str,
) -> int:
    memory = create_memory_item(
        user_id=user.id,
        title=title,
        category=category,
        memory_text=text,
        source="manual",
        db_session=db_session,
    )
    assert memory is not None, "memory creation should be allowed by default policy"
    return memory.id


def test_populated_memories_are_recalled_into_context_recency_ordered(
    db_session: Session,
) -> None:
    """Populate an account across every category, then prove those exact memories
    come back in the recall context, newest-first, and are exposed to the chat
    layer via ``as_formatted_list()``."""
    user: User = create_test_user(db_session, "memory_recall")

    seeded = [
        ("Favorite color", MemoryCategory.NOTES, "The user's favorite color is teal."),
        ("Onyx", MemoryCategory.ENTITIES, "Onyx is the user's primary work project."),
        ("Retrieval", MemoryCategory.CONCEPTS, "The user cares about RAG quality."),
        ("Q3 launch", MemoryCategory.WORKSTREAMS, "The user is driving the Q3 launch."),
    ]
    for title, category, text in seeded:
        _create(db_session, user, title=title, category=category, text=text)

    context = get_memories(user, db_session)

    seeded_texts = {text for _, _, text in seeded}
    assert seeded_texts.issubset(set(context.memories))

    # Recall is recency-ordered (updated_at desc, id desc tie-break): the memory
    # created last shows up first.
    assert context.memories[0] == seeded[-1][2]

    # The chat layer consumes memories via as_formatted_list(); every stored
    # memory must be present there so it can reach the system prompt / search.
    formatted = context.as_formatted_list()
    assert seeded_texts.issubset(set(formatted))
    assert f"User's email: {user.email}" in formatted


def test_recall_context_respects_use_memories_flag(db_session: Session) -> None:
    """The per-user ``use_memories`` gate only strips the memory text; the fetch
    still populates ``user_id`` (creation/recall wiring stays intact)."""
    user: User = create_test_user(db_session, "memory_recall_flag")
    user.use_memories = False
    db_session.commit()

    _create(
        db_session,
        user,
        title="Note",
        category=MemoryCategory.NOTES,
        text="The user prefers concise answers.",
    )

    context = get_memories(user, db_session)
    # get_memories itself is not gated by use_memories (that gate lives in the
    # chat path via without_memories()); here the row is still fetched.
    assert context.user_id == user.id
    assert "The user prefers concise answers." in context.memories

    stripped = context.without_memories()
    assert stripped.memories == ()
    assert stripped.user_id == user.id


def test_brain_graph_edges_and_source_citations(db_session: Session) -> None:
    """Seed related-page edges + source citations and prove the brain graph API
    returns the right nodes (with degree), edges, related memories, and sources."""
    user: User = create_test_user(db_session, "brain_graph")

    acme = _create(
        db_session, user, title="Acme Corp", category=MemoryCategory.ENTITIES,
        text="Acme Corp is the flagship customer.",
    )
    renewal = _create(
        db_session, user, title="Contract renewal", category=MemoryCategory.CONCEPTS,
        text="Acme's contract renews in Q3.",
    )
    planning = _create(
        db_session, user, title="Q3 planning", category=MemoryCategory.WORKSTREAMS,
        text="Plan the Q3 renewal push.",
    )

    # renewal is the hub: connected to both acme and planning.
    assert add_memory_relation(db_session, user.id, acme, renewal) is True
    assert add_memory_relation(db_session, user.id, renewal, planning) is True

    add_memory_source(
        db_session, acme,
        source_type=MemorySourceType.CHAT_SESSION,
        label="Kickoff call",
        source_id="session-abc",
    )
    add_memory_source(
        db_session, renewal,
        source_type=MemorySourceType.DOCUMENT,
        label="Renewal terms.pdf",
        source_id="doc-42",
        url="https://example.com/renewal.pdf",
    )

    # Related memories: renewal <-> {acme, planning}; acme <-> {renewal}.
    assert {m.id for m in get_related_memories(db_session, user.id, renewal)} == {
        acme,
        planning,
    }
    assert {m.id for m in get_related_memories(db_session, user.id, acme)} == {renewal}

    # Source citations.
    acme_sources = get_memory_sources(db_session, acme)
    assert len(acme_sources) == 1
    assert acme_sources[0].source_type is MemorySourceType.CHAT_SESSION
    assert acme_sources[0].source_id == "session-abc"

    # Graph: 3 nodes, 2 edges, renewal has degree 2, the leaves degree 1.
    graph = get_memory_graph(db_session, user.id)
    assert {node.id for node in graph.nodes} == {acme, renewal, planning}
    assert len(graph.edges) == 2
    degree_by_id = {node.id: node.degree for node in graph.nodes}
    assert degree_by_id[renewal] == 2
    assert degree_by_id[acme] == 1
    assert degree_by_id[planning] == 1


def test_relation_rejects_self_edge_and_cross_user_edge(db_session: Session) -> None:
    """Ownership + self-edge guards on the graph writer."""
    user: User = create_test_user(db_session, "brain_owner")
    other: User = create_test_user(db_session, "brain_other")

    mine = _create(
        db_session, user, title="Mine", category=MemoryCategory.NOTES, text="mine",
    )
    theirs = _create(
        db_session, other, title="Theirs", category=MemoryCategory.NOTES, text="theirs",
    )

    # Self-edge is rejected.
    assert add_memory_relation(db_session, user.id, mine, mine) is False
    # An edge to a memory the user does not own is rejected.
    assert add_memory_relation(db_session, user.id, mine, theirs) is False
    # No edges were created.
    assert get_related_memories(db_session, user.id, mine) == []
