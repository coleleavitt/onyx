#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
PRD_PATH = ROOT / "docs/testsprite/space-connected-knowledge-prd.json"
CODE_SUMMARY_PATH = ROOT / "docs/testsprite/space-connected-knowledge-code-summary.yaml"
PLAN_PATH = ROOT / "docs/testsprite/space-connected-knowledge-test-plan.json"
COVERAGE_PATH = ROOT / "docs/testsprite/space-connected-knowledge-coverage.json"
INVENTORY_PATH = ROOT / "docs/testsprite/space-connected-knowledge-testsprite-tests.json"


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text())
    assert isinstance(data, dict), path
    return data


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), path
    return data


def validate_steps(test: dict) -> None:
    assert test["id"], test
    assert test["title"], test["id"]
    assert test["test_id"], test["id"]
    assert test["source_file"], test["id"]
    assert test["steps"], test["id"]
    for step in test["steps"]:
        assert step["type"] in {"action", "assertion"}, step
        assert step["description"], step


def main() -> None:
    prd = load_json(PRD_PATH)
    code_summary = load_yaml(CODE_SUMMARY_PATH)
    plan = load_json(PLAN_PATH)
    coverage = load_json(COVERAGE_PATH)
    inventory = load_json(INVENTORY_PATH)

    assert prd["meta"]["project"] == "Onyx Space Connected Knowledge"
    requirements = prd["requirements"]
    requirement_ids = {requirement["id"] for requirement in requirements}
    assert len(requirement_ids) == len(requirements), "Duplicate requirement IDs"

    assert code_summary["backend"], "Code summary must describe backend changes"
    assert code_summary["frontend"], "Code summary must describe frontend changes"
    assert code_summary["testsprite_inventory"]["durable_inventory"] == str(
        INVENTORY_PATH.relative_to(ROOT)
    )
    assert code_summary["testsprite_inventory"]["durable_scripts"]
    assert code_summary["testsprite_inventory"]["stored_tests"]

    tests = plan["tests"]
    test_ids = {test["id"] for test in tests}
    stored_test_ids = {test["test_id"] for test in tests}
    assert len(test_ids) == len(tests), "Duplicate plan test IDs"
    assert len(stored_test_ids) == len(tests), "Duplicate stored TestSprite IDs"

    inventory_tests = inventory["tests"]
    inventory_by_plan = {test["plan_id"]: test for test in inventory_tests}
    assert set(inventory_by_plan) == test_ids
    assert {test["id"] for test in inventory_tests} == stored_test_ids

    for test in tests:
        validate_steps(test)
        assert set(test["requirements"]).issubset(requirement_ids), test["id"]
        inventory_test = inventory_by_plan[test["id"]]
        assert test["test_id"] == inventory_test["id"]
        assert test["durable_script"] == inventory_test["durable_script"]
        script_path = ROOT / inventory_test["durable_script"]
        assert script_path.exists(), script_path
        assert script_path.stat().st_mode & 0o111, f"{script_path} must be executable"
        assert inventory_test["code"] == f"bash {inventory_test['durable_script']}"

    requirement_coverage = plan["requirement_coverage"]
    assert set(requirement_coverage) == requirement_ids
    for requirement_id, covering_tests in requirement_coverage.items():
        assert covering_tests, requirement_id
        assert set(covering_tests).issubset(test_ids), requirement_id

    assert plan["meta"]["testsprite_inventory"] == str(
        INVENTORY_PATH.relative_to(ROOT)
    )
    assert coverage["meta"]["testsprite_inventory"] == str(
        INVENTORY_PATH.relative_to(ROOT)
    )

    summary = coverage["summary"]
    assert summary["requirements_total"] == len(requirement_ids)
    assert summary["requirements_covered"] == len(requirement_ids)
    assert summary["coverage_percent"] == 100.0
    assert summary["uncovered_requirements"] == []

    for entry in coverage["requirements"]:
        assert entry["id"] in requirement_ids, entry
        assert entry["coverage_status"] == "covered", entry["id"]
        assert entry["tests"], entry["id"]
        assert set(entry["tests"]).issubset(test_ids), entry["id"]
        assert entry["stored_test_ids"], entry["id"]

    print("Space connected knowledge TestSprite artifacts are valid")
    print("Requirement coverage: 100%")


if __name__ == "__main__":
    main()
