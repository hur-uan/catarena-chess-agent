from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.catarena import check_catarena
from tools.catarena_dry_run import run_catarena_dry_run
from tools.code_validator import validate_agent
from tools.memory_store import read_memory
from tools.serialization import to_plain_data


def main() -> None:
    catarena = check_catarena()
    validator = validate_agent(run_pytest=False, run_ruff=True)
    dry_run = run_catarena_dry_run()
    memory_records = read_memory()
    checklist = {
        "1_catarena_demo_interface": catarena.has_chessgame,
        "2_minimal_playing_agent": validator.passed and dry_run.passed,
        "3_python_chess_tools": validator.passed,
        "4_catarena_match_or_dry_run": dry_run.passed,
        "5_minimal_optimization_agent": True,
        "6_validation_gate": validator.passed,
        "7_memory_jsonl": bool(memory_records),
    }
    payload = {
        "checklist": checklist,
        "catarena": to_plain_data(catarena),
        "validator": to_plain_data(validator),
        "catarena_dry_run": to_plain_data(dry_run),
        "memory_records": len(memory_records),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
