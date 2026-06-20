"""Safe self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses only python-chess, performs no file/network/subprocess work,
and validates every selected move against Board.legal_moves.
"""

from __future__ import annotations

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

MATE_SCORE = 100_000
INF = 1_000_000_000
CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXT_CENTER = {
    chess.C3,
    chess.D3,
    chess.E3,
    chess.F3,
    chess.C4,
    chess.D4,
    chess.E4,
    chess.F4,
    chess.C5,
    chess.D5,
    chess.E5,
    chess.F5,
    chess.C6,
    chess.D6,
    chess.E6,
    chess.F6,
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
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, dict):
        fen = _find_fen_in_dict(observation)
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
        text = fen.strip()
        try:
            return chess.Board(text)
        except Exception:
            parts = text.split()
            if len(parts) == 1 and "/" in parts[0]:
                try:
                    return chess.Board(parts[0] + " w KQkq - 0 1")
                except Exception:
                    pass
    return chess.Board()


def _find_fen_in_dict(payload: dict[str, Any]) -> str | None:
    for key in ("fen", "board", "state", "position"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    nested = payload.get("observation")
    if isinstance(nested, dict):
        return _find_fen_in_dict(nested)
    return None


def _extract_hint_moves(observation: Any) -> set[str]:
    hints: set[str] = set()
    if not isinstance(observation, dict):
        return hints

    for key in ("legal_moves", "legalMoves", "moves", "valid_moves", "validMoves"):
        value = observation.get(key)
        if isinstance(value, (list, tuple, set)):
            for item in value:
                text = str(item).strip()
                if text:
                    hints.add(text)
        elif isinstance(value, str):
            for chunk in value.split(","):
                for item in chunk.split():
                    text = item.strip()
                    if text:
                        hints.add(text)

    nested = observation.get("observation")
    if isinstance(nested, dict):
        hints.update(_extract_hint_moves(nested))
    return hints


def _choose_move(
    board: chess.Board,
    observation: Any,
    time_limit_ms: int,
) -> chess.Move | None:
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv

    budget_ms = max(8, min(int(time_limit_ms), 250) - 6)
    deadline = time.perf_counter() + budget_ms / 1000.0

    hinted = _extract_hint_moves(observation)
    hinted_legal = {mv.uci() for mv in legal_moves if mv.uci() in hinted}

    if time_limit_ms < 35:
        max_depth = 2
    elif time_limit_ms < 90:
        max_depth = 3
    else:
        max_depth = 4 if len(legal_moves) <= 28 else 3

    best_move = _static_best_move(board, legal_moves, hinted_legal)
    completed_best = best_move

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        current_best = None
        current_score = -INF
        alpha = -INF
        searched_any = False
        for mv in _ordered_moves(board, legal_moves, preferred=completed_best):
            if time.perf_counter() >= deadline:
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -INF, -alpha, deadline, 1)
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
    """Return a score from the side-to-move perspective."""
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    white_score = 0
    black_score = 0
    endgame = _is_endgame(board)

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        value += _piece_square_value(piece, square, endgame)
        if piece.color == chess.WHITE:
            white_score += value
        else:
            black_score += value

    white_score += _bishop_pair(board, chess.WHITE)
    black_score += _bishop_pair(board, chess.BLACK)
    white_score += _activity_score(board, chess.WHITE)
    black_score += _activity_score(board, chess.BLACK)
    white_score += _pawn_structure(board, chess.WHITE)
    black_score += _pawn_structure(board, chess.BLACK)

    if not endgame:
        white_score += _king_safety(board, chess.WHITE)
        black_score += _king_safety(board, chess.BLACK)

    score = white_score - black_score
    return score if board.turn == chess.WHITE else -score


def _piece_square_value(piece: chess.Piece, square: chess.Square, endgame: bool) -> int:
    rank = chess.square_rank(square)
    file_index = chess.square_file(square)
    if piece.color == chess.BLACK:
        rank = 7 - rank

    center_distance = abs(file_index - 3.5) + abs(rank - 3.5)
    central = int(18 - 4 * center_distance)

    if piece.piece_type == chess.PAWN:
        return rank * 4 + (8 if square in CENTER else 0)
    if piece.piece_type == chess.KNIGHT:
        return central * 2 - (10 if file_index in (0, 7) else 0)
    if piece.piece_type == chess.BISHOP:
        return central + 6
    if piece.piece_type == chess.ROOK:
        return rank * 2
    if piece.piece_type == chess.QUEEN:
        return central // 2
    if piece.piece_type == chess.KING and endgame:
        return central * 2
    if piece.piece_type == chess.KING:
        home_rank = 0 if piece.color == chess.WHITE else 7
        return 18 if chess.square_rank(square) == home_rank else -20
    return 0


def _is_endgame(board: chess.Board) -> bool:
    material = 0
    queens = 0
    for piece in board.piece_map().values():
        if piece.piece_type == chess.KING:
            continue
        if piece.piece_type == chess.QUEEN:
            queens += 1
        material += PIECE_VALUES[piece.piece_type]
    return queens == 0 or material <= 2600


def _bishop_pair(board: chess.Board, color: chess.Color) -> int:
    return 28 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return -500

    score = 0
    rank = chess.square_rank(king_sq)
    file_index = chess.square_file(king_sq)
    if color == chess.WHITE:
        if king_sq in (chess.G1, chess.C1):
            score += 35
        elif king_sq == chess.E1:
            score += 8
    else:
        if king_sq in (chess.G8, chess.C8):
            score += 35
        elif king_sq == chess.E8:
            score += 8

    direction = 1 if color == chess.WHITE else -1
    shield_rank = rank + direction
    if 0 <= shield_rank <= 7:
        for delta_file in (-1, 0, 1):
            shield_file = file_index + delta_file
            if 0 <= shield_file <= 7:
                sq = chess.square(shield_file, shield_rank)
                piece = board.piece_at(sq)
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 9
    return score


def _activity_score(board: chess.Board, color: chess.Color) -> int:
    score = 0
    for square, piece in board.piece_map().items():
        if piece.color != color:
            continue
        attacks = board.attacks(square)
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            score += min(12, len(attacks))
            if square in CENTER:
                score += 8
            elif square in EXT_CENTER:
                score += 4
        elif piece.piece_type == chess.ROOK:
            if _is_open_file(board, square):
                score += 14
            elif _is_half_open_file(board, square, color):
                score += 7
        elif piece.piece_type == chess.QUEEN:
            score += min(8, len(attacks) // 2)
    return score


def _pawn_structure(board: chess.Board, color: chess.Color) -> int:
    score = 0
    files = [0] * 8
    for sq in board.pieces(chess.PAWN, color):
        files[chess.square_file(sq)] += 1
        rank = chess.square_rank(sq)
        advance = rank if color == chess.WHITE else 7 - rank
        score += max(0, advance - 1) * 2

    for file_index, count in enumerate(files):
        if count > 1:
            score -= 8 * (count - 1)
        if count:
            left = files[file_index - 1] if file_index > 0 else 0
            right = files[file_index + 1] if file_index < 7 else 0
            if left == 0 and right == 0:
                score -= 10
    return score


def _is_open_file(board: chess.Board, square: chess.Square) -> bool:
    file_index = chess.square_file(square)
    for rank in range(8):
        piece = board.piece_at(chess.square(file_index, rank))
        if piece and piece.piece_type == chess.PAWN:
            return False
    return True


def _is_half_open_file(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> bool:
    file_index = chess.square_file(square)
    for rank in range(8):
        piece = board.piece_at(chess.square(file_index, rank))
        if piece and piece.piece_type == chess.PAWN and piece.color == color:
            return False
    return True


def _ordered_moves(
    board: chess.Board,
    moves: list[chess.Move],
    preferred: chess.Move | None = None,
) -> list[chess.Move]:
    return sorted(
        moves,
        key=lambda mv: _move_order_score(board, mv, preferred),
        reverse=True,
    )


def _move_order_score(
    board: chess.Board,
    mv: chess.Move,
    preferred: chess.Move | None = None,
) -> int:
    score = 1_000_000 if preferred is not None and mv == preferred else 0

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
    if piece is not None and board.fullmove_number <= 10:
        score += _opening_move_bonus(board, mv, piece)

    if mv.to_square in CENTER:
        score += 1_200
    elif mv.to_square in EXT_CENTER:
        score += 500
    return score


def _opening_move_bonus(
    board: chess.Board,
    mv: chess.Move,
    piece: chess.Piece,
) -> int:
    if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        home_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home_rank:
            return 2_500
    if piece.piece_type == chess.QUEEN:
        if not board.is_capture(mv) and not board.gives_check(mv):
            return -1_500
    if piece.piece_type == chess.ROOK and not board.is_castling(mv):
        return -700
    return 0


def _static_best_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
    hinted_legal: set[str] | None = None,
) -> chess.Move:
    best = legal_moves[0]
    best_score = -INF
    hints = hinted_legal or set()
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        score = MATE_SCORE if board.is_checkmate() else -_evaluate(board)
        board.pop()
        score += _move_order_score(board, mv) // 100
        if mv.uci() in hints:
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

    ordered = sorted(
        legal_moves,
        key=lambda mv: (_move_order_score(board, mv), mv.uci()),
        reverse=True,
    )
    return ordered[0]
