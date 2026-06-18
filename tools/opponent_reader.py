"""Extract opponent strategy features from Python agent code."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable, List, Optional

from pydantic import BaseModel, Field


class OpponentSummary(BaseModel):
    path: str
    functions: List[str] = Field(default_factory=list)
    classes: List[str] = Field(default_factory=list)
    uses_search: bool = False
    search_depth: Optional[int] = None
    has_opening_book: bool = False
    has_fallback: bool = False
    uses_python_chess: bool = False
    evaluation_features: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class OpponentCodeReport(BaseModel):
    opponents: List[OpponentSummary] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


def read_opponents(path_or_dir: Optional[Path]) -> OpponentCodeReport:
    if path_or_dir is None:
        return OpponentCodeReport(notes=["opponent path not provided"])
    path = Path(path_or_dir)
    if not path.exists():
        return OpponentCodeReport(notes=["opponent path does not exist: %s" % path])
    summaries = [_summarize_file(path) for path in _iter_python_files(path)]
    return OpponentCodeReport(opponents=summaries)


def _iter_python_files(path: Path) -> Iterable[Path]:
    if path.is_file() and path.suffix == ".py":
        yield path
    elif path.is_dir():
        yield from sorted(path.rglob("*.py"))


def _summarize_file(path: Path) -> OpponentSummary:
    text = path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    summary = OpponentSummary(path=str(path))
    summary.uses_search = any(token in lower for token in ("minimax", "alpha", "negamax", "search"))
    summary.has_opening_book = any(token in lower for token in ("opening", "book", "polyglot"))
    summary.has_fallback = "fallback" in lower or "legal_moves" in lower
    summary.uses_python_chess = "import chess" in lower or "python-chess" in lower

    for token in ("material", "mobility", "center", "king", "pawn", "piece_square"):
        if token in lower:
            summary.evaluation_features.append(token)

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        summary.risks.append("syntax error: %s" % exc)
        return summary

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            summary.functions.append(node.name)
            if "search" in node.name.lower() or "minimax" in node.name.lower():
                summary.uses_search = True
        elif isinstance(node, ast.ClassDef):
            summary.classes.append(node.name)
        elif isinstance(node, ast.Assign):
            _maybe_update_depth(summary, node)

    return summary


def _maybe_update_depth(summary: OpponentSummary, node: ast.Assign) -> None:
    target_names = []
    for target in node.targets:
        if isinstance(target, ast.Name):
            target_names.append(target.id.lower())
    if not any("depth" in name for name in target_names):
        return
    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
        summary.search_depth = node.value.value

