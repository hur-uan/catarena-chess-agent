"""Backward-compatible entry point for the official CATArena platform round."""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

from tools.catarena import DEFAULT_CATARENA_PATH
from tools.catarena_platform import run_official_catarena_chess_round


class CATArenaDryRunResult(BaseModel):
    passed: bool
    games: int
    moves_played: int
    log_path: str
    ranking_path: str
    error_report_path: str
    errors: List[str] = Field(default_factory=list)
    official_report_path: str = ""
    manifest_path: str = ""
    contract_path: str = ""


def run_catarena_dry_run(
    repo_path: Path = DEFAULT_CATARENA_PATH,
    output_dir: Path = Path("reports/catarena_dry_run"),
    max_plies: int = 20,
) -> CATArenaDryRunResult:
    official = run_official_catarena_chess_round(
        repo_path=repo_path,
        output_dir=output_dir,
        max_plies=max_plies,
    )
    return CATArenaDryRunResult(
        passed=official.passed,
        games=official.games,
        moves_played=official.moves_played,
        log_path=official.battle_log_path,
        ranking_path=official.ranking_path,
        error_report_path=official.error_report_path,
        errors=official.errors,
        official_report_path=official.official_report_path,
        manifest_path=official.manifest_path,
        contract_path=official.contract_path,
    )
