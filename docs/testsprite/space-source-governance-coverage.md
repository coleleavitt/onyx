# TestSprite Requirement Coverage: Space Source Governance

Scope: `docs/testsprite/space-source-governance-prd.json`

Coverage definition: **100% scoped TestSprite requirement coverage**. This is not full repository line/branch coverage.

| Requirement | Status | Covering TestSprite tests |
| --- | --- | --- |
| GOV-REQ-001 Admin-governed source scopes | Covered | GOV-TC-001, GOV-TC-004 |
| GOV-REQ-002 Policy-filtered hierarchy browsing | Covered | GOV-TC-001, GOV-TC-004 |
| GOV-REQ-003 Governed connected knowledge save path | Covered | GOV-TC-001, GOV-TC-004 |
| GOV-REQ-004 Retrieval applies selected descendants minus exclusions with ACLs | Covered | GOV-TC-001, GOV-TC-004 |
| GOV-REQ-005 Tenant and department-first SharePoint picker UX | Covered | GOV-TC-002, GOV-TC-003, GOV-TC-004 |
| GOV-REQ-006 Curated Space defaults and templates | Covered | GOV-TC-001, GOV-TC-002, GOV-TC-004 |
| GOV-REQ-007 Group admin source visibility management | Covered | GOV-TC-001, GOV-TC-002, GOV-TC-004 |
| GOV-REQ-008 Real-user E2E smoke for governed Spaces | Covered | GOV-TC-003, GOV-TC-004 |

Summary:

- Requirements total: 8
- Requirements covered: 8
- Requirement coverage: **100%**
- Uncovered requirements: none

Durability note: local TestSprite materializations under ignored `testsprite_tests/` are not authoritative. The durable package is tracked under `docs/testsprite/space-source-governance-*` with runnable scripts in `docs/testsprite/space-connected-source-governance-tests/`.

Browser note: `GOV-TC-003` runs the real Playwright admin project. It selects and persists a governed department row when local indexed hierarchy exists; otherwise it records an honest empty-state branch while still testing modal, upload, and share affordances.
