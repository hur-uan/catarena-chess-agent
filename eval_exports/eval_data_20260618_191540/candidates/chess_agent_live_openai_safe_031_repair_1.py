"""Safe self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses python-chess legal move generation, bounded deterministic search,
and simple static evaluation. It performs no network calls, subprocesses, file
I/O, eval/exec, dynamic imports, or self-modifying behavior during play.
"""

from __future__ import annotations

import time
from typing import Any

import chess

MATE_SCORE = 100000
INF = 10**9

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
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

OPENING_HINTS_WHITE = (
    "e2e4",
    "d2d4",
    "g1f3",
    "c2c4",
    "b1c3",
    "f1c4",
    "f1b5",
    "e1g1",
)
OPENING_HINTS_BLACK = (
    "e7e5",
    "c7c5",
    "e7e6",
    "d7d5",
    "g8f6",
    "b8c6",
    "f8c5",
    "e8g8",
)


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

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
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    hinted_legal = _extract_hinted_legal_moves(observation, board)

    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return _format_move(board, mate_move, output_format)

    budget_ms = max(5, int(time_limit_ms))
    safety_buffer = 6 if budget_ms >= 40 else 2
    search_ms = max(0.003, (budget_ms - safety_buffer) / 1000.0)
    deadline = time.perf_counter() + search_ms

    chosen = _search_best_move(board, legal_moves, deadline, budget_ms)
    if chosen not in legal_moves:
        chosen = None

    if chosen is None:
        if hinted_legal:
            chosen = hinted_legal[0]
        else:
            chosen = _ordered_moves(board, legal_moves)[0]

    if chosen not in legal_moves:
        chosen = legal_moves[0]
    return _format_move(board, chosen, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    """Parse common CATArena observations into a chess.Board safely."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    moves_value = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        moves_value = observation.get("moves") or observation.get("history")
    elif isinstance(observation, str):
        fen = observation.strip()

    if fen:
        try:
            board = chess.Board(fen)
        except ValueError:
            board = chess.Board()
    else:
        board = chess.Board()

    if moves_value and not fen:
        try:
            for item in moves_value:
                text = str(item).strip()
                mv = chess.Move.from_uci(text)
                if mv in board.legal_moves:
                    board.push(mv)
                else:
                    break
        except (TypeError, ValueError):
            return board
    return board


def _extract_hinted_legal_moves(
    observation: Any,
    board: chess.Board,
) -> list[chess.Move]:
    if not isinstance(observation, dict):
        return []
    raw = (
        observation.get("legal_moves")
        or observation.get("legalMoves")
        or observation.get("moves_legal")
    )
    if not raw:
        return []

    result: list[chess.Move] = []
    legal = set(board.legal_moves)
    try:
        iterator = list(raw)
    except TypeError:
        return []

    for item in iterator:
        try:
            mv = chess.Move.from_uci(str(item).strip())
        except ValueError:
            continue
        if mv in legal and mv not in result:
            result.append(mv)
    return result


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(mv)
        except (AssertionError, ValueError):
            return mv.uci()
    return mv.uci()


def _find_immediate_mate(
    board: chess.Board,
    legal_moves: list[chess.Move],
) -> chess.Move | None:
    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _search_best_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
    deadline: float,
    budget_ms: int,
) -> chess.Move | None:
    ordered = _ordered_moves(board, legal_moves)
    best_move = ordered[0] if ordered else None

    max_depth = 2
    if budget_ms >= 35:
        max_depth = 3
    if budget_ms >= 90 and len(legal_moves) <= 24:
        max_depth = 4
    if budget_ms >= 140 and len(legal_moves) <= 18:
        max_depth = 5

    tt: dict[tuple[str, int], int] = {}
    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        alpha = -INF
        beta = INF
        current_best = best_move
        current_score = -INF
        completed = True

        for mv in ordered:
            if time.perf_counter() >= deadline:
                completed = False
                break
            board.push(mv)
            try:
                score = -_negamax(board, depth - 1, -beta, -alpha, deadline, tt, 1)
            except TimeoutError:
                board.pop()
                completed = False
                break
            board.pop()

            if score > current_score:
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score

        if completed and current_best is not None:
            best_move = current_best
            if current_score >= MATE_SCORE - 1000:
                break
    return best_move


def _position_key(board: chess.Board, depth: int) -> tuple[str, int]:
    try:
        base = board._transposition_key()  # noqa: SLF001
        text = repr(base)
    except AttributeError:
        text = board.fen(en_passant="fen")
    return (text, depth)


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    tt: dict[tuple[str, int], int],
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    key = _position_key(board, depth)
    cached = tt.get(key)
    if cached is not None:
        return cached

    if depth <= 0:
        value = _quiescence(board, alpha, beta, deadline, 0, ply)
        tt[key] = value
        return value

    best = -INF
    legal = list(board.legal_moves)
    if not legal:
        return -MATE_SCORE + ply if board.is_check() else 0

    for mv in _ordered_moves(board, legal):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, tt, ply + 1)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break

    tt[key] = best
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    qdepth: int,
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    stand_pat = _static_eval_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth >= 4:
        return alpha

    noisy: list[chess.Move] = []
    if board.is_check():
        noisy = list(board.legal_moves)
    else:
        for mv in board.legal_moves:
            if board.is_capture(mv) or mv.promotion:
                noisy.append(mv)

    for mv in _ordered_moves(board, noisy):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, qdepth + 1, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0

    if board.fullmove_number <= 10:
        hints = OPENING_HINTS_WHITE if board.turn == chess.WHITE else OPENING_HINTS_BLACK
        try:
            idx = hints.index(mv.uci())
            score += 10000 - idx * 30
        except ValueError:
            pass

    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)

    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(mv.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
        score += 5000 + 10 * victim_value - attacker_value

    if board.gives_check(mv):
        score += 1800

    piece = board.piece_at(mv.from_square)
    if piece:
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 12:
            home_rank = 0 if piece.color == chess.WHITE else 7
            if chess.square_rank(mv.from_square) == home_rank:
                score += 450
        is_castle = abs(
            chess.square_file(mv.to_square) - chess.square_file(mv.from_square),
        ) == 2
        if piece.piece_type == chess.KING and is_castle:
            score += 700
        if mv.to_square in CENTER_SQUARES:
            score += 350
        elif mv.to_square in EXTENDED_CENTER:
            score += 140

    attacked = board.is_attacked_by(not board.turn, mv.to_square)
    if piece and piece.piece_type != chess.KING and attacked:
        score -= min(350, PIECE_VALUES.get(piece.piece_type, 0) // 2)
    return score


def _static_eval_for_side_to_move(board: chess.Board) -> int:
    value = _static_eval_white(board)
    return value if board.turn == chess.WHITE else -value


def _static_eval_white(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        score += sign * PIECE_VALUES.get(piece.piece_type, 0)
        score += sign * _piece_square_bonus(piece, square)

    score += _mobility_score(board)
    score += _king_safety_score(board)
    score += _pawn_structure_score(board)
    return int(score)


def _piece_square_bonus(piece: chess.Piece, square: chess.Square) -> int:
    rank = chess.square_rank(square)
    file_ = chess.square_file(square)
    if piece.color == chess.BLACK:
        rank = 7 - rank

    bonus = 0
    if square in CENTER_SQUARES:
        bonus += 18
    elif square in EXTENDED_CENTER:
        bonus += 8

    if piece.piece_type == chess.PAWN:
        bonus += rank * 5
        if file_ in (3, 4):
            bonus += 7
    elif piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        dist_center = abs(file_ - 3.5) + abs(rank - 3.5)
        bonus += int(22 - 5 * dist_center)
        if rank >= 2:
            bonus += 6
    elif piece.piece_type == chess.ROOK:
        if rank >= 6:
            bonus += 18
    elif piece.piece_type == chess.QUEEN and rank <= 1:
        bonus -= 8
    return bonus


def _mobility_score(board: chess.Board) -> int:
    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mob = board.legal_moves.count()
        board.turn = chess.BLACK
        black_mob = board.legal_moves.count()
    finally:
        board.turn = turn
    return 2 * (white_mob - black_mob)


def _king_safety_score(board: chess.Board) -> int:
    score = 0
    for color in (chess.WHITE, chess.BLACK):
        king_sq = board.king(color)
        if king_sq is None:
            score += -5000 if color == chess.WHITE else 5000
            continue

        sign = 1 if color == chess.WHITE else -1
        enemy = not color
        attackers = len(board.attackers(enemy, king_sq))
        score -= sign * attackers * 55

        ring_penalty = 0
        for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king_sq]):
            if board.is_attacked_by(enemy, sq):
                ring_penalty += 1
        score -= sign * ring_penalty * 5

        rank_dir = 1 if color == chess.WHITE else -1
        king_rank = chess.square_rank(king_sq)
        king_file = chess.square_file(king_sq)
        for df in (-1, 0, 1):
            file_ = king_file + df
            rank = king_rank + rank_dir
            if 0 <= file_ <= 7 and 0 <= rank <= 7:
                piece = board.piece_at(chess.square(file_, rank))
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    score += sign * 10
    return score


def _pawn_structure_score(board: chess.Board) -> int:
    score = 0
    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        pawns = list(board.pieces(chess.PAWN, color))
        files: dict[int, int] = {}
        for sq in pawns:
            file_ = chess.square_file(sq)
            files[file_] = files.get(file_, 0) + 1
        for sq in pawns:
            file_ = chess.square_file(sq)
            rank = chess.square_rank(sq)
            if files.get(file_, 0) > 1:
                score -= sign * 10
            if not files.get(file_ - 1, 0) and not files.get(file_ + 1, 0):
                score -= sign * 9
            if _is_passed_pawn(board, sq, color):
                advance = rank if color == chess.WHITE else 7 - rank
                score += sign * (18 + advance * 8)
    return score


def _is_passed_pawn(board: chess.Board, sq: chess.Square, color: chess.Color) -> bool:
    file_ = chess.square_file(sq)
    rank = chess.square_rank(sq)
    enemy_pawns = board.pieces(chess.PAWN, not color)
    for df in (-1, 0, 1):
        f = file_ + df
        if not 0 <= f <= 7:
            continue
        if color == chess.WHITE:
            ranks = range(rank + 1, 8)
        else:
            ranks = range(rank - 1, -1, -1)
        for r in ranks:
            if chess.square(f, r) in enemy_pawns:
                return False
    return True
