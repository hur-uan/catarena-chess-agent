"""Historical profile pool for regression checks across optimization rounds."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from tools.pipeline_metadata import FORMAL_EXECUTION_BACKEND, RUNTIME_POLICY


class HistoricalProfileEntry(BaseModel):
    round_id: str
    profile_path: str
    rank: Optional[int] = None
    win_rate: Optional[float] = None


class OpponentPoolReport(BaseModel):
    historical_profiles: List[HistoricalProfileEntry] = Field(default_factory=list)
    selected_profiles: List[HistoricalProfileEntry] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


def build_historical_profile_pool(
    memory_records: List[Dict[str, Any]],
    *,
    current_round_id: str,
    limit: int = 3,
) -> OpponentPoolReport:
    report = OpponentPoolReport()
    seen_paths: Set[str] = set()
    skipped_legacy = 0

    for record in reversed(memory_records):
        round_id = str(record.get("round_id", ""))
        if not round_id or round_id == current_round_id:
            continue
        artifact_paths = record.get("artifact_paths")
        if not isinstance(artifact_paths, dict):
            continue
        profile_path = str(artifact_paths.get("strategy_profile_after_path", "")).strip()
        if not profile_path or profile_path in seen_paths:
            continue
        path = Path(profile_path)
        if not path.exists() or not path.is_file():
            continue
        if not _is_profile_only_round(record, artifact_paths):
            skipped_legacy += 1
            continue
        seen_paths.add(profile_path)
        report.historical_profiles.append(
            HistoricalProfileEntry(
                round_id=round_id,
                profile_path=profile_path,
                rank=_as_int(record.get("rank")),
                win_rate=_as_float(record.get("win_rate")),
            )
        )

    selected = report.historical_profiles[: max(0, limit)]
    report.selected_profiles = selected
    if skipped_legacy:
        report.notes.append(
            f"skipped {skipped_legacy} legacy rounds that predate the formal internal-runtime pipeline"
        )
    if not selected:
        report.notes.append("no historical profile artifacts available")
    return report


def _is_profile_only_round(
    record: Dict[str, Any],
    artifact_paths: Dict[str, Any],
) -> bool:
    if _matches_runtime_policy(record):
        return True

    candidate_profile_path = str(artifact_paths.get("candidate_profile_path", "")).strip()
    if candidate_profile_path.endswith(".json") and _matches_runtime_policy(
        _load_json(artifact_paths.get("evaluation_record_path"))
    ):
        return True

    evaluation_record = _load_json(artifact_paths.get("evaluation_record_path"))
    if _matches_runtime_policy(evaluation_record):
        return True

    version = evaluation_record.get("version", {})
    if isinstance(version, dict):
        candidate_profile_path = str(version.get("candidate_profile_path", "")).strip()
        if candidate_profile_path.endswith(".json") and _matches_runtime_policy(evaluation_record):
            return True

    parameter_record = _load_json(artifact_paths.get("parameter_record_path"))
    if _matches_runtime_policy(parameter_record):
        return True

    return False


def _matches_runtime_policy(record: Dict[str, Any]) -> bool:
    if str(record.get("runtime_policy", "")).strip() != RUNTIME_POLICY:
        return False
    return str(record.get("formal_execution_backend", "")).strip() == FORMAL_EXECUTION_BACKEND


def _load_json(path_value: Any) -> Dict[str, Any]:
    if not path_value:
        return {}
    path = Path(str(path_value))
    if not path.exists() or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
