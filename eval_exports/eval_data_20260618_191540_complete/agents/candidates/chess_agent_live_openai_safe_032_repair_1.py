from __future__ import annotations

import time
from typing import Any

import chess

MATE_SCORE = 100000
INF = 10**9

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
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

KNIGHT_TABLE = [
    -50, -35, -25, -20, -20, -25, -35, -50,
    -35, -20, 0, 5, 5, 0, -20, -35,
    -25, 5, 12, 18, 18, 12, 5, -25,
    -20, 8, 18, 25, 25, 18, 8, -20,
    -20, 5, 18, 25, 25, 18, 5, -20,
    -25, 5, 12, 18, 18, 12, 5, -25,
    -35, -20, 0, 5, 5, 0, -20, -35,
    -50, -35, -25, -20, -20, -25, -35, -50,
]

BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 15, 15, 10, 0, -10,
    -10, 5, 10, 15, 15, 10, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]

PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 18, 18, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]


def _mirror_index(square: chess.Square, color: chess.Color) -> int:
    if color == chess.WHITE:
        return square
    return chess.square_mirror(square)


class ChessAgent:
    def __init__(self, output_format: str = 'uci', time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(
    observation: Any,
    output_format: str = 'uci',
    time_limit_ms: int = 100,
) -> str:
    try:
        board = _parse_observation(observation)
        legal_moves = list(board.legal_moves)
        if not legal_moves or board.is_game_over(claim_draw=False):
            return ''
        move_obj = _choose_move(board, max(1, int(time_limit_ms)))
        if move_obj not in legal_moves:
            move_obj = _fallback_move(board)
        return _format_move(board, move_obj, output_format)
    except Exception:
        try:
            board = _parse_observation(observation)
            move_obj = _fallback_move(board)
            if move_obj is None:
                return ''
            return move_obj.uci()
        except Exception:
            return ''


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)
    if isinstance(observation, dict):
        fen = observation.get('fen') or observation.get('board') or observation.get('state')
        if isinstance(fen, str):
            return chess.Board(fen)
    if isinstance(observation, str):
        text = observation.strip()
        if text:
            return chess.Board(text)
    return chess.Board()


def _format_move(
    board: chess.Board,
    move_obj: chess.Move | None,
    output_format: str,
) -> str:
    if move_obj is None or move_obj not in board.legal_moves:
        return ''
    fmt = (output_format or 'uci').lower().strip()
    if fmt == 'san':
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _fallback_move(board: chess.Board) -> chess.Move | None:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None
    legal_moves.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)
    return legal_moves[0]


def _choose_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if len(legal_moves) == 1:
        return legal_moves[0]

    for move_obj in _ordered_moves(board):
        board.push(move_obj)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move_obj

    budget = max(0.003, min(0.20, (time_limit_ms - 6) / 1000.0))
    deadline = time.perf_counter() + budget

    piece_count = len(board.piece_map())
    if time_limit_ms < 45:
        max_depth = 2
    elif time_limit_ms < 90:
        max_depth = 3
    elif piece_count <= 12:
        max_depth = 4
    else:
        max_depth = 3

    best_move = _fallback_move(board) or legal_moves[0]
    best_score = -INF
    ordered_root = _ordered_moves(board)

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        current_best = best_move
        current_score = -INF
        alpha = -INF
        beta = INF
        completed = True
        for move_obj in ordered_root:
            if time.perf_counter() >= deadline:
                completed = False
                break
            board.push(move_obj)
            score = -_negamax(board, depth - 1, -beta, -alpha, deadline, 1)
            board.pop()
            if score > current_score:
                current_score = score
                current_best = move_obj
            if score > alpha:
                alpha = score
        if not completed:
            break
        best_move = current_best
        best_score = current_score
        if best_score > MATE_SCORE - 1000:
            break
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
        return _evaluate_relative(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, ply)

    value = -INF
    for move_obj in _ordered_moves(board):
        board.push(move_obj)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score > value:
            value = score
        if value > alpha:
            alpha = value
        if alpha >= beta:
            break
    return value


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> int:
    if time.perf_counter() >= deadline:
        return _evaluate_relative(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_relative(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    tactical = []
    for move_obj in board.legal_moves:
        if board.is_capture(move_obj) or move_obj.promotion or board.gives_check(move_obj):
            tactical.append(move_obj)
    tactical.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)

    for move_obj in tactical[:18]:
        if time.perf_counter() >= deadline:
            break
        board.push(move_obj)
        score = -_quiescence(board, -beta, -alpha, deadline, ply + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _ordered_moves(board: chess.Board) -> list[chess.Move]:
    moves = list(board.legal_moves)
    moves.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)
    return moves


def _move_order_score(board: chess.Board, move_obj: chess.Move) -> int:
    score = 0
    moving = board.piece_at(move_obj.from_square)
    captured = board.piece_at(move_obj.to_square)
    if captured is None and board.is_en_passant(move_obj):
        captured = chess.Piece(chess.PAWN, not board.turn)
    if captured is not None:
        attacker_value = PIECE_VALUES.get(chess.PAWN, 100)
        if moving is not None:
            attacker_value = PIECE_VALUES.get(moving.piece_type, 100)
        victim_value = PIECE_VALUES.get(captured.piece_type, 100)
        score += 10000 + 10 * victim_value - attacker_value
    if move_obj.promotion:
        score += 8500 + PIECE_VALUES.get(move_obj.promotion, 0)
    try:
        if board.gives_check(move_obj):
            score += 2500
    except Exception:
        pass
    if board.is_castling(move_obj):
        score += 650
    if move_obj.to_square in CENTER:
        score += 180
    elif move_obj.to_square in EXTENDED_CENTER:
        score += 70
    if moving is not None and moving.piece_type in (chess.KNIGHT, chess.BISHOP):
        rank = chess.square_rank(move_obj.from_square)
        is_white_home = moving.color == chess.WHITE and rank == 0
        is_black_home = moving.color == chess.BLACK and rank == 7
        if is_white_home or is_black_home:
            score += 140
    if moving is not None and moving.piece_type == chess.QUEEN:
        if board.fullmove_number <= 8:
            score -= 90
    return score


def _evaluate_relative(board: chess.Board) -> int:
    white_score = _evaluate_color(board, chess.WHITE)
    white_score -= _evaluate_color(board, chess.BLACK)
    original_turn = board.turn
    try:
        own_mobility = board.legal_moves.count()
        board.turn = not board.turn
        opponent_mobility = board.legal_moves.count()
        mobility_delta = own_mobility - opponent_mobility
        if original_turn == chess.WHITE:
            white_score += 3 * mobility_delta
        else:
            white_score -= 3 * mobility_delta
    except Exception:
        pass
    finally:
        board.turn = original_turn
    if board.turn == chess.WHITE:
        return white_score
    return -white_score


def _evaluate_color(board: chess.Board, color: chess.Color) -> int:
    score = 0
    bishops = 0
    pawns_by_file = [0] * 8

    for square, piece in board.piece_map().items():
        if piece.color != color:
            continue
        piece_type = piece.piece_type
        score += PIECE_VALUES.get(piece_type, 0)
        index = _mirror_index(square, color)
        if piece_type == chess.PAWN:
            score += PAWN_TABLE[index]
            pawns_by_file[chess.square_file(square)] += 1
            score += _passed_pawn_bonus(board, square, color)
        elif piece_type == chess.KNIGHT:
            score += KNIGHT_TABLE[index]
        elif piece_type == chess.BISHOP:
            bishops += 1
            score += BISHOP_TABLE[index]
        elif piece_type == chess.ROOK:
            score += _rook_file_bonus(board, square, color)
        elif piece_type == chess.QUEEN and square in CENTER:
            score += 8
        elif piece_type == chess.KING:
            score += _king_safety(board, square, color)

        if square in CENTER:
            score += 16
        elif square in EXTENDED_CENTER:
            score += 6

    if bishops >= 2:
        score += 35
    for count in pawns_by_file:
        if count > 1:
            score -= 14 * (count - 1)
    for file_index, count in enumerate(pawns_by_file):
        if count and not _has_neighbor_pawn(pawns_by_file, file_index):
            score -= 10 * count
    return score


def _has_neighbor_pawn(pawns_by_file: list[int], file_index: int) -> bool:
    left = file_index > 0 and pawns_by_file[file_index - 1] > 0
    right = file_index < 7 and pawns_by_file[file_index + 1] > 0
    return left or right


def _passed_pawn_bonus(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> int:
    file_index = chess.square_file(square)
    rank = chess.square_rank(square)
    enemy = not color
    files = [f for f in (file_index - 1, file_index, file_index + 1) if 0 <= f <= 7]
    if color == chess.WHITE:
        ahead_ranks = range(rank + 1, 8)
        advance = rank
    else:
        ahead_ranks = range(rank - 1, -1, -1)
        advance = 7 - rank
    for file_item in files:
        for rank_item in ahead_ranks:
            piece = board.piece_at(chess.square(file_item, rank_item))
            if piece is not None and piece.color == enemy:
                if piece.piece_type == chess.PAWN:
                    return 0
    return 8 + advance * advance * 3


def _rook_file_bonus(
    board: chess.Board,
    square: chess.Square,
    color: chess.Color,
) -> int:
    file_index = chess.square_file(square)
    own_pawn = False
    enemy_pawn = False
    for rank in range(8):
        piece = board.piece_at(chess.square(file_index, rank))
        if piece is not None and piece.piece_type == chess.PAWN:
            if piece.color == color:
                own_pawn = True
            else:
                enemy_pawn = True
    if not own_pawn and not enemy_pawn:
        return 28
    if not own_pawn and enemy_pawn:
        return 16
    return 0


def _king_safety(board: chess.Board, square: chess.Square, color: chess.Color) -> int:
    non_king_material = sum(
        PIECE_VALUES.get(piece.piece_type, 0)
        for piece in board.piece_map().values()
        if piece.piece_type != chess.KING
    )
    if non_king_material < 2400:
        return 0

    score = 0
    file_index = chess.square_file(square)
    rank = chess.square_rank(square)
    home_rank = 0 if color == chess.WHITE else 7
    if rank == home_rank and file_index in (1, 2, 6):
        score += 25

    pawn_rank = rank + (1 if color == chess.WHITE else -1)
    if 0 <= pawn_rank <= 7:
        for file_item in (file_index - 1, file_index, file_index + 1):
            if 0 <= file_item <= 7:
                piece = board.piece_at(chess.square(file_item, pawn_rank))
                if piece is not None and piece.color == color:
                    if piece.piece_type == chess.PAWN:
                        score += 10

    enemy_attacks = 0
    for ring_square in chess.SquareSet(chess.BB_KING_ATTACKS[square]):
        if board.is_attacked_by(not color, ring_square):
            enemy_attacks += 1
    score -= 8 * enemy_attacks
    return score
