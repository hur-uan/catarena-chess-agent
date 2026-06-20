"""Safe CATArena chess agent.

Public interface:
select_move(observation, output_format='uci', time_limit_ms=100) -> str

The agent performs only local computation.  It validates all selected moves
against python-chess legal moves and falls back deterministically if any helper
backend is unavailable or returns an illegal move.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import chess

try:
    from agents.engine import EngineConfig, SearchRecord, cp_to_wdl, select_move_record
except Exception:  # pragma: no cover - standalone fallback
    select_move_record = None

    class EngineConfig:  # type: ignore[no-redef]
        """Minimal placeholder used when the repository engine is absent."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

    def cp_to_wdl(
        cp: int,
        mate_distance: Optional[int],
    ) -> dict[str, float]:  # type: ignore[no-redef]
        """Convert a centipawn score into a compact WDL-like estimate."""
        if mate_distance is not None:
            if mate_distance > 0:
                return {"win": 1.0, "draw": 0.0, "loss": 0.0}
            return {"win": 0.0, "draw": 0.0, "loss": 1.0}
        win = 1.0 / (1.0 + math.exp(-cp / 250.0))
        draw = max(0.0, 1.0 - abs(win - 0.5) * 2.0)
        return {"win": win, "draw": draw, "loss": 1.0 - win}

    @dataclass
    class SearchRecord:  # type: ignore[no-redef]
        """Small diagnostics container matching the repository record shape."""

        fen: str
        selected_move: str
        cp: int = 0
        mate_distance: Optional[int] = None
        wdl: Any = None
        depth: int = 0
        elapsed_ms: float = 0.0
        nodes: int = 0
        qnodes: int = 0
        legal_moves: list[str] = field(default_factory=list)
        principal_variation: list[str] = field(default_factory=list)
        fallback_used: bool = False
        backend: str = "safe_fallback"
        engine_config: dict[str, object] = field(default_factory=dict)

try:
    from tools.board_parser import parse_observation as _external_parse_observation
except Exception:  # pragma: no cover - optional helper
    _external_parse_observation = None

try:
    from tools.strategy_profile import resolve_strategy_profile
except Exception:  # pragma: no cover - optional helper
    resolve_strategy_profile = None

DEFAULT_ENGINE_CONFIG = EngineConfig()
MATE_SCORE = 100_000
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
NEAR_CENTER_SQUARES = {
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.F4,
    chess.C5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
}


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        """Return a move for the supplied observation."""
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> str:
    """Choose a legal chess move for the supplied observation."""
    return select_move_details(observation, output_format, time_limit_ms).selected_move


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SearchRecord:
    """Return the selected move and lightweight diagnostics."""
    start = time.perf_counter()
    board = _parse_board(observation)
    legal_moves = [move.uci() for move in board.legal_moves]
    if not legal_moves or board.is_game_over(claim_draw=False):
        return _record(board, "", legal_moves, start, backend="terminal")

    mate_move = _find_mate_in_one(board)
    if mate_move is not None:
        return _record(
            board,
            mate_move.uci(),
            legal_moves,
            start,
            cp=MATE_SCORE - 1,
            mate_distance=1,
            depth=1,
            backend="mate_in_one",
        )

    engine_record = _try_repository_engine(
        observation,
        time_limit_ms,
        board,
        legal_moves,
    )
    if engine_record is not None:
        return engine_record

    fallback_move, fallback_cp, fallback_depth, nodes = _fallback_search(
        board,
        time_limit_ms,
    )
    if fallback_move not in legal_moves:
        fallback_move = _deterministic_legal_fallback(board).uci()
        fallback_cp = 0
        fallback_depth = 0
    return _record(
        board,
        fallback_move,
        legal_moves,
        start,
        cp=fallback_cp,
        depth=fallback_depth,
        nodes=nodes,
        fallback_used=True,
        backend="bounded_fallback",
    )


def agent(observation: Any) -> str:
    """Alias required by arena integrations."""
    return select_move(observation)


def act(observation: Any) -> str:
    """Alias required by arena integrations."""
    return select_move(observation)


def move(observation: Any) -> str:
    """Alias required by arena integrations."""
    return select_move(observation)


def _parse_board(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if _external_parse_observation is not None:
        try:
            parsed = _external_parse_observation(observation)
            if isinstance(parsed, chess.Board):
                return parsed
        except Exception:
            pass

    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and "/" in value:
                fen = value.strip()
                break
    elif isinstance(observation, str) and "/" in observation:
        fen = observation.strip()

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _try_repository_engine(
    observation: Any,
    time_limit_ms: int,
    board: chess.Board,
    legal_moves: list[str],
) -> Optional[SearchRecord]:
    if select_move_record is None:
        return None
    try:
        strategy_profile = None
        strategy_source = "unavailable"
        config = DEFAULT_ENGINE_CONFIG
        if resolve_strategy_profile is not None:
            strategy_profile, strategy_source = resolve_strategy_profile(
                observation=observation,
            )
            config = EngineConfig(strategy_profile=strategy_profile)

        record = select_move_record(
            observation=observation,
            output_format="uci",
            time_limit_ms=time_limit_ms,
            config=config,
        )
        selected = str(getattr(record, "selected_move", "")).strip()
        if selected not in legal_moves:
            return None

        profile_name = "default"
        if strategy_profile is not None:
            profile_name = str(getattr(strategy_profile, "profile_name", "default"))
        try:
            record.engine_config = {
                "profile_name": profile_name,
                "strategy_source": strategy_source,
                "external_clients": "disabled",
                "legal_validation": "python-chess",
            }
        except Exception:
            pass
        return record
    except Exception:
        return None


def _find_mate_in_one(board: chess.Board) -> Optional[chess.Move]:
    for candidate in _ordered_moves(board):
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return candidate
    return None


def _fallback_search(board: chess.Board, time_limit_ms: int) -> tuple[str, int, int, int]:
    legal = list(board.legal_moves)
    if not legal:
        return "", 0, 0, 0

    budget_ms = max(8, min(70, int(time_limit_ms * 0.70)))
    deadline = time.perf_counter() + budget_ms / 1000.0
    depth = 2
    if time_limit_ms >= 80 and len(legal) <= 28:
        depth = 3
    if board.is_check():
        depth = min(3, depth + 1)

    best_move = _deterministic_legal_fallback(board)
    best_score = -MATE_SCORE * 2
    alpha = -MATE_SCORE * 2
    beta = MATE_SCORE * 2
    nodes = 0
    for candidate in _ordered_moves(board):
        if time.perf_counter() >= deadline:
            break
        board.push(candidate)
        score, used_nodes = _negamax(
            board,
            depth - 1,
            -beta,
            -alpha,
            deadline,
            1,
        )
        score = -score
        nodes += used_nodes
        board.pop()
        if score > best_score or (score == best_score and candidate.uci() < best_move.uci()):
            best_score = score
            best_move = candidate
        alpha = max(alpha, best_score)
    return best_move.uci(), int(best_score), depth, nodes


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> tuple[int, int]:
    if time.perf_counter() >= deadline:
        return _evaluate(board), 1
    if board.is_checkmate():
        return -MATE_SCORE + ply, 1
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0, 1
    if depth <= 0:
        return _evaluate(board), 1

    best = -MATE_SCORE * 2
    nodes = 1
    for candidate in _ordered_moves(board):
        if time.perf_counter() >= deadline:
            break
        board.push(candidate)
        score, child_nodes = _negamax(
            board,
            depth - 1,
            -beta,
            -alpha,
            deadline,
            ply + 1,
        )
        score = -score
        nodes += child_nodes
        board.pop()
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best, nodes


def _evaluate(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    score += _material_score(board)
    score += _mobility_score(board)
    score += _center_score(board)
    score += _king_safety_score(board)
    score += _hanging_piece_score(board)
    if board.is_check():
        score -= 30
    return score


def _material_score(board: chess.Board) -> int:
    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, board.turn)) * value
        score -= len(board.pieces(piece_type, not board.turn)) * value
    return score


def _mobility_score(board: chess.Board) -> int:
    own_mobility = min(45, board.legal_moves.count())
    board.push(chess.Move.null())
    try:
        opposing_mobility = min(45, board.legal_moves.count())
    finally:
        board.pop()
    return own_mobility - opposing_mobility // 2


def _center_score(board: chess.Board) -> int:
    score = 0
    for square in CENTER_SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        score += 18 if piece.color == board.turn else -18
    for square in NEAR_CENTER_SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        score += 7 if piece.color == board.turn else -7
    return score


def _king_safety_score(board: chess.Board) -> int:
    score = 0
    if board.has_castling_rights(board.turn):
        score += 12
    if board.has_castling_rights(not board.turn):
        score -= 12
    own_king = board.king(board.turn)
    enemy_king = board.king(not board.turn)
    if own_king is not None:
        score -= 6 * len(board.attackers(not board.turn, own_king))
    if enemy_king is not None:
        score += 6 * len(board.attackers(board.turn, enemy_king))
    return score


def _hanging_piece_score(board: chess.Board) -> int:
    score = 0
    for square, piece in board.piece_map().items():
        if piece.piece_type == chess.KING:
            continue
        value = PIECE_VALUES[piece.piece_type]
        attackers = len(board.attackers(not piece.color, square))
        defenders = len(board.attackers(piece.color, square))
        if attackers > defenders:
            penalty = min(90, value // 10)
            score += -penalty if piece.color == board.turn else penalty
    return score


def _ordered_moves(board: chess.Board) -> list[chess.Move]:
    moves = list(board.legal_moves)

    def key(move_obj: chess.Move) -> tuple[int, str]:
        score = _move_order_score(board, move_obj)
        return -score, move_obj.uci()

    moves.sort(key=key)
    return moves


def _move_order_score(board: chess.Board, move_obj: chess.Move) -> int:
    score = 0
    if board.is_capture(move_obj):
        victim = board.piece_at(move_obj.to_square)
        attacker = board.piece_at(move_obj.from_square)
        if victim is None and board.is_en_passant(move_obj):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 100
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 100
        score += 10_000 + victim_value * 10 - attacker_value
    if move_obj.promotion:
        score += PIECE_VALUES.get(move_obj.promotion, 0) + 8_000
    if move_obj.to_square in CENTER_SQUARES:
        score += 120
    elif move_obj.to_square in NEAR_CENTER_SQUARES:
        score += 45

    board.push(move_obj)
    if board.is_checkmate():
        score += 1_000_000
    elif board.is_check():
        score += 3_000
    board.pop()
    return score


def _deterministic_legal_fallback(board: chess.Board) -> chess.Move:
    ordered = _ordered_moves(board)
    if ordered:
        return ordered[0]
    return next(iter(board.legal_moves))


def _record(
    board: chess.Board,
    selected_move: str,
    legal_moves: list[str],
    start: float,
    cp: int = 0,
    mate_distance: Optional[int] = None,
    depth: int = 0,
    nodes: int = 0,
    fallback_used: bool = False,
    backend: str = "safe_guard",
) -> SearchRecord:
    elapsed = (time.perf_counter() - start) * 1000.0
    return SearchRecord(
        fen=board.fen(),
        selected_move=selected_move,
        cp=cp,
        mate_distance=mate_distance,
        wdl=cp_to_wdl(cp, mate_distance),
        depth=depth,
        elapsed_ms=elapsed,
        nodes=nodes,
        qnodes=0,
        legal_moves=legal_moves,
        principal_variation=[selected_move] if selected_move else [],
        fallback_used=fallback_used,
        backend=backend,
        engine_config={
            "external_clients": "disabled",
            "legal_validation": "python-chess",
        },
    )
