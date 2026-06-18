"""Interactive browser UI for playing against the local chess agent."""

from __future__ import annotations

import importlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import chess
from flask import Flask, jsonify, make_response, render_template, request

from optimization.meta_agent import run_optimization_round
from tools.catarena_platform import run_official_catarena_chess_round
from tools.move_validator import validate_move

PIECE_SYMBOLS = {
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}
FILES = "abcdefgh"
AUTO_REPORTS_DIR = Path("reports/web_auto")
LEARNING_LOCK = threading.Lock()


@dataclass
class GameSession:
    board: chess.Board = field(default_factory=chess.Board)
    human_color: bool = chess.WHITE
    history: List[Dict[str, str]] = field(default_factory=list)
    last_move: Optional[str] = None
    mode: str = "human_vs_agent"
    game_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    learned: bool = False
    learning_error: str = ""
    learning_status: str = "idle"
    learning_message: str = "Idle"
    learning_started_at: str = ""
    learning_updated_at: str = ""
    learning_finished_at: str = ""
    learning_artifacts: Dict[str, str] = field(default_factory=dict)
    learning_result: Dict[str, Any] = field(default_factory=dict)
    max_plies: int = 200
    search_records: List[Dict[str, Any]] = field(default_factory=list)


GAMES: Dict[str, GameSession] = {}


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        response = make_response(render_template("board.html"))
        _session_id(response)
        return response

    @app.route("/api/state", methods=["GET"])
    def state():
        game = _game()
        return jsonify(_serialize_game(game))

    @app.route("/api/new", methods=["POST"])
    def new_game():
        data = request.get_json(silent=True) or {}
        human_color = chess.BLACK if data.get("human_color") == "black" else chess.WHITE
        mode = data.get("mode") or "human_vs_agent"
        max_plies = int(data.get("max_plies", 200))
        max_plies = max(20, min(max_plies, 400))
        session_id = request.cookies.get("chess_agent_session") or uuid.uuid4().hex
        GAMES[session_id] = GameSession(
            human_color=human_color,
            mode=mode,
            max_plies=max_plies,
        )
        game = GAMES[session_id]
        if mode == "human_vs_agent" and human_color == chess.BLACK:
            _play_agent_move(game)
        response = jsonify(_serialize_game(game))
        response.set_cookie("chess_agent_session", session_id, samesite="Lax")
        return response

    @app.route("/api/move", methods=["POST"])
    def human_move():
        game = _game()
        data = request.get_json(silent=True) or {}
        move_text = str(data.get("move", "")).strip()
        if not move_text:
            return jsonify({"error": "move is required", "state": _serialize_game(game)}), 400
        if game.board.turn != game.human_color:
            return jsonify({"error": "not human turn", "state": _serialize_game(game)}), 400

        result = validate_move(game.board, move_text)
        if not result.is_legal or not result.normalized_move:
            return jsonify({"error": result.reason, "state": _serialize_game(game)}), 400

        _push_move(game, chess.Move.from_uci(result.normalized_move), "Human")
        if not game.board.is_game_over() and game.mode == "human_vs_agent":
            _play_agent_move(game)
        return jsonify(_serialize_game(game))

    @app.route("/api/agent-move", methods=["POST"])
    def agent_move():
        game = _game()
        if not _auto_terminal(game):
            _play_agent_move(game)
        return jsonify(_serialize_game(game))

    @app.route("/api/autoplay", methods=["POST"])
    def autoplay():
        game = _game()
        data = request.get_json(silent=True) or {}
        plies = int(data.get("plies", 1))
        plies = max(1, min(plies, 20))
        for _ in range(plies):
            if _auto_terminal(game):
                break
            _play_agent_move(game)
        return jsonify(_serialize_game(game))

    @app.route("/api/learn", methods=["POST"])
    def learn_from_game():
        game = _game()
        data = request.get_json(silent=True) or {}
        backend = data.get("backend", "profile")
        max_repair_attempts = int(data.get("max_repair_attempts", 0))
        legacy_promote = data.get("promote")
        legacy_promote_default = legacy_promote if legacy_promote is not None else False
        promote_agent = bool(data.get("promote_agent", legacy_promote_default))
        promote_profile = bool(
            data.get("promote_profile", legacy_promote_default)
        )
        if not _auto_terminal(game):
            return jsonify({"error": "game is not finished", "state": _serialize_game(game)}), 400
        if game.learned:
            return jsonify({"status": "already_learned", "state": _serialize_game(game)})
        if _learning_in_progress(game):
            return jsonify({"status": "in_progress", "state": _serialize_game(game)})

        _set_learning(game, "queued", "Learning queued")
        worker = threading.Thread(
            target=_run_background_learning,
            args=(game, backend, max_repair_attempts, promote_agent, promote_profile),
            daemon=True,
        )
        worker.start()
        return jsonify({"status": "started", "state": _serialize_game(game)})

    @app.route("/api/learn-status", methods=["GET"])
    def learn_status():
        game = _game()
        return jsonify({"learning": _learning_payload(game), "state": _serialize_game(game)})

    return app


def _session_id(response=None) -> str:
    session_id = request.cookies.get("chess_agent_session") or uuid.uuid4().hex
    if session_id not in GAMES:
        GAMES[session_id] = GameSession()
    if response is not None:
        response.set_cookie("chess_agent_session", session_id, samesite="Lax")
    return session_id


def _game() -> GameSession:
    return GAMES[_session_id()]


def _play_agent_move(game: GameSession) -> Optional[str]:
    chess_agent = importlib.import_module("agents.chess_agent")
    chess_agent = importlib.reload(chess_agent)
    details = chess_agent.select_move_details(
        {"fen": game.board.fen(), "legal_moves": [m.uci() for m in game.board.legal_moves]}
    )
    move_text = details.selected_move
    result = validate_move(game.board, move_text)
    if not result.is_legal or not result.normalized_move:
        return None
    game.search_records.append(
        {
            "fen": details.fen,
            "selected_move": details.selected_move,
            "backend": details.backend,
            "engine_config": details.engine_config,
            "cp": details.cp,
            "mate_distance": details.mate_distance,
            "wdl": details.wdl,
            "depth": details.depth,
            "elapsed_ms": details.elapsed_ms,
            "nodes": details.nodes,
            "qnodes": details.qnodes,
            "legal_moves": details.legal_moves,
            "principal_variation": details.principal_variation,
            "fallback_used": details.fallback_used,
        }
    )
    move = chess.Move.from_uci(result.normalized_move)
    _push_move(game, move, "Agent")
    return move.uci()


def _push_move(game: GameSession, move: chess.Move, actor: str) -> None:
    san = game.board.san(move)
    uci = move.uci()
    color = "White" if game.board.turn == chess.WHITE else "Black"
    game.board.push(move)
    game.last_move = uci
    game.history.append(
        {
            "actor": actor,
            "color": color,
            "uci": uci,
            "san": san,
            "fen_after": game.board.fen(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def _serialize_game(game: GameSession) -> Dict:
    board_rows = []
    for rank in range(7, -1, -1):
        row = []
        for file_index in range(8):
            square = chess.square(file_index, rank)
            piece = game.board.piece_at(square)
            row.append(
                {
                    "square": chess.square_name(square),
                    "piece": PIECE_SYMBOLS.get(piece.symbol(), "") if piece else "",
                    "piece_symbol": piece.symbol() if piece else "",
                    "light": (rank + file_index) % 2 == 1,
                    "last": _square_in_last_move(game.last_move, square),
                }
            )
        board_rows.append(row)

    legal_moves = [move.uci() for move in game.board.legal_moves]
    return {
        "board": board_rows,
        "fen": game.board.fen(),
        "turn": "white" if game.board.turn == chess.WHITE else "black",
        "human_color": "white" if game.human_color == chess.WHITE else "black",
        "agent_color": "black" if game.human_color == chess.WHITE else "white",
        "mode": game.mode,
        "status": _game_status(game),
        "is_game_over": game.board.is_game_over(),
        "auto_terminal": _auto_terminal(game),
        "max_plies": game.max_plies,
        "game_id": game.game_id,
        "learned": game.learned,
        "learning_error": game.learning_error,
        "learning": _learning_payload(game),
        "legal_moves": legal_moves,
        "legal_by_from": _legal_by_from(legal_moves),
        "history": game.history,
        "last_move": game.last_move,
        "files": list(FILES),
        "ranks": list(range(8, 0, -1)),
    }


def _run_background_learning(
    game: GameSession,
    backend: str,
    max_repair_attempts: int,
    promote_agent: bool,
    promote_profile: bool,
) -> None:
    lock_acquired = False
    try:
        _set_learning(game, "waiting", "Waiting for current learning job")
        LEARNING_LOCK.acquire()
        lock_acquired = True
        _set_learning(game, "saving_logs", "Saving logs and ranking")
        artifacts = _write_game_artifacts(game)
        game.learning_artifacts = {key: str(value) for key, value in artifacts.items()}
        _set_learning(game, "catarena_running", "Running official CATArena chess round")
        platform_run = run_official_catarena_chess_round(
            output_dir=AUTO_REPORTS_DIR / game.game_id / "official_catarena",
            max_plies=min(game.max_plies, 80),
        )
        game.learning_artifacts.update(
            {
                "catarena_context_path": platform_run.context_path,
                "catarena_contract_path": platform_run.contract_path,
                "catarena_manifest_path": platform_run.manifest_path,
                "catarena_battle_log_path": platform_run.battle_log_path,
                "catarena_ranking_path": platform_run.ranking_path,
                "catarena_error_report_path": platform_run.error_report_path,
                "catarena_official_report_path": platform_run.official_report_path,
            }
        )
        round_id = f"web_auto_{game.game_id}"

        def on_progress(status: str, message: str) -> None:
            _set_learning(game, status, message)

        report = run_optimization_round(
            round_id=round_id,
            backend=backend,
            logs=Path(platform_run.battle_log_path),
            ranking=Path(platform_run.ranking_path),
            report_path=artifacts["optimization_report_path"],
            next_agent_path=Path("agents/candidates") / f"strategy_profile_{round_id}.json",
            max_repair_attempts=max_repair_attempts,
            promote_agent=promote_agent,
            promote_profile=promote_profile,
            strict_catarena=True,
            progress_callback=on_progress,
        )
        game.learned = True
        game.learning_error = ""
        game.learning_result = {
            "validator_passed": report.validator_passed,
            "promoted_agent": False,
            "promoted_profile": report.tuning_report.promoted_strategy_profile,
            "candidate_path": report.generated_agent.path,
            "repair_attempts": report.repair_attempts,
            "artifact_paths": report.artifact_paths,
            "promotion_gate": report.promotion_gate.model_dump(),
        }
        if report.validator_passed and report.tuning_report.promoted_strategy_profile:
            _set_learning(game, "promoted", "Promoted profile")
        elif report.validator_passed:
            _set_learning(game, "validated", "Candidate validated but not promoted")
        else:
            game.learning_error = "candidate failed validation"
            _set_learning(game, "failed", "Candidate failed validation")
    except Exception as exc:  # noqa: BLE001 - background job should preserve failure detail.
        game.learning_error = str(exc)
        game.learning_result = {}
        _set_learning(game, "failed", f"Learning failed: {exc}")
    finally:
        game.learning_finished_at = datetime.now(timezone.utc).isoformat()
        if lock_acquired:
            LEARNING_LOCK.release()


def _learning_in_progress(game: GameSession) -> bool:
    return game.learning_status in {
        "queued",
        "waiting",
        "saving_logs",
        "catarena_running",
        "reading_feedback",
        "generating",
        "prescreen",
        "regression",
        "validating",
        "promoting",
        "writing_report",
    }


def _set_learning(game: GameSession, status: str, message: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    if not game.learning_started_at or status in {"queued", "saving_logs"}:
        game.learning_started_at = now
    game.learning_status = status
    game.learning_message = message
    game.learning_updated_at = now


def _learning_payload(game: GameSession) -> Dict[str, Any]:
    return {
        "status": game.learning_status,
        "message": game.learning_message,
        "error": game.learning_error,
        "started_at": game.learning_started_at,
        "updated_at": game.learning_updated_at,
        "finished_at": game.learning_finished_at,
        "artifacts": game.learning_artifacts,
        "result": game.learning_result,
    }


def _auto_terminal(game: GameSession) -> bool:
    return game.board.is_game_over() or len(game.history) >= game.max_plies


def _game_status(game: GameSession) -> str:
    if len(game.history) >= game.max_plies and not game.board.is_game_over():
        return "Draw · max plies reached"
    return _status(game.board)


def _write_game_artifacts(game: GameSession) -> Dict[str, Path]:
    game_dir = AUTO_REPORTS_DIR / game.game_id
    game_dir.mkdir(parents=True, exist_ok=True)
    log_path = game_dir / "battle.log"
    ranking_path = game_dir / "ranking.csv"
    error_report_path = game_dir / "error_report.json"
    summary_path = game_dir / "game_summary.json"
    optimization_report_path = game_dir / "optimization_report.json"

    result = _game_result(game)
    log_lines = [
        f"game_id={game.game_id}",
        f"result={result}",
        f"status={_game_status(game)}",
        f"final_fen={game.board.fen()}",
    ]
    for index, item in enumerate(game.history, start=1):
        log_lines.append(
            "ply=%d color=%s actor=%s san=%s uci=%s fen_after=%s"
            % (
                index,
                item["color"],
                item["actor"],
                item["san"],
                item["uci"],
                item.get("fen_after", ""),
            )
        )
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    score = 0.5 if result.startswith("draw") else 1.0
    ranking_path.write_text(
        "agent,rank,games,wins,losses,draws,win_rate\n"
        f"chess_agent,1,1,{1 if score == 1.0 else 0},0,{1 if score == 0.5 else 0},{score}\n",
        encoding="utf-8",
    )
    error_report_path.write_text(
        json.dumps({"errors": [], "result": result}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(
            {
                "game_id": game.game_id,
                "result": result,
                "status": _game_status(game),
                "final_fen": game.board.fen(),
                "moves": game.history,
                "search_records": game.search_records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "log_path": log_path,
        "ranking_path": ranking_path,
        "error_report_path": error_report_path,
        "summary_path": summary_path,
        "optimization_report_path": optimization_report_path,
    }


def _game_result(game: GameSession) -> str:
    if len(game.history) >= game.max_plies and not game.board.is_game_over():
        return "draw_max_plies"
    if game.board.is_checkmate():
        return "black_win" if game.board.turn == chess.WHITE else "white_win"
    if game.board.is_stalemate():
        return "draw_stalemate"
    if game.board.is_insufficient_material():
        return "draw_insufficient_material"
    if game.board.is_seventyfive_moves():
        return "draw_seventyfive_moves"
    if game.board.is_fivefold_repetition():
        return "draw_fivefold_repetition"
    return game.board.result()


def _square_in_last_move(last_move: Optional[str], square: int) -> bool:
    if not last_move:
        return False
    return chess.square_name(square) in {last_move[:2], last_move[2:4]}


def _legal_by_from(legal_moves: List[str]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for move in legal_moves:
        result.setdefault(move[:2], []).append(move)
    return result


def _status(board: chess.Board) -> str:
    if board.is_checkmate():
        winner = "Black" if board.turn == chess.WHITE else "White"
        return f"Checkmate · {winner} wins"
    if board.is_stalemate():
        return "Stalemate"
    if board.is_insufficient_material():
        return "Draw · insufficient material"
    if board.is_seventyfive_moves():
        return "Draw · seventy-five move rule"
    if board.is_fivefold_repetition():
        return "Draw · fivefold repetition"
    if board.is_check():
        return "Check"
    return "Ongoing"


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5055, debug=False)
