"""Safe self-contained CATArena chess agent.

Public entry point:
select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses python-chess for parsing and legality validation. It performs a
small deterministic alpha-beta search with capture quiescence under a strict
node/time budget. It does not use files, subprocesses, network calls, dynamic
imports, eval, or exec during play.
"""

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


class _SearchTimeout(Exception):
    """Internal signal for stopping search inside the allotted budget."""


class ChessAgent:
    """Small wrapper class compatible with common arena integrations."""

    def __init__(self, output_format: str = "uci", time_limit_ms: int = 100) -> None:
        self.output_format = output_format
        self.time_limit_ms = time_limit_ms

    def act(self, observation: Any) -> str:
        return select_move(observation, self.output_format, self.time_limit_ms)


class _Searcher:
    def __init__(self, board: chess.Board, time_limit_ms: int) -> None:
        self.board = board
        safe_ms = max(5, int(time_limit_ms))
        self.deadline = time.perf_counter() + max(0.004, (safe_ms - 8) / 1000.0)
        self.nodes = 0
        self.node_limit = 5000 if safe_ms < 40 else 18000 if safe_ms < 100 else 32000
        self.max_qdepth = 3 if safe_ms < 60 else 4

    def time_check(self) -> None:
        self.nodes += 1
        if self.nodes >= self.node_limit or time.perf_counter() >= self.deadline:
            raise _SearchTimeout

    def choose(self) -> chess.Move:
        legal_moves = list(self.board.legal_moves)
        if not legal_moves:
            raise ValueError("no legal moves available")
        if len(legal_moves) == 1:
            return legal_moves[0]

        for mv in self._ordered_moves(legal_moves):
            self.board.push(mv)
            is_mate = self.board.is_checkmate()
            self.board.pop()
            if is_mate:
                return mv

        best_move = self._fallback_move(legal_moves)
        max_depth = self._depth_for_budget(len(legal_moves))

        for depth in range(1, max_depth + 1):
            current_best = best_move
            current_score = -INF
            alpha = -INF
            try:
                for mv in self._ordered_moves(legal_moves):
                    self.time_check()
                    self.board.push(mv)
                    score = -self._negamax(depth - 1, -INF, -alpha, 1)
                    self.board.pop()
                    if score > current_score:
                        current_score = score
                        current_best = mv
                    if score > alpha:
                        alpha = score
                best_move = current_best
                if current_score >= MATE_SCORE - 10:
                    break
            except _SearchTimeout:
                break

        if best_move in self.board.legal_moves:
            return best_move
        return self._fallback_move(legal_moves)

    def _depth_for_budget(self, legal_count: int) -> int:
        remaining_ms = max(1.0, (self.deadline - time.perf_counter()) * 1000.0)
        if remaining_ms < 18 or legal_count > 45:
            return 2
        if remaining_ms < 65 or legal_count > 34:
            return 3
        return 4

    def _negamax(self, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.time_check()

        if self.board.is_checkmate():
            return -MATE_SCORE + ply
        if self.board.is_stalemate() or self.board.is_insufficient_material():
            return 0
        if self.board.can_claim_fifty_moves() or self.board.can_claim_threefold_repetition():
            return 0

        if depth <= 0 and not self.board.is_check():
            return self._quiescence(alpha, beta, self.max_qdepth)
        if depth <= 0:
            depth = 1

        best = -INF
        moves = list(self.board.legal_moves)
        for mv in self._ordered_moves(moves):
            self.board.push(mv)
            score = -self._negamax(depth - 1, -beta, -alpha, ply + 1)
            self.board.pop()
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        return best

    def _quiescence(self, alpha: int, beta: int, qdepth: int) -> int:
        self.time_check()
        stand_pat = self._evaluate()
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
        if qdepth <= 0:
            return alpha

        tactical_moves = [
            mv
            for mv in self.board.legal_moves
            if self.board.is_capture(mv) or mv.promotion is not None
        ]
        for mv in self._ordered_moves(tactical_moves):
            self.board.push(mv)
            score = -self._quiescence(-beta, -alpha, qdepth - 1)
            self.board.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    def _ordered_moves(self, moves: list[chess.Move]) -> list[chess.Move]:
        return sorted(moves, key=self._move_score, reverse=True)

    def _move_score(self, mv: chess.Move) -> int:
        score = 0
        if mv.promotion is not None:
            score += 9000 + PIECE_VALUES.get(mv.promotion, 0)
        if self.board.is_capture(mv):
            victim = self.board.piece_at(mv.to_square)
            if victim is None and self.board.is_en_passant(mv):
                victim_value = PIECE_VALUES[chess.PAWN]
            else:
                victim_value = PIECE_VALUES.get(victim.piece_type, 0) if victim else 0
            attacker = self.board.piece_at(mv.from_square)
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
            score += 5000 + 10 * victim_value - attacker_value
        if self.board.gives_check(mv):
            score += 700
        if self.board.is_castling(mv):
            score += 250
        if mv.to_square in CENTER_SQUARES:
            score += 90
        elif mv.to_square in EXTENDED_CENTER:
            score += 35
        piece = self.board.piece_at(mv.from_square)
        if piece and piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            home_rank = 0 if piece.color == chess.WHITE else 7
            if chess.square_rank(mv.from_square) == home_rank:
                score += 80
        if piece and piece.piece_type == chess.QUEEN and self.board.fullmove_number <= 8:
            score -= 70
        return score

    def _fallback_move(self, legal_moves: list[chess.Move]) -> chess.Move:
        return max(legal_moves, key=self._move_score)

    def _evaluate(self) -> int:
        if self.board.is_checkmate():
            return -MATE_SCORE
        if self.board.is_stalemate() or self.board.is_insufficient_material():
            return 0

        score = 0
        for square, piece in self.board.piece_map().items():
            value = PIECE_VALUES.get(piece.piece_type, 0)
            value += self._piece_activity_bonus(square, piece)
            if piece.color == chess.WHITE:
                score += value
            else:
                score -= value

        score += self._pawn_structure_score(chess.WHITE)
        score -= self._pawn_structure_score(chess.BLACK)
        score += self._king_safety_score(chess.WHITE)
        score -= self._king_safety_score(chess.BLACK)
        score += self._mobility_score()
        score += 8 if self.board.turn == chess.WHITE else -8
        return score if self.board.turn == chess.WHITE else -score

    def _piece_activity_bonus(self, square: chess.Square, piece: chess.Piece) -> int:
        rank = chess.square_rank(square)
        file_index = chess.square_file(square)
        bonus = 0
        if square in CENTER_SQUARES:
            bonus += 18
        elif square in EXTENDED_CENTER:
            bonus += 7

        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            center_distance = abs(file_index - 3.5) + abs(rank - 3.5)
            bonus += max(0, int(14 - 3 * center_distance))
            if piece.color == chess.WHITE:
                bonus += max(0, rank - 1) * 3
            else:
                bonus += max(0, 6 - rank) * 3
        elif piece.piece_type == chess.ROOK:
            if self._is_open_file(file_index):
                bonus += 22
            elif self._is_half_open_file(file_index, piece.color):
                bonus += 10
        elif piece.piece_type == chess.PAWN:
            bonus += rank * 2 if piece.color == chess.WHITE else (7 - rank) * 2
        return bonus

    def _is_open_file(self, file_index: int) -> bool:
        for rank in range(8):
            piece = self.board.piece_at(chess.square(file_index, rank))
            if piece and piece.piece_type == chess.PAWN:
                return False
        return True

    def _is_half_open_file(self, file_index: int, color: chess.Color) -> bool:
        own_pawn = False
        enemy_pawn = False
        for rank in range(8):
            piece = self.board.piece_at(chess.square(file_index, rank))
            if piece and piece.piece_type == chess.PAWN:
                if piece.color == color:
                    own_pawn = True
                else:
                    enemy_pawn = True
        return not own_pawn and enemy_pawn

    def _pawn_structure_score(self, color: chess.Color) -> int:
        pawns = list(self.board.pieces(chess.PAWN, color))
        if not pawns:
            return 0
        score = 0
        files: dict[int, int] = {}
        for sq in pawns:
            file_index = chess.square_file(sq)
            files[file_index] = files.get(file_index, 0) + 1
        for sq in pawns:
            file_index = chess.square_file(sq)
            rank = chess.square_rank(sq)
            if files[file_index] > 1:
                score -= 10
            if not any(adj in files for adj in (file_index - 1, file_index + 1)):
                score -= 12
            score += rank * 3 if color == chess.WHITE else (7 - rank) * 3
        return score

    def _king_safety_score(self, color: chess.Color) -> int:
        king_sq = self.board.king(color)
        if king_sq is None:
            return -500
        enemy = not color
        score = 0
        for sq in chess.SquareSet(chess.BB_KING_ATTACKS[king_sq]):
            if self.board.is_attacked_by(enemy, sq):
                score -= 8
            piece = self.board.piece_at(sq)
            if piece and piece.color == color:
                if piece.piece_type == chess.PAWN:
                    score += 7
                else:
                    score += 2
        if self.board.is_attacked_by(enemy, king_sq):
            score -= 45
        return score

    def _mobility_score(self) -> int:
        turn = self.board.turn
        try:
            own_mobility = self.board.legal_moves.count()
            self.board.turn = not turn
            if self.board.is_valid():
                enemy_mobility = self.board.legal_moves.count()
            else:
                enemy_mobility = 0
        finally:
            self.board.turn = turn
        raw = 2 * (own_mobility - enemy_mobility)
        return raw if turn == chess.WHITE else -raw


def select_move(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> str:
    """Choose a legal chess move for the supplied observation."""
    board = _parse_observation(observation)
    legal_moves = list(board.legal_moves)
    if not legal_moves or board.is_game_over(claim_draw=False):
        return ""

    try:
        chosen = _Searcher(board, time_limit_ms).choose()
    except Exception:
        chosen = _safe_fallback(board)

    if chosen not in board.legal_moves:
        chosen = _safe_fallback(board)

    fmt = (output_format or "uci").lower().strip()
    if fmt == "san":
        try:
            return board.san(chosen)
        except Exception:
            return chosen.uci()
    return chosen.uci()


def _safe_fallback(board: chess.Board) -> chess.Move:
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        raise ValueError("no legal fallback move available")

    def score(mv: chess.Move) -> int:
        value = 0
        if mv.promotion is not None:
            value += 10000 + PIECE_VALUES.get(mv.promotion, 0)
        if board.is_capture(mv):
            victim = board.piece_at(mv.to_square)
            if victim is None:
                victim_value = PIECE_VALUES[chess.PAWN]
            else:
                victim_value = PIECE_VALUES.get(victim.piece_type, 0)
            attacker = board.piece_at(mv.from_square)
            attacker_value = PIECE_VALUES.get(attacker.piece_type, 0) if attacker else 0
            value += 5000 + 10 * victim_value - attacker_value
        if board.gives_check(mv):
            value += 700
        if board.is_castling(mv):
            value += 250
        if mv.to_square in CENTER_SQUARES:
            value += 70
        elif mv.to_square in EXTENDED_CENTER:
            value += 25
        return value

    return max(legal_moves, key=score)


def _parse_observation(observation: Any) -> chess.Board:
    if isinstance(observation, chess.Board):
        return observation.copy(stack=False)

    fen = None
    if isinstance(observation, dict):
        for key in ("fen", "board", "position"):
            value = observation.get(key)
            if isinstance(value, str) and value.strip():
                fen = value.strip()
                break
    elif isinstance(observation, str) and observation.strip():
        fen = observation.strip()

    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass
    return chess.Board()


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)
