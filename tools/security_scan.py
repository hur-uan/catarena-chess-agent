"""Static safety checks for candidate or user-supplied playing agents."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field

FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp",
    "httpx",
    "openai",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "urllib",
}
FORBIDDEN_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
}
FORBIDDEN_ATTRS = {
    "popen",
    "remove",
    "replace",
    "rmdir",
    "run",
    "unlink",
    "write",
}


class SecurityScanReport(BaseModel):
    passed: bool
    issues: List[str] = Field(default_factory=list)


def scan_agent_source(source: str) -> SecurityScanReport:
    issues: List[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return SecurityScanReport(passed=False, issues=[f"syntax error: {exc}"])

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    issues.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".", 1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS:
                issues.append(f"forbidden import: {module}")
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in FORBIDDEN_CALLS:
                issues.append(f"forbidden call: {name}")
            attr = _call_attr(node.func)
            if attr in FORBIDDEN_ATTRS:
                issues.append(f"forbidden method call: {attr}")

    return SecurityScanReport(passed=not issues, issues=sorted(set(issues)))


def scan_agent_file(path: Path) -> SecurityScanReport:
    return scan_agent_source(Path(path).read_text(encoding="utf-8"))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _call_attr(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr.lower()
    return ""
