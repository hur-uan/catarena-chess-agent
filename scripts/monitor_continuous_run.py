from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.memory_store import DEFAULT_MEMORY_PATH, read_memory

REQUIRED_COMPLETION_FILES = (
    "optimization_report.json",
    "round_record.json",
    "evaluation_record.json",
    "parameter_record.json",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize progress and effectiveness for a continuous CATArena run."
    )
    parser.add_argument("--reports-dir", type=Path, default=Path("reports/catarena_platform"))
    parser.add_argument("--memory", type=Path, default=DEFAULT_MEMORY_PATH)
    parser.add_argument(
        "--prefix",
        required=True,
        help="Round prefix, for example live_profile",
    )
    parser.add_argument("--start-round", type=int, required=True)
    parser.add_argument("--round-count", type=int, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--stop-when-complete", action="store_true")
    args = parser.parse_args()

    while True:
        payload = build_summary(
            reports_dir=args.reports_dir,
            memory_path=args.memory,
            prefix=args.prefix,
            start_round=args.start_round,
            round_count=args.round_count,
        )
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

        if args.output is not None:
            _atomic_write(args.output, text)
        else:
            print(text)

        if not args.watch:
            return
        if args.stop_when_complete and (
            payload["aggregate"]["completed_count"] >= payload["expected"]["round_count"]
        ):
            return
        time.sleep(max(1.0, args.interval))


def build_summary(
    *,
    reports_dir: Path,
    memory_path: Path,
    prefix: str,
    start_round: int,
    round_count: int,
) -> Dict[str, Any]:
    reports_dir = Path(reports_dir)
    expected_round_ids = [
        f"{prefix}_{round_number:03d}"
        for round_number in range(start_round, start_round + max(0, round_count))
    ]
    expected_round_id_set = set(expected_round_ids)
    memory_records = read_memory(memory_path)
    filtered_memory = [
        record
        for record in memory_records
        if str(record.get("round_id", "")) in expected_round_id_set
    ]
    latest_memory_by_round = _latest_memory_by_round(filtered_memory)

    rounds: List[Dict[str, Any]] = []
    flag_counts: Counter[str] = Counter()
    parameter_action_counts: Counter[str] = Counter()
    win_rates: List[float] = []

    completed_count = 0
    incomplete_count = 0
    discovered_count = 0
    generation_succeeded_count = 0
    validator_passed_count = 0
    changed_candidate_count = 0
    effective_profile_change_count = 0
    repair_round_count = 0
    latest_round_started = ""
    latest_round_completed = ""

    for round_id in expected_round_ids:
        round_dir = reports_dir / round_id
        entry = _build_round_entry(round_id, round_dir, latest_memory_by_round.get(round_id, {}))
        rounds.append(entry)

        if entry["status"] != "missing":
            discovered_count += 1
            latest_round_started = round_id
        if entry["status"] == "completed":
            completed_count += 1
            latest_round_completed = round_id
            win_rate = entry.get("win_rate")
            if isinstance(win_rate, (int, float)):
                win_rates.append(float(win_rate))
            if entry.get("generation_succeeded") is True:
                generation_succeeded_count += 1
            if entry.get("validator_passed") is True:
                validator_passed_count += 1
            if entry.get("candidate_changed") is True:
                changed_candidate_count += 1
            if int(entry.get("effective_profile_change_count") or 0) > 0:
                effective_profile_change_count += 1
            if int(entry.get("repair_attempts") or 0) > 0:
                repair_round_count += 1
            for flag in entry.get("flags", []):
                flag_counts[flag] += 1
            action = str(entry.get("parameter_action") or "")
            if action:
                parameter_action_counts[action] += 1
        elif entry["status"] == "in_progress":
            incomplete_count += 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reports_dir": str(reports_dir),
        "memory_path": str(memory_path),
        "prefix": prefix,
        "expected": {
            "start_round": start_round,
            "round_count": max(0, round_count),
            "end_round": start_round + max(0, round_count) - 1 if round_count > 0 else start_round,
            "round_ids": expected_round_ids,
        },
        "aggregate": {
            "expected_count": len(expected_round_ids),
            "discovered_count": discovered_count,
            "completed_count": completed_count,
            "incomplete_count": incomplete_count,
            "missing_count": max(0, len(expected_round_ids) - discovered_count),
            "latest_round_started": latest_round_started,
            "latest_round_completed": latest_round_completed,
            "generation_succeeded_count": generation_succeeded_count,
            "validator_passed_count": validator_passed_count,
            "changed_candidate_count": changed_candidate_count,
            "effective_profile_change_count": effective_profile_change_count,
            "repair_round_count": repair_round_count,
            "mean_win_rate": (
                round(sum(win_rates) / len(win_rates), 4) if win_rates else None
            ),
            "flag_counts": dict(sorted(flag_counts.items())),
            "parameter_action_counts": dict(sorted(parameter_action_counts.items())),
        },
        "memory": {
            "matching_records": len(filtered_memory),
            "unique_round_ids": sorted(latest_memory_by_round),
        },
        "rounds": rounds,
    }
    return payload


def _build_round_entry(
    round_id: str,
    round_dir: Path,
    memory_record: Dict[str, Any],
) -> Dict[str, Any]:
    files_present = sorted(path.name for path in round_dir.iterdir()) if round_dir.is_dir() else []
    entry: Dict[str, Any] = {
        "round_id": round_id,
        "artifact_dir": str(round_dir),
        "status": "missing",
        "files_present": files_present,
        "flags": [],
        "memory_seen": bool(memory_record),
    }

    if not round_dir.is_dir():
        return entry

    if not all((round_dir / name).exists() for name in REQUIRED_COMPLETION_FILES):
        entry["status"] = "in_progress"
        return entry

    round_record = _load_json(round_dir / "round_record.json")
    evaluation_record = _load_json(round_dir / "evaluation_record.json")
    parameter_record = _load_json(round_dir / "parameter_record.json")

    version = evaluation_record.get("version", {})
    abnormal = evaluation_record.get("abnormal_events", {})
    game_stats = evaluation_record.get("game_result_statistics", {})
    core_mod = evaluation_record.get("core_modification_summary", {})
    tuning = parameter_record.get("tuning", {})
    effective_changed_paths = parameter_record.get("effective_changed_paths", [])
    flags = _collect_flags(round_record, evaluation_record, parameter_record)

    entry.update(
        {
            "status": "completed",
            "rank": game_stats.get("rank"),
            "win_rate": game_stats.get("win_rate"),
            "games": game_stats.get("games"),
            "wins": game_stats.get("wins"),
            "losses": game_stats.get("losses"),
            "draws": game_stats.get("draws"),
            "illegal_moves": abnormal.get("illegal_moves"),
            "timeouts": abnormal.get("timeouts"),
            "crashes": abnormal.get("crashes"),
            "generation_succeeded": version.get("generation_succeeded"),
            "validator_passed": version.get("validator_passed"),
            "repair_attempts": version.get("repair_attempts"),
            "candidate_backend": version.get("candidate_backend"),
            "candidate_path": version.get("candidate_agent_path"),
            "candidate_changed": core_mod.get("changed"),
            "parameter_action": tuning.get("action"),
            "parameter_reason_code": tuning.get("reason_code"),
            "selected_block": tuning.get("selected_block"),
            "effective_profile_change_count": len(effective_changed_paths),
            "effective_changed_paths": effective_changed_paths,
            "flags": flags,
        }
    )
    return entry


def _collect_flags(
    round_record: Dict[str, Any],
    evaluation_record: Dict[str, Any],
    parameter_record: Dict[str, Any],
) -> List[str]:
    flags: List[str] = []
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
    if version.get("generation_succeeded") is False:
        flags.append("generation_failed")
    if version.get("validator_passed") is False:
        flags.append("validator_failed")

    tuning = parameter_record.get("tuning", {})
    action = tuning.get("action")
    reason_code = tuning.get("reason_code")
    if action in {"freeze", "hold"} and reason_code in {
        "no_gate_cross",
        "direction_unstable",
        "negative_signal",
    }:
        flags.append(f"tuning_{action}_{reason_code}")
    if tuning.get("promoted_strategy_profile"):
        flags.append("profile_promoted")
    if round_record.get("version_identifier", {}).get("candidate_agent_promoted"):
        flags.append("agent_promoted")
    return flags


def _latest_memory_by_round(records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        round_id = str(record.get("round_id", ""))
        if round_id:
            latest[round_id] = record
    return latest


def _load_json(path: Path) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return {}
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _atomic_write(path: Path, text: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(output_path)


if __name__ == "__main__":
    main()
