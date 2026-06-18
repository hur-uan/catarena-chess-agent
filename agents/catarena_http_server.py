"""Local agent hosted through the official CATArena chess demo HTTP app."""

from __future__ import annotations

import argparse
import importlib.util
from typing import Optional

import chess

from agents.chess_agent import select_move
from tools.catarena import DEFAULT_CATARENA_PATH, assert_catarena_ready
from tools.move_validator import validate_move

OFFICIAL_DEMO_PATH = (
    DEFAULT_CATARENA_PATH / "chessgame/AI_competitors/chess/round_1/demo1/demo1_ai.py"
)


def _load_official_demo():
    assert_catarena_ready()
    spec = importlib.util.spec_from_file_location("official_catarena_demo1_ai", OFFICIAL_DEMO_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load official CATArena demo from {OFFICIAL_DEMO_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_official = _load_official_demo()
app = _official.app


class LocalCATArenaChessAI(_official.Demo1ChessAI):
    """Official demo service shell with this project's active chess strategy."""

    def find_best_move(self, fen: str, algorithm: str = "advanced") -> Optional[str]:
        try:
            board = chess.Board(fen)
        except ValueError:
            return None
        if board.is_game_over():
            return None

        move_text = select_move(
            {
                "fen": fen,
                "legal_moves": [move.uci() for move in board.legal_moves],
                "algorithm": algorithm,
            }
        )
        validation = validate_move(board, move_text)
        if not validation.is_legal or not validation.normalized_move:
            fallback = next(iter(board.legal_moves), None)
            return fallback.uci() if fallback else None
        return validation.normalized_move


def configure_agent(
    ai_id: str = "LocalChessAgent",
    ai_name: str = "Local CATArena Chess Agent",
    game_server_url: str = "http://localhost:40000",
) -> LocalCATArenaChessAI:
    agent = LocalCATArenaChessAI(ai_id, ai_name, game_server_url)
    _official.ai_instance = agent
    return agent


ai_instance = configure_agent()
ACTIVE_GAMES = ai_instance.active_games


def main() -> None:
    parser = argparse.ArgumentParser(description="Official CATArena demo HTTP app for local agent")
    parser.add_argument("--port", type=int, default=41001)
    parser.add_argument("--ai_id", default="LocalChessAgent")
    parser.add_argument("--ai_name", default="Local CATArena Chess Agent")
    parser.add_argument("--game_server", default="http://localhost:40000")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    global ai_instance, ACTIVE_GAMES
    ai_instance = configure_agent(args.ai_id, args.ai_name, args.game_server)
    ACTIVE_GAMES = ai_instance.active_games
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
