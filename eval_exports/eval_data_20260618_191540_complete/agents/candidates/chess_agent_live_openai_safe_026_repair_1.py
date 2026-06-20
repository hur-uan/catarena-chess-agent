"""Safe CATArena chess agent.

Public entry point:
    select_move(observation, output_format="uci", time_limit_ms=100) -> str

The agent uses only local Python code.  It never calls network APIs, never uses
subprocess/eval/exec/dynamic imports, and validates every returned UCI move
against python-chess legal_moves before formatting it for output.
"""

from typing import Any, List, Optional, Tuple

try:
    import chess
except Exception:  # pragma: no cover - python-chess is expected in arena
    chess = None  # type: ignore[assignment]

try:
    from agents.engine import EngineConfig, select_move_record
except Exception:  # pragma: no cover - optional local backend
    EngineConfig = None  # type: ignore[assignment]
    select_move_record = None  # type: ignore[assignment]

try:
    from tools.board_parser import extract_legal_moves, parse_observation
except Exception:  # pragma: no cover - optional local helpers
    extract_legal_moves = None  # type: ignore[assignment]
    parse_observation = None  # type: ignore[assignment]

try:
    from tools.strategy_profile import resolve_strategy_profile
except Exception:  # pragma: no cover - optional local helper
    resolve_strategy_profile = None  # type: ignore[assignment]


PIECE_VALUES = {
    "P": 100,
    "N": 320,
    "B": 330,
    "R": 500,
    "Q": 900,
    "K": 0,
}

if chess is not None:
    CENTER_SQUARES = {chess.D4, chess.E4, chess.D5, chess.E5}
    EXTENDED_CENTER_SQUARES = {
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
else:
    CENTER_SQUARES = set()
    EXTENDED_CENTER_SQUARES = set()


class SimpleSearchRecord:
    """Small diagnostics container without dataclass import-time machinery."""

    def __init__(
        self,
        fen: str,
        selected_move: str,
        cp: int = 0,
        mate_distance: Optional[int] = None,
        wdl: object = None,
        depth: int = 0,
        elapsed_ms: float = 0.0,
        nodes: int = 0,
        qnodes: int = 0,
        legal_moves: Optional[List[str]] = None,
        principal_variation: Optional[List[str]] = None,
        fallback_used: bool = False,
        backend: str = "safe_wrapper",
        engine_config: Optional[dict] = None,
    ) -> None:
        self.fen = fen
        self.selected_move = selected_move
        self.cp = cp
        self.mate_distance = mate_distance
        self.wdl = wdl
        self.depth = depth
        self.elapsed_ms = elapsed_ms
        self.nodes = nodes
        self.qnodes = qnodes
        self.legal_moves = legal_moves
        self.principal_variation = principal_variation
        self.fallback_used = fallback_used
        self.backend = backend
        self.engine_config = engine_config


class ChessAgent:
    """Wrapper class compatible with common arena integrations."""

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
    """Choose a legal chess move for the supplied observation."""
    board = _safe_parse_board(observation)
    record = select_move_details(observation, output_format="uci", time_limit_ms=time_limit_ms)
    move_uci = _validate_uci(board, record.selected_move)
    if not move_uci:
        move_uci = _fallback_legal_uci(board, observation)
    if not move_uci:
        return ""
    return _format_move(board, move_uci, output_format)


def select_move_details(
    observation: Any,
    output_format: str = "uci",
    time_limit_ms: int = 100,
) -> SimpleSearchRecord:
    """Return selected move plus lightweight diagnostics."""
    board = _safe_parse_board(observation)
    legal_uci = _legal_uci_list(board)

    if chess is None or not isinstance(board, chess.Board) or not legal_uci:
        return SimpleSearchRecord(
            fen=_board_fen(board),
            selected_move="",
            legal_moves=legal_uci,
            fallback_used=True,
            backend="unavailable_or_terminal",
        )

    if board.is_game_over(claim_draw=False):
        return SimpleSearchRecord(
            fen=board.fen(),
            selected_move="",
            legal_moves=legal_uci,
            fallback_used=True,
            backend="terminal",
        )

    mate_move = _find_immediate_mate(board)
    if mate_move is not None:
        return SimpleSearchRecord(
            fen=board.fen(),
            selected_move=mate_move.uci(),
            mate_distance=1,
            legal_moves=legal_uci,
            backend="mate_in_one_guard",
        )

    selected_uci = _validate_uci(board, _engine_candidate_uci(observation, time_limit_ms))
    backend = "project_engine" if selected_uci else "shallow_fallback"
    fallback_used = not bool(selected_uci)

    if not selected_uci:
        selected_uci = _best_shallow_move(board, avoid_opponent_mate=True)
        fallback_used = True

    if selected_uci:
        try:
            selected_move_obj = chess.Move.from_uci(selected_uci)
        except Exception:
            selected_move_obj = None
        if selected_move_obj is None or selected_move_obj not in board.legal_moves:
            selected_uci = ""
        elif _allows_immediate_opponent_mate(board, selected_move_obj):
            safer = _best_shallow_move(board, avoid_opponent_mate=True)
            if safer and safer != selected_uci:
                selected_uci = safer
                backend = "opponent_mate_guard"
                fallback_used = True

    if not _validate_uci(board, selected_uci):
        selected_uci = _fallback_legal_uci(board, observation)
        backend = "legal_last_resort"
        fallback_used = True

    return SimpleSearchRecord(
        fen=board.fen(),
        selected_move=selected_uci,
        legal_moves=legal_uci,
        fallback_used=fallback_used,
        backend=backend,
    )


def agent(observation: Any) -> str:
    return select_move(observation)


def act(observation: Any) -> str:
    return select_move(observation)


def move(observation: Any) -> str:
    return select_move(observation)


def _engine_candidate_uci(observation: Any, time_limit_ms: int) -> str:
    """Ask the optional local project engine for a candidate UCI move."""
    if EngineConfig is None or select_move_record is None:
        return ""
    try:
        if resolve_strategy_profile is not None:
            strategy_profile, _strategy_source = resolve_strategy_profile(observation=observation)
            config = EngineConfig(strategy_profile=strategy_profile)
        else:
            config = EngineConfig()
        safe_limit = max(1, min(1000, int(time_limit_ms)))
        record = select_move_record(
            observation=observation,
            output_format="uci",
            time_limit_ms=safe_limit,
            config=config,
        )
        return str(getattr(record, "selected_move", "") or "").strip()
    except Exception:
        return ""


def _safe_parse_board(observation: Any) -> Any:
    if chess is None:
        return _NullBoard()

    if parse_observation is not None:
        try:
            board = parse_observation(observation)
            if isinstance(board, chess.Board):
                return board
        except Exception:
            pass

    fen = _extract_fen(observation)
    if fen:
        try:
            return chess.Board(fen)
        except Exception:
            pass

    return chess.Board()


def _extract_fen(observation: Any) -> str:
    if isinstance(observation, dict):
        for key in ("fen", "board", "state"):
            value = observation.get(key)
            if isinstance(value, str) and "/" in value:
                return value.strip()
    if isinstance(observation, str) and "/" in observation:
        return observation.strip()
    for attr in ("fen", "board", "state"):
        value = getattr(observation, attr, None)
        if isinstance(value, str) and "/" in value:
            return value.strip()
    return ""


def _legal_uci_list(board: Any) -> List[str]:
    if chess is None or not isinstance(board, chess.Board):
        return []
    try:
        return [move_obj.uci() for move_obj in board.legal_moves]
    except Exception:
        return []


def _validate_uci(board: Any, move_text: Any) -> str:
    if chess is None or not isinstance(board, chess.Board):
        return ""
    text = str(move_text or "").strip()
    if not text:
        return ""
    try:
        move_obj = chess.Move.from_uci(text)
    except Exception:
        return ""
    return text if move_obj in board.legal_moves else ""


def _fallback_legal_uci(board: Any, observation: Any) -> str:
    if chess is None or not isinstance(board, chess.Board):
        return _hinted_legal_fallback(observation)
    legal = _legal_uci_list(board)
    if not legal:
        return ""

    for move_uci in _hinted_legal_moves(observation):
        if move_uci in legal:
            return move_uci

    shallow = _best_shallow_move(board, avoid_opponent_mate=False)
    return shallow if shallow in legal else legal[0]


def _hinted_legal_moves(observation: Any) -> List[str]:
    moves = []  # type: List[str]
    if extract_legal_moves is not None:
        try:
            moves.extend(str(item).strip() for item in extract_legal_moves(observation))
        except Exception:
            pass
    if isinstance(observation, dict):
        for key in ("legal_moves", "legalMoves", "moves"):
            value = observation.get(key)
            if isinstance(value, list):
                moves.extend(str(item).strip() for item in value)

    cleaned = []  # type: List[str]
    seen = set()
    for item in moves:
        if item and item not in seen:
            cleaned.append(item)
            seen.add(item)
    return cleaned


def _hinted_legal_fallback(observation: Any) -> str:
    hinted = _hinted_legal_moves(observation)
    return hinted[0] if hinted else ""


def _format_move(board: Any, move_uci: str, output_format: str) -> str:
    fmt = str(output_format or "uci").lower().strip()
    if fmt in ("", "default", "uci") or chess is None or not isinstance(board, chess.Board):
        return move_uci
    if fmt == "san":
        try:
            return board.san(chess.Move.from_uci(move_uci))
        except Exception:
            return move_uci
    return move_uci


def _find_immediate_mate(board: Any) -> Optional[Any]:
    if chess is None or not isinstance(board, chess.Board):
        return None
    for move_obj in _ordered_legal_moves(board):
        board.push(move_obj)
        is_mate = board.is_checkmate()
        board.pop()
        if is_mate:
            return move_obj
    return None


def _allows_immediate_opponent_mate(board: Any, move_obj: Any) -> bool:
    if chess is None or not isinstance(board, chess.Board):
        return False
    if move_obj not in board.legal_moves:
        return True
    board.push(move_obj)
    try:
        if board.is_game_over(claim_draw=False):
            return False
        for reply in board.legal_moves:
            board.push(reply)
            is_mate = board.is_checkmate()
            board.pop()
            if is_mate:
                return True
        return False
    finally:
        board.pop()


def _best_shallow_move(board: Any, avoid_opponent_mate: bool) -> str:
    if chess is None or not isinstance(board, chess.Board):
        return ""
    legal = list(_ordered_legal_moves(board))
    if not legal:
        return ""

    safe_scored = []  # type: List[Tuple[int, str]]
    all_scored = []  # type: List[Tuple[int, str]]
    for move_obj in legal:
        score = _move_score(board, move_obj)
        item = (score, move_obj.uci())
        all_scored.append(item)
        if not avoid_opponent_mate or not _allows_immediate_opponent_mate(board, move_obj):
            safe_scored.append(item)

    pool = safe_scored if safe_scored else all_scored
    pool.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return pool[0][1]


def _ordered_legal_moves(board: Any) -> List[Any]:
    if chess is None or not isinstance(board, chess.Board):
        return []
    moves = list(board.legal_moves)
    moves.sort(key=lambda move_obj: (_move_score(board, move_obj), move_obj.uci()), reverse=True)
    return moves


def _move_score(board: Any, move_obj: Any) -> int:
    if chess is None or not isinstance(board, chess.Board):
        return 0

    moving_piece = board.piece_at(move_obj.from_square)
    captured_piece = board.piece_at(move_obj.to_square)
    score = 0

    if captured_piece is not None:
        victim = PIECE_VALUES.get(captured_piece.symbol().upper(), 0)
        attacker = PIECE_VALUES.get(moving_piece.symbol().upper(), 0) if moving_piece else 0
        score += 1000 + victim * 10 - attacker

    if board.is_en_passant(move_obj):
        score += 1000 + PIECE_VALUES["P"] * 10

    if move_obj.promotion:
        promoted = chess.Piece(move_obj.promotion, board.turn)
        score += 800 + PIECE_VALUES.get(promoted.symbol().upper(), 0)

    if board.gives_check(move_obj):
        score += 300

    if board.is_castling(move_obj):
        score += 150

    if moving_piece is not None:
        piece_type = moving_piece.piece_type
        if piece_type in (chess.KNIGHT, chess.BISHOP):
            if board.fullmove_number <= 12:
                home_rank = 0 if moving_piece.color == chess.WHITE else 7
                if chess.square_rank(move_obj.from_square) == home_rank:
                    score += 55
            if move_obj.to_square in CENTER_SQUARES:
                score += 35
            elif move_obj.to_square in EXTENDED_CENTER_SQUARES:
                score += 18
        elif piece_type == chess.PAWN:
            if move_obj.to_square in CENTER_SQUARES:
                score += 30
            elif move_obj.to_square in EXTENDED_CENTER_SQUARES:
                score += 10
            score += _pawn_advance_bonus(move_obj, moving_piece.color)
        elif piece_type == chess.QUEEN and board.fullmove_number <= 8:
            score -= 35
        elif piece_type == chess.ROOK and board.fullmove_number <= 8:
            score -= 15

    board.push(move_obj)
    try:
        if board.is_checkmate():
            score += 100000
        score += _material_eval(board, not board.turn) // 40
        score += min(20, len(list(board.legal_moves)))
    finally:
        board.pop()

    return score


def _pawn_advance_bonus(move_obj: Any, color: bool) -> int:
    if chess is None:
        return 0
    rank = chess.square_rank(move_obj.to_square)
    if color == chess.WHITE:
        return max(0, rank - 1) * 2
    return max(0, 6 - rank) * 2


def _material_eval(board: Any, color: bool) -> int:
    if chess is None or not isinstance(board, chess.Board):
        return 0
    total = 0
    for piece in board.piece_map().values():
        value = PIECE_VALUES.get(piece.symbol().upper(), 0)
        total += value if piece.color == color else -value
    return total


def _board_fen(board: Any) -> str:
    try:
        return str(board.fen())
    except Exception:
        return ""


class _NullBoard:
    legal_moves = []  # type: List[Any]

    def is_game_over(self, claim_draw: bool = False) -> bool:
        return True

    def fen(self) -> str:
        return ""
