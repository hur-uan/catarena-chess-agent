from __future__ import annotations

import time
from typing import Any

import chess

INF = 10_000_000
MATE = 9_000_000
DEFAULT_TIME_LIMIT_MS = 100

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 27, 27, 10, 5, 5,
    0, 0, 0, 25, 25, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -25, -25, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_PST = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_PST = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_PST = [
    0, 0, 5, 10, 10, 5, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
QUEEN_PST = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,
    0, 0, 5, 5, 5, 5, 0, -5,
    -5, 0, 5, 5, 5, 5, 0, -5,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_MID_PST = [
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]
KING_END_PST = [
    -50, -30, -30, -30, -30, -30, -30, -50,
    -30, -10, 0, 0, 0, 0, -10, -30,
    -30, 0, 20, 30, 30, 20, 0, -30,
    -30, 0, 30, 40, 40, 30, 0, -30,
    -30, 0, 30, 40, 40, 30, 0, -30,
    -30, 0, 20, 30, 30, 20, 0, -30,
    -30, -10, 0, 0, 0, 0, -10, -30,
    -50, -30, -30, -30, -30, -30, -30, -50,
]
PSTS = {
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


class SearchState:
    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        self.nodes = 0
        self.stopped = False


class ChessAgent:
    def __init__(
        self,
        output_format: str = 'uci',
        time_limit_ms: int = DEFAULT_TIME_LIMIT_MS,
    ) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(
    observation: Any,
    output_format: str = 'uci',
    time_limit_ms: int = DEFAULT_TIME_LIMIT_MS,
) -> str:
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ''

    legal_set = {mv.uci() for mv in legal_moves}

    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate and mv.uci() in legal_set:
            return _format_move(board, mv, output_format)

    budget_ms = _safe_budget_ms(time_limit_ms)
    state = SearchState(time.monotonic() + budget_ms / 1000.0)
    best_move = _fallback_move(board, legal_moves)
    best_score = -INF
    max_depth = _choose_depth(board, budget_ms)
    root_moves = _ordered_moves(board, legal_moves)

    for depth in range(1, max_depth + 1):
        if _time_up(state):
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        beta = INF
        for mv in root_moves:
            if _time_up(state):
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -beta, -alpha, state, 1)
            board.pop()
            if state.stopped:
                break
            tie_now = _move_tiebreak(board, mv)
            tie_best = _move_tiebreak(board, current_best)
            if score > current_score or (score == current_score and tie_now > tie_best):
                current_score = score
                current_best = mv
            if score > alpha:
                alpha = score
        if not state.stopped and current_best in legal_moves:
            best_move = current_best
            best_score = current_score
            if best_score > MATE - 1000:
                break

    if best_move.uci() not in legal_set:
        best_move = _fallback_move(board, legal_moves)
    return _format_move(board, best_move, output_format)


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
        for key in ('fen', 'board', 'state'):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass
    return chess.Board()


def _safe_budget_ms(time_limit_ms: int) -> int:
    try:
        requested = int(time_limit_ms)
    except (TypeError, ValueError):
        requested = DEFAULT_TIME_LIMIT_MS
    requested = max(10, requested)
    if requested <= 30:
        return max(5, requested - 5)
    if requested <= 100:
        return max(15, requested - 15)
    return max(30, min(requested - 25, 450))


def _choose_depth(board: chess.Board, budget_ms: int) -> int:
    legal_count = board.legal_moves.count()
    phase = _phase_material(board)
    if budget_ms < 35:
        return 2
    if budget_ms < 85:
        return 3 if legal_count <= 28 else 2
    if budget_ms < 180:
        return 4 if legal_count <= 18 or phase < 2600 else 3
    return 4


def _time_up(state: SearchState) -> bool:
    if state.nodes & 63 == 0 and time.monotonic() >= state.deadline:
        state.stopped = True
    return state.stopped


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    state: SearchState,
    ply: int,
) -> int:
    state.nodes += 1
    if _time_up(state):
        return 0
    if board.is_checkmate():
        return -MATE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, state, ply)

    best = -INF
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return -MATE + ply if board.is_check() else 0

    for mv in _ordered_moves(board, legal_moves):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state, ply + 1)
        board.pop()
        if state.stopped:
            return 0
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    state: SearchState,
    ply: int,
) -> int:
    state.nodes += 1
    if _time_up(state):
        return 0
    if board.is_checkmate():
        return -MATE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    stand_pat = _evaluate_for_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)

    for mv in _ordered_moves(board, tactical):
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


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_type_at(mv.from_square) or chess.PAWN
    captured_piece = board.piece_type_at(mv.to_square)
    if captured_piece is None and board.is_en_passant(mv):
        captured_piece = chess.PAWN
    if captured_piece is not None:
        score += 10_000 + 10 * PIECE_VALUES[captured_piece] - PIECE_VALUES[moving_piece]
    if mv.promotion:
        score += 8_000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.gives_check(mv):
        score += 1_200
    if mv.to_square in CENTER_SQUARES:
        score += 90
    elif mv.to_square in EXTENDED_CENTER:
        score += 35
    if board.is_castling(mv):
        score += 250
    if moving_piece in (chess.KNIGHT, chess.BISHOP) and board.fullmove_number <= 12:
        score += 30
    return score


def _move_tiebreak(board: chess.Board, mv: chess.Move) -> int:
    return _move_order_score(board, mv) + (63 - mv.from_square) + mv.to_square


def _fallback_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    return _ordered_moves(board, legal_moves)[0]


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    fmt = (output_format or 'uci').lower().strip()
    if fmt in {'san', 'algebraic'}:
        try:
            return board.san(mv)
        except (ValueError, AssertionError):
            return mv.uci()
    return mv.uci()


def _evaluate_for_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white_minus_black(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE if board.turn == chess.WHITE else MATE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    endgame = _phase_material(board) < 1800
    for color in (chess.WHITE, chess.BLACK):
        sign = 1 if color == chess.WHITE else -1
        bishops = 0
        for piece_type in chess.PIECE_TYPES:
            pieces = board.pieces(piece_type, color)
            if piece_type == chess.BISHOP:
                bishops = len(pieces)
            for sq in pieces:
                score += sign * PIECE_VALUES[piece_type]
                pst_sq = sq if color == chess.WHITE else chess.square_mirror(sq)
                if piece_type == chess.KING:
                    table = KING_END_PST if endgame else KING_MID_PST
                    score += sign * table[pst_sq]
                else:
                    score += sign * PSTS[piece_type][pst_sq]
                if sq in CENTER_SQUARES and piece_type != chess.KING:
                    score += sign * 12
        if bishops >= 2:
            score += sign * 35

    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE, endgame)
    score -= _king_safety_score(board, chess.BLACK, endgame)
    score += _mobility_score(board)

    white_castle = (
        board.has_kingside_castling_rights(chess.WHITE)
        or board.has_queenside_castling_rights(chess.WHITE)
    )
    black_castle = (
        board.has_kingside_castling_rights(chess.BLACK)
        or board.has_queenside_castling_rights(chess.BLACK)
    )
    if white_castle:
        score += 12
    if black_castle:
        score -= 12
    if board.is_check():
        score += -25 if board.turn == chess.WHITE else 25
    return score


def _phase_material(board: chess.Board) -> int:
    total = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += len(board.pieces(piece_type, chess.WHITE)) * PIECE_VALUES[piece_type]
        total += len(board.pieces(piece_type, chess.BLACK)) * PIECE_VALUES[piece_type]
    return total


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0
    files: dict[int, int] = {}
    for sq in pawns:
        file_index = chess.square_file(sq)
        files[file_index] = files.get(file_index, 0) + 1

    score = 0
    enemy_pawns = board.pieces(chess.PAWN, not color)
    direction = 1 if color == chess.WHITE else -1
    for sq in pawns:
        file_index = chess.square_file(sq)
        rank_index = chess.square_rank(sq)
        if files[file_index] > 1:
            score -= 12
        if files.get(file_index - 1, 0) == 0 and files.get(file_index + 1, 0) == 0:
            score -= 10

        passed = True
        for adj_file in (file_index - 1, file_index, file_index + 1):
            if adj_file < 0 or adj_file > 7:
                continue
            for enemy_sq in enemy_pawns:
                if chess.square_file(enemy_sq) != adj_file:
                    continue
                enemy_rank = chess.square_rank(enemy_sq)
                white_blocked = color == chess.WHITE and enemy_rank > rank_index
                black_blocked = color == chess.BLACK and enemy_rank < rank_index
                if white_blocked or black_blocked:
                    passed = False
                    break
            if not passed:
                break
        if passed:
            advance = rank_index if color == chess.WHITE else 7 - rank_index
            score += 18 + 8 * advance

        next_rank = rank_index + direction
        if 0 <= next_rank <= 7:
            front = chess.square(file_index, next_rank)
            if board.piece_at(front) is not None:
                score -= 8
    return score


def _king_safety_score(board: chess.Board, color: chess.Color, endgame: bool) -> int:
    if endgame:
        return 0
    king_sq = board.king(color)
    if king_sq is None:
        return -500
    score = 0
    enemy = not color
    if board.is_attacked_by(enemy, king_sq):
        score -= 40
    king_file = chess.square_file(king_sq)
    king_rank = chess.square_rank(king_sq)
    shield_rank = king_rank + (1 if color == chess.WHITE else -1)
    if 0 <= shield_rank <= 7:
        for file_index in (king_file - 1, king_file, king_file + 1):
            if 0 <= file_index <= 7:
                sq = chess.square(file_index, shield_rank)
                piece = board.piece_at(sq)
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 12
                else:
                    score -= 8
    attackers = 0
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king_sq]):
        if board.is_attacked_by(enemy, sq):
            attackers += 1
    score -= 5 * attackers
    return score


def _mobility_score(board: chess.Board) -> int:
    turn = board.turn
    score = 0
    try:
        board.turn = chess.WHITE
        score += min(60, board.legal_moves.count())
        board.turn = chess.BLACK
        score -= min(60, board.legal_moves.count())
    finally:
        board.turn = turn
    return 2 * score
