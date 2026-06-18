"""Analyze per-round ranking and trend data."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from tools.memory_store import read_memory


class RankingSummary(BaseModel):
    agent_name: str = "chess_agent"
    rank: Optional[int] = None
    win_rate: Optional[float] = None
    rank_delta: Optional[int] = None
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    opponent_records: Dict[str, str] = Field(default_factory=dict)
    source: Optional[str] = None
    notes: List[str] = Field(default_factory=list)


def analyze_ranking(
    ranking_path: Optional[Path],
    memory_path: Optional[Path] = None,
    agent_name: str = "chess_agent",
) -> RankingSummary:
    summary = RankingSummary(agent_name=agent_name)
    if ranking_path is None:
        summary.notes.append("ranking path not provided")
    else:
        path = Path(ranking_path)
        summary.source = str(path)
        if not path.exists():
            summary.notes.append("ranking path does not exist: %s" % path)
        elif path.suffix.lower() == ".json":
            _apply_json_ranking(summary, path)
        elif path.suffix.lower() == ".csv":
            _apply_csv_ranking(summary, path)
        else:
            _apply_text_ranking(summary, path)

    if summary.win_rate is None and summary.games:
        summary.win_rate = summary.wins / summary.games

    if memory_path is not None:
        previous = _previous_rank(Path(memory_path))
        if previous is not None and summary.rank is not None:
            summary.rank_delta = previous - summary.rank
    return summary


def _apply_json_ranking(summary: RankingSummary, path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("ranking") or data.get("results") or [data]
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _row_agent_name(row) != summary.agent_name and len(rows) > 1:
            continue
        _apply_row(summary, row)
        break


def _apply_csv_ranking(summary: RankingSummary, path: Path) -> None:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if _row_agent_name(row) != summary.agent_name and len(rows) > 1:
            continue
        _apply_row(summary, row)
        break


def _apply_text_ranking(summary: RankingSummary, path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if summary.agent_name not in line:
            continue
        parts = [part for part in line.replace(",", " ").split() if part]
        for index, part in enumerate(parts):
            if part.lower() in {"rank", "ranking"} and index + 1 < len(parts):
                summary.rank = _to_int(parts[index + 1])
            if part.lower() in {"win_rate", "winrate"} and index + 1 < len(parts):
                summary.win_rate = _to_float(parts[index + 1])


def _apply_row(summary: RankingSummary, row: Dict[str, Any]) -> None:
    summary.rank = _first_int(row, ("rank", "ranking", "place", "position"))
    summary.games = _first_int(row, ("games", "game_count", "played")) or summary.games
    summary.wins = _first_int(row, ("wins", "win")) or summary.wins
    summary.losses = _first_int(row, ("losses", "loss")) or summary.losses
    summary.draws = _first_int(row, ("draws", "draw")) or summary.draws
    summary.win_rate = _first_float(row, ("win_rate", "winrate", "score_rate"))


def _row_agent_name(row: Dict[str, Any]) -> str:
    for key in ("agent", "name", "player", "bot", "submission"):
        if key in row:
            return str(row[key])
    return "chess_agent"


def _previous_rank(memory_path: Path) -> Optional[int]:
    records = read_memory(memory_path)
    for record in reversed(records):
        value = record.get("rank")
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_int(row: Dict[str, Any], keys: tuple[str, ...]) -> Optional[int]:
    for key in keys:
        if key in row:
            return _to_int(row[key])
    return None


def _first_float(row: Dict[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    for key in keys:
        if key in row:
            return _to_float(row[key])
    return None


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip().rstrip("."))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        text = str(value).strip().rstrip("%")
        number = float(text)
        return number / 100 if "%" in str(value) else number
    except (TypeError, ValueError):
        return None

