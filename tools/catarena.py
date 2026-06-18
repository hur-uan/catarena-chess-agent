"""Local checks for the official CATArena checkout."""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

DEFAULT_CATARENA_PATH = Path("external/CATArena")


class CATArenaStatus(BaseModel):
    repo_path: str
    exists: bool
    has_chessgame: bool
    demo_files: List[str] = Field(default_factory=list)
    rules_files: List[str] = Field(default_factory=list)
    message: str


def check_catarena(repo_path: Path = DEFAULT_CATARENA_PATH) -> CATArenaStatus:
    repo_path = Path(repo_path)
    chessgame = repo_path / "chessgame"
    exists = repo_path.exists()
    has_chessgame = chessgame.is_dir()
    demo_files: List[str] = []
    rules_files: List[str] = []

    if has_chessgame:
        for path in chessgame.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            rel = str(path.relative_to(repo_path))
            if "demo" in name or "example" in name or "agent" in name:
                demo_files.append(rel)
            if name.startswith("readme") or "rule" in name or name.endswith(".md"):
                rules_files.append(rel)

    if not exists:
        message = "CATArena checkout is missing. Clone the official repo into external/CATArena."
    elif not has_chessgame:
        message = "CATArena checkout exists but chessgame/ was not found."
    else:
        message = "CATArena chessgame checkout is present."

    return CATArenaStatus(
        repo_path=str(repo_path),
        exists=exists,
        has_chessgame=has_chessgame,
        demo_files=sorted(demo_files),
        rules_files=sorted(rules_files),
        message=message,
    )


def assert_catarena_ready(repo_path: Path = DEFAULT_CATARENA_PATH) -> CATArenaStatus:
    status = check_catarena(repo_path)
    if not status.has_chessgame:
        raise RuntimeError(status.message)
    return status

