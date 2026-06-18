"""Compatibility wrapper that now runs the official CATArena-backed dry run."""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

from tools.catarena_dry_run import run_catarena_dry_run


class DryRunResult(BaseModel):
    passed: bool
    games: int
    moves_checked: int
    log_path: str
    ranking_path: str
    error_report_path: str
    errors: List[str] = Field(default_factory=list)
    official_report_path: str = ""
    manifest_path: str = ""
    contract_path: str = ""


def run_local_dry_run(output_dir: Path = Path("reports/local_dry_run")) -> DryRunResult:
    official = run_catarena_dry_run(output_dir=output_dir)
    return DryRunResult(
        passed=official.passed,
        games=official.games,
        moves_checked=official.moves_played,
        log_path=official.log_path,
        ranking_path=official.ranking_path,
        error_report_path=official.error_report_path,
        errors=official.errors,
        official_report_path=official.official_report_path,
        manifest_path=official.manifest_path,
        contract_path=official.contract_path,
    )
