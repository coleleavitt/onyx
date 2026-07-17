#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRD_PATH = ROOT / "docs/testsprite/standard_prd.json"
PLAN_PATH = ROOT / "docs/testsprite/testsprite_frontend_test_plan.json"


def load_json(path: Path) -> dict:
    with path.open() as file:
        data = json.load(file)
    assert isinstance(data, dict), path
    return data


def main() -> None:
    prd = load_json(PRD_PATH)
    plan = load_json(PLAN_PATH)

    assert prd["meta"]["project"] == "Onyx Regression Coverage"
    assert prd["core_goals"], "PRD must list goals"
    assert prd["validation_criteria"], "PRD must list validation criteria"
    assert prd["features"], "PRD must map features to files"

    tests = plan["tests"]
    assert len(tests) >= 10
    ids = [test["id"] for test in tests]
    assert len(ids) == len(set(ids)), "Test ids must be unique"

    for test in tests:
        assert test["title"]
        assert test["test_id"]
        assert test["source_file"]
        assert test["steps"], test["id"]
        for step in test["steps"]:
            assert step["type"] in {"action", "assertion"}
            assert step["description"]

    print("TestSprite JSON artifacts are valid")


if __name__ == "__main__":
    main()
