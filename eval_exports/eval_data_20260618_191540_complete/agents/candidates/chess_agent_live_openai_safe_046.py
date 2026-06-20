"""Self-contained safe CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The implementation intentionally avoids network access, subprocesses, file I/O,
eval/exec, and dynamic imports.  Every returned move is validated against
python-chess legal moves, with a deterministic legal fallback.
"""

from __future__ import annotations

import time
from typing import Any

import chess


MATE_SCORE = 100_000
INF = 1_000_000

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Small piece-square tables from White's point of view.  Values are deliberately
# modest so tactics/material dominate.
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    8, 10, 10, -12, -12, 10, 10, 8,
    4, 6, 8, 14, 14, 8, 6, 4,
    2, 4, 7, 18, 18, 7, 4, 2,
    2, 4, 8, 20, 20, 8, 4, 2,
    5, 8, 10, 12, 12, 10, 8, 5,
    20, 22, 22, 24, 24, 22, 22, 20,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_PST = [
    -45, -25, -18, -14, -14, -18, -25, -45,
    -25, -10, 2, 5, 5, 2, -10, -25,
    -18, 4, 12, 18, 18, 12, 4, -18,
    -12, 8, 20, 26, 26, 20, 8, -12,
    -12, 8, 20, 26, 26, 20, 8, -12,
    -18, 4, 12, 18, 18, 12, 4, -18,
    -25, -10, 2, 5, 5, 2, -10, -25,
    -45, -25, -18, -14, -14, -18, -25, -45,
]
BISHOP_PST = [
    -18, -8, -8, -6, -6, -8, -8, -18,
    -8, 8, 4, 6, 6, 4, 8, -8,
    -6, 8, 10, 14, 14, 10, 8, -6,
    -4, 6, 14, 18, 18, 14, 6, -4,
    -4, 6, 14, 18, 18, 14, 6, -4,
    -6, 8, 10, 14, 14, 10, 8, -6,
    -8, 8, 4, 6, 6, 4, 8, -8,
    -18, -8, -8, -6, -6, -8, -8, -18,
]
ROOK_PST = [
    0, 0, 2, 6, 6, 2, 0, 0,
    -2, 0, 2, 6, 6, 2, 0, -2,
    -4, 0, 2, 6, 6, 2, 0, -4,
    -4, 0, 2, 6, 6, 2, 0, -4,
    -4, 0, 2, 6, 6, 2, 0, -4,
    -4, 0, 2, 6, 6, 2, 0, -4,
    8, 10, 10, 12, 12, 10, 10, 8,
    0, 0, 2, 6, 6, 2, 0, 0,
]
QUEEN_PST = [
    -10, -6, -4, -2, -2, -4, -6, -10,
    -6, 0, 2, 2, 2, 2, 0, -6,
    -4, 2, 5, 6, 6, 5, 2, -4,
    -2, 2, 6, 8, 8, 6, 2, -2,
    -2, 2, 6, 8, 8, 6, 2, -2,
    -4, 2, 5, 6, 6, 5, 2, -4,
    -6, 0, 2, 2, 2, 2, 0, -6,
    -10, -6, -4, -2, -2, -4, -6, -10,
]
KING_MID_PST = [
    18, 24, 8, 0, 0, 8, 24, 18,
    12, 10, 0, -8, -8, 0, 10, 12,
    -10, -16, -18, -24, -24, -18, -16, -10,
    -25, -30, -35, -40, -40, -35, -30, -25,
    -30, -35, -40, -45, -45, -40, -35, -30,
    -35, -40, -45, -50, -50, -45, -40, -35,
    -35, -40, -45, -50, -50, -45, -40, -35,
    -35, -40, -45, -50, -50, -45, -40, -35,
]

PST = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
    chess.KING: KING_MID_PST,
}

CENTER = {chess.D4, chess.E4, chess.D5, chess.E5}
EXTENDED_CENTER = {
    chess.C3, chess.D3, chess.E3, chess.F3,
    chess.C4, chess.D4, chess.E4, chess.F4,
    chess.C5, chess.D5, chess.E5, chess.F5,
    chess.C6, chess.D6, chess.E6, chess.F6,
}


class SearchTimeout(Exception):
    """Raised internally when the bounded search reaches its deadline."""


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


class _Searcher:
    def __init__(self, deadline: float, allowed_root: set[chess.Move] | None) -> None:
        self.deadline = deadline
        self.allowed_root = allowed_root
        self.nodes = 0

    def check_time(self) -> None:
        self.nodes += 1
        if self.nodes % 128 == 0 and time.perf_counter() >= self.deadline:
            raise SearchTimeout

    def choose(self, board: chess.Board, max_depth: int) -> chess.Move:
        legal = list(board.legal_moves)
        if self.allowed_root:
            filtered = [mv for mv in legal if mv in self.allowed_root]
            if filtered:
                legal = filtered
        if not legal:
            raise SearchTimeout

        ordered = self.order_moves(board, legal, root=True)
        best_move = ordered[0]

        # Tactical fast path: never miss a mate in one.
        for mv in ordered:
            board.push(mv)
            is_mate = board.is_checkmate()
            board.pop()
            if is_mate:
                return mv

        for depth in range(1, max_depth + 1):
            if time.perf_counter() >= self.deadline:
                break
            alpha = -INF
            beta = INF
            current_best = best_move
            current_score = -INF
            try:
                for mv in ordered:
                    self.check_time()
                    board.push(mv)
                    score = -self.negamax(board, depth - 1, -beta, -alpha, 1)
                    board.pop()
                    if score > current_score:
                        current_score = score
                        current_best = mv
                    if score > alpha:
                        alpha = score
                best_move = current_best
                ordered = [best_move] + [mv for mv in ordered if mv != best_move]
            except SearchTimeout:
                break
        return best_move

    def negamax(self, board: chess.Board, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.check_time()
        if board.is_checkmate():
            return -MATE_SCORE + ply
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        if board.can_claim_fifty_moves() or board.can_claim_threefold_repetition():
            return 0
        if depth <= 0:
            return self.quiescence(board, alpha, beta, 0)

        best = -INF
        moves = self.order_moves(board, list(board.legal_moves), root=False)
        for mv in moves:
            board.push(mv)
            score = -self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        return best

    def quiescence(self, board: chess.Board, alpha: int, beta: int, qdepth: int) -> int:
        self.check_time()
        stand_pat = evaluate(board)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
        if qdepth >= 5:
            return alpha

        noisy = []
        for mv in board.legal_moves:
            if board.is_capture(mv) or mv.promotion is not None:
                noisy.append(mv)
        noisy = self.order_moves(board, noisy, root=False)
        for mv in noisy:
            board.push(mv)
            score = -self.quiescence(board, -beta, -alpha, qdepth + 1)
            board.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def order_moves(self, board: chess.Board, moves: list[chess.Move], root: bool) -> list[chess.Move]:
        return sorted(moves, key=lambda mv: self.move_score(board, mv, root), reverse=True)

    def move_score(self, board: chess.Board, mv: chess.Move, root: bool) -> int:
        score = 0
        moving_piece = board.piece_at(mv.from_square)
        victim = board.piece_at(mv.to_square)
        if board.is_en_passant(mv):
            victim_value = PIECE_VALUES[chess.PAWN]
        else:
            victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
        attacker_value = PIECE_VALUES.get(moving_piece.piece_type, 0) if moving_piece else 0
        if board.is_capture(mv):
            score += 10_000 + 10 * victim_value - attacker_value
        if mv.promotion is not None:
            score += 8_000 + PIECE_VALUES.get(mv.promotion, 0)
        if board.gives_check(mv):
            score += 1_200
        if board.is_castling(mv):
            score += 500
        if mv.to_square in CENTER:
            score += 180
        elif mv.to_square in EXTENDED_CENTER:
            score += 70
        if moving_piece:
            if moving_piece.piece_type in (chess.KNIGHT, chess.BISHOP):
                if _home_rank(mv.from_square, moving_piece.color):
                    score += 220
            if moving_piece.piece_type == chess.QUEEN and board.fullmove_number <= 8 and root:
                score -= 180
            if moving_piece.piece_type == chess.ROOK and board.fullmove_number <= 10 and root:
                score -= 80
        return score


def select_move(observation: Any, output_format: str = "uci", time_limit_ms: int = 100) -> str:
    """Choose a legal chess move for the supplied observation."""
    board = parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    legal_uci = {mv.uci() for mv in legal_moves}
    hinted = extract_legal_uci(observation)
    allowed = None
    if hinted:
        intersection = legal_uci.intersection(hinted)
        if intersection:
            allowed = {chess.Move.from_uci(text) for text in intersection}

    fallback = _fallback_move(board, allowed)
    budget_ms = _safe_budget_ms(time_limit_ms)
    deadline = time.perf_counter() + budget_ms / 1000.0
    max_depth = _depth_for_budget(time_limit_ms, board)

    chosen = fallback
    try:
        searcher = _Searcher(deadline=deadline, allowed_root=allowed)
        chosen = searcher.choose(board, max_depth=max_depth)
    except Exception:
        chosen = fallback

    if chosen not in board.legal_moves:
        chosen = fallback
    if allowed and chosen not in allowed:
        chosen = fallback

    return _format_move(board, chosen, output_format)


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def parse_observation(observation: Any) -> chess.Board:
    """Parse common CATArena payload shapes into a python-chess Board."""
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    payload = observation
    if isinstance(payload, dict) and isinstance(payload.get("observation"), dict):
        payload = payload["observation"]

    fen = None
    current_player = None
    if isinstance(payload, dict):
        for key in ("fen", "FEN", "board", "state"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
        current_player = payload.get("current_player") or payload.get("turn") or payload.get("player")
    elif isinstance(payload, str):
        fen = payload.strip()

    if not fen:
        return chess.Board()

    parts = fen.split()
    try:
        if len(parts) >= 4:
            return chess.Board(fen)
        board = chess.Board(None)
        board.set_board_fen(parts[0])
        board.turn = _turn_from_player(current_player, chess.WHITE)
        board.clear_stack()
        return board
    except Exception:
        return chess.Board()


def extract_legal_uci(observation: Any) -> set[str]:
    payload = observation
    if isinstance(payload, dict) and isinstance(payload.get("observation"), dict):
        payload = payload["observation"]
    if not isinstance(payload, dict):
        return set()

    values = []
    for key in ("legal_moves", "legal", "moves", "valid_moves"):
        item = payload.get(key)
        if isinstance(item, (list, tuple, set)):
            values.extend(item)
    result = set()
    for value in values:
        text = str(value).strip()
        if len(text) in (4, 5):
            try:
                result.add(chess.Move.from_uci(text).uci())
            except ValueError:
                pass
    return result


def evaluate(board: chess.Board) -> int:
    if board.is_checkmate():
        return -MATE_SCORE
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    white_score = 0
    black_score = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type]
        table = PST[piece.piece_type]
        pst_square = square if piece.color == chess.WHITE else chess.square_mirror(square)
        value += table[pst_square]
        if piece.color == chess.WHITE:
            white_score += value
        else:
            black_score += value

    white_score += _bishop_pair_bonus(board, chess.WHITE)
    black_score += _bishop_pair_bonus(board, chess.BLACK)
    white_score += _pawn_structure_score(board, chess.WHITE)
    black_score += _pawn_structure_score(board, chess.BLACK)
    white_score += _king_safety_score(board, chess.WHITE)
    black_score += _king_safety_score(board, chess.BLACK)

    turn = board.turn
    board.turn = chess.WHITE
    white_mobility = board.legal_moves.count()
    board.turn = chess.BLACK
    black_mobility = board.legal_moves.count()
    board.turn = turn
    white_score += 2 * white_mobility
    black_score += 2 * black_mobility

    if board.is_check():
        if board.turn == chess.WHITE:
            white_score -= 35
        else:
            black_score -= 35

    score = white_score - black_score
    return score if board.turn == chess.WHITE else -score


def _bishop_pair_bonus(board: chess.Board, color: chess.Color) -> int:
    return 35 if len(board.pieces(chess.BISHOP, color)) >= 2 else 0


def _pawn_structure_score(board: chess.Board, color: chess.Color) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    if not pawns:
        return 0
    files: dict[int, int] = {}
    for sq in pawns:
        files[chess.square_file(sq)] = files.get(chess.square_file(sq), 0) + 1
    score = 0
    for sq in pawns:
        file_index = chess.square_file(sq)
        if files[file_index] > 1:
            score -= 10
        if not any(files.get(adj, 0) for adj in (file_index - 1, file_index + 1)):
            score -= 8
        rank = chess.square_rank(sq) if color == chess.WHITE else 7 - chess.square_rank(sq)
        score += rank * 3
    return score


def _king_safety_score(board: chess.Board, color: chess.Color) -> int:
    king_square = board.king(color)
    if king_square is None:
        return -500
    score = 0
    if color == chess.WHITE:
        if king_square in (chess.G1, chess.C1):
            score += 35
        shield_rank = 1
        forward = 1
    else:
        if king_square in (chess.G8, chess.C8):
            score += 35
        shield_rank = 6
        forward = -1
    king_file = chess.square_file(king_square)
    for file_index in (king_file - 1, king_file, king_file + 1):
        if 0 <= file_index <= 7:
            shield_square = chess.square(file_index, shield_rank)
            piece = board.piece_at(shield_square)
            if piece and piece.color == color and piece.piece_type == chess.PAWN:
                score += 8
            advanced_rank = shield_rank + forward
            if 0 <= advanced_rank <= 7:
                advanced_square = chess.square(file_index, advanced_rank)
                piece = board.piece_at(advanced_square)
                if piece and piece.color == color and piece.piece_type == chess.PAWN:
                    score += 4
    enemy = not color
    if board.is_attacked_by(enemy, king_square):
        score -= 80
    return score


def _fallback_move(board: chess.Board, allowed: set[chess.Move] | None) -> chess.Move:
    legal = list(board.legal_moves)
    if allowed:
        filtered = [mv for mv in legal if mv in allowed]
        if filtered:
            legal = filtered
    # Deterministic and decent fallback: ordered by the same tactical heuristic.
    searcher = _Searcher(deadline=time.perf_counter() + 0.001, allowed_root=allowed)
    return searcher.order_moves(board, legal, root=True)[0]


def _format_move(board: chess.Board, mv: chess.Move, output_format: str) -> str:
    fmt = (output_format or "uci").lower().strip()
    if fmt in {"san", "algebraic"}:
        try:
            return board.san(mv)
        except Exception:
            return mv.uci()
    return mv.uci()


def _safe_budget_ms(time_limit_ms: int) -> float:
    try:
        requested = float(time_limit_ms)
    except Exception:
        requested = 100.0
    requested = max(5.0, min(500.0, requested))
    if requested <= 30:
        return max(3.0, requested * 0.55)
    if requested <= 100:
        return max(10.0, requested * 0.72)
    return max(25.0, requested * 0.78)


def _depth_for_budget(time_limit_ms: int, board: chess.Board) -> int:
    try:
        requested = int(time_limit_ms)
    except Exception:
        requested = 100
    legal_count = board.legal_moves.count()
    if requested < 35:
        return 2
    if requested < 90:
        return 3
    if legal_count > 42:
        return 3
    return 4


def _turn_from_player(player: Any, default: chess.Color) -> chess.Color:
    text = str(player).lower().strip()
    if text in {"black", "b", "false", "1"}:
        return chess.BLACK
    if text in {"white", "w", "true", "0"}:
        return chess.WHITE
    return default


def _home_rank(square: chess.Square, color: chess.Color) -> bool:
    rank = chess.square_rank(square)
    return rank == (0 if color == chess.WHITE else 7)
