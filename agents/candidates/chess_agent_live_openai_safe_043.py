from __future__ import annotations

import time
from typing import Any

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

MATE_SCORE = 100000
INF = 10 ** 9
CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}

PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    8, 10, 10, -12, -12, 10, 10, 8,
    4, 6, 8, 12, 12, 8, 6, 4,
    2, 4, 6, 16, 16, 6, 4, 2,
    1, 2, 4, 12, 12, 4, 2, 1,
    1, 1, 2, -6, -6, 2, 1, 1,
    2, 2, 2, -10, -10, 2, 2, 2,
    0, 0, 0, 0, 0, 0, 0, 0,
]

KNIGHT_TABLE = [
    -40, -20, -12, -8, -8, -12, -20, -40,
    -20, -8, 0, 4, 4, 0, -8, -20,
    -12, 4, 10, 14, 14, 10, 4, -12,
    -8, 6, 14, 18, 18, 14, 6, -8,
    -8, 6, 14, 18, 18, 14, 6, -8,
    -12, 4, 10, 14, 14, 10, 4, -12,
    -20, -8, 0, 4, 4, 0, -8, -20,
    -40, -20, -12, -8, -8, -12, -20, -40,
]

BISHOP_TABLE = [
    -16, -8, -8, -8, -8, -8, -8, -16,
    -8, 4, 2, 2, 2, 2, 4, -8,
    -8, 6, 8, 8, 8, 8, 6, -8,
    -8, 2, 8, 10, 10, 8, 2, -8,
    -8, 4, 8, 10, 10, 8, 4, -8,
    -8, 2, 8, 8, 8, 8, 2, -8,
    -8, 2, 2, 2, 2, 2, 2, -8,
    -16, -8, -8, -8, -8, -8, -8, -16,
]

ROOK_TABLE = [
    0, 0, 2, 6, 6, 2, 0, 0,
    2, 4, 6, 8, 8, 6, 4, 2,
    -2, 0, 2, 4, 4, 2, 0, -2,
    -2, 0, 2, 4, 4, 2, 0, -2,
    -2, 0, 2, 4, 4, 2, 0, -2,
    -2, 0, 2, 4, 4, 2, 0, -2,
    -2, 0, 2, 4, 4, 2, 0, -2,
    0, 0, 2, 6, 6, 2, 0, 0,
]

QUEEN_TABLE = [
    -10, -6, -4, -2, -2, -4, -6, -10,
    -6, 0, 2, 2, 2, 2, 0, -6,
    -4, 2, 4, 4, 4, 4, 2, -4,
    -2, 2, 4, 6, 6, 4, 2, -2,
    -2, 2, 4, 6, 6, 4, 2, -2,
    -4, 2, 4, 4, 4, 4, 2, -4,
    -6, 0, 2, 2, 2, 2, 0, -6,
    -10, -6, -4, -2, -2, -4, -6, -10,
]

KING_MID_TABLE = [
    18, 24, 10, 0, 0, 10, 24, 18,
    12, 12, 0, 0, 0, 0, 12, 12,
    -8, -12, -16, -20, -20, -16, -12, -8,
    -18, -24, -28, -34, -34, -28, -24, -18,
    -26, -32, -38, -44, -44, -38, -32, -26,
    -34, -40, -46, -52, -52, -46, -40, -34,
    -40, -48, -54, -60, -60, -54, -48, -40,
    -44, -52, -60, -70, -70, -60, -52, -44,
]

KING_END_TABLE = [
    -28, -18, -10, -6, -6, -10, -18, -28,
    -18, -6, 4, 8, 8, 4, -6, -18,
    -10, 4, 14, 18, 18, 14, 4, -10,
    -6, 8, 18, 24, 24, 18, 8, -6,
    -6, 8, 18, 24, 24, 18, 8, -6,
    -10, 4, 14, 18, 18, 14, 4, -10,
    -18, -6, 4, 8, 8, 4, -6, -18,
    -28, -18, -10, -6, -6, -10, -18, -28,
]

PIECE_TABLES = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
}


class ChessAgent:
    def __init__(self, output_format: str = 'uci', time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(observation: Any, output_format: str = 'uci', time_limit_ms: int = 100) -> str:
    try:
        board = _parse_board(observation)
        legal_moves = list(board.legal_moves)
        if not legal_moves or board.is_game_over(claim_draw=False):
            return ''
        selected = _choose_move(board, legal_moves, time_limit_ms)
        if selected not in legal_moves:
            selected = legal_moves[0]
        return _format_move(board, selected, output_format)
    except Exception:
        try:
            board = _parse_board(observation)
            fallback_moves = list(board.legal_moves)
            return fallback_moves[0].uci() if fallback_moves else ''
        except Exception:
            return ''


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_board(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, dict):
        for key in ('fen', 'board', 'state'):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                return chess.Board(value.strip())
        if isinstance(observation.get('observation'), dict):
            return _parse_board(observation['observation'])
        if isinstance(observation.get('observation'), str):
            return chess.Board(observation['observation'].strip())
    if isinstance(observation, str) and observation.strip():
        text = observation.strip()
        if text.lower() in {'start', 'startpos'}:
            return chess.Board()
        return chess.Board(text)
    return chess.Board()


def _format_move(board: chess.Board, move_obj: chess.Move, output_format: str) -> str:
    requested = (output_format or 'uci').lower().strip()
    if requested == 'san':
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _choose_move(board: chess.Board, legal_moves: list[chess.Move], time_limit_ms: int) -> chess.Move:
    mate = _find_immediate_mate(board, legal_moves)
    if mate is not None:
        return mate

    budget_ms = max(8, min(180, int(time_limit_ms or 100)))
    deadline = time.perf_counter() + max(0.004, (budget_ms - 4) / 1000.0)
    best_move = _best_static_move(board, legal_moves)
    best_score = -INF
    ordered = _ordered_moves(board, legal_moves)

    max_depth = 2
    if budget_ms >= 55:
        max_depth = 3
    if budget_ms >= 130 and len(legal_moves) <= 28:
        max_depth = 4

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        depth_best = best_move
        depth_score = -INF
        alpha = -INF
        for candidate in ordered:
            if time.perf_counter() >= deadline:
                break
            board.push(candidate)
            score = -_negamax(board, depth - 1, -INF, -alpha, deadline, 0)
            board.pop()
            if score > depth_score:
                depth_score = score
                depth_best = candidate
            if score > alpha:
                alpha = score
        if time.perf_counter() < deadline and depth_best in legal_moves:
            best_move = depth_best
            best_score = depth_score
            if best_score >= MATE_SCORE - 128:
                break
    return best_move


def _negamax(board: chess.Board, depth: int, alpha: int, beta: int, deadline: float, ply: int) -> int:
    if time.perf_counter() >= deadline:
        return _evaluate_for_turn(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    value = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for candidate in moves:
        board.push(candidate)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score > value:
            value = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
        if time.perf_counter() >= deadline:
            break
    return value


def _quiescence(board: chess.Board, alpha: int, beta: int, deadline: float, ply: int) -> int:
    if board.is_checkmate():
        return -MATE_SCORE + ply
    stand_pat = _evaluate_for_turn(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if time.perf_counter() >= deadline:
        return alpha

    tactical = []
    for candidate in board.legal_moves:
        if board.is_capture(candidate) or candidate.promotion or board.gives_check(candidate):
            tactical.append(candidate)
    for candidate in _ordered_moves(board, tactical):
        if time.perf_counter() >= deadline:
            break
        board.push(candidate)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _find_immediate_mate(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move | None:
    for candidate in _ordered_moves(board, legal_moves):
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return candidate
    return None


def _best_static_move(board: chess.Board, legal_moves: list[chess.Move]) -> chess.Move:
    return max(legal_moves, key=lambda item: _move_order_score(board, item))


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda item: _move_order_score(board, item), reverse=True)


def _move_order_score(board: chess.Board, move_obj: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(move_obj.from_square)
    captured_piece = board.piece_at(move_obj.to_square)

    if board.is_capture(move_obj):
        if captured_piece is None and board.is_en_passant(move_obj):
            captured_value = PIECE_VALUES[chess.PAWN]
        else:
            captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0) if captured_piece else 0
        attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        score += 10000 + captured_value * 10 - attacker_value
    if move_obj.promotion:
        score += 9000 + PIECE_VALUES.get(move_obj.promotion, 0)
    if board.gives_check(move_obj):
        score += 7000
    if board.is_castling(move_obj):
        score += 1200
    if move_obj.to_square in CENTER_SQUARES:
        score += 140
    elif move_obj.to_square in EXTENDED_CENTER:
        score += 55
    if moving_piece:
        if moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP) and _is_back_rank(move_obj.from_square, moving_piece.color):
            score += 180
        if moving_piece.piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 90
        if moving_piece.piece_type == chess.ROOK and board.fullmove_number <= 10:
            score -= 35
    return score


def _is_back_rank(square: chess.Square, color: chess.Color) -> bool:
    rank = chess.square_rank(square)
    return rank == (0 if color == chess.WHITE else 7)


def _evaluate_for_turn(board: chess.Board) -> int:
    score = _evaluate_white_minus_black(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    non_king_material = 0
    white_bishops = 0
    black_bishops = 0

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES.get(piece.piece_type, 0)
        if piece.piece_type != chess.KING:
            non_king_material += value
        table_bonus = _piece_square_bonus(piece, square, non_king_material)
        piece_score = value + table_bonus
        if piece.color == chess.WHITE:
            score += piece_score
            if piece.piece_type == chess.BISHOP:
                white_bishops += 1
        else:
            score -= piece_score
            if piece.piece_type == chess.BISHOP:
                black_bishops += 1

    if white_bishops >= 2:
        score += 28
    if black_bishops >= 2:
        score -= 28

    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)
    score += _king_safety_score(board, chess.WHITE)
    score -= _king_safety_score(board, chess.BLACK)
    score += _mobility_score(board)
    if board.is_check():
        score += -35 if board.turn == chess.WHITE else 35
    return score


def _piece_square_bonus(piece: chess.Piece, square: chess.Square, non_king_material: int) -> int:
    lookup_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
    if piece.piece_type == chess.KING:
        table = KING_END_TABLE if non_king_material <= 2200 else KING_MID_TABLE
        return table[lookup_square]
    table = PIECE_TABLES.get(piece.piece_type)
    if table is None:
        return 0
    return table[lookup_square]


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = board.pieces(chess.PAWN, color)
    score = 0
    files = [0] * 8
    for square in pawns:
        files[chess.square_file(square)] += 1
        rank = chess.square_rank(square)
        score += (rank if color == chess.WHITE else 7 - rank) * 3
    for file_index, count in enumerate(files):
        if count > 1:
            score -= 10 * (count - 1)
        if count:
            left = files[file_index - 1] if file_index > 0 else 0
            right = files[file_index + 1] if file_index < 7 else 0
            if left == 0 and right == 0:
                score -= 8 * count
    return score


def _king_safety_score(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return -500
    score = 0
    opponent = not color
    for target in chess.SquareSet(chess.BB_KING_ATTACKS[king_square]):
        if board.is_attacked_by(opponent, target):
            score -= 4
    file_index = chess.square_file(king_square)
    rank_index = chess.square_rank(king_square)
    pawn_rank = rank_index + (1 if color == chess.WHITE else -1)
    if 0 <= pawn_rank <= 7:
        for file_delta in (-1, 0, 1):
            pawn_file = file_index + file_delta
            if 0 <= pawn_file <= 7:
                piece = board.piece_at(chess.square(pawn_file, pawn_rank))
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 7
    return score


def _mobility_score(board: chess.Board) -> int:
    turn = board.turn
    try:
        board.turn = chess.WHITE
        white_mobility = board.legal_moves.count()
        board.turn = chess.BLACK
        black_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    return 2 * (white_mobility - black_mobility)
