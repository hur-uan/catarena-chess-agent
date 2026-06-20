"""Safe self-contained CATArena chess agent.

Public interface:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation avoids network calls, subprocesses, dynamic imports, file I/O,
eval/exec, and non-standard dependencies beyond python-chess.
"""

import time

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

PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_TABLE = [
    0, 0, 0, 5, 5, 0, 0, 0,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    5, 10, 10, 10, 10, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -10, 5, 5, 5, 5, 5, 0, -10,
    0, 0, 5, 5, 5, 5, 0, -5,
    -5, 0, 5, 5, 5, 5, 0, -5,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_TABLE = [
    20, 30, 10, 0, 0, 10, 30, 20,
    20, 20, 0, 0, 0, 0, 20, 20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
]
PST = {
    chess.PAWN: PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE,
    chess.QUEEN: QUEEN_TABLE,
    chess.KING: KING_TABLE,
}

OPENING_BOOK = {
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -": "g1f3",
    "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq -": "g8f6",
    "rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq -": "d2d4",
    "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -": "c7c5",
    "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq -": "g8f6",
}


class ChessAgent:
    """Small wrapper compatible with common arena integrations."""

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

    chosen = None
    try:
        chosen = _book_move(board)
        if chosen is None:
            chosen = _find_mate_in_one(board)
        if chosen is None:
            chosen = _search_move(board, time_limit_ms)
    except Exception:
        chosen = None

    if chosen not in legal_moves:
        chosen = _fallback_move(board)
    if chosen not in legal_moves:
        chosen = legal_moves[0]
    return _format_move(board, chosen, output_format)


def agent(observation):
    return select_move(observation)


def act(observation):
    return select_move(observation)


def move(observation):
    return select_move(observation)


def _parse_observation(observation):
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
        except ValueError:
            pass
    return chess.Board()


def _format_move(board, move_obj, output_format):
    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def _book_key(board):
    parts = board.fen().split()
    if len(parts) >= 4:
        return " ".join(parts[:4])
    return board.fen()


def _book_move(board):
    uci = OPENING_BOOK.get(_book_key(board))
    if not uci:
        return None
    try:
        candidate = chess.Move.from_uci(uci)
    except ValueError:
        return None
    if candidate in board.legal_moves:
        return candidate
    return None


def _find_mate_in_one(board):
    for move_obj in _ordered_moves(board, None):
        board.push(move_obj)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move_obj
    return None


def _search_move(board, time_limit_ms):
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    safe_ms = max(8, min(int(time_limit_ms or 100), 250))
    deadline = time.perf_counter() + (safe_ms * 0.82 / 1000.0)
    node_limit = max(1000, min(18000, safe_ms * 90))
    state = {
        "nodes": 0,
        "deadline": deadline,
        "node_limit": node_limit,
        "stop": False,
    }
    tt = {}

    best_move = _fallback_move(board)
    max_depth = 4 if safe_ms >= 70 else 3
    if board.fullmove_number <= 8 and safe_ms >= 90:
        max_depth = 5

    for depth in range(1, max_depth + 1):
        if _time_up(state):
            break
        current_best = None
        current_score = -INF
        alpha = -INF
        beta = INF
        for move_obj in _ordered_moves(board, best_move):
            if _time_up(state):
                break
            board.push(move_obj)
            score = -_negamax(board, depth - 1, -beta, -alpha, 1, state, tt)
            board.pop()
            if state["stop"]:
                break
            if score > current_score:
                current_score = score
                current_best = move_obj
            if score > alpha:
                alpha = score
        if not state["stop"] and current_best is not None:
            best_move = current_best
            if current_score >= MATE_SCORE - 100:
                break
        if state["stop"]:
            break
    return best_move


def _position_key(board, depth):
    parts = board.fen().split()
    if len(parts) >= 4:
        return (parts[0], parts[1], parts[2], parts[3], depth)
    turn = "w" if board.turn else "b"
    return (board.board_fen(), turn, depth)


def _negamax(board, depth, alpha, beta, ply, state, tt):
    if _time_up(state):
        state["stop"] = True
        return 0

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    key = _position_key(board, depth)
    cached = tt.get(key)
    if cached is not None:
        return cached

    if depth <= 0:
        return _quiescence(board, alpha, beta, ply, state)

    best = -INF
    for move_obj in _ordered_moves(board, None):
        board.push(move_obj)
        score = -_negamax(board, depth - 1, -beta, -alpha, ply + 1, state, tt)
        board.pop()
        if state["stop"]:
            return 0
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    tt[key] = best
    return best


def _quiescence(board, alpha, beta, ply, state):
    if _time_up(state):
        state["stop"] = True
        return 0
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat

    tactical_moves = []
    if board.is_check():
        tactical_moves = list(board.legal_moves)
    else:
        for move_obj in board.legal_moves:
            if board.is_capture(move_obj) or move_obj.promotion:
                tactical_moves.append(move_obj)
    tactical_moves.sort(
        key=lambda mv: _move_order_score(board, mv, None),
        reverse=True,
    )

    for move_obj in tactical_moves[:24]:
        board.push(move_obj)
        score = -_quiescence(board, -beta, -alpha, ply + 1, state)
        board.pop()
        if state["stop"]:
            return 0
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def _evaluate(board):
    score = 0
    white_bishops = 0
    black_bishops = 0

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        table = PST[piece.piece_type]
        if piece.color == chess.WHITE:
            pst_square = square
        else:
            pst_square = chess.square_mirror(square)
        piece_score = value + table[pst_square]

        if piece.color == chess.WHITE:
            score += piece_score
            if piece.piece_type == chess.BISHOP:
                white_bishops += 1
        else:
            score -= piece_score
            if piece.piece_type == chess.BISHOP:
                black_bishops += 1

    if white_bishops >= 2:
        score += 30
    if black_bishops >= 2:
        score -= 30

    mobility = len(list(board.legal_moves))
    if board.turn == chess.WHITE:
        score += 2 * mobility
    else:
        score -= 2 * mobility

    if board.has_kingside_castling_rights(chess.WHITE):
        score += 8
    if board.has_queenside_castling_rights(chess.WHITE):
        score += 5
    if board.has_kingside_castling_rights(chess.BLACK):
        score -= 8
    if board.has_queenside_castling_rights(chess.BLACK):
        score -= 5

    if board.turn == chess.WHITE:
        return score
    return -score


def _ordered_moves(board, preferred):
    moves = list(board.legal_moves)
    moves.sort(
        key=lambda mv: _move_order_score(board, mv, preferred),
        reverse=True,
    )
    return moves


def _move_order_score(board, move_obj, preferred):
    if preferred is not None and move_obj == preferred:
        return 1_000_000

    score = 0
    if move_obj.promotion:
        score += 80_000 + PIECE_VALUES.get(move_obj.promotion, 0)

    if board.is_capture(move_obj):
        victim = board.piece_at(move_obj.to_square)
        if victim is None and board.is_en_passant(move_obj):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker = board.piece_at(move_obj.from_square)
        attacker_value = PIECE_VALUES.get(attacker.piece_type, 1) if attacker else 1
        score += 60_000 + 10 * victim_value - attacker_value

    if board.gives_check(move_obj):
        score += 20_000

    piece = board.piece_at(move_obj.from_square)
    if piece:
        if piece.color == chess.WHITE:
            to_sq = move_obj.to_square
            from_sq = move_obj.from_square
        else:
            to_sq = chess.square_mirror(move_obj.to_square)
            from_sq = chess.square_mirror(move_obj.from_square)
        score += PST[piece.piece_type][to_sq] - PST[piece.piece_type][from_sq]

        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            if board.fullmove_number <= 10:
                white_development = (chess.C3, chess.D2, chess.E2, chess.F3)
                black_development = (chess.C6, chess.D7, chess.E7, chess.F6)
                if piece.color == chess.WHITE and move_obj.to_square in white_development:
                    score += 12
                if piece.color == chess.BLACK and move_obj.to_square in black_development:
                    score += 12

    return score


def _fallback_move(board):
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return chess.Move.null()
    return max(legal_moves, key=lambda mv: _move_order_score(board, mv, None))


def _time_up(state):
    state["nodes"] += 1
    if state["nodes"] >= state["node_limit"]:
        return True
    if state["nodes"] % 128 == 0:
        return time.perf_counter() >= state["deadline"]
    return False
