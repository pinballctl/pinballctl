#!/usr/bin/env python3
"""Generate a semantic identifier inventory and check manager/editor parity."""

import argparse
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pinballctl.game.registry import (
    COMMANDS,
    PRIVILEGED,
    LEGACY,
    RESERVED,
    extend_rules_registry,
)
from pinballctl.rules.evaluation import SUPPORTED_ACTIONS


def audit():
    registry = extend_rules_registry(
        json.loads(
            (ROOT / "src/pinballctl/app/modules/rules/registry.json").read_text()
        )
    )
    assert (
        set(k for k, v in registry["actions"].items() if not v.get("planned"))
        == SUPPORTED_ACTIONS
    ), "Editor/runtime action mismatch"
    runtime = ast.parse((ROOT / "src/pinballctl/game/runtime.py").read_text())
    handlers = {
        node.value
        for node in ast.walk(runtime)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value in COMMANDS
    }
    assert handlers == set(COMMANDS), "Manager command lacks handler"
    assert not LEGACY & set(registry["conditions"]["counter"].get("counters", []))
    assert not LEGACY & set(registry["conditions"]["flag"].get("flags", []))
    wizards = ROOT / "src/pinballctl/app/modules/rules/wizards/bundled"
    counts = {"available": 0, "unavailable": 0}
    for file in wizards.glob("*.json"):
        data = json.loads(file.read_text())
        counts[data["availability"]] += 1
        if data["availability"] != "available":
            continue
        for rule in data["rules"]:
            for action in rule.get("actions", []):
                assert action["type"] in SUPPORTED_ACTIONS, (file, action["type"])
                if action["type"] == "emit_event":
                    assert action.get("target") not in RESERVED, (file, "forged result")
    entries = {}
    for tree in ("src/pinballctl", "src/firmware/src", "tests", "docs/docs"):
        for file in sorted((ROOT / tree).rglob("*")):
            if file.suffix not in (".py", ".js", ".json", ".cpp", ".h", ".md", ".html"):
                continue
            for line, text in enumerate(
                file.read_text(errors="replace").splitlines(), 1
            ):
                for name in set(
                    re.findall(
                        r"\b(?:[A-Z][A-Z0-9_]*(?:GAME|BALL|PLAYER|CREDIT)[A-Z0-9_]*|(?:GAME|BALL|PLAYER|CREDIT)[A-Z0-9_]*)\b",
                        text,
                    )
                ):
                    item = entries.setdefault(
                        name,
                        {
                            "owner": (
                                "Ball Management"
                                if any(
                                    part in name
                                    for part in (
                                        "MOVEMENT",
                                        "SENSOR",
                                        "OBSERVED",
                                        "LAUNCHED",
                                        "DRAINED",
                                        "RECONCILED",
                                    )
                                )
                                else "Game Management"
                            ),
                            "disposition": (
                                "reject / replace with typed manager interface"
                                if name in LEGACY
                                else (
                                    "manager contract"
                                    if name in RESERVED
                                    else "retained consumer/reference; inspect listed context"
                                )
                            ),
                            "producer": (
                                "game/runtime.py or ball/runtime.py"
                                if name in RESERVED
                                else None
                            ),
                            "validator": (
                                "game/registry.py"
                                if name in RESERVED | LEGACY
                                else None
                            ),
                            "runtimeHandler": (
                                "game/runtime.py:execute"
                                if name in COMMANDS
                                else "committed outbox" if name in RESERVED else None
                            ),
                            "uiExposure": (
                                "manager registry"
                                if name in RESERVED
                                else "context dependent"
                            ),
                            "consumers": [],
                            "references": [],
                        },
                    )
                    item["references"].append(
                        {"file": str(file.relative_to(ROOT)), "line": line}
                    )
                    consumer = str(file.relative_to(ROOT))
                    if consumer not in item["consumers"]:
                        item["consumers"].append(consumer)
    return {
        "registryVersion": registry["managerContract"]["version"],
        "wizardCounts": counts,
        "identifiers": entries,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"Manager contract parity passed; {len(report['identifiers'])} semantic identifiers; {report['wizardCounts']}"
    )
