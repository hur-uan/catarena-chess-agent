"""Local validation runner for generated chess agent code."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    name: str
    passed: bool
    output: str = ""


class ValidatorReport(BaseModel):
    passed: bool
    checks: List[CheckResult] = Field(default_factory=list)


def validate_agent(
    agent_path: Path = Path("agents/chess_agent.py"),
    run_pytest: bool = False,
    run_ruff: bool = True,
) -> ValidatorReport:
    checks: List[CheckResult] = []
    checks.append(_run_command("py_compile", [sys.executable, "-m", "py_compile", str(agent_path)]))

    if run_ruff:
        ruff_path = _find_ruff()
        if ruff_path:
            checks.append(_run_command("ruff", [ruff_path, "check", str(agent_path)]))
        else:
            checks.append(
                CheckResult(name="ruff", passed=True, output="ruff not installed; skipped")
            )

    checks.append(_import_and_move_check(agent_path))

    if run_pytest:
        checks.append(_run_command("pytest", [sys.executable, "-m", "pytest"]))

    return ValidatorReport(passed=all(check.passed for check in checks), checks=checks)


def _find_ruff() -> str:
    local_ruff = Path(sys.executable).parent / "ruff"
    if local_ruff.exists():
        return str(local_ruff)
    return shutil.which("ruff") or ""


def _run_command(name: str, command: List[str], timeout: int = 20) -> CheckResult:
    env = os.environ.copy()
    env.setdefault("PYTHONPYCACHEPREFIX", str(Path(".pycache").resolve()))
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CheckResult(name=name, passed=False, output=str(exc))
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return CheckResult(name=name, passed=completed.returncode == 0, output=output)


def _import_and_move_check(agent_path: Path) -> CheckResult:
    try:
        spec = importlib.util.spec_from_file_location("candidate_chess_agent", agent_path)
        if spec is None or spec.loader is None:
            return CheckResult(
                name="import_move",
                passed=False,
                output="could not load module spec",
            )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        move = module.select_move(
            {"fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}
        )
        if not isinstance(move, str) or not move:
            return CheckResult(
                name="import_move",
                passed=False,
                output="select_move returned empty",
            )
        return CheckResult(name="import_move", passed=True, output=move)
    except Exception as exc:  # noqa: BLE001 - validator should report any import/runtime failure.
        return CheckResult(name="import_move", passed=False, output=repr(exc))
