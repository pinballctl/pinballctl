#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_PD="$ROOT_DIR/src/instance/rules/rules.pd"
ARGS=("$@")
if [ ${#ARGS[@]} -eq 0 ]; then
  ARGS=("$DEFAULT_PD")
fi

python3 - "${ARGS[@]}" <<'PY'
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

from pinballctl.ops.rules_blob import load_rules_pd  # noqa: E402

args = list(sys.argv[1:])
summary_only = False
path_arg = None
for arg in args:
    if arg == "--summary":
        summary_only = True
    elif not arg.startswith("-") and path_arg is None:
        path_arg = arg

path = Path(path_arg) if path_arg else root / "src" / "instance" / "rules" / "rules.pd"
if not path.exists():
    print(f"rules.pd not found: {path}")
    sys.exit(2)

bundle = load_rules_pd(path)
preview = {
    "schema": bundle.schema,
    "builtAt": bundle.built_at,
    "sourceHash": bundle.source_hash,
    "ruleCount": len(bundle.rules),
    "indexKeys": len(bundle.index),
}
if not summary_only:
    preview["rules"] = bundle.rules
    preview["index"] = bundle.index
print(json.dumps(preview, indent=2))
PY
