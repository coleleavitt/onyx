import base64
from typing import Any
from unittest.mock import patch

import pytest

from onyx.connectors.ers.connector import ErsCheckpoint
from onyx.connectors.ers.connector import ErsConnector
from onyx.connectors.ers.connector import ErsPhase
from onyx.connectors.models import ConnectorFailure
from onyx.connectors.models import Document

_SEED_B64 = base64.urlsafe_b64encode(bytes([7] * 32)).decode().rstrip("=")

_CLIENT_ROW = {
    "clientKey": "ck-1",
    "masterClientId": "mc-1",
    "orionId": "9001",
    "clientName": "Dana Reyes",
    "firstName": "Dana",
    "lastName": "Reyes",
    "state": "AZ",
    "advisorName": "Sam Fox",
    "sources": ["orion", "nic"],
    "annuityCount": 2,
    "lifeCount": 1,
    "totalPolicies": 3,
    "annuityValue": 250000.0,
    "lifePremium": 1200.0,
}
_ADVISOR_ROW = {
    "advisorName": "Sam Fox",
    "masterAdvisorId": "ma-1",
    "orionRepId": "77",
    "sources": ["orion"],
    "annuityCount": 5,
    "lifeCount": 2,
    "totalPolicies": 7,
    "totalAnnuityValue": 900000.0,
    "totalLifePremium": 4300.0,
}
_POLICY_ROW = {
    "policyKey": "pk-1",
    "source": "ibexis",
    "sourceId": "src-1",
    "ownerName": "Dana Reyes",
    "policyNumber": "AN-123",
    "carrier": "Ibexis",
    "status": "Active",
    "productName": "MYGA 5",
    "accountValue": 100000.0,
    "advisorName": "Sam Fox",
    "lastSyncedAt": "2026-07-01T00:00:00Z",
    "ownerEmail": "dana@example.com",
    "ownerPhone": "555-0100",
}
_CARRIER_ROW = {
    "carrierId": "c-1",
    "displayName": "Ibexis",
    "annuityCount": 12,
    "lifeCount": 0,
    "hasAnnuity": True,
    "hasLife": False,
    "rawNames": ["IBEXIS LIFE"],
}


def _connector(**kwargs: Any) -> ErsConnector:
    connector = ErsConnector(**kwargs)
    connector.load_credentials({"ers_key_id": "k1", "ers_private_key": _SEED_B64})
    return connector


class _Responder:
    """Serves each field's pages in order, recording calls for assertions."""

    def __init__(self, pages: dict[str, list[list[dict[str, Any]]]]) -> None:
        self._pages = pages
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        self.calls.append({"query": query, "variables": variables})
        if "carriers" in query:
            return {"carriers": self._pages.get("carriers", [[]])[0]}
        for field, field_pages in self._pages.items():
            if field == "carriers" or f"{field}(input:" not in query:
                continue
            offset = (variables or {})["input"]["offset"]
            total = sum(len(p) for p in field_pages)
            seen = 0
            for page in field_pages:
                if seen == offset:
                    return {field: {"total": total, "rows": page}}
                seen += len(page)
            return {field: {"total": total, "rows": []}}
        raise AssertionError(f"unexpected query: {query}")


def _run(connector: ErsConnector) -> tuple[list[Document], list[ConnectorFailure]]:
    docs: list[Document] = []
    failures: list[ConnectorFailure] = []
    checkpoint = connector.build_dummy_checkpoint()
    for _ in range(50):
        if not checkpoint.has_more:
            break
        gen = connector.load_from_checkpoint(0, 0, checkpoint)
        try:
            while True:
                item = next(gen)
                if isinstance(item, ConnectorFailure):
                    failures.append(item)
                elif isinstance(item, Document):
                    docs.append(item)
        except StopIteration as e:
            checkpoint = e.value
    return docs, failures


def _failed_entity_ids(failures: list[ConnectorFailure]) -> list[str]:
    return [f.failed_entity.entity_id for f in failures if f.failed_entity]


_ALL_PAGES = {
    "insuranceClientsPage": [[_CLIENT_ROW]],
    "insuranceAdvisorsPage": [[_ADVISOR_ROW]],
    "annuityBookPage": [[_POLICY_ROW]],
    "lifeBookPage": [[]],
    "carriers": [[_CARRIER_ROW]],
}


def test_indexes_every_phase_and_terminates() -> None:
    connector = _connector()
    with patch.object(connector.client, "execute", _Responder(_ALL_PAGES)):
        docs, failures = _run(connector)

    assert not failures
    assert [d.id for d in docs] == [
        "ers:client:ck-1",
        "ers:advisor:ma-1",
        "ers:policy:pk-1",
        "ers:carrier:c-1",
    ]


def test_paginates_until_total_is_reached() -> None:
    rows = [dict(_CLIENT_ROW, clientKey=f"ck-{i}") for i in range(5)]
    pages = dict(_ALL_PAGES, insuranceClientsPage=[rows[:2], rows[2:4], rows[4:]])
    connector = _connector(batch_size=2)
    execute = _Responder(pages)
    with patch.object(connector.client, "execute", execute):
        docs, failures = _run(connector)

    assert not failures
    client_ids = [d.id for d in docs if d.id.startswith("ers:client:")]
    assert client_ids == [f"ers:client:ck-{i}" for i in range(5)]


def test_contact_pii_is_excluded_by_default() -> None:
    connector = _connector()
    with patch.object(connector.client, "execute", _Responder(_ALL_PAGES)):
        docs, _ = _run(connector)

    policy = next(d for d in docs if d.id == "ers:policy:pk-1")
    text = policy.sections[0].text or ""
    assert "dana@example.com" not in text
    assert "555-0100" not in text


def test_contact_pii_is_included_when_opted_in() -> None:
    connector = _connector(include_contact_pii=True)
    execute = _Responder(_ALL_PAGES)
    with patch.object(connector.client, "execute", execute):
        docs, _ = _run(connector)

    annuity_query = next(
        c["query"] for c in execute.calls if "annuityBookPage(input:" in c["query"]
    )
    assert "ownerEmail" in annuity_query

    policy = next(d for d in docs if d.id == "ers:policy:pk-1")
    assert "dana@example.com" in (policy.sections[0].text or "")


def test_advisor_filter_is_pushed_into_the_query() -> None:
    connector = _connector(advisors=["Sam Fox"])
    execute = _Responder(_ALL_PAGES)
    with patch.object(connector.client, "execute", execute):
        _run(connector)

    paged = [c for c in execute.calls if c["variables"]]
    assert paged
    assert all(
        c["variables"]["input"]["filter"] == {"advisors": ["Sam Fox"]} for c in paged
    )


def test_policy_carries_last_synced_at() -> None:
    connector = _connector()
    with patch.object(connector.client, "execute", _Responder(_ALL_PAGES)):
        docs, _ = _run(connector)

    policy = next(d for d in docs if d.id == "ers:policy:pk-1")
    assert policy.doc_updated_at is not None
    assert policy.doc_updated_at.year == 2026


def test_query_failure_yields_failure_and_advances_phase() -> None:
    from onyx.connectors.ers.client import ErsGraphQLError

    def execute(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        if "insuranceClientsPage(input:" in query:
            raise ErsGraphQLError("boom")
        return _Responder(_ALL_PAGES)(query, variables)

    connector = _connector()
    with patch.object(connector.client, "execute", execute):
        docs, failures = _run(connector)

    assert _failed_entity_ids(failures) == ["insuranceClientsPage:0"]
    # The remaining phases still run.
    assert "ers:advisor:ma-1" in [d.id for d in docs]


def test_checkpoint_round_trips_through_json() -> None:
    connector = _connector()
    checkpoint = ErsCheckpoint(has_more=True, phase=ErsPhase.ANNUITY, offset=400)
    restored = connector.validate_checkpoint_json(checkpoint.model_dump_json())
    assert restored.phase == ErsPhase.ANNUITY
    assert restored.offset == 400


def test_missing_credentials_are_rejected() -> None:
    from onyx.connectors.models import ConnectorMissingCredentialError

    with pytest.raises(ConnectorMissingCredentialError):
        ErsConnector().load_credentials({"ers_key_id": "k1"})
