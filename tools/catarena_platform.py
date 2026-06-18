"""Official CATArena chess platform integration.

This module treats the checked-out CATArena repository as the source of truth
for chess-agent interface contracts and dry-run battle feedback.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from agents.chess_agent import select_move_details
from tools.catarena import DEFAULT_CATARENA_PATH, assert_catarena_ready
from tools.move_validator import validate_move

OFFICIAL_REPO_URL = "https://github.com/AGI-Eval-Official/CATArena"


class CATArenaSourceFile(BaseModel):
    path: str
    sha256: str
    bytes: int
    role: str
    required: bool = True


class CATArenaContract(BaseModel):
    repository_url: str = OFFICIAL_REPO_URL
    game: str = "chess"
    game_server_endpoints: Dict[str, str]
    ai_server_endpoints: Dict[str, str]
    arena_payload: Dict[str, List[str]]
    move_format: str = "UCI string, for example e2e4 or a7a8q"
    observation_format: str = "JSON payload with fen, algorithm, game_id, and current_player"
    report_files: List[str]


class CATArenaPlatformContext(BaseModel):
    repo_path: str
    repository_url: str = OFFICIAL_REPO_URL
    source_files: List[CATArenaSourceFile] = Field(default_factory=list)
    missing_required_files: List[str] = Field(default_factory=list)
    contract: CATArenaContract


class CATArenaPlatformRun(BaseModel):
    passed: bool
    context_path: str
    contract_path: str
    manifest_path: str
    battle_log_path: str
    ranking_path: str
    error_report_path: str
    official_report_path: str
    games: int
    moves_played: int
    errors: List[str] = Field(default_factory=list)


def collect_catarena_platform_context(
    repo_path: Path = DEFAULT_CATARENA_PATH,
) -> CATArenaPlatformContext:
    status = assert_catarena_ready(repo_path)
    chessgame = Path(status.repo_path) / "chessgame"
    source_files = []
    for path in sorted(chessgame.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(Path(status.repo_path)))
        source_files.append(
            CATArenaSourceFile(
                path=rel,
                sha256=_sha256(path),
                bytes=path.stat().st_size,
                role=_classify_source_file(path),
                required=_is_required_source_file(rel),
            )
        )

    present = {item.path for item in source_files}
    missing = [path for path in _required_chess_files() if path not in present]
    return CATArenaPlatformContext(
        repo_path=status.repo_path,
        source_files=source_files,
        missing_required_files=missing,
        contract=_official_contract(),
    )


def write_catarena_platform_context(
    output_dir: Path,
    repo_path: Path = DEFAULT_CATARENA_PATH,
) -> CATArenaPlatformContext:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    context = collect_catarena_platform_context(repo_path)
    manifest = [item.model_dump() for item in context.source_files]
    (output_dir / "catarena_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "catarena_contract.json").write_text(
        context.contract.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "catarena_context.json").write_text(
        context.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return context


def run_official_catarena_chess_round(
    repo_path: Path = DEFAULT_CATARENA_PATH,
    output_dir: Path = Path("reports/catarena_platform"),
    max_plies: int = 80,
) -> CATArenaPlatformRun:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    context = write_catarena_platform_context(output_dir, repo_path)
    battle_log_path = output_dir / "battle.log"
    ranking_path = output_dir / "ranking.csv"
    error_report_path = output_dir / "error_report.json"
    official_report_path = output_dir / "official_catarena_report.json"

    errors: List[str] = []
    log_lines: List[str] = [
        f"platform={OFFICIAL_REPO_URL}",
        "official_files=%d" % len(context.source_files),
        "missing_required=%s" % ",".join(context.missing_required_files),
    ]
    if context.missing_required_files:
        errors.append("missing required CATArena files: %s" % context.missing_required_files)

    repo = Path(context.repo_path)
    server_module = _load_module(
        repo / "chessgame/chess/server.py",
        "official_catarena_chess_server",
    )
    ai_module = _load_module(
        repo / "chessgame/chess/AI_example/ai_http_server.py",
        "official_catarena_chess_ai_example",
    )
    arena_probe = _load_official_arena_probe(repo, output_dir)
    log_lines.append("official_arena_loaded=%s" % arena_probe.get("loaded"))
    baseline_ai = ai_module.ChessAI("OfficialExample", "Official CATArena Example AI")

    games = []
    moves_played = 0
    for local_color in ("white", "black"):
        result = _play_official_game(
            server_module=server_module,
            baseline_ai=baseline_ai,
            local_color=local_color,
            max_plies=max_plies,
            log_lines=log_lines,
        )
        moves_played += int(result["moves_count"])
        games.append(result)
        if result.get("errors"):
            errors.extend(result["errors"])

    stats = _score_local_agent(games)
    battle_log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    ranking_path.write_text(
        "agent,rank,games,wins,losses,draws,win_rate\n"
        "chess_agent,{rank},{games},{wins},{losses},{draws},{win_rate}\n".format(**stats),
        encoding="utf-8",
    )
    error_report_path.write_text(
        json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    official_report_path.write_text(
        json.dumps(
            {
                "platform": OFFICIAL_REPO_URL,
                "contract": context.contract.model_dump(),
                "source_manifest_count": len(context.source_files),
                "arena_probe": arena_probe,
                "games": games,
                "stats": stats,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return CATArenaPlatformRun(
        passed=not errors and moves_played > 0,
        context_path=str(output_dir / "catarena_context.json"),
        contract_path=str(output_dir / "catarena_contract.json"),
        manifest_path=str(output_dir / "catarena_manifest.json"),
        battle_log_path=str(battle_log_path),
        ranking_path=str(ranking_path),
        error_report_path=str(error_report_path),
        official_report_path=str(official_report_path),
        games=len(games),
        moves_played=moves_played,
        errors=errors,
    )


def _play_official_game(
    server_module: Any,
    baseline_ai: Any,
    local_color: str,
    max_plies: int,
    log_lines: List[str],
) -> Dict[str, Any]:
    client = server_module.app.test_client()
    player_white = "chess_agent" if local_color == "white" else "official_example"
    player_black = "official_example" if local_color == "white" else "chess_agent"
    create_response = client.post(
        "/games",
        json={"player_white": player_white, "player_black": player_black},
    )
    if create_response.status_code != 201:
        return {
            "local_color": local_color,
            "moves_count": 0,
            "errors": ["create game failed: %s" % create_response.get_data(as_text=True)],
        }

    game_id = create_response.get_json()["game_id"]
    errors: List[str] = []
    moves_history = []
    final_state: Dict[str, Any] = {}
    for ply in range(1, max_plies + 1):
        state_response = client.get(f"/games/{game_id}/state")
        if state_response.status_code != 200:
            errors.append("state failed: %s" % state_response.get_data(as_text=True))
            break
        state = state_response.get_json()
        final_state = state
        if state.get("game_status") != "ongoing":
            break

        player = state["current_player"]
        if player == local_color:
            details = select_move_details(state)
            move = details.selected_move
            actor = "chess_agent"
        else:
            details = None
            move = baseline_ai.find_best_move(state["fen"], "simple")
            actor = "official_example"

        board = server_module.games[game_id].board
        validation = validate_move(board, move or "")
        if not validation.is_legal or not validation.normalized_move:
            errors.append(
                "illegal move game=%s actor=%s player=%s move=%s reason=%s"
                % (game_id, actor, player, move, validation.reason)
            )
            break

        move_response = client.post(
            f"/games/{game_id}/move",
            json={"player": player, "move": validation.normalized_move},
        )
        if move_response.status_code != 200:
            errors.append("move failed: %s" % move_response.get_data(as_text=True))
            break
        new_state = move_response.get_json().get("new_state", {})
        moves_history.append(
            {
                "ply": ply,
                "player": player,
                "actor": actor,
                "move": validation.normalized_move,
                "fen_after": new_state.get("fen", ""),
                "search": (
                    {
                        "backend": details.backend,
                        "engine_config": details.engine_config,
                        "cp": details.cp,
                        "mate_distance": details.mate_distance,
                        "wdl": details.wdl,
                        "depth": details.depth,
                        "elapsed_ms": details.elapsed_ms,
                        "nodes": details.nodes,
                        "qnodes": details.qnodes,
                        "principal_variation": details.principal_variation,
                        "fallback_used": details.fallback_used,
                    }
                    if details is not None
                    else None
                ),
            }
        )
        log_lines.append(
            (
                "game_id=%s local_color=%s ply=%d player=%s actor=%s "
                "move=%s fen_after=%s backend=%s cp=%s depth=%s elapsed_ms=%s "
                "phase=%s cfg_depth=%s cfg_nodes=%s cfg_time=%s"
            )
            % (
                game_id,
                local_color,
                ply,
                player,
                actor,
                validation.normalized_move,
                new_state.get("fen", ""),
                details.backend if details is not None else "",
                details.cp if details is not None else "",
                details.depth if details is not None else "",
                round(details.elapsed_ms, 3) if details is not None else "",
                details.engine_config.get("phase", "") if details is not None else "",
                details.engine_config.get("depth_limit", "") if details is not None else "",
                details.engine_config.get("node_limit", "") if details is not None else "",
                details.engine_config.get("search_time_limit_ms", "") if details is not None else "",
            )
        )

    state_response = client.get(f"/games/{game_id}/state")
    if state_response.status_code == 200:
        final_state = state_response.get_json()
    result = _local_result(local_color, final_state.get("game_status", "ongoing"))
    log_lines.append(
        "game_id=%s result=%s status=%s final_fen=%s"
        % (game_id, result, final_state.get("game_status"), final_state.get("fen", ""))
    )
    return {
        "game_id": game_id,
        "local_color": local_color,
        "result": result,
        "status": final_state.get("game_status", "ongoing"),
        "moves_count": len(moves_history),
        "moves": moves_history,
        "final_state": final_state,
        "errors": errors,
    }


def _score_local_agent(games: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = sum(1 for game in games if game.get("result") == "win")
    losses = sum(1 for game in games if game.get("result") == "loss")
    draws = sum(1 for game in games if game.get("result") == "draw")
    game_count = len(games)
    score = wins + 0.5 * draws
    win_rate = score / game_count if game_count else 0.0
    return {
        "rank": 1 if losses == 0 else 2,
        "games": game_count,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round(win_rate, 4),
    }


def _local_result(local_color: str, game_status: str) -> str:
    if game_status == f"{local_color}_win":
        return "win"
    if game_status in {"white_win", "black_win"}:
        return "loss"
    if game_status.startswith("draw") or game_status == "ongoing":
        return "draw"
    return "draw"


def _official_contract() -> CATArenaContract:
    return CATArenaContract(
        game_server_endpoints={
            "create_game": "POST /games",
            "state": "GET /games/{game_id}/state",
            "move": "POST /games/{game_id}/move",
            "history": "GET /games/{game_id}/history",
            "board": "GET /games/{game_id}/board",
            "legal_moves": "GET /games/{game_id}/legal_moves",
            "health": "GET /health",
        },
        ai_server_endpoints={
            "health": "GET /health",
            "info": "GET /info",
            "join_game": "POST /join_game",
            "leave_game": "POST /leave_game",
            "move": "POST /move",
            "get_move": "POST /get_move",
            "legal_moves": "POST /legal_moves",
            "evaluate": "POST /evaluate",
        },
        arena_payload={
            "ai_move_request": ["fen", "algorithm", "game_id", "current_player"],
            "move_response": ["move"],
            "game_move_request": ["player", "move"],
        },
        report_files=[
            "battle.log",
            "ranking.csv",
            "error_report.json",
            "official_catarena_report.json",
            "catarena_manifest.json",
            "catarena_contract.json",
        ],
    )


def _required_chess_files() -> List[str]:
    return [
        "chessgame/README.md",
        "chessgame/README_CN.md",
        "chessgame/ChatPrompt.py",
        "chessgame/chess/server.py",
        "chessgame/chess/develop_instruction.md",
        "chessgame/chess/AI_example/ai_http_server.py",
        "chessgame/chess_Arena/arena.py",
        "chessgame/chess_Arena/config.py",
        "chessgame/chess_Arena/start_arena.py",
        "chessgame/chess_variant/server.py",
        "chessgame/chess_variant/develop_instruction.md",
        "chessgame/chess_variant/AI_example/ai_http_server.py",
    ]


def _is_required_source_file(rel_path: str) -> bool:
    return rel_path in set(_required_chess_files())


def _classify_source_file(path: Path) -> str:
    parts = set(path.parts)
    name = path.name.lower()
    if "AI_competitors" in parts:
        return "official_competitor_example"
    if "AI_example" in parts:
        return "official_ai_example"
    if "chess_Arena" in parts:
        return "official_arena"
    if name.endswith(".md") or name == "chatprompt.py":
        return "official_documentation"
    if name.endswith(".sh"):
        return "official_launcher"
    if name == "server.py":
        return "official_game_server"
    return "official_chessgame_support"


def _load_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load official CATArena module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_official_arena_probe(repo_path: Path, output_dir: Path) -> Dict[str, Any]:
    arena_dir = repo_path / "chessgame/chess_Arena"
    previous_config = sys.modules.get("config")
    sys.path.insert(0, str(arena_dir))
    try:
        config_module = _load_module(arena_dir / "config.py", "config")
        sys.modules["config"] = config_module
        arena_module = _load_module(arena_dir / "arena.py", "official_catarena_chess_arena")
        config_path = output_dir / "official_arena_config.json"
        arena_config = config_module.ArenaConfig(str(config_path))
        arena_config.config["logging"]["file"] = str(output_dir / "official_arena.log")
        arena_config.config["logging"]["console"] = False
        arena_config.config["reports"]["output_dir"] = str(output_dir)
        arena = arena_module.ChessArena(arena_config)
        return {
            "loaded": True,
            "config_file": str(config_path),
            "arena_class": arena.__class__.__name__,
            "configured_ais": len(arena.ais),
        }
    except Exception as exc:  # noqa: BLE001 - report probe failures without hiding dry-run output.
        return {"loaded": False, "error": str(exc)}
    finally:
        try:
            sys.path.remove(str(arena_dir))
        except ValueError:
            pass
        if previous_config is not None:
            sys.modules["config"] = previous_config
        else:
            sys.modules.pop("config", None)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
