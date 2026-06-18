"""Build position suites from CATArena feedback for prescreen and diagnostics."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from tools.log_parser import GameLogReport
from tuning.prescreen import PrescreenPosition, default_prescreen_positions


class FenSuitePosition(BaseModel):
    name: str
    fen: str
    source: str


class FenSuiteReport(BaseModel):
    total_positions: int = 0
    feedback_positions: int = 0
    default_positions: int = 0
    duplicates_removed: int = 0
    positions: List[FenSuitePosition] = Field(default_factory=list)

    def as_prescreen_positions(self) -> List[PrescreenPosition]:
        return [PrescreenPosition(name=item.name, fen=item.fen) for item in self.positions]


def build_feedback_fen_suite(
    log_report: GameLogReport,
    *,
    include_defaults: bool = True,
    feedback_limit: int = 12,
) -> FenSuiteReport:
    positions: List[FenSuitePosition] = []
    seen = set()
    duplicates_removed = 0

    for index, fen in enumerate(log_report.key_failure_fens[: max(0, feedback_limit)], start=1):
        normalized = str(fen).strip()
        if not normalized:
            continue
        if normalized in seen:
            duplicates_removed += 1
            continue
        seen.add(normalized)
        positions.append(
            FenSuitePosition(
                name=f"feedback_failure_{index:03d}",
                fen=normalized,
                source="catarena_failure_log",
            )
        )

    feedback_positions = len(positions)
    default_positions = 0
    if include_defaults:
        for position in default_prescreen_positions():
            if position.fen in seen:
                duplicates_removed += 1
                continue
            seen.add(position.fen)
            positions.append(
                FenSuitePosition(
                    name=position.name,
                    fen=position.fen,
                    source="default_prescreen",
                )
            )
            default_positions += 1

    return FenSuiteReport(
        total_positions=len(positions),
        feedback_positions=feedback_positions,
        default_positions=default_positions,
        duplicates_removed=duplicates_removed,
        positions=positions,
    )
