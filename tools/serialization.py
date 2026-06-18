"""Small serialization helpers shared by report and memory tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def to_plain_data(value: Any) -> Any:
    """Convert Pydantic models and paths into JSON-serializable data."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_plain_data(item) for item in value]
    return value

