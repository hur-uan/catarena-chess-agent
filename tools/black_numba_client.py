"""Client wrapper around the isolated black_numba worker process."""

from __future__ import annotations

import atexit
import json
import select
import subprocess
import threading
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
BLACK_NUMBA_VENV = ROOT / ".venv311_black_numba"
BLACK_NUMBA_PYTHON = BLACK_NUMBA_VENV / "bin/python"
BLACK_NUMBA_WORKER = ROOT / "tools/black_numba_worker.py"
BLACK_NUMBA_SOURCE = ROOT / "black_numba-master"
DEFAULT_RESPONSE_TIMEOUT_SECONDS = 5.0

_LOCK = threading.Lock()
_PROCESS: Optional[subprocess.Popen] = None


class BlackNumbaUnavailable(RuntimeError):
    """Raised when the isolated black_numba runtime is unavailable."""


def is_black_numba_available() -> bool:
    return (
        BLACK_NUMBA_PYTHON.exists()
        and BLACK_NUMBA_WORKER.exists()
        and BLACK_NUMBA_SOURCE.exists()
    )


def analyze_position(
    fen: str,
    time_limit_ms: int = 100,
    depth_limit: int = 4,
    node_limit: int = 10**7,
    response_timeout_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    process = _ensure_process()
    timeout_seconds = (
        max(0.1, response_timeout_seconds)
        if response_timeout_seconds is not None
        else _response_timeout_seconds(time_limit_ms)
    )
    payload = {
        "fen": fen,
        "time_limit_ms": time_limit_ms,
        "depth_limit": depth_limit,
        "node_limit": node_limit,
    }
    with _LOCK:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(json.dumps(payload, ensure_ascii=True) + "\n")
        process.stdin.flush()
        line = _readline_with_timeout(process, timeout_seconds)
        if not line:
            _discard_process(process)
            raise BlackNumbaUnavailable(
                f"black_numba worker timed out after {timeout_seconds:.2f}s"
            )
    if not line:
        raise BlackNumbaUnavailable("black_numba worker returned no response")
    response = json.loads(line)
    if not response.get("ok"):
        raise BlackNumbaUnavailable(response.get("error", "black_numba worker failed"))
    return response


def shutdown() -> None:
    global _PROCESS
    with _LOCK:
        process = _PROCESS
        _PROCESS = None
    if process is None:
        return
    try:
        process.terminate()
        process.wait(timeout=2)
    except Exception:  # noqa: BLE001
        try:
            process.kill()
        except Exception:  # noqa: BLE001
            pass


def _ensure_process() -> subprocess.Popen:
    global _PROCESS
    if not is_black_numba_available():
        raise BlackNumbaUnavailable(
            "black_numba runtime is unavailable; expected %s and %s"
            % (BLACK_NUMBA_PYTHON, BLACK_NUMBA_SOURCE)
        )

    with _LOCK:
        if _PROCESS is not None and _PROCESS.poll() is None:
            return _PROCESS

        env = {
            "BLACK_NUMBA_SOURCE_DIR": str(BLACK_NUMBA_SOURCE),
            "PYTHONUNBUFFERED": "1",
        }
        _PROCESS = subprocess.Popen(
            [str(BLACK_NUMBA_PYTHON), str(BLACK_NUMBA_WORKER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(ROOT),
            env=env,
        )
        return _PROCESS


def _readline_with_timeout(process: subprocess.Popen, timeout_seconds: float) -> str:
    assert process.stdout is not None
    readable, _, _ = select.select([process.stdout], [], [], timeout_seconds)
    if not readable:
        return ""
    return process.stdout.readline()


def _response_timeout_seconds(time_limit_ms: int) -> float:
    return max(DEFAULT_RESPONSE_TIMEOUT_SECONDS, (max(1, time_limit_ms) / 1000.0) * 20.0)


def _discard_process(process: subprocess.Popen) -> None:
    global _PROCESS
    if _PROCESS is process:
        _PROCESS = None
    try:
        process.kill()
        process.wait(timeout=2)
    except Exception:  # noqa: BLE001
        pass


atexit.register(shutdown)
