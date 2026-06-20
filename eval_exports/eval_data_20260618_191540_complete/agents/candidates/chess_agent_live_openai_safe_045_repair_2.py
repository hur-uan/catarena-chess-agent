"""Safe self-contained CATArena chess agent.

Public entry point:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses python-chess when available, performs no network or file I/O, and
validates every chosen move against board.legal_moves before returning it.
"""

import time
from typing import Any, Optional

try:
    import chess
except Exception:  # pragma: no cover - arena normally provides python-chess
    chess = None


MATE_SCORE = 100000
INF = 10**9

PIECE_VALUES = {
    1: 100,
    2: 320,
    3: 330,
    4: 500,
    5: 900,
    6: 0,
}

CENTER_SQUARES = set()
EXTENDED_CENTER = set()
if chess is not None:
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


class _SearchState:
    def __init__(self, deadline: float, node_limit: int) -> None:
        self.deadline = deadline
        self.node_limit = node_limit
        self.nodes = 0
        self.stopped = False


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
    if chess is None:
        return _fallback_from_observation_without_chess(observation)

    board = _parse_board(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    hinted = _extract_legal_hints(observation)
    if hinted:
        hinted_legal = [mv for mv in legal_moves if mv.uci() in hinted]
        if hinted_legal:
            legal_moves = hinted_legal

    selected = _choose_move(board, legal_moves, time_limit_ms)
    if selected not in board.legal_moves:
        selected = _deterministic_fallback(board, legal_moves)

    if selected is None or selected not in board.legal_moves:
        final_moves = list(board.legal_moves)
        if not final_moves:
            return ""
        selected = sorted(final_moves, key=lambda mv: mv.uci())[0]

    fmt = output_format.lower().strip()
    if fmt == "san":
        try:
            return board.san(selected)
        except Exception:
            return selected.uci()
    return selected.uci()


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_board(observation: Any):
    if chess is None:
        raise RuntimeError("python-chess is unavailable")
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    elif isinstance(observation, str):
        fen = observation.strip()

    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def _split_move_text(text: str) -> list:
    tokens = []
    for chunk in text.split(","):
        for part in chunk.split():
            item = part.strip()
            if item:
                tokens.append(item)
    return tokens


def _extract_legal_hints(observation: Any) -> set:
    hints = set()
    if not isinstance(observation, dict):
        return hints
    for key in ("legal_moves", "legalMoves", "moves"):
        value = observation.get(key)
        if isinstance(value, (list, tuple, set)):
            for item in value:
                text = str(item).strip()
                if text:
                    hints.add(text)
        elif isinstance(value, str):
            for text in _split_move_text(value):
                hints.add(text)
    return hints


def _fallback_from_observation_without_chess(observation: Any) -> str:
    if isinstance(observation, dict):
        for key in ("legal_moves", "legalMoves", "moves"):
            value = observation.get(key)
            if isinstance(value, (list, tuple, set)):
                moves = sorted(str(item).strip() for item in value if str(item).strip())
                return moves[0] if moves else ""
            if isinstance(value, str):
                moves = sorted(_split_move_text(value))
                return moves[0] if moves else ""
    return ""


def _choose_move(board: Any, legal_moves: list, time_limit_ms: int) -> Any:
    if len(legal_moves) == 1:
        return legal_moves[0]

    book_move = _book_move(board, legal_moves)
    if book_move is not None:
        return book_move

    mate_move = _find_immediate_mate(board, legal_moves)
    if mate_move is not None:
        return mate_move

    try:
        budget = int(time_limit_ms)
    except Exception:
        budget = 100
    budget_ms = max(8, min(budget, 250))
    deadline = time.perf_counter() + (budget_ms * 0.82 / 1000.0)
    if budget_ms < 60:
        node_limit = 6000
    elif budget_ms < 140:
        node_limit = 16000
    else:
        node_limit = 30000
    state = _SearchState(deadline, node_limit)

    ordered = _ordered_moves(board, legal_moves)
    best_move = ordered[0]
    best_score = -INF

    depth_limit = 2
    if budget_ms >= 55:
        depth_limit = 3
    if budget_ms >= 140 or _is_endgame(board):
        depth_limit = 4
    if len(legal_moves) > 45 and budget_ms < 120:
        depth_limit = min(depth_limit, 3)

    for depth in range(1, depth_limit + 1):
        if _time_up(state):
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        beta = INF
        for mv in ordered:
            if _time_up(state):
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -beta, -alpha, state, 1)
            board.pop()
            if state.stopped:
                break
            score += _root_tiebreak(board, mv)
            if score > current_score:
                current_score = score
                current_best = mv
            elif score == current_score and mv.uci() < current_best.uci():
                current_best = mv
            alpha = max(alpha, score)
        if not state.stopped and current_score > -INF:
            best_move = current_best
            best_score = current_score
            ordered = [best_move] + [mv for mv in ordered if mv != best_move]
        if best_score >= MATE_SCORE - 100:
            break

    return best_move


def _find_immediate_mate(board: Any, legal_moves: list) -> Any:
    mating = []
    for mv in legal_moves:
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            mating.append(mv)
    if not mating:
        return None
    return sorted(mating, key=lambda mv: mv.uci())[0]


def _book_move(board: Any, legal_moves: list) -> Any:
    legal_by_uci = {mv.uci(): mv for mv in legal_moves}
    board_key = board.board_fen()
    start = chess.STARTING_BOARD_FEN
    if board.fullmove_number == 1 and board.turn == chess.WHITE and board_key == start:
        for uci in ("g1f3", "e2e4", "d2d4", "c2c4"):
            if uci in legal_by_uci:
                return legal_by_uci[uci]
    if board.fullmove_number == 1 and board.turn == chess.BLACK:
        for uci in ("g8f6", "e7e5", "c7c5", "e7e6", "d7d5"):
            if uci in legal_by_uci:
                return legal_by_uci[uci]
    return None


def _negamax(
    board: Any,
    depth: int,
    alpha: int,
    beta: int,
    state: _SearchState,
    ply: int,
) -> int:
    if _time_up(state):
        state.stopped = True
        return 0
    state.nodes += 1
    if state.nodes >= state.node_limit:
        state.stopped = True
        return 0

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, state, ply)

    moves = _ordered_moves(board, list(board.legal_moves))
    if not moves:
        return _evaluate_for_side_to_move(board)

    best = -INF
    for mv in moves:
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return 0
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def _quiescence(
    board: Any,
    alpha: int,
    beta: int,
    state: _SearchState,
    ply: int,
) -> int:
    if _time_up(state):
        state.stopped = True
        return 0
    state.nodes += 1
    if state.nodes >= state.node_limit:
        state.stopped = True
        return 0
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    noisy = [mv for mv in board.legal_moves if board.is_capture(mv) or mv.promotion]
    for mv in _ordered_moves(board, noisy):
        if _time_up(state):
            state.stopped = True
            break
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return 0
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _ordered_moves(board: Any, moves: list) -> list:
    return sorted(moves, key=lambda mv: (-_move_order_score(board, mv), mv.uci()))


def _move_order_score(board: Any, mv: Any) -> int:
    score = 0
    if mv.promotion:
        score += 9000 + PIECE_VALUES.get(int(mv.promotion), 0)
    if board.is_capture(mv):
        victim_value = 100
        if not board.is_en_passant(mv):
            victim = board.piece_at(mv.to_square)
            if victim is not None:
                victim_value = PIECE_VALUES.get(int(victim.piece_type), 0)
        attacker = board.piece_at(mv.from_square)
        attacker_value = 100
        if attacker is not None:
            attacker_value = PIECE_VALUES.get(int(attacker.piece_type), 100)
        score += 5000 + victim_value * 10 - attacker_value
    try:
        if board.gives_check(mv):
            score += 1800
    except Exception:
        pass
    if mv.to_square in CENTER_SQUARES:
        score += 80
    elif mv.to_square in EXTENDED_CENTER:
        score += 30
    piece = board.piece_at(mv.from_square)
    if piece is not None:
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            home_rank = 0 if piece.color == chess.WHITE else 7
            if board.fullmove_number <= 12 and chess.square_rank(mv.from_square) == home_rank:
                score += 90
        if piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 60
    if board.is_castling(mv):
        score += 300
    return score


def _root_tiebreak(board: Any, mv: Any) -> int:
    bonus = 0
    if mv.to_square in CENTER_SQUARES:
        bonus += 4
    if board.is_castling(mv):
        bonus += 5
    if mv.promotion:
        bonus += 8
    return bonus


def _evaluate_for_side_to_move(board: Any) -> int:
    white_score = _evaluate_white(board)
    return white_score if board.turn == chess.WHITE else -white_score


def _evaluate_white(board: Any) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        score += sign * PIECE_VALUES.get(int(piece.piece_type), 0)
        score += sign * _piece_square_bonus(piece, square, board)

    score += _king_safety(board, chess.WHITE) - _king_safety(board, chess.BLACK)
    score += _pawn_structure(board, chess.WHITE) - _pawn_structure(board, chess.BLACK)
    score += _safe_mobility_delta(board)
    return score


def _safe_mobility_delta(board: Any) -> int:
    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mob = board.legal_moves.count()
        board.turn = chess.BLACK
        black_mob = board.legal_moves.count()
    except Exception:
        white_mob = 0
        black_mob = 0
    finally:
        board.turn = turn
    return 2 * (white_mob - black_mob)


def _piece_square_bonus(piece: Any, square: int, board: Any) -> int:
    rank = chess.square_rank(square)
    file_index = chess.square_file(square)
    if piece.color == chess.BLACK:
        rank = 7 - rank
    center_distance = abs(file_index - 3.5) + abs(rank - 3.5)

    if piece.piece_type == chess.PAWN:
        return rank * 5 - int(abs(file_index - 3.5) * 2)
    if piece.piece_type == chess.KNIGHT:
        return int(28 - center_distance * 8)
    if piece.piece_type == chess.BISHOP:
        return int(18 - center_distance * 4)
    if piece.piece_type == chess.ROOK:
        return 8 if rank >= 6 else 0
    if piece.piece_type == chess.QUEEN:
        return int(8 - center_distance * 2)
    if piece.piece_type == chess.KING:
        if _is_endgame(board):
            return int(14 - center_distance * 3)
        return int(center_distance * 4)
    return 0


def _king_safety(board: Any, color: bool) -> int:
    king_square = board.king(color)
    if king_square is None:
        return -500
    safety = 0
    enemy = not color
    attackers = board.attackers(enemy, king_square)
    safety -= 45 * len(attackers)
    rank_dir = -1 if color == chess.WHITE else 1
    king_rank = chess.square_rank(king_square)
    king_file = chess.square_file(king_square)
    for df in (-1, 0, 1):
        file_index = king_file + df
        shield_rank = king_rank + rank_dir
        if 0 <= file_index <= 7 and 0 <= shield_rank <= 7:
            sq = chess.square(file_index, shield_rank)
            piece = board.piece_at(sq)
            if piece is not None and piece.color == color:
                if piece.piece_type == chess.PAWN:
                    safety += 10
    return safety


def _pawn_structure(board: Any, color: bool) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    files = {}
    for sq in pawns:
        file_index = chess.square_file(sq)
        files[file_index] = files.get(file_index, 0) + 1
    score = 0
    for sq in pawns:
        file_index = chess.square_file(sq)
        if files.get(file_index, 0) > 1:
            score -= 8
        if files.get(file_index - 1, 0) == 0 and files.get(file_index + 1, 0) == 0:
            score -= 10
    return score


def _is_endgame(board: Any) -> bool:
    material = 0
    for piece in board.piece_map().values():
        if piece.piece_type != chess.KING:
            material += PIECE_VALUES.get(int(piece.piece_type), 0)
    return material <= 2600


def _deterministic_fallback(board: Any, preferred: Optional[list] = None) -> Any:
    source = preferred or list(board.legal_moves)
    candidates = [mv for mv in source if mv in board.legal_moves]
    if not candidates:
        return None
    mate = _find_immediate_mate(board, candidates)
    if mate is not None:
        return mate
    ordered = _ordered_moves(board, candidates)
    return ordered[0] if ordered else None


def _time_up(state: _SearchState) -> bool:
    return time.perf_counter() >= state.deadline
