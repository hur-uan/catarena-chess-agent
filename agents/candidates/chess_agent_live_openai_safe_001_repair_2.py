"""Safe self-contained CATArena chess agent.

Public interface:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation avoids network calls, subprocesses, eval/exec, file I/O,
and third-party dependencies other than python-chess.
"""

import json
import time

import chess

MATE_SCORE = 100000
INF = 100000000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

BOOK_BY_BOARD_FEN = {
    chess.STARTING_BOARD_FEN: "g1f3",
    "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R": "g8f6",
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR": "g8f6",
    "rnbqkb1r/pppppppp/5n2/8/4P3/8/PPPP1PPP/RNBQKBNR": "b1c3",
    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR": "g8f6",
}


class SearchState:
    """Small mutable search budget tracker."""

    def __init__(self, deadline, node_limit):
        self.deadline = deadline
        self.node_limit = node_limit
        self.nodes = 0
        self.stopped = False

    def tick(self):
        self.nodes += 1
        if self.nodes >= self.node_limit:
            self.stopped = True
            return False
        if self.nodes % 128 == 0 and time.monotonic() >= self.deadline:
            self.stopped = True
            return False
        return True


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format="uci", time_limit_ms=100):
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation):
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(observation, output_format="uci", time_limit_ms=100) -> str:
    """Choose a legal chess move for the supplied observation."""
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    legal_by_uci = {move.uci(): move for move in legal_moves}
    book_uci = BOOK_BY_BOARD_FEN.get(board.board_fen())
    if book_uci in legal_by_uci and board.fullmove_number <= 4:
        return _format_move(board, legal_by_uci[book_uci], output_format)

    ordered = _ordered_moves(board, legal_moves)
    for candidate in ordered:
        board.push(candidate)
        gives_mate = board.is_checkmate()
        board.pop()
        if gives_mate:
            return _format_move(board, candidate, output_format)

    fallback = _safe_fallback(board, legal_moves)
    best_move = fallback
    budget_ms = max(5, min(int(time_limit_ms or 100), 1000))
    deadline = time.monotonic() + max(0.003, budget_ms * 0.00082)
    state = SearchState(deadline, _node_limit_for_budget(budget_ms))
    max_depth = _depth_for_budget(board, budget_ms)

    try:
        for depth in range(1, max_depth + 1):
            if state.stopped or time.monotonic() >= deadline:
                break
            current_best = best_move
            current_score = -INF
            alpha = -INF
            beta = INF
            for root_move in ordered:
                if state.stopped or time.monotonic() >= deadline:
                    state.stopped = True
                    break
                board.push(root_move)
                score = -_negamax(board, depth - 1, -beta, -alpha, 1, state)
                board.pop()
                if state.stopped:
                    break
                if score > current_score:
                    current_score = score
                    current_best = root_move
                elif score == current_score and root_move.uci() < current_best.uci():
                    current_best = root_move
                if score > alpha:
                    alpha = score
            if not state.stopped and current_score > -INF:
                best_move = current_best
            if current_score >= MATE_SCORE - 100:
                break
    except Exception:
        best_move = fallback

    if best_move not in board.legal_moves:
        best_move = fallback
    return _format_move(board, best_move, output_format)


def agent(observation):
    return select_move(observation)


def act(observation):
    return select_move(observation)


def move(observation):
    return select_move(observation)


def _parse_observation(observation):
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    payload = observation
    if isinstance(observation, str):
        text = observation.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                payload = json.loads(text)
            except Exception:
                payload = observation
        else:
            return _board_from_fen(text)

    if isinstance(payload, dict):
        fen = _find_fen(payload)
        if fen:
            return _board_from_fen(fen)

    return chess.Board()


def _find_fen(payload):
    for key in ("fen", "FEN", "board", "state"):
        value = payload.get(key)
        if isinstance(value, str) and "/" in value:
            return value.strip()
    for key in ("observation", "game", "payload", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _find_fen(value)
            if nested:
                return nested
    return None


def _board_from_fen(fen):
    try:
        return chess.Board(fen)
    except Exception:
        return chess.Board()


def _format_move(board, chosen, output_format):
    if chosen not in board.legal_moves:
        legal = list(board.legal_moves)
        if not legal:
            return ""
        chosen = _safe_fallback(board, legal)

    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(chosen)
        except Exception:
            return chosen.uci()
    return chosen.uci()


def _safe_fallback(board, legal_moves):
    ordered = sorted(legal_moves, key=lambda item: item.uci())
    for candidate in ordered:
        board.push(candidate)
        wins_now = board.is_checkmate()
        board.pop()
        if wins_now:
            return candidate

    captures = [candidate for candidate in ordered if board.is_capture(candidate)]
    if captures:
        return max(captures, key=lambda item: _capture_value(board, item))

    checks = [candidate for candidate in ordered if board.gives_check(candidate)]
    if checks:
        return checks[0]
    return ordered[0]


def _node_limit_for_budget(budget_ms):
    if budget_ms < 20:
        return 800
    if budget_ms < 60:
        return 2200
    if budget_ms < 150:
        return 6500
    if budget_ms < 400:
        return 15000
    return 30000


def _depth_for_budget(board, budget_ms):
    legal_count = board.legal_moves.count()
    if budget_ms < 20:
        return 2
    if budget_ms < 70:
        return 3
    if budget_ms < 180:
        return 4 if legal_count <= 30 else 3
    if budget_ms < 500:
        return 4
    return 5 if legal_count <= 34 else 4


def _negamax(board, depth, alpha, beta, ply, state):
    if not state.tick():
        return _relative_eval(board)

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
        return 0

    if depth <= 0:
        return _quiescence(board, alpha, beta, ply, state)

    best = -INF
    moves = list(board.legal_moves)
    for candidate in _ordered_moves(board, moves):
        board.push(candidate)
        score = -_negamax(board, depth - 1, -beta, -alpha, ply + 1, state)
        board.pop()
        if state.stopped:
            return best if best > -INF else _relative_eval(board)
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def _quiescence(board, alpha, beta, ply, state):
    if not state.tick():
        return _relative_eval(board)
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _relative_eval(board)
    if not board.is_check():
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

    if board.is_check():
        tactical_moves = list(board.legal_moves)
    else:
        tactical_moves = []
        for candidate in board.legal_moves:
            if board.is_capture(candidate) or candidate.promotion is not None:
                tactical_moves.append(candidate)

    for candidate in _ordered_moves(board, tactical_moves):
        if not board.is_check() and board.is_capture(candidate):
            if stand_pat + _capture_value(board, candidate) + 120 < alpha:
                continue
        board.push(candidate)
        score = -_quiescence(board, -beta, -alpha, ply + 1, state)
        board.pop()
        if state.stopped:
            return alpha
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _relative_eval(board):
    score = _evaluate_white(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white(board):
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    phase_material = 0
    for piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
        phase_material += len(board.pieces(piece_type, chess.WHITE))
        phase_material += len(board.pieces(piece_type, chess.BLACK))
    endgame = phase_material <= 6

    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == chess.WHITE else -1
        score += sign * PIECE_VALUES[piece.piece_type]
        score += sign * _piece_square(piece.piece_type, square, piece.color, endgame)

    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += 25
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= 25

    score += _passed_pawn_bonus(board, chess.WHITE)
    score -= _passed_pawn_bonus(board, chess.BLACK)

    if _has_any_castling_right(board, chess.WHITE):
        score += 8
    if _has_any_castling_right(board, chess.BLACK):
        score -= 8

    if board.turn == chess.WHITE and board.is_check():
        score -= 20
    if board.turn == chess.BLACK and board.is_check():
        score += 20
    return score


def _has_any_castling_right(board, color):
    return board.has_kingside_castling_rights(color) or board.has_queenside_castling_rights(color)


def _piece_square(piece_type, square, color, endgame):
    sq = square if color == chess.WHITE else chess.square_mirror(square)
    file_index = chess.square_file(sq)
    rank_index = chess.square_rank(sq)
    center_file = min(file_index, 7 - file_index)
    center_rank = min(rank_index, 7 - rank_index)
    center = center_file + center_rank

    if piece_type == chess.PAWN:
        bonus = rank_index * 5
        if file_index in (3, 4):
            bonus += 6
        return bonus
    if piece_type == chess.KNIGHT:
        return center * 8 - 28
    if piece_type == chess.BISHOP:
        return center * 6 - 18
    if piece_type == chess.ROOK:
        return 10 if rank_index == 6 else 0
    if piece_type == chess.QUEEN:
        return center * 2 - 8
    if piece_type == chess.KING:
        if endgame:
            return center * 8 - 30
        if rank_index == 0 and file_index in (1, 2, 6):
            return 18
        return -center * 5
    return 0


def _passed_pawn_bonus(board, color):
    bonus = 0
    enemy_pawns = board.pieces(chess.PAWN, not color)
    for square in board.pieces(chess.PAWN, color):
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        blocked = False
        for enemy_square in enemy_pawns:
            enemy_file = chess.square_file(enemy_square)
            enemy_rank = chess.square_rank(enemy_square)
            if abs(enemy_file - file_index) > 1:
                continue
            if color == chess.WHITE and enemy_rank > rank_index:
                blocked = True
                break
            if color == chess.BLACK and enemy_rank < rank_index:
                blocked = True
                break
        if not blocked:
            advance = rank_index if color == chess.WHITE else 7 - rank_index
            bonus += 12 + advance * advance * 2
    return bonus


def _ordered_moves(board, moves):
    return sorted(moves, key=lambda candidate: _move_order_score(board, candidate), reverse=True)


def _move_order_score(board, candidate):
    score = 0
    if candidate.promotion is not None:
        score += 8000 + PIECE_VALUES.get(candidate.promotion, 0)
    if board.is_capture(candidate):
        score += 10000 + _capture_value(board, candidate)
    if board.gives_check(candidate):
        score += 2500
    if board.is_castling(candidate):
        score += 300

    moving_piece = board.piece_at(candidate.from_square)
    if moving_piece is not None:
        score += _move_piece_square_delta(board, candidate, moving_piece)

    score -= sum(ord(char) for char in candidate.uci()) % 17
    return score


def _move_piece_square_delta(board, candidate, moving_piece):
    phase_count = 0
    for piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
        phase_count += len(board.pieces(piece_type, chess.WHITE))
        phase_count += len(board.pieces(piece_type, chess.BLACK))
    endgame = phase_count <= 6
    to_value = _piece_square(
        moving_piece.piece_type,
        candidate.to_square,
        moving_piece.color,
        endgame,
    )
    from_value = _piece_square(
        moving_piece.piece_type,
        candidate.from_square,
        moving_piece.color,
        endgame,
    )
    return to_value - from_value


def _capture_value(board, candidate):
    victim = board.piece_at(candidate.to_square)
    if victim is None and board.is_en_passant(candidate):
        victim_value = PIECE_VALUES[chess.PAWN]
    else:
        victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
    attacker = board.piece_at(candidate.from_square)
    attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
    return victim_value * 10 - attacker_value
