"""Parse CATArena battle logs into structured failure-oriented reports."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, List, Optional

from pydantic import BaseModel, Field

RESULT_RE = re.compile(r"\b(1-0|0-1|1/2-1/2|draw|win|loss|lost|won)\b", re.IGNORECASE)
FEN_RE = re.compile(
    r"([rnbqkpRNBQKP1-8]+/[rnbqkpRNBQKP1-8]+/[rnbqkpRNBQKP1-8]+/"
    r"[rnbqkpRNBQKP1-8]+/[rnbqkpRNBQKP1-8]+/[rnbqkpRNBQKP1-8]+/"
    r"[rnbqkpRNBQKP1-8]+/[rnbqkpRNBQKP1-8]+ [wb] [-KQkq]+ [-a-h1-8]+ \d+ \d+)"
)


class GameRecord(BaseModel):
    source: str
    result: Optional[str] = None
    moves: int = 0
    illegal_moves: int = 0
    timeouts: int = 0
    crashes: int = 0
    runtime_errors: List[str] = Field(default_factory=list)
    key_fens: List[str] = Field(default_factory=list)
    response_times_ms: List[float] = Field(default_factory=list)
    search_depths: List[int] = Field(default_factory=list)
    cp_scores: List[int] = Field(default_factory=list)


class GameLogReport(BaseModel):
    total_games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    illegal_moves: int = 0
    timeouts: int = 0
    crashes: int = 0
    runtime_errors: List[str] = Field(default_factory=list)
    key_failure_fens: List[str] = Field(default_factory=list)
    games: List[GameRecord] = Field(default_factory=list)
    raw_files: List[str] = Field(default_factory=list)
    total_actions: int = 0
    interface_successes: int = 0
    average_response_ms: Optional[float] = None
    average_depth: Optional[float] = None
    average_cp: Optional[float] = None


def parse_logs(path_or_dir: Optional[Path]) -> GameLogReport:
    if path_or_dir is None:
        return GameLogReport()

    path = Path(path_or_dir)
    if not path.exists():
        return GameLogReport(runtime_errors=["log path does not exist: %s" % path])

    files = list(_iter_log_files(path))
    games = [_parse_file(path) for path in files]
    report = GameLogReport(
        total_games=len(games),
        games=games,
        raw_files=[str(item) for item in files],
    )

    for game in games:
        normalized_result = (game.result or "").lower()
        if normalized_result in {"1-0", "win", "won"}:
            report.wins += 1
        elif normalized_result in {"0-1", "loss", "lost"}:
            report.losses += 1
        elif normalized_result in {"1/2-1/2", "draw"}:
            report.draws += 1
        report.illegal_moves += game.illegal_moves
        report.timeouts += game.timeouts
        report.crashes += game.crashes
        report.runtime_errors.extend(game.runtime_errors)
        report.key_failure_fens.extend(game.key_fens)
        report.total_actions += game.moves
        report.interface_successes += max(0, game.moves - game.illegal_moves - game.timeouts)

    if report.total_actions > 0:
        all_response_times = [
            item
            for game in games
            for item in game.response_times_ms
        ]
        all_depths = [item for game in games for item in game.search_depths]
        all_cp_scores = [item for game in games for item in game.cp_scores]
        if all_response_times:
            report.average_response_ms = sum(all_response_times) / len(all_response_times)
        if all_depths:
            report.average_depth = sum(all_depths) / len(all_depths)
        if all_cp_scores:
            report.average_cp = sum(all_cp_scores) / len(all_cp_scores)

    report.key_failure_fens = sorted(set(report.key_failure_fens))
    return report


def _iter_log_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    for suffix in ("*.json", "*.jsonl", "*.log", "*.txt", "*.pgn"):
        yield from sorted(path.rglob(suffix))


def _parse_file(path: Path) -> GameRecord:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
            return _parse_json_record(path, data, text)
        except json.JSONDecodeError:
            pass
    if path.suffix.lower() == ".jsonl":
        records = []
        for line in text.splitlines():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if records:
            return _parse_json_record(path, records, text)
    return _parse_text_record(path, text)


def _parse_json_record(path: Path, data: Any, raw_text: str) -> GameRecord:
    flattened = " ".join(str(item) for item in _walk_values(data))
    record = _parse_text_record(path, raw_text + "\n" + flattened)
    moves = _find_first_int(data, ("moves", "ply", "turns", "move_count"))
    if moves is not None:
        record.moves = moves
    result = _find_first_text(data, ("result", "winner", "outcome", "status"))
    if result:
        record.result = _normalize_result(result)
    structured_illegal = _sum_int_fields(data, ("illegal_moves", "illegal_move_count"))
    structured_timeouts = _sum_int_fields(
        data,
        (
            "timeouts",
            "timeout_count",
            "player_a_timeouts",
            "player_b_timeouts",
        ),
    )
    structured_crashes = _sum_int_fields(
        data,
        (
            "crashes",
            "crash_count",
            "player_a_crashes",
            "player_b_crashes",
        ),
    )
    has_error_fields = _has_any_field(
        data,
        ("error", "errors", "runtime_error", "runtime_errors"),
    )
    explicit_errors = _collect_error_texts(data)
    structured_response_times = _collect_numeric_fields(
        data,
        ("response_times_ms", "elapsed_ms"),
    )
    if structured_illegal is not None:
        record.illegal_moves = structured_illegal
    if structured_timeouts is not None:
        record.timeouts = structured_timeouts
    if structured_crashes is not None:
        record.crashes = structured_crashes
    if (
        explicit_errors
        or has_error_fields
        or structured_crashes is not None
        or structured_timeouts is not None
    ):
        record.runtime_errors = explicit_errors[:20]
    if structured_response_times:
        record.response_times_ms = structured_response_times[:200]
    return record


def _parse_text_record(path: Path, text: str) -> GameRecord:
    lower = text.lower()
    illegal_moves = lower.count("illegal move") + lower.count("invalid move")
    timeouts = lower.count("timeout") + lower.count("timed out") + lower.count("time limit")
    crashes = (
        lower.count("traceback")
        + lower.count("exception")
        + lower.count("crash")
        + lower.count("failed")
    )
    runtime_errors = []
    for line in text.splitlines():
        line_lower = line.lower()
        if any(token in line_lower for token in ("traceback", "exception", "error", "failed")):
            runtime_errors.append(line.strip()[:300])

    result_match = RESULT_RE.search(text)
    result = _normalize_result(result_match.group(1)) if result_match else None
    move_count = _estimate_move_count(text)
    key_fens = sorted(set(FEN_RE.findall(text)))
    response_times_ms = _extract_named_floats(text, "elapsed_ms")
    search_depths = _extract_named_ints(text, "depth")
    cp_scores = _extract_named_ints(text, "cp")

    return GameRecord(
        source=str(path),
        result=result,
        moves=move_count,
        illegal_moves=illegal_moves,
        timeouts=timeouts,
        crashes=crashes,
        runtime_errors=runtime_errors[:20],
        key_fens=key_fens[:20],
        response_times_ms=response_times_ms[:200],
        search_depths=search_depths[:200],
        cp_scores=cp_scores[:200],
    )


def _estimate_move_count(text: str) -> int:
    uci_moves = re.findall(r"\b[a-h][1-8][a-h][1-8][qrbn]?\b", text)
    san_moves = re.findall(
        r"\b(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b",
        text,
    )
    return max(len(uci_moves), len(san_moves))


def _normalize_result(value: Any) -> Optional[str]:
    text = str(value).strip().lower()
    if text in {"1-0", "white", "white_win", "win", "won"}:
        return "1-0" if text in {"1-0", "white", "white_win"} else "win"
    if text in {"0-1", "black", "black_win", "loss", "lost"}:
        return "0-1" if text in {"0-1", "black", "black_win"} else "loss"
    if text in {"1/2-1/2", "draw", "tie"}:
        return "draw"
    return text or None


def _walk_values(data: Any) -> Iterable[Any]:
    if isinstance(data, dict):
        for value in data.values():
            yield from _walk_values(value)
    elif isinstance(data, list):
        for value in data:
            yield from _walk_values(value)
    else:
        yield data


def _find_first_text(data: Any, keys: tuple[str, ...]) -> Optional[str]:
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys and value is not None:
                return str(value)
            found = _find_first_text(value, keys)
            if found:
                return found
    if isinstance(data, list):
        for value in data:
            found = _find_first_text(value, keys)
            if found:
                return found
    return None


def _collect_numeric_fields(data: Any, keys: tuple[str, ...]) -> List[float]:
    values: List[float] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys:
                values.extend(_coerce_numeric_values(value))
            else:
                values.extend(_collect_numeric_fields(value, keys))
    elif isinstance(data, list):
        for value in data:
            values.extend(_collect_numeric_fields(value, keys))
    return values


def _coerce_numeric_values(value: Any) -> List[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, list):
        values: List[float] = []
        for item in value:
            values.extend(_coerce_numeric_values(item))
        return values
    return []


def _find_first_int(data: Any, keys: tuple[str, ...]) -> Optional[int]:
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    pass
            found = _find_first_int(value, keys)
            if found is not None:
                return found
    if isinstance(data, list):
        for value in data:
            found = _find_first_int(value, keys)
            if found is not None:
                return found
    return None


def _sum_int_fields(data: Any, keys: tuple[str, ...]) -> Optional[int]:
    total = 0
    seen = False
    if isinstance(data, dict):
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in keys:
                try:
                    total += int(value)
                    seen = True
                except (TypeError, ValueError):
                    pass
            nested = _sum_int_fields(value, keys)
            if nested is not None:
                total += nested
                seen = True
    elif isinstance(data, list):
        for value in data:
            nested = _sum_int_fields(value, keys)
            if nested is not None:
                total += nested
                seen = True
    return total if seen else None


def _collect_error_texts(data: Any) -> List[str]:
    errors: List[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in {"error", "errors", "runtime_error", "runtime_errors"}:
                errors.extend(_non_empty_error_values(value))
                continue
            errors.extend(_collect_error_texts(value))
    elif isinstance(data, list):
        for value in data:
            errors.extend(_collect_error_texts(value))
    return errors


def _has_any_field(data: Any, keys: tuple[str, ...]) -> bool:
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys:
                return True
            if _has_any_field(value, keys):
                return True
    elif isinstance(data, list):
        return any(_has_any_field(value, keys) for value in data)
    return False


def _non_empty_error_values(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text[:300]] if text else []
    if isinstance(value, dict):
        return _collect_error_texts(value)
    if isinstance(value, list):
        errors: List[str] = []
        for item in value:
            errors.extend(_non_empty_error_values(item))
        return errors
    text = str(value).strip()
    return [text[:300]] if text else []


def _extract_named_floats(text: str, key: str) -> List[float]:
    values = []
    pattern = re.compile(rf"\b{re.escape(key)}=([-+]?\d+(?:\.\d+)?)\b")
    for match in pattern.finditer(text):
        try:
            values.append(float(match.group(1)))
        except ValueError:
            continue
    return values


def _extract_named_ints(text: str, key: str) -> List[int]:
    values = []
    pattern = re.compile(rf"\b{re.escape(key)}=([-+]?\d+)\b")
    for match in pattern.finditer(text):
        try:
            values.append(int(match.group(1)))
        except ValueError:
            continue
    return values
