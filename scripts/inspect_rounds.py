from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.memory_store import DEFAULT_MEMORY_PATH, read_memory


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect per-round optimization artifacts.")
    parser.add_argument(
        "--memory",
        type=Path,
        default=DEFAULT_MEMORY_PATH,
        help="Path to memory.jsonl",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of rounds to return",
    )
    parser.add_argument(
        "--mode",
        choices=["list", "flag"],
        default="list",
        help="list: summarize recent rounds; flag: show only suspicious rounds",
    )
    args = parser.parse_args()

    records = read_memory(args.memory)
    rounds = [_load_round_bundle(record) for record in records]
    rounds = [item for item in rounds if item]

    if args.mode == "flag":
        payload = {
            "mode": "flag",
            "memory_path": str(args.memory),
            "count": 0,
            "rounds": [],
        }
        flagged = [item for item in rounds if item["flags"]]
        selected = list(reversed(flagged))[: max(0, args.limit)]
        payload["count"] = len(selected)
        payload["rounds"] = selected
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return

    selected = list(reversed(rounds))[: max(0, args.limit)]
    payload = {
        "mode": "list",
        "memory_path": str(args.memory),
        "count": len(selected),
        "rounds": selected,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _load_round_bundle(record: Dict[str, Any]) -> Dict[str, Any]:
    round_id = str(record.get("round_id", ""))
    artifact_paths = record.get("artifact_paths")
    if not isinstance(artifact_paths, dict):
        return {
            "round_id": round_id,
            "flags": ["missing_artifact_paths"],
            "memory_summary": _memory_summary(record),
        }

    round_record = _load_json(artifact_paths.get("round_record_path"))
    evaluation_record = _load_json(artifact_paths.get("evaluation_record_path"))
    parameter_record = _load_json(artifact_paths.get("parameter_record_path"))

    flags = _collect_flags(record, round_record, evaluation_record, parameter_record)
    return {
        "round_id": round_id,
        "flags": flags,
        "memory_summary": _memory_summary(record),
        "round_summary": _round_summary(round_record, evaluation_record, parameter_record),
        "artifact_paths": artifact_paths,
    }


def _memory_summary(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rank": record.get("rank"),
        "win_rate": record.get("win_rate"),
        "runtime_policy": record.get("runtime_policy"),
        "failure_reason": record.get("failure_reason"),
        "generation_succeeded": record.get("generation_succeeded"),
        "generation_error": record.get("generation_error"),
        "illegal_moves": record.get("illegal_moves"),
        "timeouts": record.get("timeouts"),
        "crashes": record.get("crashes"),
        "next_focus": record.get("next_focus"),
    }


def _round_summary(
    round_record: Dict[str, Any],
    evaluation_record: Dict[str, Any],
    parameter_record: Dict[str, Any],
) -> Dict[str, Any]:
    game_stats = evaluation_record.get("game_result_statistics", {})
    abnormal = evaluation_record.get("abnormal_events", {})
    parameter_tuning = parameter_record.get("tuning", {})
    return {
        "version_identifier": round_record.get("version_identifier", {}),
        "runtime_policy": evaluation_record.get("runtime_policy"),
        "formal_execution_backend": evaluation_record.get("formal_execution_backend"),
        "rank": game_stats.get("rank"),
        "win_rate": game_stats.get("win_rate"),
        "games": game_stats.get("games"),
        "wins": game_stats.get("wins"),
        "losses": game_stats.get("losses"),
        "draws": game_stats.get("draws"),
        "illegal_moves": abnormal.get("illegal_moves"),
        "timeouts": abnormal.get("timeouts"),
        "crashes": abnormal.get("crashes"),
        "runtime_errors": abnormal.get("runtime_errors", []),
        "key_failure_positions": evaluation_record.get("key_failure_positions", []),
        "next_round_revision_plan": evaluation_record.get("next_round_revision_plan", {}),
        "generation_succeeded": (
            evaluation_record.get("version", {}).get("generation_succeeded")
        ),
        "generation_error": evaluation_record.get("version", {}).get("generation_error", ""),
        "validator_passed": evaluation_record.get("version", {}).get("validator_passed"),
        "parameter_action": parameter_tuning.get("action"),
        "parameter_reason_code": parameter_tuning.get("reason_code"),
        "selected_block": parameter_tuning.get("selected_block"),
        "effective_changed_paths": parameter_record.get("effective_changed_paths", []),
    }


def _collect_flags(
    record: Dict[str, Any],
    round_record: Dict[str, Any],
    evaluation_record: Dict[str, Any],
    parameter_record: Dict[str, Any],
) -> List[str]:
    flags: List[str] = []
    if not round_record:
        flags.append("missing_round_record")
    if not evaluation_record:
        flags.append("missing_evaluation_record")
    if not parameter_record:
        flags.append("missing_parameter_record")
        return flags

    abnormal = evaluation_record.get("abnormal_events", {})
    if int(abnormal.get("illegal_moves") or 0) > 0:
        flags.append("illegal_moves")
    if int(abnormal.get("timeouts") or 0) > 0:
        flags.append("timeouts")
    if int(abnormal.get("crashes") or 0) > 0:
        flags.append("crashes")
    if abnormal.get("runtime_errors"):
        flags.append("runtime_errors")

    version = evaluation_record.get("version", {})
    if version and version.get("generation_succeeded") is False:
        flags.append("generation_failed")
    if version and version.get("validator_passed") is False:
        flags.append("validator_failed")

    parameter_tuning = parameter_record.get("tuning", {})
    action = parameter_tuning.get("action")
    reason_code = parameter_tuning.get("reason_code")
    if action in {"freeze", "hold"} and reason_code in {
        "no_gate_cross",
        "direction_unstable",
        "negative_signal",
    }:
        flags.append(f"tuning_{action}_{reason_code}")

    if parameter_tuning.get("promoted_strategy_profile"):
        flags.append("profile_promoted")
    if round_record.get("version_identifier", {}).get("candidate_agent_promoted"):
        flags.append("agent_promoted")

    if not record.get("artifact_paths"):
        flags.append("missing_artifact_paths")
    return flags


def _load_json(path_value: Any) -> Dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


if __name__ == "__main__":
    main()
