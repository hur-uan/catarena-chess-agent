from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any, Optional

import chess


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

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
MATE_SCORE = 100000
INF = 10000000


@dataclass
class SearchRecord:
    fen: str
    selected_move: str
    cp: int = 0
    mate_distance: Optional[int] = None
    wdl: Optional[dict[str, float]] = None
    depth: int = 0
    elapsed_ms: float = 0.0
    nodes: int = 0
    qnodes: int = 0
    legal_moves: Optional[list[str]] = None
    principal_variation: Optional[list[str]] = None
    fallback_used: bool = False
    backend: str = 'standalone_safe'
    engine_config: Optional[dict[str, object]] = None


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
    board = _parse_board(observation)
    chosen = _choose_uci(board, time_limit_ms)
    chosen = _validated_uci_or_fallback(board, chosen)
    if output_format.lower().strip() == 'san' and chosen:
        try:
            return board.san(chess.Move.from_uci(chosen))
        except ValueError:
            return chosen
    return chosen


def select_move_details(
    observation: Any,
    output_format: str = 'uci',
    time_limit_ms: int = 100,
) -> SearchRecord:
    start = time.perf_counter()
    board = _parse_board(observation)
    legal = [mv.uci() for mv in board.legal_moves]
    selected = select_move(observation, output_format, time_limit_ms)
    cp = _static_eval(board) if legal else 0
    elapsed = (time.perf_counter() - start) * 1000.0
    return SearchRecord(
        fen=board.fen(),
        selected_move=selected,
        cp=int(cp),
        mate_distance=1 if selected and _move_mates(board, selected) else None,
        wdl=_cp_to_wdl(int(cp)),
        depth=_depth_for_time(time_limit_ms),
        elapsed_ms=elapsed,
        nodes=0,
        qnodes=0,
        legal_moves=legal,
        principal_variation=[selected] if selected else [],
        fallback_used=False,
        backend='standalone_safe',
        engine_config={'external_engine': 'disabled'},
    )


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
        fen = observation.get('fen') or observation.get('board')
        if isinstance(fen, str):
            return _board_from_fen(fen)
    if isinstance(observation, str):
        text = observation.strip()
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            fen = payload.get('fen') or payload.get('board')
            if isinstance(fen, str):
                return _board_from_fen(fen)
        return _board_from_fen(text)
    return chess.Board()


def _board_from_fen(fen: str) -> chess.Board:
    try:
        return chess.Board(fen)
    except ValueError:
        return chess.Board()


def _cp_to_wdl(cp: int) -> dict[str, float]:
    x = max(-800, min(800, cp)) / 250.0
    win = 1.0 / (1.0 + math.exp(-x))
    return {'win': win, 'draw': 0.0, 'loss': 1.0 - win}


def _choose_uci(board: chess.Board, time_limit_ms: int) -> str:
    if board.is_game_over(claim_draw=False):
        return ''
    legal = list(board.legal_moves)
    if not legal:
        return ''

    mate = _find_mate_in_one(board)
    if mate is not None:
        return mate.uci()

    start = time.perf_counter()
    budget = max(8, min(250, int(time_limit_ms))) / 1000.0
    deadline = start + max(0.006, budget * 0.82)
    depth = _depth_for_time(time_limit_ms)
    best_move = legal[0]
    best_score = -INF
    alpha = -INF
    nodes = 0

    ordered = sorted(legal, key=lambda mv: _move_order_score(board, mv), reverse=True)
    for mv in ordered:
        if time.perf_counter() >= deadline:
            break
        board.push(mv)
        score, used = _negamax(board, depth - 1, -INF, -alpha, deadline)
        score = -score
        board.pop()
        nodes += used
        tie = score == best_score and mv.uci() < best_move.uci()
        if score > best_score or tie:
            best_score = score
            best_move = mv
        if best_score > alpha:
            alpha = best_score
        if nodes > 70000:
            break

    chosen = best_move.uci()
    if time_limit_ms >= 45:
        chosen = _avoid_mate_blunder(board, chosen, deadline)
    return chosen


def _depth_for_time(time_limit_ms: int) -> int:
    if time_limit_ms < 35:
        return 2
    if time_limit_ms < 110:
        return 3
    return 4


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
) -> tuple[int, int]:
    if time.perf_counter() >= deadline:
        return _static_eval(board), 1
    if board.is_checkmate():
        return -MATE_SCORE + board.ply(), 1
    if board.is_stalemate() or board.is_insufficient_material():
        return 0, 1
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, 0)

    nodes = 1
    best = -INF
    moves = sorted(board.legal_moves, key=lambda mv: _move_order_score(board, mv), reverse=True)
    for mv in moves:
        board.push(mv)
        score, child_nodes = _negamax(board, depth - 1, -beta, -alpha, deadline)
        score = -score
        board.pop()
        nodes += child_nodes
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta or time.perf_counter() >= deadline or nodes > 60000:
            break
    return best, nodes


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    deadline: float,
    ply: int,
) -> tuple[int, int]:
    stand_pat = _static_eval(board)
    if stand_pat >= beta:
        return beta, 1
    if stand_pat > alpha:
        alpha = stand_pat
    if ply >= 4 or time.perf_counter() >= deadline:
        return alpha, 1

    nodes = 1
    noisy = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            noisy.append(mv)
    noisy.sort(key=lambda mv: _move_order_score(board, mv), reverse=True)

    for mv in noisy[:18]:
        board.push(mv)
        score, child_nodes = _quiescence(board, -beta, -alpha, deadline, ply + 1)
        score = -score
        board.pop()
        nodes += child_nodes
        if score >= beta:
            return beta, nodes
        if score > alpha:
            alpha = score
        if time.perf_counter() >= deadline:
            break
    return alpha, nodes


def _static_eval(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE + board.ply()
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        val = PIECE_VALUES.get(piece.piece_type, 0)
        val += _activity_bonus(square, piece)
        if piece.color == board.turn:
            score += val
        else:
            score -= val

    score += 2 * _safe_mobility_delta(board)
    if board.is_check():
        score -= 35
    return int(score)


def _activity_bonus(square: int, piece: chess.Piece) -> int:
    bonus = 0
    if square in CENTER:
        bonus += 16
    elif square in EXT_CENTER:
        bonus += 6
    if piece.piece_type in {chess.KNIGHT, chess.BISHOP}:
        rank = chess.square_rank(square)
        bonus += 2 * (rank if piece.color == chess.WHITE else 7 - rank)
        file_dist = abs(chess.square_file(square) - 3.5)
        rank_dist = abs(chess.square_rank(square) - 3.5)
        bonus -= int(file_dist + rank_dist)
    if piece.piece_type == chess.ROOK:
        file_mask = chess.BB_FILES[chess.square_file(square)]
        own_pawns = board_piece_count_on_file_placeholder(piece.color, file_mask)
        if own_pawns == 0:
            bonus += 4
    return bonus


def board_piece_count_on_file_placeholder(color: chess.Color, file_mask: int) -> int:
    return 0 if file_mask and color in {chess.WHITE, chess.BLACK} else 0


def _safe_mobility_delta(board: chess.Board) -> int:
    own = board.legal_moves.count()
    copy_board = board.copy(stack=False)
    copy_board.turn = not copy_board.turn
    try:
        opp = copy_board.legal_moves.count()
    except chess.IllegalMoveError:
        opp = 0
    return own - opp


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    attacker = board.piece_at(mv.from_square)
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        victim_value = 100 if board.is_en_passant(mv) else 0
        if victim is not None:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
        score += 1000 + 10 * victim_value - attacker_value
    if mv.promotion:
        score += 900 + PIECE_VALUES.get(mv.promotion, 0)
    if mv.to_square in CENTER:
        score += 45
    elif mv.to_square in EXT_CENTER:
        score += 16
    if attacker and attacker.piece_type in {chess.KNIGHT, chess.BISHOP}:
        home = 0 if attacker.color == chess.WHITE else 7
        if chess.square_rank(mv.from_square) == home:
            score += 35
    if board.is_castling(mv):
        score += 150
    if board.gives_check(mv):
        score += 280
    return score


def _find_mate_in_one(board: chess.Board) -> Optional[chess.Move]:
    moves = sorted(board.legal_moves, key=lambda mv: _move_order_score(board, mv), reverse=True)
    for mv in moves:
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return mv
    return None


def _move_mates(board: chess.Board, uci: str) -> bool:
    try:
        mv = chess.Move.from_uci(uci)
    except ValueError:
        return False
    if mv not in board.legal_moves:
        return False
    board.push(mv)
    result = board.is_checkmate()
    board.pop()
    return result


def _allows_reply_mate(board: chess.Board, uci: str) -> bool:
    try:
        mv = chess.Move.from_uci(uci)
    except ValueError:
        return True
    if mv not in board.legal_moves:
        return True
    board.push(mv)
    bad = _find_mate_in_one(board) is not None
    board.pop()
    return bad


def _avoid_mate_blunder(board: chess.Board, chosen: str, deadline: float) -> str:
    if not chosen or not _allows_reply_mate(board, chosen):
        return chosen
    best = None
    moves = sorted(board.legal_moves, key=lambda mv: _move_order_score(board, mv), reverse=True)
    for mv in moves:
        if time.perf_counter() >= deadline:
            break
        uci = mv.uci()
        if _allows_reply_mate(board, uci):
            continue
        board.push(mv)
        score = -_static_eval(board)
        board.pop()
        value = score + _move_order_score(board, mv) // 100
        if best is None or value > best[0] or (value == best[0] and uci < best[1]):
            best = (value, uci)
    return best[1] if best is not None else chosen


def _validated_uci_or_fallback(board: chess.Board, move_text: str) -> str:
    legal = list(board.legal_moves)
    if not legal:
        return ''
    text = str(move_text).strip()
    try:
        mv = chess.Move.from_uci(text)
        if mv in legal:
            return mv.uci()
    except ValueError:
        pass
    try:
        mv = board.parse_san(text)
        if mv in legal:
            return mv.uci()
    except ValueError:
        pass
    mate = _find_mate_in_one(board)
    if mate is not None:
        return mate.uci()
    ordered = sorted(legal, key=lambda mv: _move_order_score(board, mv), reverse=True)
    return ordered[0].uci()
