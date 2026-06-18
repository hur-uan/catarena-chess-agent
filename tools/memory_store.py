"""JSONL reflection memory for optimization rounds."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from tools.serialization import to_plain_data

DEFAULT_MEMORY_PATH = Path("memory/memory.jsonl")


def read_memory(path: Path = DEFAULT_MEMORY_PATH) -> List[Dict[str, Any]]:
    path = Path(path)
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                records.append({"parse_error": line})
    return records


def append_memory(record: Dict[str, Any], path: Path = DEFAULT_MEMORY_PATH) -> Dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = to_plain_data(dict(record))
    payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return payload


def latest_memory(path: Path = DEFAULT_MEMORY_PATH) -> Dict[str, Any]:
    records = read_memory(path)
    return records[-1] if records else {}

