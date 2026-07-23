# TestSprite Requirement Coverage: Space Connected Knowledge

Scope: `docs/testsprite/space-connected-knowledge-prd.json`

Coverage definition: **100% scoped TestSprite requirement coverage**. This is not full repository line/branch coverage.

| Requirement | Status | Covering TestSprite tests |
| --- | --- | --- |
| SK-REQ-001 Persist exact indexed documents | Covered | SK-TC-001 / `6da9c452-847d-4ed6-8eca-6f16e3ee45f8` |
| SK-REQ-002 Persist hierarchy nodes/folders/sites | Covered | SK-TC-001 / `6da9c452-847d-4ed6-8eca-6f16e3ee45f8` |
| SK-REQ-003 Require edit access for updates | Covered | SK-TC-001 / `6da9c452-847d-4ed6-8eca-6f16e3ee45f8` |
| SK-REQ-004 Reject inaccessible connector selections | Covered | SK-TC-001 / `6da9c452-847d-4ed6-8eca-6f16e3ee45f8` |
| SK-REQ-005 Retrieval uses selected scopes and ACLs | Covered | SK-TC-001 / `6da9c452-847d-4ed6-8eca-6f16e3ee45f8` |
| SK-REQ-006 UI separates uploaded files and connected sources | Covered | SK-TC-002, SK-TC-003, SK-TC-004 |
| SK-REQ-007 Browser E2E opens picker and saves/reloads when possible | Covered | SK-TC-003, SK-TC-004, SK-TC-005 |

Summary:

- Requirements total: 7
- Requirements covered: 7
- Requirement coverage: **100%**
- Uncovered requirements: none
- Static/unit fallbacks: none required; backend/retrieval and frontend component coverage are executable local TestSprite command tests, and browser coverage runs through Playwright/TestSprite.

Durability note: the local TestSprite database and `testsprite_tests/` materializations are ignored by git, so this scope also includes a tracked runnable inventory at `docs/testsprite/space-connected-knowledge-testsprite-tests.json` and tracked command scripts under `docs/testsprite/space-connected-knowledge-tests/`.

Browser note: `SK-TC-003` exercises the real authenticated space path. When indexed hierarchy rows are available, it selects a row, saves, reloads, and verifies the selected label in the right rail. If no indexed connector hierarchy is available, the test records the honest empty-state branch while still verifying the connected-source modal and uploaded-file controls.
