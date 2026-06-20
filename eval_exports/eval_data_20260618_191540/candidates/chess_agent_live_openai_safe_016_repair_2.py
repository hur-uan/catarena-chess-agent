"""Safe bounded chess agent for CATArena.

The module exposes select_move(observation, output_format="uci",
time_limit_ms=100) and aliases agent, act, and move. It uses only
python-chess plus the standard library, performs no file or network access,
and validates every selected move against board.legal_moves.
"""

import time
from typing import Any, Optional

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

CENTER_FILES = (3, 4)
PROMOTION_VALUES = {
    chess.QUEEN: 900,
    chess.ROOK: 500,
    chess.BISHOP: 330,
    chess.KNIGHT: 320,
}


class SearchStopped(Exception):
    """Internal signal for time/node budget exhaustion."""


class SearchLimits:
    """Small non-dataclass budget tracker.

    A plain class avoids import-time dataclass annotation resolution issues in
    validators that load modules without inserting them into sys.modules.
    """

    def __init__(self, deadline: float, node_limit: int) -> None:
        self.deadline = deadline
        self.node_limit = node_limit
        self.nodes = 0

    def check(self) -> None:
        self.nodes += 1
        if self.nodes >= self.node_limit or time.perf_counter() >= self.deadline:
            raise SearchStopped


class ChessAgent:
    """Small wrapper compatible with common arena integrations."""

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
    """Return a legal move string for the supplied observation."""
    board = parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    ordered = ordered_moves(board, legal_moves)

    # Always take an immediate checkmate before spending search time.
    for candidate in ordered:
        board.push(candidate)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return format_move(board, candidate, output_format)

    fallback = ordered[0]
    chosen = fallback
    try:
        chosen = search_best_move(board, time_limit_ms, fallback)
    except Exception:
        chosen = fallback

    # Final legality guard: never return an illegal move if legal moves exist.
    if chosen not in board.legal_moves:
        chosen = fallback
    if chosen not in board.legal_moves:
        fresh_legal = list(board.legal_moves)
        if not fresh_legal:
            return ""
        chosen = fresh_legal[0]
    return format_move(board, chosen, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def parse_observation(observation: Any) -> chess.Board:
    """Parse common CATArena payloads without side effects."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen: Optional[str] = None
    moves: Optional[Any] = None
    current_player: Optional[Any] = None

    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        for key in ("moves", "move_history", "history"):
            value = observation.get(key)
            if isinstance(value, (list, tuple)):
                moves = value
                break
        current_player = observation.get("current_player")
    elif isinstance(observation, str):
        text = observation.strip()
        if text:
            fen = text

    board = safe_board_from_fen(fen, current_player)
    if moves:
        apply_move_history(board, moves)
    return board


def safe_board_from_fen(fen: Optional[str], current_player: Optional[Any]) -> chess.Board:
    if not fen:
        board = chess.Board()
        apply_current_player(board, current_player)
        return board

    text = fen.strip()
    try:
        board = chess.Board(text)
        apply_current_player(board, current_player)
        return board
    except Exception:
        pass

    parts = text.split()
    if len(parts) == 1 and "/" in parts[0]:
        try:
            board = chess.Board(parts[0] + " w - - 0 1")
            apply_current_player(board, current_player)
            return board
        except Exception:
            return chess.Board()
    return chess.Board()


def apply_current_player(board: chess.Board, current_player: Optional[Any]) -> None:
    if current_player is None:
        return
    text = str(current_player).strip().lower()
    if text in ("white", "w", "true", "1"):
        board.turn = chess.WHITE
    elif text in ("black", "b", "false", "0"):
        board.turn = chess.BLACK


def apply_move_history(board: chess.Board, moves: Any) -> None:
    for item in moves:
        if not isinstance(item, str):
            continue
        token = item.strip()
        if not token:
            continue
        try:
            candidate = chess.Move.from_uci(token)
            if candidate in board.legal_moves:
                board.push(candidate)
                continue
        except Exception:
            pass
        try:
            candidate = board.parse_san(token)
            if candidate in board.legal_moves:
                board.push(candidate)
        except Exception:
            continue


def format_move(board: chess.Board, move_obj: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").strip().lower()
    if fmt == "san":
        try:
            return board.san(move_obj)
        except Exception:
            return move_obj.uci()
    return move_obj.uci()


def search_best_move(
    board: chess.Board,
    time_limit_ms: int,
    fallback: chess.Move,
) -> chess.Move:
    ms = max(5, int(time_limit_ms or 100))
    usable_ms = min(ms * 0.78, max(3.0, ms - 5.0))
    deadline = time.perf_counter() + usable_ms / 1000.0
    legal_count = board.legal_moves.count()

    if ms <= 35:
        max_depth = 2
        node_limit = 1000
    elif ms <= 120:
        max_depth = 3 if legal_count > 12 else 4
        node_limit = 5500
    elif ms <= 250:
        max_depth = 4
        node_limit = 12000
    else:
        max_depth = 4 if legal_count > 8 else 5
        node_limit = 22000

    limits = SearchLimits(deadline=deadline, node_limit=node_limit)
    moves = ordered_moves(board, list(board.legal_moves))
    best = fallback

    for depth in range(1, max_depth + 1):
        current_best = best
        current_score = -INF
        alpha = -INF
        beta = INF
        try:
            for candidate in moves:
                limits.check()
                board.push(candidate)
                score = -negamax(board, depth - 1, -beta, -alpha, 1, limits)
                board.pop()
                if score > current_score:
                    current_score = score
                    current_best = candidate
                if score > alpha:
                    alpha = score
            best = current_best
            moves = [best] + [item for item in moves if item != best]
            if current_score >= MATE_SCORE - 1000:
                break
        except SearchStopped:
            break
    return best


def negamax(
    board: chess.Board,
    depth: int,
    alpha: int,
    beta: int,
    ply: int,
    limits: SearchLimits,
) -> int:
    limits.check()

    if board.is_checkmate():
        return -MATE_SCORE + ply
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    if board.can_claim_fifty_moves():
        return 0
    if depth <= 0:
        return quiescence(board, alpha, beta, ply, limits, 0)

    best = -INF
    for candidate in ordered_moves(board, list(board.legal_moves)):
        board.push(candidate)
        score = -negamax(board, depth - 1, -beta, -alpha, ply + 1, limits)
        board.pop()
        if score > best:
            best = score
        if score > alpha:
            alpha = score
        if alpha >= beta:
            break
    return best


def quiescence(
    board: chess.Board,
    alpha: int,
    beta: int,
    ply: int,
    limits: SearchLimits,
    q_depth: int,
) -> int:
    limits.check()
    if board.is_checkmate():
        return -MATE_SCORE + ply

    stand_pat = evaluate_side_to_move(board)
    if stand_pat >= beta:
        return beta
    if stand_pat > alpha:
        alpha = stand_pat
    if q_depth >= 4:
        return alpha

    tactical = []
    for candidate in board.legal_moves:
        if board.is_capture(candidate) or candidate.promotion:
            tactical.append(candidate)
        elif q_depth <= 1 and board.gives_check(candidate):
            tactical.append(candidate)

    for candidate in ordered_moves(board, tactical):
        board.push(candidate)
        score = -quiescence(board, -beta, -alpha, ply + 1, limits, q_depth + 1)
        board.pop()
        if score >= beta:
            return beta
        if score > alpha:
            alpha = score
    return alpha


def ordered_moves(board: chess.Board, moves: list) -> list:
    return sorted(moves, key=lambda item: move_order_score(board, item), reverse=True)


def move_order_score(board: chess.Board, move_obj: chess.Move) -> int:
    score = 0
    if move_obj.promotion:
        score += 8000 + PROMOTION_VALUES.get(move_obj.promotion, 0)

    if board.is_capture(move_obj):
        victim_value = PIECE_VALUES[chess.PAWN]
        if not board.is_en_passant(move_obj):
            victim = board.piece_at(move_obj.to_square)
            if victim is not None:
                victim_value = PIECE_VALUES.get(victim.piece_type, 0)
        attacker = board.piece_at(move_obj.from_square)
        attacker_value = 1
        if attacker is not None:
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 1)
        score += 10000 + 10 * victim_value - attacker_value

    if board.gives_check(move_obj):
        score += 1200

    moving_piece = board.piece_at(move_obj.from_square)
    if moving_piece is not None:
        if moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            if is_home_back_rank(move_obj.from_square, moving_piece.color):
                score += 25
        if moving_piece.piece_type == chess.KING and board.is_castling(move_obj):
            score += 350

    file_index = chess.square_file(move_obj.to_square)
    rank_index = chess.square_rank(move_obj.to_square)
    score += 14 - abs(2 * file_index - 7) - abs(2 * rank_index - 7)
    return score


def is_home_back_rank(square: chess.Square, color: chess.Color) -> bool:
    rank_index = chess.square_rank(square)
    return rank_index == (0 if color == chess.WHITE else 7)


def evaluate_side_to_move(board: chess.Board) -> int:
    score = evaluate_white_pov(board)
    return score if board.turn == chess.WHITE else -score


def evaluate_white_pov(board: chess.Board) -> int:
    score = 0
    white_non_pawn = 0
    black_non_pawn = 0

    for square, piece in board.piece_map().items():
        base_value = PIECE_VALUES.get(piece.piece_type, 0)
        positional = positional_bonus(square, piece, board)
        signed_value = base_value + positional
        if piece.color == chess.WHITE:
            score += signed_value
            if piece.piece_type not in (chess.PAWN, chess.KING):
                white_non_pawn += base_value
        else:
            score -= signed_value
            if piece.piece_type not in (chess.PAWN, chess.KING):
                black_non_pawn += base_value

    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += 35
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= 35

    score += pawn_structure_score(board, chess.WHITE)
    score -= pawn_structure_score(board, chess.BLACK)
    score += king_safety_score(board, chess.WHITE, white_non_pawn + black_non_pawn)
    score -= king_safety_score(board, chess.BLACK, white_non_pawn + black_non_pawn)
    score += mobility_score(board)

    if board.is_check():
        score += -30 if board.turn == chess.WHITE else 30
    return int(score)


def positional_bonus(square: chess.Square, piece: chess.Piece, board: chess.Board) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    rank_from_home = rank_index if piece.color == chess.WHITE else 7 - rank_index
    center_distance = min(abs(file_index - 3), abs(file_index - 4))
    center_distance += min(abs(rank_index - 3), abs(rank_index - 4))

    if piece.piece_type == chess.PAWN:
        bonus = rank_from_home * 8 - center_distance * 3
        if file_index in CENTER_FILES:
            bonus += 8
        return bonus
    if piece.piece_type == chess.KNIGHT:
        return 32 - center_distance * 12
    if piece.piece_type == chess.BISHOP:
        return 22 - center_distance * 6
    if piece.piece_type == chess.ROOK:
        bonus = 4 * rank_from_home
        if is_open_or_half_open_file(board, file_index, piece.color):
            bonus += 14
        return bonus
    if piece.piece_type == chess.QUEEN:
        return 10 - center_distance * 3
    if piece.piece_type == chess.KING:
        material = total_non_pawn_material(board)
        if material < 1800:
            return 24 - center_distance * 8
        return -center_distance * 4
    return 0


def total_non_pawn_material(board: chess.Board) -> int:
    total = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        total += len(board.pieces(piece_type, chess.WHITE)) * PIECE_VALUES[piece_type]
        total += len(board.pieces(piece_type, chess.BLACK)) * PIECE_VALUES[piece_type]
    return total


def is_open_or_half_open_file(
    board: chess.Board,
    file_index: int,
    color: chess.Color,
) -> bool:
    for rank_index in range(8):
        piece = board.piece_at(chess.square(file_index, rank_index))
        if piece is not None and piece.piece_type == chess.PAWN and piece.color == color:
            return False
    return True


def pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    score = 0
    pawn_files = []
    for square in board.pieces(chess.PAWN, color):
        pawn_files.append(chess.square_file(square))
    for file_index in range(8):
        count = pawn_files.count(file_index)
        if count > 1:
            score -= 12 * (count - 1)
    for file_index in pawn_files:
        has_neighbor = (file_index - 1 in pawn_files) or (file_index + 1 in pawn_files)
        if not has_neighbor:
            score -= 10
    return score


def king_safety_score(board: chess.Board, color: chess.Color, material: int) -> int:
    king_square = board.king(color)
    if king_square is None:
        return 0
    if material < 1800:
        return 0

    score = 0
    file_index = chess.square_file(king_square)
    rank_index = chess.square_rank(king_square)
    forward = 1 if color == chess.WHITE else -1
    shield_rank = rank_index + forward
    if 0 <= shield_rank <= 7:
        for delta_file in (-1, 0, 1):
            check_file = file_index + delta_file
            if 0 <= check_file <= 7:
                piece = board.piece_at(chess.square(check_file, shield_rank))
                if piece is not None and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 12
    edge_file_bonus = 10 if file_index in (0, 1, 6, 7) else -8
    return score + edge_file_bonus


def mobility_score(board: chess.Board) -> int:
    original_turn = board.turn
    try:
        board.turn = chess.WHITE
        white_moves = board.legal_moves.count()
        board.turn = chess.BLACK
        black_moves = board.legal_moves.count()
    except Exception:
        white_moves = 0
        black_moves = 0
    finally:
        board.turn = original_turn
    return 2 * (white_moves - black_moves)
