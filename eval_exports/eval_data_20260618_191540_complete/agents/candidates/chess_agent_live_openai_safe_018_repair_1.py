from __future__ import annotations

import json
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

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
BIG_CENTER = {
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
        board = parse_observation(observation)
        legal = list(board.legal_moves)
        if not legal or board.is_game_over(claim_draw=False):
            return ''
        chosen = choose_move(board, observation, time_limit_ms)
        if chosen not in board.legal_moves:
            chosen = fallback_move(board)
        return format_move(board, chosen, output_format)
    except Exception:
        try:
            board = parse_observation(observation)
            legal = list(board.legal_moves)
            if not legal:
                return ''
            return legal[0].uci()
        except Exception:
            return 'g1f3'


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, dict):
        for key in ('fen', 'board', 'state'):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        nested = observation.get('observation')
        if fen is None and isinstance(nested, dict):
            value = nested.get('fen')
            if isinstance(value, str) and value.strip():
                fen = value.strip()
    elif isinstance(observation, str):
        text = observation.strip()
        if text.startswith('{') and text.endswith('}'):
            try:
                payload = json.loads(text)
                if isinstance(payload, dict):
                    return parse_observation(payload)
            except json.JSONDecodeError:
                pass
        fen = text

    if not fen or fen.lower() in {'start', 'startpos'}:
        return chess.Board()
    try:
        return chess.Board(fen)
    except ValueError:
        return chess.Board()


def choose_move(board: chess.Board, observation: Any, time_limit_ms: int) -> chess.Move:
    legal = list(board.legal_moves)
    if len(legal) == 1:
        return legal[0]

    mate = immediate_mate(board)
    if mate is not None:
        return mate

    book = opening_preference(board)
    if book is not None:
        return book

    hint = hinted_legal_move(board, observation)
    best = hint if hint is not None else fallback_move(board)
    safe_ms = max(8, min(int(time_limit_ms), 250))
    deadline = time.perf_counter() + safe_ms * 0.00082
    if time_limit_ms <= 35:
        max_depth = 2
    elif time_limit_ms <= 140:
        max_depth = 3
    else:
        max_depth = 4

    table: dict[tuple[object, ...], int] = {}
    try:
        for depth in range(1, max_depth + 1):
            if time.perf_counter() >= deadline:
                break
            alpha = -INF
            depth_best = best
            depth_score = -INF
            completed = True
            moves = ordered_moves(board, list(board.legal_moves), best)
            for mv in moves:
                if time.perf_counter() >= deadline:
                    completed = False
                    break
                board.push(mv)
                score = -negamax(board, depth - 1, -INF, -alpha, deadline, 1, table)
                board.pop()
                if score > depth_score:
                    depth_score = score
                    depth_best = mv
                if score > alpha:
                    alpha = score
            if completed:
                best = depth_best
                if depth_score > MATE_SCORE - 1000:
                    break
    except TimeoutError:
        pass

    if best not in board.legal_moves:
        return fallback_move(board)
    return best


def hinted_legal_move(board: chess.Board, observation: Any) -> chess.Move | None:
    if not isinstance(observation, dict):
        return None
    hints: list[str] = []
    for key in ('move', 'best_move', 'bestMove'):
        value = observation.get(key)
        if isinstance(value, str):
            hints.append(value.strip())
    for key in ('legal_moves', 'legalMoves', 'moves'):
        value = observation.get(key)
        if isinstance(value, list):
            hints.extend(str(item).strip() for item in value)
    legal = {mv.uci(): mv for mv in board.legal_moves}
    for text in hints:
        move_obj = legal.get(text)
        if move_obj is not None:
            return move_obj
    return None


def immediate_mate(board: chess.Board) -> chess.Move | None:
    for mv in ordered_moves(board, list(board.legal_moves), None):
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def opening_preference(board: chess.Board) -> chess.Move | None:
    if board.fullmove_number > 3:
        return None
    if board.turn == chess.WHITE:
        preferred = ('e2e4', 'd2d4', 'g1f3', 'c2c4', 'b1c3', 'f1c4')
    else:
        preferred = ('e7e5', 'c7c5', 'g8f6', 'd7d5', 'b8c6', 'f8c5')
    legal = {mv.uci(): mv for mv in board.legal_moves}
    for text in preferred:
        move_obj = legal.get(text)
        if move_obj is not None:
            return move_obj
    return None


def negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
    table: dict[tuple[object, ...], int],
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError
    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    key = (
        board.board_fen(),
        board.turn,
        board.castling_xfen(),
        board.ep_square,
        board.halfmove_clock,
        depth,
    )
    cached = table.get(key)
    if cached is not None:
        return cached

    if depth <= 0:
        return quiescence(board, alpha, beta, deadline, ply, 4)

    best = -INF
    for mv in ordered_moves(board, list(board.legal_moves), None):
        board.push(mv)
        score = -negamax(board, depth - 1, -beta, -alpha, deadline, ply + 1, table)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    table[key] = best
    return best


def quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
    depth: int,
) -> int:
    if time.perf_counter() >= deadline:
        raise TimeoutError
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = evaluate_for_turn(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if depth <= 0:
        return alpha

    moves = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion is not None:
            moves.append(mv)
    for mv in ordered_moves(board, moves, None):
        board.push(mv)
        score = -quiescence(board, -beta, -alpha, deadline, ply + 1, depth - 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def ordered_moves(
    board: chess.Board,
    moves: list[chess.Move],
    previous_best: chess.Move | None,
) -> list[chess.Move]:
    def score_move(mv: chess.Move) -> int:
        score = 0
        if previous_best is not None and mv == previous_best:
            score += 100000
        if mv.promotion is not None:
            score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
        if board.is_capture(mv):
            victim = board.piece_at(mv.to_square)
            attacker = board.piece_at(mv.from_square)
            victim_value = 100 if victim is None else PIECE_VALUES[victim.piece_type]
            attacker_value = 100 if attacker is None else PIECE_VALUES[attacker.piece_type]
            score += 6000 + 10 * victim_value - attacker_value
        if board.gives_check(mv):
            score += 2500
        if mv.to_square in CENTER:
            score += 90
        elif mv.to_square in BIG_CENTER:
            score += 35
        piece = board.piece_at(mv.from_square)
        develops = piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP)
        if develops and board.fullmove_number <= 8:
            score += 25
        return score

    return sorted(moves, key=lambda item: (-score_move(item), item.uci()))


def evaluate_for_turn(board: chess.Board) -> int:
    score = evaluate_white_minus_black(board)
    if board.turn == chess.WHITE:
        return score
    return -score


def evaluate_white_minus_black(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    white_bishops = 0
    black_bishops = 0
    white_pawns = list(board.pieces(chess.PAWN, chess.WHITE))
    black_pawns = list(board.pieces(chess.PAWN, chess.BLACK))

    for sq, piece in board.piece_map().items():
        term = PIECE_VALUES[piece.piece_type] + square_bonus(sq, piece)
        mobility = len(board.attacks(sq))
        if piece.color == chess.WHITE:
            score += term + mobility
            if piece.piece_type == chess.BISHOP:
                white_bishops += 1
        else:
            score -= term + mobility
            if piece.piece_type == chess.BISHOP:
                black_bishops += 1

    if white_bishops >= 2:
        score += 35
    if black_bishops >= 2:
        score -= 35
    score += pawn_score(chess.WHITE, white_pawns, black_pawns)
    score -= pawn_score(chess.BLACK, black_pawns, white_pawns)
    score += king_safety(board)
    return int(score)


def square_bonus(square: int, piece: chess.Piece) -> int:
    file_idx = chess.square_file(square)
    rank_idx = chess.square_rank(square)
    if piece.color == chess.BLACK:
        rank_idx = 7 - rank_idx
    file_dist = abs(file_idx - 3.5)
    rank_dist = abs(rank_idx - 3.5)
    central = int(18 - 4 * (file_dist + rank_dist))
    if piece.piece_type == chess.PAWN:
        return rank_idx * 7 + (8 if square in CENTER else 0)
    if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        return central + rank_idx * 2
    if piece.piece_type == chess.ROOK:
        return 4 if rank_idx >= 6 else 0
    if piece.piece_type == chess.QUEEN:
        return central // 2
    if piece.piece_type == chess.KING:
        return 18 if rank_idx == 0 and file_idx in (2, 6) else -central
    return 0


def pawn_score(color: chess.Color, own: list[int], enemy: list[int]) -> int:
    score = 0
    files = [chess.square_file(sq) for sq in own]
    for sq in own:
        file_idx = chess.square_file(sq)
        rank_idx = chess.square_rank(sq)
        if files.count(file_idx) > 1:
            score -= 12
        if file_idx - 1 not in files and file_idx + 1 not in files:
            score -= 10
        passed = True
        for enemy_sq in enemy:
            enemy_file = chess.square_file(enemy_sq)
            enemy_rank = chess.square_rank(enemy_sq)
            if abs(enemy_file - file_idx) > 1:
                continue
            if color == chess.WHITE and enemy_rank > rank_idx:
                passed = False
            if color == chess.BLACK and enemy_rank < rank_idx:
                passed = False
        if passed:
            advance = rank_idx if color == chess.WHITE else 7 - rank_idx
            score += 8 + 6 * advance
    return score


def king_safety(board: chess.Board) -> int:
    score = 0
    if board.has_kingside_castling_rights(chess.WHITE):
        score += 8
    if board.has_queenside_castling_rights(chess.WHITE):
        score += 6
    if board.has_kingside_castling_rights(chess.BLACK):
        score -= 8
    if board.has_queenside_castling_rights(chess.BLACK):
        score -= 6
    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)
    if white_king is not None:
        if white_king in (chess.G1, chess.C1):
            score += 22
        score -= 8 * len(board.attackers(chess.BLACK, white_king))
    if black_king is not None:
        if black_king in (chess.G8, chess.C8):
            score -= 22
        score += 8 * len(board.attackers(chess.WHITE, black_king))
    return score


def fallback_move(board: chess.Board) -> chess.Move:
    legal = list(board.legal_moves)
    if not legal:
        return chess.Move.null()
    captures = [mv for mv in legal if board.is_capture(mv)]
    if captures:
        return ordered_moves(board, captures, None)[0]
    return sorted(legal, key=lambda item: item.uci())[0]


def format_move(board: chess.Board, chosen: chess.Move, output_format: str) -> str:
    if chosen not in board.legal_moves:
        chosen = fallback_move(board)
    fmt = (output_format or 'uci').strip().lower()
    if fmt == 'san':
        return board.san(chosen)
    return chosen.uci()
