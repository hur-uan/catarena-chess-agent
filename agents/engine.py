"""Proposal-aligned chess search engine for the active playing agent."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional

import chess

from tools.board_parser import extract_legal_moves, parse_observation
from tools.move_formatter import format_move
from tools.move_validator import coerce_move, first_legal_move
from tools.strategy_profile import StrategyProfile, load_strategy_profile

INFINITY = 1_000_000_000

CENTER = {
    chess.D4,
    chess.E4,
    chess.D5,
    chess.E5,
}

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

TT_EXACT = "exact"
TT_LOWER = "lower"
TT_UPPER = "upper"


@dataclass
class SearchStats:
    nodes: int = 0
    qnodes: int = 0
    tt_hits: int = 0
    cutoffs: int = 0
    max_depth_completed: int = 0
    elapsed_ms: float = 0.0


@dataclass
class SearchRecord:
    fen: str
    selected_move: str
    cp: int
    mate_distance: Optional[int]
    wdl: Dict[str, float]
    depth: int
    elapsed_ms: float
    nodes: int
    qnodes: int
    legal_moves: list[str] = field(default_factory=list)
    principal_variation: list[str] = field(default_factory=list)
    fallback_used: bool = False
    backend: str = "internal"
    engine_config: dict[str, object] = field(default_factory=dict)


@dataclass
class SearchResult:
    move: Optional[chess.Move]
    score_cp: int
    mate_distance: Optional[int]
    depth: int
    stats: SearchStats
    pv: list[chess.Move] = field(default_factory=list)
    fallback_used: bool = False

    def move_text(self, board: chess.Board, output_format: str = "uci") -> str:
        if self.move is None:
            return ""
        return format_move(board, self.move, output_format)

    def wdl(self) -> Dict[str, float]:
        return cp_to_wdl(self.score_cp, self.mate_distance)


@dataclass
class TTEntry:
    depth: int
    score: int
    flag: str
    best_move: Optional[chess.Move]
    mate_distance: Optional[int] = None


@dataclass
class EngineConfig:
    strategy_profile: StrategyProfile = field(default_factory=load_strategy_profile)


class SearchTimeout(Exception):
    """Raised when the engine must stop due to the move time budget."""


def select_move_record(
    observation: object,
    output_format: str = "uci",
    time_limit_ms: int = 100,
    config: Optional[EngineConfig] = None,
) -> SearchRecord:
    cfg = config or EngineConfig()
    board = parse_observation(observation)
    legal_moves = _candidate_moves(board, observation)
    fen = board.fen()
    if not legal_moves or board.is_game_over(claim_draw=False):
        return SearchRecord(
            fen=fen,
            selected_move="",
            cp=cfg.strategy_profile.eval.draw_score,
            mate_distance=None,
            wdl=cp_to_wdl(cfg.strategy_profile.eval.draw_score, None, cfg.strategy_profile),
            depth=0,
            elapsed_ms=0.0,
            nodes=0,
            qnodes=0,
            legal_moves=[move.uci() for move in legal_moves],
            backend="internal",
        )

    result = search_best_move(
        board=board,
        legal_moves=legal_moves,
        time_limit_ms=time_limit_ms,
        config=cfg,
    )
    move_text = result.move_text(board, output_format)
    return SearchRecord(
        fen=fen,
        selected_move=move_text,
        cp=result.score_cp,
        mate_distance=result.mate_distance,
        wdl=result.wdl(),
        depth=result.depth,
        elapsed_ms=result.stats.elapsed_ms,
        nodes=result.stats.nodes,
        qnodes=result.stats.qnodes,
        legal_moves=[move.uci() for move in legal_moves],
        principal_variation=[move.uci() for move in result.pv],
        fallback_used=result.fallback_used,
        backend="internal",
    )


def search_best_move(
    board: chess.Board,
    legal_moves: Optional[Iterable[chess.Move]] = None,
    time_limit_ms: int = 100,
    config: Optional[EngineConfig] = None,
) -> SearchResult:
    cfg = config or EngineConfig()
    started = time.monotonic()
    side = board.turn
    root_moves = _prepare_root_moves(board, legal_moves)
    if not root_moves:
        return SearchResult(
            move=None,
            score_cp=cfg.strategy_profile.eval.draw_score,
            mate_distance=None,
            depth=0,
            stats=SearchStats(elapsed_ms=0.0),
        )

    engine = _SearchEngine(
        started=started,
        time_limit_ms=time_limit_ms,
        side=side,
        config=cfg,
    )
    result = engine.iterative_deepening(board, root_moves)
    result.stats.elapsed_ms = (time.monotonic() - started) * 1000.0
    return result


class _SearchEngine:
    def __init__(
        self,
        started: float,
        time_limit_ms: int,
        side: bool,
        config: EngineConfig,
    ) -> None:
        self.started = started
        self.time_limit_ms = time_limit_ms
        self.side = side
        self.config = config
        self.tt: dict[tuple[object, ...], TTEntry] = {}
        self.stats = SearchStats()
        self.history_scores: dict[tuple[int, int], int] = {}

    def iterative_deepening(
        self,
        board: chess.Board,
        root_moves: list[chess.Move],
    ) -> SearchResult:
        search_profile = self.config.strategy_profile.search
        best_move = root_moves[0]
        best_score = -INFINITY
        best_pv = [best_move]
        best_mate_distance: Optional[int] = None
        completed_depth = 0

        for depth in range(1, search_profile.max_depth + 1):
            if depth > search_profile.default_depth and self._time_near_limit():
                break
            try:
                score, move, pv = self._search_root(board, root_moves, depth)
            except SearchTimeout:
                break
            if move is not None:
                best_move = move
                best_score = score
                best_pv = pv or [move]
                best_mate_distance = score_to_mate_distance(score, self.config.strategy_profile)
            completed_depth = depth
            self.stats.max_depth_completed = depth
            root_moves = self._reorder_root_moves(best_move, root_moves)
            if (
                best_mate_distance is not None
                and abs(best_mate_distance)
                <= self.config.strategy_profile.search.root_mate_stop_distance
            ):
                break

        fallback_used = False
        if best_move not in board.legal_moves:
            best_move = first_legal_move(board)
            fallback_used = True

        return SearchResult(
            move=best_move,
            score_cp=clamp_cp(best_score, self.config.strategy_profile),
            mate_distance=best_mate_distance,
            depth=completed_depth,
            stats=self.stats,
            pv=best_pv,
            fallback_used=fallback_used,
        )

    def _search_root(
        self,
        board: chess.Board,
        root_moves: list[chess.Move],
        depth: int,
    ) -> tuple[int, Optional[chess.Move], list[chess.Move]]:
        alpha = -INFINITY
        beta = INFINITY
        best_move: Optional[chess.Move] = None
        best_score = -INFINITY
        best_pv: list[chess.Move] = []
        ordered = self._order_moves(board, root_moves, tt_move=self._tt_best_move(board))

        for move in ordered:
            self._check_time()
            board.push(move)
            try:
                score = -self._alpha_beta(board, depth - 1, -beta, -alpha, ply=1)
            finally:
                board.pop()
            if score > best_score or (
                score == best_score and best_move is not None and move.uci() < best_move.uci()
            ):
                best_score = score
                best_move = move
                best_pv = [move]
            if score > alpha:
                alpha = score
            if alpha >= beta:
                self.stats.cutoffs += 1
                self._record_history(board, move, depth)
                break

        return best_score, best_move, best_pv

    def _alpha_beta(
        self,
        board: chess.Board,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
    ) -> int:
        self._check_time()
        self.stats.nodes += 1

        if board.is_checkmate():
            return -mate_score_for_ply(ply, self.config.strategy_profile)
        if _is_search_draw(board):
            return self.config.strategy_profile.eval.draw_score

        key = board._transposition_key()
        original_alpha = alpha
        entry = self.tt.get(key)
        if entry is not None and entry.depth >= depth:
            self.stats.tt_hits += 1
            if entry.flag == TT_EXACT:
                return entry.score
            if entry.flag == TT_LOWER:
                alpha = max(alpha, entry.score)
            elif entry.flag == TT_UPPER:
                beta = min(beta, entry.score)
            if alpha >= beta:
                return entry.score

        if depth <= 0:
            return self._quiescence(board, alpha, beta, ply, qdepth=0)

        tt_move = entry.best_move if entry is not None else None
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return self.config.strategy_profile.eval.draw_score

        best_score = -INFINITY
        best_move: Optional[chess.Move] = None
        ordered = self._order_moves(board, legal_moves, tt_move=tt_move)

        for move in ordered:
            board.push(move)
            try:
                score = -self._alpha_beta(board, depth - 1, -beta, -alpha, ply + 1)
            finally:
                board.pop()

            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                self.stats.cutoffs += 1
                self._record_history(board, move, depth)
                break

        flag = TT_EXACT
        if best_score <= original_alpha:
            flag = TT_UPPER
        elif best_score >= beta:
            flag = TT_LOWER
        self.tt[key] = TTEntry(
            depth=depth,
            score=best_score,
            flag=flag,
            best_move=best_move,
            mate_distance=score_to_mate_distance(best_score, self.config.strategy_profile),
        )
        return best_score

    def _quiescence(
        self,
        board: chess.Board,
        alpha: int,
        beta: int,
        ply: int,
        qdepth: int,
    ) -> int:
        self._check_time()
        self.stats.qnodes += 1
        stand_pat = evaluate_board(board, self.side, self.config.strategy_profile)
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        if qdepth >= self.config.strategy_profile.search.quiescence_depth:
            return stand_pat

        noisy_moves = self._noisy_moves(board)
        ordered = self._order_moves(board, noisy_moves, tt_move=None)
        for move in ordered:
            board.push(move)
            try:
                if board.is_checkmate():
                    score = mate_score_for_ply(ply, self.config.strategy_profile)
                else:
                    score = -self._quiescence(board, -beta, -alpha, ply + 1, qdepth + 1)
            finally:
                board.pop()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    def _order_moves(
        self,
        board: chess.Board,
        moves: Iterable[chess.Move],
        tt_move: Optional[chess.Move],
    ) -> list[chess.Move]:
        scored: list[tuple[int, str, chess.Move]] = []
        for move in moves:
            score = move_order_score(board, move, self.config.strategy_profile)
            if tt_move is not None and move == tt_move:
                score += self.config.strategy_profile.search.tt_move_bonus
            score += self.history_scores.get((move.from_square, move.to_square), 0)
            scored.append((-score, move.uci(), move))
        scored.sort()
        return [move for _, _, move in scored]

    def _reorder_root_moves(
        self,
        best_move: chess.Move,
        root_moves: list[chess.Move],
    ) -> list[chess.Move]:
        return [best_move] + [move for move in root_moves if move != best_move]

    def _record_history(self, board: chess.Board, move: chess.Move, depth: int) -> None:
        key = (move.from_square, move.to_square)
        profile = self.config.strategy_profile.search
        increment = profile.history_bonus_scale * (depth ** profile.history_bonus_power)
        self.history_scores[key] = self.history_scores.get(key, 0) + increment

    def _tt_best_move(self, board: chess.Board) -> Optional[chess.Move]:
        entry = self.tt.get(board._transposition_key())
        return entry.best_move if entry is not None else None

    def _noisy_moves(self, board: chess.Board) -> list[chess.Move]:
        moves = []
        for move in board.legal_moves:
            if board.is_capture(move) or move.promotion or board.gives_check(move):
                moves.append(move)
        return moves

    def _elapsed_ms(self) -> float:
        return (time.monotonic() - self.started) * 1000.0

    def _time_near_limit(self) -> bool:
        if self.time_limit_ms <= 0:
            return False
        margin = self.config.strategy_profile.search.min_time_margin_ms
        return self._elapsed_ms() >= max(1, self.time_limit_ms - margin)

    def _check_time(self) -> None:
        if self._time_near_limit():
            raise SearchTimeout


def _is_search_draw(board: chess.Board) -> bool:
    """Use only cheap draw checks inside the search tree."""
    return (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.is_seventyfive_moves()
        or board.is_fifty_moves()
    )


def evaluate_board(
    board: chess.Board,
    side: bool,
    strategy_profile: Optional[StrategyProfile] = None,
) -> int:
    profile = strategy_profile or load_strategy_profile()
    if board.is_checkmate():
        mate_score = profile.eval.mate_score
        return -mate_score if board.turn == side else mate_score
    if _is_search_draw(board):
        return profile.eval.draw_score

    score = material_score(board, side, profile) * profile.eval.material_weight
    score += piece_activity_score(board, side, profile) * profile.eval.piece_activity_weight
    score += pawn_structure_score(board, side, profile) * profile.eval.pawn_structure_weight
    score += king_safety_score(board, side, profile) * profile.eval.king_safety_weight
    score += mobility_score(board, side, profile) * profile.eval.mobility_weight
    return int(round(score))


def material_score(board: chess.Board, side: bool, profile: StrategyProfile) -> int:
    score = 0
    for piece_type, value in _piece_values(profile).items():
        score += len(board.pieces(piece_type, side)) * value
        score -= len(board.pieces(piece_type, not side)) * value
    return score


def mobility_score(board: chess.Board, side: bool, profile: StrategyProfile) -> int:
    own = _count_legal_moves_for(board, side)
    opp = _count_legal_moves_for(board, not side)
    return 2 * (own - opp)


def piece_activity_score(board: chess.Board, side: bool, profile: StrategyProfile) -> int:
    score = 0
    activity = profile.piece_activity
    for square, piece in board.piece_map().items():
        sign = 1 if piece.color == side else -1
        if square in CENTER:
            score += sign * activity.center_bonus
        elif square in EXTENDED_CENTER:
            score += sign * activity.extended_center_bonus
        if piece.piece_type in (chess.KNIGHT, chess.BISHOP):
            score += sign * minor_piece_square_bonus(square, piece.color, profile)
        elif piece.piece_type == chess.ROOK:
            score += sign * rook_file_bonus(board, square, piece.color, profile)
    return score


def pawn_structure_score(board: chess.Board, side: bool, profile: StrategyProfile) -> int:
    return pawn_score_for(board, side, profile) - pawn_score_for(board, not side, profile)


def king_safety_score(board: chess.Board, side: bool, profile: StrategyProfile) -> int:
    return king_safety_for(board, side, profile) - king_safety_for(board, not side, profile)


def pawn_score_for(board: chess.Board, color: bool, profile: StrategyProfile) -> int:
    pawns = list(board.pieces(chess.PAWN, color))
    score = 0
    file_counts = [0] * 8
    pawn_profile = profile.pawn_structure
    for square in pawns:
        file_counts[chess.square_file(square)] += 1

    for square in pawns:
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        advance = rank_index if color == chess.WHITE else 7 - rank_index
        score += advance * pawn_profile.advance_bonus_per_rank
        if file_counts[file_index] > 1:
            score -= pawn_profile.doubled_penalty
        left_empty = file_index == 0 or file_counts[file_index - 1] == 0
        right_empty = file_index == 7 or file_counts[file_index + 1] == 0
        if left_empty and right_empty:
            score -= pawn_profile.isolated_penalty
    return score


def king_safety_for(board: chess.Board, color: bool, profile: StrategyProfile) -> int:
    king_square = board.king(color)
    if king_square is None:
        return -profile.eval.missing_king_penalty
    score = 0
    king_profile = profile.king_safety
    if board.is_attacked_by(not color, king_square):
        score -= king_profile.attacked_king_penalty
    for square in chess.SquareSet(chess.BB_KING_ATTACKS[king_square]):
        piece = board.piece_at(square)
        if piece is not None and piece.color == color:
            score += (
                king_profile.pawn_shield_bonus
                if piece.piece_type == chess.PAWN
                else king_profile.piece_shield_bonus
            )
        if board.is_attacked_by(not color, square):
            score -= king_profile.attacked_ring_penalty
    return score


def minor_piece_square_bonus(square: chess.Square, color: bool, profile: StrategyProfile) -> int:
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    if color == chess.BLACK:
        rank_index = 7 - rank_index
    file_distance = abs(file_index - 3.5)
    activity = profile.piece_activity
    rank_bonus = min(rank_index, 5)
    return int(
        activity.minor_base_bonus
        + rank_bonus * activity.minor_rank_bonus_weight
        - file_distance * activity.minor_center_distance_penalty
    )


def rook_file_bonus(
    board: chess.Board,
    square: chess.Square,
    color: bool,
    profile: StrategyProfile,
) -> int:
    file_index = chess.square_file(square)
    own_pawns = board.pieces(chess.PAWN, color)
    opp_pawns = board.pieces(chess.PAWN, not color)
    own_on_file = any(chess.square_file(pawn) == file_index for pawn in own_pawns)
    opp_on_file = any(chess.square_file(pawn) == file_index for pawn in opp_pawns)
    if not own_on_file and not opp_on_file:
        return profile.piece_activity.rook_open_file_bonus
    if not own_on_file:
        return profile.piece_activity.rook_half_open_file_bonus
    return 0


def move_order_score(board: chess.Board, move: chess.Move, profile: StrategyProfile) -> int:
    score = 0
    ordering = profile.move_ordering
    piece_values = _piece_values(profile)
    attacker = board.piece_at(move.from_square)
    captured = captured_piece(board, move)
    if captured is not None:
        victim_value = piece_values.get(captured.piece_type, 0)
        attacker_value = piece_values.get(attacker.piece_type, 0) if attacker else 0
        score += (
            ordering.capture_base_bonus
            + ordering.capture_victim_multiplier * victim_value
            - ordering.capture_attacker_penalty * attacker_value
        )
    if move.promotion:
        score += piece_values.get(move.promotion, 0) + ordering.promotion_bonus
    if board.gives_check(move):
        score += ordering.check_bonus
    if board.is_castling(move):
        score += ordering.castling_bonus
    if move.to_square in CENTER:
        score += ordering.center_bonus
    elif move.to_square in EXTENDED_CENTER:
        score += ordering.extended_center_bonus
    if attacker is not None:
        score += development_bonus(board, move, attacker, profile)
    return score


def development_bonus(
    board: chess.Board,
    move: chess.Move,
    moving_piece: Optional[chess.Piece],
    profile: StrategyProfile,
) -> int:
    if moving_piece is None:
        return 0
    bonus = 0
    ordering = profile.move_ordering
    piece_type = moving_piece.piece_type
    color = moving_piece.color
    from_rank = chess.square_rank(move.from_square)
    home_rank = 0 if color == chess.WHITE else 7
    if piece_type in (chess.KNIGHT, chess.BISHOP) and from_rank == home_rank:
        bonus += ordering.minor_development_bonus
    if piece_type == chess.PAWN and move.to_square in CENTER:
        bonus += ordering.center_pawn_development_bonus
    if board.fullmove_number <= profile.phase.opening_fullmove_limit and piece_type == chess.QUEEN:
        bonus -= ordering.early_queen_penalty
    if (
        board.fullmove_number <= profile.phase.opening_fullmove_limit
        and piece_type == chess.ROOK
        and not board.is_castling(move)
    ):
        bonus -= ordering.early_rook_penalty
    return bonus


def captured_piece(board: chess.Board, move: chess.Move) -> Optional[chess.Piece]:
    captured = board.piece_at(move.to_square)
    if captured is None and board.is_en_passant(move):
        return chess.Piece(chess.PAWN, not board.turn)
    return captured


def cp_to_wdl(
    score_cp: int,
    mate_distance: Optional[int],
    strategy_profile: Optional[StrategyProfile] = None,
) -> Dict[str, float]:
    if mate_distance is not None:
        if mate_distance > 0:
            return {"win": 1.0, "draw": 0.0, "loss": 0.0}
        return {"win": 0.0, "draw": 0.0, "loss": 1.0}
    if score_cp >= 250:
        return {"win": 0.85, "draw": 0.12, "loss": 0.03}
    if score_cp >= 80:
        return {"win": 0.58, "draw": 0.30, "loss": 0.12}
    if score_cp <= -250:
        return {"win": 0.03, "draw": 0.12, "loss": 0.85}
    if score_cp <= -80:
        return {"win": 0.12, "draw": 0.30, "loss": 0.58}
    return {"win": 0.25, "draw": 0.50, "loss": 0.25}


def clamp_cp(score: int, strategy_profile: Optional[StrategyProfile] = None) -> int:
    profile = strategy_profile or load_strategy_profile()
    mate_score = profile.eval.mate_score
    return max(-mate_score, min(mate_score, score))


def score_to_mate_distance(
    score: int,
    strategy_profile: Optional[StrategyProfile] = None,
) -> Optional[int]:
    profile = strategy_profile or load_strategy_profile()
    mate_score = profile.eval.mate_score
    margin = profile.search.mate_detection_margin
    if abs(score) < mate_score - margin:
        return None
    distance = mate_score - abs(score)
    if distance < 0:
        distance = 0
    return distance if score > 0 else -distance


def mate_score_for_ply(ply: int, strategy_profile: Optional[StrategyProfile] = None) -> int:
    profile = strategy_profile or load_strategy_profile()
    return profile.eval.mate_score - ply


def _count_legal_moves_for(board: chess.Board, side: bool) -> int:
    if board.turn == side:
        return board.legal_moves.count()
    board_copy = board.copy(stack=False)
    board_copy.turn = side
    if board_copy.is_checkmate():
        return 0
    return board_copy.legal_moves.count()


def _candidate_moves(board: chess.Board, observation: object) -> list[chess.Move]:
    hinted = []
    for raw_move in extract_legal_moves(observation):
        move = coerce_move(board, raw_move)
        if move is not None and move in board.legal_moves:
            hinted.append(move)
    return hinted or list(board.legal_moves)


def _prepare_root_moves(
    board: chess.Board,
    legal_moves: Optional[Iterable[chess.Move]],
) -> list[chess.Move]:
    if legal_moves is None:
        return list(board.legal_moves)
    root_moves = []
    for move in legal_moves:
        if move in board.legal_moves:
            root_moves.append(move)
    return root_moves or list(board.legal_moves)


def _piece_values(profile: StrategyProfile) -> Dict[int, int]:
    return {
        chess.PAWN: profile.piece_values.pawn,
        chess.KNIGHT: profile.piece_values.knight,
        chess.BISHOP: profile.piece_values.bishop,
        chess.ROOK: profile.piece_values.rook,
        chess.QUEEN: profile.piece_values.queen,
        chess.KING: 0,
    }


def find_stockfish_binary() -> Optional[str]:
    env_candidate = Path("tools/stockfish")
    if env_candidate.exists() and env_candidate.is_file():
        return str(env_candidate)
    return shutil.which("stockfish")


def analyze_with_stockfish(
    fen: str,
    depth: int = 10,
    multipv: int = 1,
    binary: Optional[str] = None,
    timeout: int = 10,
) -> Dict[str, object]:
    engine = binary or find_stockfish_binary()
    if not engine:
        return {"available": False, "reason": "stockfish binary not found"}

    command = [engine]
    script = "\n".join(
        [
            "uci",
            f"setoption name MultiPV value {max(1, multipv)}",
            f"position fen {fen}",
            f"go depth {max(1, depth)}",
            "quit",
            "",
        ]
    )
    try:
        completed = subprocess.run(
            command,
            input=script,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": str(exc)}

    output = completed.stdout.splitlines()
    bestmove = ""
    lines = []
    for line in output:
        if line.startswith("info depth "):
            lines.append(line.strip())
        if line.startswith("bestmove "):
            bestmove = line.split(" ", 1)[1].strip()
    return {
        "available": completed.returncode == 0,
        "bestmove": bestmove,
        "info_lines": lines[-multipv:],
        "returncode": completed.returncode,
    }
