"""JSON-line worker process for black_numba search."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(os.environ.get("BLACK_NUMBA_SOURCE_DIR", ROOT / "black_numba-master"))

if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from black_numba.constants import LOWER_MATE, UPPER_MATE, start_position  # noqa: E402
from black_numba.moves import get_move_uci  # noqa: E402
from black_numba.position import parse_fen  # noqa: E402
from black_numba.search import Black_numba, search  # noqa: E402


def _mate_distance(score: float) -> int | None:
    if -UPPER_MATE < score < -LOWER_MATE:
        return -int(-(score + UPPER_MATE) // 2)
    if LOWER_MATE < score < UPPER_MATE:
        return int((UPPER_MATE - score) // 2 + 1)
    return None


def _warmup(bot: Black_numba) -> None:
    pos = parse_fen(start_position)
    search(bot, pos, print_info=False, depth_limit=2, time_limit=100, node_limit=100000)


def _pv_line(bot: Black_numba) -> list[str]:
    pv = []
    length = int(bot.pv_length[0])
    for index in range(length):
        move = int(bot.pv_table[0][index])
        if not move:
            continue
        pv.append(get_move_uci(move))
    return pv


def main() -> None:
    bot = Black_numba()
    _warmup(bot)

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue

        try:
            payload = json.loads(raw)
            fen = str(payload["fen"])
            time_limit_ms = max(10, int(payload.get("time_limit_ms", 100)))
            depth_limit = max(1, int(payload.get("depth_limit", 4)))
            node_limit = max(1000, int(payload.get("node_limit", 10**7)))

            started = time.perf_counter()
            position = parse_fen(fen)
            depth, move, score = search(
                bot,
                position,
                print_info=False,
                depth_limit=depth_limit,
                time_limit=time_limit_ms,
                node_limit=node_limit,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            move_text = get_move_uci(move) if int(move) else ""
            response = {
                "ok": True,
                "move": move_text,
                "depth": int(depth),
                "score_cp": int(score),
                "mate_distance": _mate_distance(score),
                "nodes": int(bot.nodes),
                "elapsed_ms": elapsed_ms,
                "principal_variation": _pv_line(bot),
                "backend": "black_numba",
            }
        except Exception as exc:  # noqa: BLE001
            response = {"ok": False, "error": repr(exc), "backend": "black_numba"}

        sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
