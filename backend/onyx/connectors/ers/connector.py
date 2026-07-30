"""Connector for ERS (Entity Resolution System).

Indexes the resolved book of business — clients, advisors, annuity contracts,
life policies, and carriers — so it is searchable in Onyx. ERS has already
deduplicated these across upstream providers (Orion, NIC, Ibexis, Proformex,
Salesforce, Allianz), so one document here is one resolved entity rather than
one source record.
"""

import copy
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

from onyx.configs.constants import DocumentSource
from onyx.connectors.ers.client import DEFAULT_BASE_URL
from onyx.connectors.ers.client import ErsClient
from onyx.connectors.ers.client import ErsGraphQLError
from onyx.connectors.exceptions import ConnectorValidationError
from onyx.connectors.interfaces import CheckpointedConnector
from onyx.connectors.interfaces import CheckpointOutput
from onyx.connectors.interfaces import SecondsSinceUnixEpoch
from onyx.connectors.models import ConnectorCheckpoint
from onyx.connectors.models import ConnectorFailure
from onyx.connectors.models import ConnectorMissingCredentialError
from onyx.connectors.models import Document
from onyx.connectors.models import EntityFailure
from onyx.connectors.models import TextSection
from onyx.utils.datetime import datetime_to_utc
from onyx.utils.logger import setup_logger

logger = setup_logger()

_KEY_ID = "ers_key_id"
_PRIVATE_KEY = "ers_private_key"

_DEFAULT_PAGE_SIZE = 200
# Every phase is a full sweep, so cap the work a single checkpoint round does.
_MAX_PAGES_PER_CALL = 5


class ErsPhase(str, Enum):
    CLIENTS = "clients"
    ADVISORS = "advisors"
    ANNUITY = "annuity"
    LIFE = "life"
    CARRIERS = "carriers"
    DONE = "done"


_PHASE_ORDER = [
    ErsPhase.CLIENTS,
    ErsPhase.ADVISORS,
    ErsPhase.ANNUITY,
    ErsPhase.LIFE,
    ErsPhase.CARRIERS,
    ErsPhase.DONE,
]


class ErsCheckpoint(ConnectorCheckpoint):
    phase: ErsPhase = ErsPhase.CLIENTS
    offset: int = 0


class ErsPageQuery(BaseModel):
    """A paged QueryRoot field, plus the row fields to select from it."""

    field: str
    fields: list[str]
    pii_fields: list[str] = []


_CLIENTS_QUERY = ErsPageQuery(
    field="insuranceClientsPage",
    fields=[
        "clientKey",
        "masterClientId",
        "orionId",
        "clientName",
        "firstName",
        "lastName",
        "state",
        "advisorName",
        "sources",
        "annuityCount",
        "lifeCount",
        "totalPolicies",
        "annuityValue",
        "lifePremium",
    ],
)

_ADVISORS_QUERY = ErsPageQuery(
    field="insuranceAdvisorsPage",
    fields=[
        "advisorName",
        "masterAdvisorId",
        "orionRepId",
        "sources",
        "annuityCount",
        "lifeCount",
        "totalPolicies",
        "totalAnnuityValue",
        "totalLifePremium",
    ],
)

_POLICY_FIELDS = [
    "policyKey",
    "source",
    "sourceId",
    "ownerName",
    "policyNumber",
    "contractNo",
    "productName",
    "productType",
    "carrier",
    "status",
    "accountValue",
    "surrenderValue",
    "deathBenefit",
    "totalPremium",
    "modalPremium",
    "issueDate",
    "paidToDate",
    "advisorName",
    "distributor",
    "state",
    "insuredName",
    "annuitantName",
    "beneficiaryName",
    "riderNames",
    "paymentFrequency",
    "underwritingClass",
    "lastSyncedAt",
]

# Direct contact identifiers. Indexing these copies PII into the search index,
# so they are opt-in per connector.
_POLICY_PII_FIELDS = [
    "ownerAddress",
    "ownerCity",
    "ownerZip",
    "ownerPhone",
    "ownerEmail",
    "insuredEmail",
    "annuitantEmail",
    "advisorEmail",
    "beneficiaryEmails",
    "annuitantBirthDate",
]

_ANNUITY_QUERY = ErsPageQuery(
    field="annuityBookPage",
    fields=_POLICY_FIELDS,
    pii_fields=_POLICY_PII_FIELDS,
)

_LIFE_QUERY = ErsPageQuery(
    field="lifeBookPage",
    fields=_POLICY_FIELDS,
    pii_fields=_POLICY_PII_FIELDS,
)

_CARRIERS_QUERY = """
query OnyxCarriers {
  carriers {
    carrierId
    displayName
    annuityCount
    lifeCount
    hasAnnuity
    hasLife
    rawNames
  }
}
"""

_PHASE_QUERIES: dict[ErsPhase, ErsPageQuery] = {
    ErsPhase.CLIENTS: _CLIENTS_QUERY,
    ErsPhase.ADVISORS: _ADVISORS_QUERY,
    ErsPhase.ANNUITY: _ANNUITY_QUERY,
    ErsPhase.LIFE: _LIFE_QUERY,
}


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime_to_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _render(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v not in (None, ""))
    return str(value)


def _label(field: str) -> str:
    """`totalAnnuityValue` -> `Total Annuity Value`."""
    spaced = "".join(f" {c}" if c.isupper() else c for c in field)
    return spaced.strip().title()


def _lines(row: dict[str, Any], fields: list[str]) -> list[str]:
    return [
        f"{_label(f)}: {_render(row[f])}"
        for f in fields
        if row.get(f) not in (None, "", [], 0.0)
    ]


def _metadata(row: dict[str, Any], fields: list[str]) -> dict[str, str | list[str]]:
    metadata: dict[str, str | list[str]] = {}
    for f in fields:
        value = row.get(f)
        if value in (None, "", []):
            continue
        metadata[f] = [str(v) for v in value] if isinstance(value, list) else str(value)
    return metadata


class ErsConnector(CheckpointedConnector[ErsCheckpoint]):
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        advisors: list[str] | None = None,
        include_contact_pii: bool = False,
        batch_size: int = _DEFAULT_PAGE_SIZE,
    ) -> None:
        self._base_url = base_url
        self._advisors = advisors or []
        self._include_contact_pii = include_contact_pii
        self._batch_size = batch_size
        self._client: ErsClient | None = None

    def load_credentials(self, credentials: dict[str, Any]) -> dict[str, Any] | None:
        key_id = credentials.get(_KEY_ID)
        private_key = credentials.get(_PRIVATE_KEY)
        if not key_id or not private_key:
            raise ConnectorMissingCredentialError("ERS")
        self._client = ErsClient(self._base_url, key_id, private_key)
        return None

    @property
    def client(self) -> ErsClient:
        if self._client is None:
            raise ConnectorMissingCredentialError("ERS")
        return self._client

    def _page_input(self, offset: int) -> dict[str, Any]:
        page_input: dict[str, Any] = {"limit": self._batch_size, "offset": offset}
        if self._advisors:
            page_input["filter"] = {"advisors": self._advisors}
        return page_input

    def _row_fields(self, query: ErsPageQuery) -> list[str]:
        if self._include_contact_pii:
            return query.fields + query.pii_fields
        return query.fields

    def _fetch_page(
        self, query: ErsPageQuery, offset: int
    ) -> tuple[int, list[dict[str, Any]]]:
        selection = "\n        ".join(self._row_fields(query))
        gql = f"""
query OnyxErsPage($input: InsuranceBookPageInput!) {{
  {query.field}(input: $input) {{
    total
    rows {{
        {selection}
    }}
  }}
}}
"""
        data = self.client.execute(gql, {"input": self._page_input(offset)})
        page = data[query.field]
        return page["total"], page["rows"]

    def _client_to_document(self, row: dict[str, Any]) -> Document:
        name = row.get("clientName") or row["clientKey"]
        header = (
            f"Insurance client {name}"
            + (f", advised by {row['advisorName']}" if row.get("advisorName") else "")
            + f". Resolved from {len(row.get('sources') or [])} source system(s)"
            f" into {row.get('totalPolicies', 0)} policies."
        )
        return Document(
            id=f"ers:client:{row['clientKey']}",
            source=DocumentSource.ERS,
            title=f"ERS client: {name}",
            semantic_identifier=f"Client: {name}",
            sections=[
                TextSection(
                    text="\n".join(
                        [header, *_lines(row, self._row_fields(_CLIENTS_QUERY))]
                    )
                )
            ],
            metadata=_metadata(
                row,
                [
                    "clientKey",
                    "masterClientId",
                    "orionId",
                    "state",
                    "advisorName",
                    "sources",
                ],
            ),
        )

    def _advisor_to_document(self, row: dict[str, Any]) -> Document:
        name = row["advisorName"]
        header = (
            f"Insurance advisor {name} with {row.get('totalPolicies', 0)} policies"
            f" ({row.get('annuityCount', 0)} annuity, {row.get('lifeCount', 0)} life)."
        )
        return Document(
            id=f"ers:advisor:{row.get('masterAdvisorId') or name}",
            source=DocumentSource.ERS,
            title=f"ERS advisor: {name}",
            semantic_identifier=f"Advisor: {name}",
            sections=[
                TextSection(
                    text="\n".join(
                        [header, *_lines(row, self._row_fields(_ADVISORS_QUERY))]
                    )
                )
            ],
            metadata=_metadata(
                row, ["masterAdvisorId", "orionRepId", "advisorName", "sources"]
            ),
        )

    def _policy_to_document(self, row: dict[str, Any], phase: ErsPhase) -> Document:
        kind = "annuity contract" if phase == ErsPhase.ANNUITY else "life policy"
        number = row.get("policyNumber") or row.get("contractNo") or row["policyKey"]
        owner = row.get("ownerName") or "unknown owner"
        header = (
            f"{kind.capitalize()} {number} held by {owner}"
            + (f" with {row['carrier']}" if row.get("carrier") else "")
            + (f", status {row['status']}" if row.get("status") else "")
            + f". Sourced from {row.get('source', 'unknown')}."
        )
        query = _ANNUITY_QUERY if phase == ErsPhase.ANNUITY else _LIFE_QUERY
        return Document(
            id=f"ers:policy:{row['policyKey']}",
            source=DocumentSource.ERS,
            title=f"ERS {kind}: {number}",
            semantic_identifier=f"{kind.capitalize()}: {number}",
            sections=[
                TextSection(
                    text="\n".join([header, *_lines(row, self._row_fields(query))])
                )
            ],
            metadata=_metadata(
                row,
                [
                    "policyKey",
                    "source",
                    "carrier",
                    "status",
                    "productType",
                    "advisorName",
                    "state",
                ],
            ),
            doc_updated_at=_parse_time(row.get("lastSyncedAt")),
        )

    def _carrier_to_document(self, row: dict[str, Any]) -> Document:
        name = row["displayName"]
        header = (
            f"Insurance carrier {name} with {row.get('annuityCount', 0)} annuity"
            f" contracts and {row.get('lifeCount', 0)} life policies in the book."
        )
        fields = ["carrierId", "displayName", "annuityCount", "lifeCount", "rawNames"]
        return Document(
            id=f"ers:carrier:{row['carrierId']}",
            source=DocumentSource.ERS,
            title=f"ERS carrier: {name}",
            semantic_identifier=f"Carrier: {name}",
            sections=[TextSection(text="\n".join([header, *_lines(row, fields)]))],
            metadata=_metadata(row, ["carrierId", "displayName", "rawNames"]),
        )

    def _advance_phase(self, checkpoint: ErsCheckpoint) -> ErsCheckpoint:
        checkpoint.phase = _PHASE_ORDER[_PHASE_ORDER.index(checkpoint.phase) + 1]
        checkpoint.offset = 0
        if checkpoint.phase == ErsPhase.DONE:
            checkpoint.has_more = False
        return checkpoint

    def load_from_checkpoint(
        self,
        start: SecondsSinceUnixEpoch,  # noqa: ARG002
        end: SecondsSinceUnixEpoch,  # noqa: ARG002
        checkpoint: ErsCheckpoint,
    ) -> CheckpointOutput[ErsCheckpoint]:
        """Sweep the whole book.

        The ERS page queries expose no updated-since filter, so the window is
        not applicable — each run re-reads every row. Documents carry stable
        ids and `lastSyncedAt`, so re-indexing is idempotent.
        """
        checkpoint = copy.deepcopy(checkpoint)

        if checkpoint.phase == ErsPhase.DONE:
            checkpoint.has_more = False
            return checkpoint

        if checkpoint.phase == ErsPhase.CARRIERS:
            try:
                for row in self.client.execute(_CARRIERS_QUERY)["carriers"]:
                    yield self._carrier_to_document(row)
            except ErsGraphQLError as e:
                yield ConnectorFailure(
                    failed_entity=EntityFailure(entity_id="carriers"),
                    failure_message=f"Failed to fetch ERS carriers: {e}",
                    exception=e,
                )
            return self._advance_phase(checkpoint)

        query = _PHASE_QUERIES[checkpoint.phase]
        for _ in range(_MAX_PAGES_PER_CALL):
            try:
                total, rows = self._fetch_page(query, checkpoint.offset)
            except ErsGraphQLError as e:
                yield ConnectorFailure(
                    failed_entity=EntityFailure(
                        entity_id=f"{query.field}:{checkpoint.offset}"
                    ),
                    failure_message=(
                        f"Failed to fetch {query.field} at offset"
                        f" {checkpoint.offset}: {e}"
                    ),
                    exception=e,
                )
                checkpoint.has_more = True
                return checkpoint

            for row in rows:
                if checkpoint.phase == ErsPhase.CLIENTS:
                    yield self._client_to_document(row)
                elif checkpoint.phase == ErsPhase.ADVISORS:
                    yield self._advisor_to_document(row)
                else:
                    yield self._policy_to_document(row, checkpoint.phase)

            checkpoint.offset += len(rows)
            if not rows or checkpoint.offset >= total:
                return self._advance_phase(checkpoint)

        return checkpoint

    def build_dummy_checkpoint(self) -> ErsCheckpoint:
        return ErsCheckpoint(has_more=True)

    def validate_checkpoint_json(self, checkpoint_json: str) -> ErsCheckpoint:
        return ErsCheckpoint.model_validate_json(checkpoint_json)

    def validate_connector_settings(self) -> None:
        if self._batch_size < 1:
            raise ConnectorValidationError("Batch size must be at least 1")
        self.client.validate()
