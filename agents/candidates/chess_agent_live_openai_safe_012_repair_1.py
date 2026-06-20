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
    chess.QUEEN: 920,
    chess.KING: 0,
}

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
NEAR_CENTER = {
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
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ''

    ordered = _ordered_moves(board, legal_moves)
    for mv in ordered:
        board.push(mv)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return _format_move(board, mv, output_format)

    chosen = _search_best_move(board, time_limit_ms)
    if chosen not in legal_moves:
        chosen = _safe_fallback(board, legal_moves)
    return _format_move(board, chosen, output_format)


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
    elif isinstance(observation, str) and observation.strip():
        fen = observation.strip()

    if fen:
        try:
            return chess.Board(fen)
        except ValueError:
            pass

    board = chess.Board()
    if not isinstance(observation, dict):
        return board

    history = (
        observation.get('moves')
        or observation.get('move_history')
        or observation.get('history')
        or []
    )
    if not isinstance(history, list):
        return board

    for item in history:
        token = ''
        if isinstance(item, str):
            token = item.strip()
        elif isinstance(item, dict):
            raw = item.get('move') or item.get('uci') or item.get('san')
            token = str(raw).strip() if raw is not None else ''
        if not token:
            continue
        try:
            mv = chess.Move.from_uci(token)
            if mv in board.legal_moves:
                board.push(mv)
                continue
        except ValueError:
            pass
        try:
            board.push_san(token)
        except ValueError:
            break
    return board


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    fmt = (output_format or 'uci').lower().strip()
    if fmt == 'san':
        try:
            return board.san(mv)
        except (AssertionError, ValueError):
            return mv.uci()
    return mv.uci()


def _search_best_move(board: chess.Board, time_limit_ms: int) -> chess.Move:
    legal_moves = list(board.legal_moves)
    fallback = _safe_fallback(board, legal_moves)
    if len(legal_moves) <= 1:
        return fallback

    requested = max(10, int(time_limit_ms or 100))
    budget_ms = min(max(requested * 0.72, 5.0), 120.0)
    deadline = time.perf_counter() + (budget_ms / 1000.0)
    state = {'deadline': deadline, 'stop': False, 'nodes': 0}

    max_depth = 4 if requested >= 60 else 3
    if requested >= 140:
        max_depth = 5
    if requested <= 25:
        max_depth = 2

    ordered = _ordered_moves(board, legal_moves)
    best_move = fallback
    best_score = -INF

    for depth in range(1, max_depth + 1):
        if time.perf_counter() >= deadline:
            break
        current_move = best_move
        current_score = -INF
        alpha = -INF
        for mv in ordered:
            if time.perf_counter() >= deadline:
                state['stop'] = True
                break
            board.push(mv)
            score = -_negamax(board, depth - 1, -INF, -alpha, state)
            board.pop()
            if state['stop']:
                break
            better_tie = _move_tiebreak(board, mv) > _move_tiebreak(board, current_move)
            if score > current_score or (score == current_score and better_tie):
                current_score = score
                current_move = mv
            alpha = max(alpha, score)
        if state['stop']:
            break
        best_move = current_move
        best_score = current_score
        ordered = [best_move] + [mv for mv in ordered if mv != best_move]
        if best_score > MATE_SCORE - 1000:
            break
    return best_move


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    state: dict[str, Any],
) -> int:
    state['nodes'] += 1
    if state['nodes'] & 255 == 0 and time.perf_counter() >= state['deadline']:
        state['stop'] = True
        return _evaluate(board)

    if board.is_checkmate():
        return -MATE_SCORE + board.ply()
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, state)

    best = -INF
    for mv in _ordered_moves(board, list(board.legal_moves)):
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, state)
        board.pop()
        if state['stop']:
            return score
        best = max(best, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return best


def _quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    state: dict[str, Any],
) -> int:
    if board.is_checkmate():
        return -MATE_SCORE + board.ply()

    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    alpha = max(alpha, stand_pat)

    if state['nodes'] & 255 == 0 and time.perf_counter() >= state['deadline']:
        state['stop'] = True
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_check() or board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)

    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, state)
        board.pop()
        if state['stop']:
            return alpha
        if score >= beta:
            return beta
        alpha = max(alpha, score)
    return alpha


def _evaluate(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE + board.ply()
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        value = PIECE_VALUES[piece.piece_type]
        score += sign * value

        if square in CENTER:
            score += sign * 14
        elif square in NEAR_CENTER:
            score += sign * 6

        if piece.piece_type == chess.PAWN:
            rank = chess.square_rank(square)
            progress = rank if piece.color == chess.WHITE else 7 - rank
            if progress >= 4:
                score += sign * (progress - 3) * 10
        elif piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            file_index = chess.square_file(square)
            edge_distance = min(file_index, 7 - file_index)
            score += sign * edge_distance * 4

    white_bishops = len(board.pieces(chess.BISHOP, chess.WHITE))
    black_bishops = len(board.pieces(chess.BISHOP, chess.BLACK))
    if white_bishops >= 2:
        score += 35
    if black_bishops >= 2:
        score -= 35

    score += _pawn_structure_score(board, chess.WHITE)
    score -= _pawn_structure_score(board, chess.BLACK)

    for sq in CENTER:
        score += 5 * len(board.attackers(chess.WHITE, sq))
        score -= 5 * len(board.attackers(chess.BLACK, sq))
    for sq in NEAR_CENTER:
        score += 2 * len(board.attackers(chess.WHITE, sq))
        score -= 2 * len(board.attackers(chess.BLACK, sq))

    turn = board.turn
    own_mobility = board.legal_moves.count()
    board.turn = not turn
    try:
        opp_mobility = board.legal_moves.count()
    finally:
        board.turn = turn
    mobility = max(-40, min(40, 2 * (own_mobility - opp_mobility)))
    score += mobility if turn == chess.WHITE else -mobility

    if board.is_check():
        score += -30 if board.turn == chess.WHITE else 30

    return score if board.turn == chess.WHITE else -score


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns_by_file = [0] * 8
    for square in board.pieces(chess.PAWN, color):
        pawns_by_file[chess.square_file(square)] += 1

    score = 0
    for file_index, count in enumerate(pawns_by_file):
        if count > 1:
            score -= 14 * (count - 1)
        if count and _is_open_neighbor(pawns_by_file, file_index):
            score -= 8
    return score


def _is_open_neighbor(pawns_by_file: list[int], file_index: int) -> bool:
    left_empty = file_index == 0 or pawns_by_file[file_index - 1] == 0
    right_empty = file_index == 7 or pawns_by_file[file_index + 1] == 0
    return left_empty and right_empty


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_tiebreak(board, mv), reverse=True)


def _move_tiebreak(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    attacker = board.piece_at(mv.from_square)

    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        if victim is None and board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
        score += 10000 + 10 * victim_value - attacker_value

    if mv.promotion:
        score += 8000 + PIECE_VALUES.get(mv.promotion, 0)
    if board.gives_check(mv):
        score += 2600
    if mv.to_square in CENTER:
        score += 140
    elif mv.to_square in NEAR_CENTER:
        score += 55
    if attacker:
        score += PIECE_VALUES[attacker.piece_type] // 20
        if attacker.piece_type in (chess.KNIGHT, chess.BISHOP) and mv.to_square in CENTER:
            score += 35

    score += 63 - mv.from_square
    score += mv.to_square // 2
    return score


def _safe_fallback(
    board: chess.Board,
    legal_moves: list[chess.Move] | None = None,
) -> chess.Move:
    moves = legal_moves if legal_moves is not None else list(board.legal_moves)
    if not moves:
        return chess.Move.null()
    return _ordered_moves(board, moves)[0]
