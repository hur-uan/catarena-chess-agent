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


class SearchTimeout(Exception):
    pass


class ChessAgent:
    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: object) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


def select_move(
    observation: object,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> str:
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    selected = _choose_move(board, legal_moves, time_limit_ms)
    if selected not in legal_moves:
        selected = _safe_fallback_move(board, legal_moves)

    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(selected)
        except Exception:
            return selected.uci()
    return selected.uci()


def agent(observation: object) -> str:
    return select_move(observation)


def act(observation: object) -> str:
    return select_move(observation)


def move(observation: object) -> str:
    return select_move(observation)


def _parse_observation(observation: object) -> chess.Board:
    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        nested = observation.get("observation")
        if fen is None and isinstance(nested, dict):
            value = nested.get("fen")
            if isinstance(value, str) and value.strip():
                fen = value.strip()
    elif isinstance(observation, str) and observation.strip():
        fen = observation.strip()

    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def _choose_move(
    board: chess.Board,
    legal_moves: list[chess.Move],
    time_limit_ms: int,
) -> chess.Move:
    mate = _find_immediate_mate(board, legal_moves)
    if mate is not None:
        return mate

    safe_ms = max(1, int(time_limit_ms))
    if safe_ms < 25:
        return _safe_fallback_move(board, legal_moves)

    budget_ms = max(1, min(safe_ms - 2, int(safe_ms * 0.82)))
    deadline = time.perf_counter() + budget_ms / 1000.0

    if len(legal_moves) <= 8 and safe_ms >= 120:
        max_depth = 4
    elif safe_ms >= 70:
        max_depth = 3
    else:
        max_depth = 2

    best_move = _safe_fallback_move(board, legal_moves)
    ordered = _ordered_moves(board, legal_moves)
    nodes = [0]

    try:
        for depth in range(1, max_depth + 1):
            alpha = -INF
            current_best = best_move
            current_score = -INF
            for mv in ordered:
                _check_time(deadline, nodes)
                board.push(mv)
                score = -_negamax(board, depth - 1, -INF, -alpha, deadline, nodes, 1)
                board.pop()
                if score > current_score:
                    current_score = score
                    current_best = mv
                if score > alpha:
                    alpha = score
            best_move = current_best
            if current_score >= MATE_SCORE - 100:
                break
    except SearchTimeout:
        pass
    except Exception:
        return _safe_fallback_move(board, legal_moves)

    if best_move in legal_moves:
        return best_move
    return _safe_fallback_move(board, legal_moves)


def _negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    deadline: float,
    nodes: list[int],
    ply: int,
) -> int:
    _check_time(deadline, nodes)
    nodes[0] += 1

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if depth <= 0:
        return _quiescence(board, alpha, beta, deadline, nodes, ply, 2)

    best = -INF
    moves = _ordered_moves(board, list(board.legal_moves))
    for mv in moves:
        board.push(mv)
        score = -_negamax(board, depth - 1, -beta, -alpha, deadline, nodes, ply + 1)
        board.pop()
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
    deadline: float,
    nodes: list[int],
    ply: int,
    qdepth: int,
) -> int:
    _check_time(deadline, nodes)
    nodes[0] += 1

    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = _evaluate_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if qdepth <= 0:
        return alpha

    tactical = []
    for mv in board.legal_moves:
        if board.is_capture(mv) or mv.promotion or board.gives_check(mv):
            tactical.append(mv)

    for mv in _ordered_moves(board, tactical):
        board.push(mv)
        score = -_quiescence(board, -beta, -alpha, deadline, nodes, ply + 1, qdepth - 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


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


def _ordered_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    return sorted(moves, key=lambda mv: _move_order_score(board, mv), reverse=True)


def _move_order_score(board: chess.Board, mv: chess.Move) -> int:
    score = 0
    moving_piece = board.piece_at(mv.from_square)
    target_piece = board.piece_at(mv.to_square)

    if mv.promotion:
        score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
    if target_piece is not None:
        attacker = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        victim = PIECE_VALUES.get(target_piece.piece_type, 0)
        score += 10000 + 10 * victim - attacker
    elif board.is_en_passant(mv):
        score += 11000

    try:
        if board.gives_check(mv):
            score += 750
    except Exception:
        pass

    if board.is_castling(mv):
        score += 360
    if mv.to_square in CENTER_SQUARES:
        score += 100
    elif mv.to_square in EXTENDED_CENTER:
        score += 40

    if moving_piece is not None:
        if moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            home_rank = 0 if moving_piece.color == chess.WHITE else 7
            if chess.square_rank(mv.from_square) == home_rank:
                score += 125
        if moving_piece.piece_type == chess.PAWN and mv.to_square in CENTER_SQUARES:
            score += 65
    return score


def _evaluate_side_to_move(board: chess.Board) -> int:
    score = _evaluate_white_perspective(board)
    return score if board.turn == chess.WHITE else -score


def _evaluate_white_perspective(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    white_non_king = 0
    black_non_king = 0

    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        activity = _piece_activity(board, square, piece)
        piece_score = value + activity
        if piece.color == chess.WHITE:
            score += piece_score
            if piece.piece_type != chess.KING:
                white_non_king += 1
        else:
            score -= piece_score
            if piece.piece_type != chess.KING:
                black_non_king += 1

    score += _bishop_pair_bonus(board, chess.WHITE)
    score -= _bishop_pair_bonus(board, chess.BLACK)
    score += _king_safety(board, chess.WHITE)
    score -= _king_safety(board, chess.BLACK)
    score += _pawn_structure(board, chess.WHITE)
    score -= _pawn_structure(board, chess.BLACK)
    score += 3 * (white_non_king - black_non_king)
    return score


def _piece_activity(board: chess.Board, square: chess.Square, piece: chess.Piece) -> int:
    bonus = 0
    if square in CENTER_SQUARES:
        bonus += 22
    elif square in EXTENDED_CENTER:
        bonus += 9

    if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
        rank = chess.square_rank(square)
        advance = rank if piece.color == chess.WHITE else 7 - rank
        bonus += 6 + 2 * advance
    elif piece.piece_type == chess.ROOK:
        file_index = chess.square_file(square)
        friendly = board.pieces(chess.PAWN, piece.color)
        enemy = board.pieces(chess.PAWN, not piece.color)
        friendly_on_file = any(chess.square_file(sq) == file_index for sq in friendly)
        enemy_on_file = any(chess.square_file(sq) == file_index for sq in enemy)
        if not friendly_on_file and not enemy_on_file:
            bonus += 18
        elif not friendly_on_file:
            bonus += 9
    elif piece.piece_type == chess.QUEEN and board.fullmove_number < 10:
        home_rank = 0 if piece.color == chess.WHITE else 7
        if chess.square_rank(square) != home_rank:
            bonus -= 18
    return bonus


def _bishop_pair_bonus(board: chess.Board, color: chess.Color) -> int:
    return 35 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0


def _king_safety(board: chess.Board, color: chess.Color) -> int:
    king_sq = board.king(color)
    if king_sq is None:
        return -500

    enemy = not color
    penalty = 0
    for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king_sq]):
        if board.is_attacked_by(enemy, sq):
            penalty += 8
    if board.is_attacked_by(enemy, king_sq):
        penalty += 50

    bonus = 0
    rank_dir = 1 if color == chess.WHITE else -1
    king_file = chess.square_file(king_sq)
    shield_rank = chess.square_rank(king_sq) + rank_dir
    if 0 <= shield_rank <= 7:
        for delta in (-1, 0, 1):
            file_index = king_file + delta
            if 0 <= file_index <= 7:
                sq = chess.square(file_index, shield_rank)
                piece = board.piece_at(sq)
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    bonus += 10
    return bonus - penalty


def _pawn_structure(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0

    files = [chess.square_file(sq) for sq in pawns]
    occupied_files = set(files)
    score = 0

    for file_index in range(8):
        count = files.count(file_index)
        if count > 1:
            score -= 12 * (count - 1)

    for sq in pawns:
        file_index = chess.square_file(sq)
        if file_index - 1 not in occupied_files and file_index + 1 not in occupied_files:
            score -= 10
        rank = chess.square_rank(sq)
        progress = rank if color == chess.WHITE else 7 - rank
        score += 3 * progress
    return score


def _safe_fallback_move(
    board: chess.Board,
    legal_moves: list[chess.Move] | None = None,
) -> chess.Move:
    moves = legal_moves if legal_moves is not None else list(board.legal_moves)
    if not moves:
        return chess.Move.null()
    return max(moves, key=lambda mv: _move_order_score(board, mv))


def _check_time(deadline: float, nodes: list[int]) -> None:
    if (nodes[0] & 0x3F) == 0 and time.perf_counter() >= deadline:
        raise SearchTimeout
