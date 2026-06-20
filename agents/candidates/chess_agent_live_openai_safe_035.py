"""Safe self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

Design goals:
- No network calls, no subprocesses, no arbitrary file I/O.
- No eval/exec/dynamic imports/self-modifying behavior.
- Every returned move is validated against python-chess legal moves.
- Bounded deterministic alpha-beta search with tactical quiescence.
"""

from __future__ import annotations

import math
import time
from typing import Any

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

MATE_SCORE = 100000
INF = 10**9

# White-oriented piece-square tables. Values are deliberately modest so tactics
# and material dominate, while opening development still receives guidance.
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    8, 10, 10, -12, -12, 10, 10, 8,
    4, 6, 8, 14, 14, 8, 6, 4,
    2, 4, 6, 16, 16, 6, 4, 2,
    0, 2, 4, 12, 12, 4, 2, 0,
    2, -2, -4, 4, 4, -4, -2, 2,
    2, 4, 4, -10, -10, 4, 4, 2,
    0, 0, 0, 0, 0, 0, 0, 0,
]

KNIGHT_PST = [
    -35, -20, -12, -8, -8, -12, -20, -35,
    -20, -8, 4, 8, 8, 4, -8, -20,
    -12, 6, 12, 18, 18, 12, 6, -12,
    -8, 8, 18, 24, 24, 18, 8, -8,
    -8, 8, 18, 24, 24, 18, 8, -8,
    -12, 6, 12, 18, 18, 12, 6, -12,
    -20, -8, 4, 8, 8, 4, -8, -20,
    -35, -20, -12, -8, -8, -12, -20, -35,
]

BISHOP_PST = [
    -16, -8, -8, -8, -8, -8, -8, -16,
    -8, 6, 2, 2, 2, 2, 6, -8,
    -8, 8, 8, 10, 10, 8, 8, -8,
    -8, 2, 10, 14, 14, 10, 2, -8,
    -8, 4, 10, 14, 14, 10, 4, -8,
    -8, 10, 8, 10, 10, 8, 10, -8,
    -8, 8, 4, 2, 2, 4, 8, -8,
    -16, -8, -8, -8, -8, -8, -8, -16,
]

ROOK_PST = [
    0, 0, 2, 6, 6, 2, 0, 0,
    -2, 0, 2, 6, 6, 2, 0, -2,
    -4, 0, 2, 6, 6, 2, 0, -4,
    -4, 0, 2, 6, 6, 2, 0, -4,
    -4, 0, 2, 6, 6, 2, 0, -4,
    -4, 0, 2, 6, 6, 2, 0, -4,
    8, 10, 10, 12, 12, 10, 10, 8,
    0, 0, 2, 6, 6, 2, 0, 0,
]

QUEEN_PST = [
    -12, -8, -4, -2, -2, -4, -8, -12,
    -8, 0, 2, 2, 2, 2, 0, -8,
    -4, 2, 4, 4, 4, 4, 2, -4,
    -2, 2, 4, 6, 6, 4, 2, -2,
    -2, 2, 4, 6, 6, 4, 2, -2,
    -4, 2, 4, 4, 4, 4, 2, -4,
    -8, 0, 2, 2, 2, 2, 0, -8,
    -12, -8, -4, -2, -2, -4, -8, -12,
]

KING_MID_PST = [
    18, 24, 10, 0, 0, 10, 24, 18,
    14, 12, 0, -8, -8, 0, 12, 14,
    -8, -12, -16, -20, -20, -16, -12, -8,
    -18, -24, -28, -34, -34, -28, -24, -18,
    -26, -32, -36, -42, -42, -36, -32, -26,
    -34, -40, -44, -50, -50, -44, -40, -34,
    -36, -42, -46, -52, -52, -46, -42, -36,
    -30, -36, -40, -46, -46, -40, -36, -30,
]

KING_END_PST = [
    -40, -28, -20, -16, -16, -20, -28, -40,
    -24, -12, -4, 0, 0, -4, -12, -24,
    -16, -4, 8, 12, 12, 8, -4, -16,
    -12, 0, 12, 18, 18, 12, 0, -12,
    -12, 0, 12, 18, 18, 12, 0, -12,
    -16, -4, 8, 12, 12, 8, -4, -16,
    -24, -12, -4, 0, 0, -4, -12, -24,
    -40, -28, -20, -16, -16, -20, -28, -40,
]

PST = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


class ChessAgent:
    """Small wrapper compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> str:
    """Choose a legal chess move for the supplied observation."""
    try:
        board = _parse_observation(observation)
    except Exception:
        board = chess.Board()

    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    try:
        chosen = _choose_move(board, observation, time_limit_ms)
    except Exception:
        chosen = None

    if chosen not in legal_moves:
        chosen = _safe_fallback_move(board, observation)

    if chosen not in legal_moves:
        return ""

    fmt = (output_format or "uci").strip().lower()
    if fmt == "san":
        try:
            return board.san(chosen)
        except Exception:
            return chosen.uci()
    return chosen.uci()


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    """Parse CATArena-style observations and common local test payloads."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "state", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        if fen is None:
            nested = observation.get("observation")
            if isinstance(nested, dict):
                for key in ("fen", "board", "state", "position"):
                    value = nested.get(key)
                    if isinstance(value, str) and value.strip():
                        fen = value.strip()
                        break
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text
    else:
        value = getattr(observation, "fen", None)
        if callable(value):
            fen = value()
        elif isinstance(value, str):
            fen = value

    if isinstance(fen, str) and fen.strip():
        try:
            return chess.Board(fen.strip())
        except Exception:
            # Some payloads may contain only the board part. Append defaults.
            parts = fen.strip().split()
            if len(parts) == 1 and "/" in parts[0]:
                try:
                    return chess.Board(parts[0] + " w KQkq - 0 1")
                except Exception:
                    pass
    return chess.Board()


def _extract_hint_moves(observation: Any) -> set[str]:
    hints: set[str] = set()
    if not isinstance(observation, dict):
        return hints
    keys = ("legal_moves", "legalMoves", "moves", "valid_moves", "validMoves")
    for key in keys:
        value = observation.get(key)
        if isinstance(value, (list, tuple, set)):
            for item in value:
                text = str(item).strip()
                if text:
                    hints.add(text)
        elif isinstance(value, str):
            for item in value.replace(",", " ").split():
                text = item.strip()
                if text:
                    hints.add(text)
    nested = observation.get("observation")
    if isinstance(nested, dict):
        hints.update(_extract_hint_moves(nested))
    return hints


def _choose_move(board: chess.Board, observation: Any, time_limit_ms: int) -> chess.Move | None:
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    # If a mating move is immediately available, play it without spending time.
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv

    # Conservative time budgeting. The arena reports average responses well below
    # 100 ms; this keeps a safety buffer for slower positions/environments.
    budget_ms = max(8, min(int(time_limit_ms), 250) - 6)
    deadline = time.perf_counter() + budget_ms / 1000.0

    # Respect explicit legal-move hints when present, but still search normally.
    hinted = _extract_hint_moves(observation)
    hinted_legal = {mv.uci() for mv in legal_moves if mv.uci() in hinted}

    if time_limit_ms < 35:
        max_depth = 2
    elif time_limit_ms < 90:
        max_depth = 3
    else:
        # Depth 4 is allowed only when branching is moderate; otherwise depth 3
        # plus quiescence is safer under the 100 ms default.
        max_depth = 4 if len(legal_moves) <= 28 else 3

    best_move = _static_best_move(board, legal_moves, hinted_legal)
    completed_best = best_move

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        current_best = None
        current_score = -INF
        alpha = -INF
        beta = INF
        searched_any = False
        for mv in _ordered_moves(board, legal_moves, preferred=completed_best):
            if time.perf_counter() >= deadline:
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -beta, -alpha, deadline, 1)
            board.pop()
            searched_any = True
            if mv.uci() in hinted_legal:
                score += 2
            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if searched_any and current_best is not None:
            completed_best = current_best
            best_move = current_best

    return best_move


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        return _evaluate(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    best = -INF
    moves = list(board.legal_moves)
    if not moves:
        return _evaluate(board)

    for mv in _ordered_moves(board, moves):
        if time.perf_counter() >= deadline:
            break
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best if best != -INF else _evaluate(board)


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        return _evaluate(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion is not None:
            tactical.append(mv)

    # Include evasions/checks naturally through normal search; quiescence stays
    # capture-focused to avoid unstable time use.
    for mv in _ordered_moves(board, tactical):
        if time.perf_counter() >= deadline:
            break
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate(board: chess.Board) -> int:
    """Return score from side-to-move perspective."""
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    white_score = 0
    black_score = 0
    endgame = _is_endgame(board)

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        if piece.piece_type == chess.KING:
            pst = KING_END_PST if endgame else KING_MID_PST
        else:
            pst = PST.get(piece.piece_type, [0] * 64)
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        value += pst[pst_square]
        if piece.color == chess.WHITE:
            white_score += value
        else:
            black_score += value

    # Bishop pair.
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        white_score += 28
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        black_score += 28

    # Castling/king shelter hints in non-endgames.
    if not endgame:
        white_score += _king_safety(board, chess.WHITE)
        black_score += _king_safety(board, chess.BLACK)

    # Small mobility term. Legal move count is for side to move only, so use
    # pseudo-legal attacks for a cheap symmetric approximation.
    white_score += _activity_score(board, chess.WHITE)
    black_score += _activity_score(board, chess.BLACK)

    score = white_score - black_score
    return score if board.turn == chess.WHITE else -score


def _is_endgame(board: chess.Board) -> bool:
    non_king_material = 0
    queens = 0
    for piece in board.piece_map().values():
        if piece.piece_type == chess.KING:
            continue
        if piece.piece_type == chess.QUEEN:
            queens += 1
        non_king_material += PIECE_VALUES[piece.piece_type]
    return queens == 0 or non_king_material <= 2600


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return -500
    score = 0
    rank = chess.square_rank(king_sq)
    file_ = chess.square_file(king_sq)

    # Prefer castled-looking king locations while many pieces remain.
    if color == chess.WHITE:
        if king_sq in (chess.G1, chess.C1):
            score += 35
        elif rank == 0 and file_ in (4,):
            score += 8
    else:
        if king_sq in (chess.G8, chess.C8):
            score += 35
        elif rank == 7 and file_ in (4,):
            score += 8

    # Pawn shield in front of king.
    direction = 1 if color == chess.WHITE else -1
    shield_rank = rank + direction
    if 0 <= shield_rank <= 7:
        for df in (-1, 0, 1):
            sf = file_ + df
            if 0 <= sf <= 7:
                sq = chess.square(sf, shield_rank)
                piece = board.piece_at(sq)
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 9
    return score


def _activity_score(board: chess.Board, color: chess.Color) -> int:
    score = 0
    for square, piece in board.piece_map().items():
        if piece.color != color:
            continue
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            attacks = board.attacks(square)
            score += min(12, len(attacks))
            if square in CENTER_SQUARES:
                score += 8
            elif square in EXTENDED_CENTER:
                score += 4
        elif piece.piece_type == chess.ROOK:
            if _is_open_file(board, square):
                score += 14
            elif _is_half_open_file(board, square, color):
                score += 7
        elif piece.piece_type == chess.QUEEN:
            score += min(8, len(board.attacks(square)) // 2)
    return score


def _is_open_file(board: chess.Board, square: chess.Square) -> bool:
    file_ = chess.square_file(square)
    for rank in range(8):
        piece = board.piece_at(chess.square(file_, rank))
        if piece and piece.piece_type == chess.PAWN:
            return False
    return True


def _is_half_open_file(board: chess.Board, square: chess.Square, color: chess.Color) -> bool:
    file_ = chess.square_file(square)
    own_pawn = False
    for rank in range(8):
        piece = board.piece_at(chess.square(file_, rank))
        if piece and piece.piece_type == chess.PAWN and piece.color == color:
            own_pawn = True
            break
    return not own_pawn


def _ordered_moves(
    board: chess.Board,
    moves: list[chess.Move],
    preferred: chess.Move | None = None,
) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv, preferred), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move, preferred: chess.Move | None = None) -> int:
    if preferred is not None and mv == preferred:
        score = 1_000_000
    else:
        score = 0

    if mv.promotion is not None:
        score += 80_000 + PIECE_VALUES.get(mv.promotion, 0)

    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 50_000 + 10 * victim_value - attacker_value

    if board.gives_check(mv):
        score += 12_000
    if board.is_castling(mv):
        score += 5_000

    piece = board.piece_at(mv.from_square)
    if piece is not None:
        # Opening development: encourage minor pieces out, discourage early queen
        # adventures unless tactically justified by capture/check bonuses above.
        if board.fullmove_number <= 10:
            if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                home_rank = 0 if piece.color == chess.WHITE else 7
                if chess.square_rank(mv.from_square) == home_rank:
                    score += 2_500
            elif piece.piece_type == chess.QUEEN and not board.is_capture(mv) and not board.gives_check(mv):
                score -= 1_500
            elif piece.piece_type == chess.ROOK and not board.is_castling(mv):
                score -= 700

    if mv.to_square in CENTER_SQUARES:
        score += 1_200
    elif mv.to_square in EXTENDED_CENTER:
        score += 500

    return score


def _static_best_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
    hinted_legal: set[str] | None = None,
) -> chess.Move:
    best = legal_moves[0]
    best_score = -INF
    hinted_legal = hinted_legal or set()
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        score = -_evaluate(board)
        if board.is_checkmate():
            score = MATE_SCORE
        board.pop()
        score += _move_order_score(board, mv) // 100
        if mv.uci() in hinted_legal:
            score += 2
        if score > best_score:
            best_score = score
            best = mv
    return best


def _safe_fallback_move(board: chess.Board, observation: Any) -> chess.Move | None:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    hinted = _extract_hint_moves(observation)
    if hinted:
        legal_by_uci = {mv.uci(): mv for mv in legal_moves}
        for uci in sorted(hinted):
            mv = legal_by_uci.get(uci)
            if mv is not None:
                return mv

    # Deterministic tactical fallback, not random.
    return sorted(legal_moves, key=lambda mv: (_move_order_score(board, mv), mv.uci()), reverse=True)[0]
