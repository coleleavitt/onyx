"""Brain (self-improving memory) data layer.

Builds the "related pages" graph on top of the flat `memory` table:
- `memory_relation` stores undirected edges between a user's memories.
- `memory_source` stores the citations that link a memory to whatever produced
  it (a chat session, indexed document, connector, uploaded file, or manual).
- per-user brain settings live on the `user` row.

All DB access for the Brain feature funnels through this module (per the repo
convention that DB operations live under `onyx/db`).
"""

import datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.db.enums import MemoryCategory
from onyx.db.enums import MemorySourceType
from onyx.db.models import Memory
from onyx.db.models import MemoryRelation
from onyx.db.models import MemorySource
from onyx.db.models import User

# ---------------------------------------------------------------------------
# Brain settings
# ---------------------------------------------------------------------------


class BrainSettings(BaseModel):
    brain_enabled: bool
    brain_use_connectors: bool
    brain_focus_instructions: str | None
    brain_last_run_at: datetime.datetime | None

    @classmethod
    def from_user(cls, user: User) -> "BrainSettings":
        return cls(
            brain_enabled=user.brain_enabled,
            brain_use_connectors=user.brain_use_connectors,
            brain_focus_instructions=user.brain_focus_instructions,
            brain_last_run_at=user.brain_last_run_at,
        )


_UNSET: object = object()


def update_brain_settings(
    db_session: Session,
    user_id: UUID,
    *,
    brain_enabled: bool | None = None,
    brain_use_connectors: bool | None = None,
    brain_focus_instructions: str | None | object = _UNSET,
) -> BrainSettings | None:
    """Patch the given user's brain settings; only provided fields change.

    Passing `brain_focus_instructions=None` clears it, while omitting it leaves
    it untouched (that is why the sentinel is used instead of `None`).
    """
    user = db_session.get(User, user_id)
    if user is None:
        return None
    if brain_enabled is not None:
        user.brain_enabled = brain_enabled
    if brain_use_connectors is not None:
        user.brain_use_connectors = brain_use_connectors
    if brain_focus_instructions is not _UNSET:
        instructions = brain_focus_instructions  # type: ignore[assignment]
        user.brain_focus_instructions = (
            instructions.strip() or None if isinstance(instructions, str) else None
        )
    db_session.commit()
    return BrainSettings.from_user(user)


def mark_brain_run_complete(
    db_session: Session, user_id: UUID, *, run_at: datetime.datetime
) -> None:
    user = db_session.get(User, user_id)
    if user is None:
        return
    user.brain_last_run_at = run_at
    db_session.commit()


def list_brain_enabled_user_ids(db_session: Session) -> list[UUID]:
    return list(
        db_session.scalars(select(User.id).where(User.brain_enabled.is_(True))).all()
    )


# ---------------------------------------------------------------------------
# Related-pages graph edges
# ---------------------------------------------------------------------------


def _ordered_pair(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a < b else (b, a)


def _user_owns_all(db_session: Session, user_id: UUID, memory_ids: list[int]) -> bool:
    if not memory_ids:
        return False
    owned = set(
        db_session.scalars(
            select(Memory.id).where(
                Memory.user_id == user_id, Memory.id.in_(memory_ids)
            )
        ).all()
    )
    return owned == set(memory_ids)


def add_memory_relation(
    db_session: Session, user_id: UUID, memory_id_a: int, memory_id_b: int
) -> bool:
    """Create an undirected edge between two of the user's memories.

    Returns True when the edge exists after the call, False when the request is
    invalid (self-edge or a memory the user does not own).
    """
    if memory_id_a == memory_id_b:
        return False
    if not _user_owns_all(db_session, user_id, [memory_id_a, memory_id_b]):
        return False

    low, high = _ordered_pair(memory_id_a, memory_id_b)
    existing = db_session.get(MemoryRelation, (low, high))
    if existing is not None:
        return True
    db_session.add(MemoryRelation(memory_id_low=low, memory_id_high=high))
    db_session.commit()
    return True


def remove_memory_relation(
    db_session: Session, user_id: UUID, memory_id_a: int, memory_id_b: int
) -> bool:
    if not _user_owns_all(db_session, user_id, [memory_id_a, memory_id_b]):
        return False
    low, high = _ordered_pair(memory_id_a, memory_id_b)
    existing = db_session.get(MemoryRelation, (low, high))
    if existing is None:
        return True
    db_session.delete(existing)
    db_session.commit()
    return True


def get_related_memory_ids(db_session: Session, memory_id: int) -> list[int]:
    rows = db_session.execute(
        select(MemoryRelation.memory_id_low, MemoryRelation.memory_id_high).where(
            or_(
                MemoryRelation.memory_id_low == memory_id,
                MemoryRelation.memory_id_high == memory_id,
            )
        )
    ).all()
    return [high if low == memory_id else low for low, high in rows]


def get_related_memories(
    db_session: Session, user_id: UUID, memory_id: int
) -> list[Memory]:
    related_ids = get_related_memory_ids(db_session, memory_id)
    if not related_ids:
        return []
    return list(
        db_session.scalars(
            select(Memory)
            .where(Memory.user_id == user_id, Memory.id.in_(related_ids))
            .order_by(Memory.category, Memory.updated_at.desc())
        ).all()
    )


# ---------------------------------------------------------------------------
# Source citations
# ---------------------------------------------------------------------------


def add_memory_source(
    db_session: Session,
    memory_id: int,
    *,
    source_type: MemorySourceType,
    label: str,
    source_id: str | None = None,
    url: str | None = None,
    commit: bool = True,
) -> MemorySource:
    source = MemorySource(
        memory_id=memory_id,
        source_type=source_type,
        source_id=source_id,
        label=label[:512],
        url=url,
    )
    db_session.add(source)
    if commit:
        db_session.commit()
    return source


def get_memory_sources(db_session: Session, memory_id: int) -> list[MemorySource]:
    return list(
        db_session.scalars(
            select(MemorySource)
            .where(MemorySource.memory_id == memory_id)
            .order_by(MemorySource.created_at)
        ).all()
    )


# ---------------------------------------------------------------------------
# Graph query
# ---------------------------------------------------------------------------


class MemoryGraphNode(BaseModel):
    id: int
    title: str
    category: MemoryCategory
    degree: int
    updated_at: datetime.datetime


class MemoryGraphEdge(BaseModel):
    source: int
    target: int


class MemoryGraph(BaseModel):
    nodes: list[MemoryGraphNode]
    edges: list[MemoryGraphEdge]


def get_memory_graph(db_session: Session, user_id: UUID) -> MemoryGraph:
    """Return the user's memories as graph nodes (degree = edge count) plus the
    undirected edges between them, ready for a force-directed layout."""
    memories = list(
        db_session.scalars(
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(Memory.updated_at.desc())
        ).all()
    )
    memory_ids = {memory.id for memory in memories}
    if not memory_ids:
        return MemoryGraph(nodes=[], edges=[])

    edge_rows = db_session.execute(
        select(MemoryRelation.memory_id_low, MemoryRelation.memory_id_high).where(
            MemoryRelation.memory_id_low.in_(memory_ids),
            MemoryRelation.memory_id_high.in_(memory_ids),
        )
    ).all()

    degree: dict[int, int] = {}
    for low, high in edge_rows:
        degree[low] = degree.get(low, 0) + 1
        degree[high] = degree.get(high, 0) + 1

    nodes = [
        MemoryGraphNode(
            id=memory.id,
            title=memory.title or "Untitled memory",
            category=memory.category,
            degree=degree.get(memory.id, 0),
            updated_at=memory.updated_at,
        )
        for memory in memories
    ]
    edges = [MemoryGraphEdge(source=low, target=high) for low, high in edge_rows]
    return MemoryGraph(nodes=nodes, edges=edges)
