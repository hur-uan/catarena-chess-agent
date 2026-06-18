"""Local paired self-play matches for strategy-profile tuning."""

from __future__ import annotations

import itertools
from typing import List, Optional

import chess
from pydantic import BaseModel, Field

from agents.engine import EngineConfig, evaluate_board, search_best_move
from tools.strategy_profile import StrategyProfile


class OpeningPosition(BaseModel):
    name: str
    fen: str


class MatchConfig(BaseModel):
    pair_count: int = 8
    time_limit_ms: int = 40
    max_plies: int = 60
    adjudication_cp: int = 250
    timeout_slack_ms: int = 5
    timeout_slack_ratio: float = 0.20
    force_internal_engine: bool = True
    openings: List[OpeningPosition] = Field(default_factory=list)

    def timeout_threshold_ms(self) -> float:
        return max(
            self.time_limit_ms + self.timeout_slack_ms,
            self.time_limit_ms * (1.0 + self.timeout_slack_ratio),
        )


class MatchGameResult(BaseModel):
    opening_name: str
    opening_fen: str
    result: str
    score_a: float
    plies: int
    adjudicated: bool = False
    player_a_color: str = "white"
    player_a_timeouts: int = 0
    player_b_timeouts: int = 0
    player_a_moves: int = 0
    player_b_moves: int = 0
    player_a_crashes: int = 0
    player_b_crashes: int = 0
    response_times_ms: List[float] = Field(default_factory=list)
    error: str = ""


class MatchSummary(BaseModel):
    games: int = 0
    wins_a: int = 0
    losses_a: int = 0
    draws: int = 0
    score_a: float = 0.0
    mean_score_a: float = 0.5
    game_scores_a: List[float] = Field(default_factory=list)
    player_a_moves: int = 0
    player_b_moves: int = 0
    player_a_timeouts: int = 0
    player_b_timeouts: int = 0
    player_a_crashes: int = 0
    player_b_crashes: int = 0
    results: List[MatchGameResult] = Field(default_factory=list)

    def timeout_rate_a(self) -> float:
        return self.player_a_timeouts / self.player_a_moves if self.player_a_moves else 0.0

    def timeout_rate_b(self) -> float:
        return self.player_b_timeouts / self.player_b_moves if self.player_b_moves else 0.0


def run_paired_match(
    profile_a: StrategyProfile,
    profile_b: StrategyProfile,
    config: Optional[MatchConfig] = None,
) -> MatchSummary:
    match_config = config or MatchConfig()
    openings = match_config.openings or default_opening_positions()
    summary = MatchSummary()
    for opening in itertools.islice(itertools.cycle(openings), match_config.pair_count):
        first = _play_game(profile_a, profile_b, opening, match_config, player_a_white=True)
        second = _play_game(profile_a, profile_b, opening, match_config, player_a_white=False)
        for game in (first, second):
            summary.games += 1
            summary.score_a += game.score_a
            summary.game_scores_a.append(game.score_a)
            summary.player_a_moves += game.player_a_moves
            summary.player_b_moves += game.player_b_moves
            summary.player_a_timeouts += game.player_a_timeouts
            summary.player_b_timeouts += game.player_b_timeouts
            summary.player_a_crashes += game.player_a_crashes
            summary.player_b_crashes += game.player_b_crashes
            if game.score_a >= 0.99:
                summary.wins_a += 1
            elif game.score_a <= 0.01:
                summary.losses_a += 1
            else:
                summary.draws += 1
            summary.results.append(game)
    if summary.games:
        summary.mean_score_a = summary.score_a / summary.games
    return summary


def default_opening_positions() -> List[OpeningPosition]:
    sequences = [
        ("startpos", []),
        ("queens_pawn", ["d2d4", "d7d5"]),
        ("ruy_lopez", ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5"]),
        ("italian_game", ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"]),
        ("sicilian", ["e2e4", "c7c5", "g1f3", "d7d6"]),
        ("french", ["e2e4", "e7e6", "d2d4", "d7d5"]),
        ("caro_kann", ["e2e4", "c7c6", "d2d4", "d7d5"]),
        ("queens_gambit", ["d2d4", "d7d5", "c2c4"]),
        ("english", ["c2c4", "e7e5", "b1c3", "g8f6"]),
        ("kings_indian", ["d2d4", "g8f6", "c2c4", "g7g6", "b1c3", "f8g7"]),
        ("scandinavian", ["e2e4", "d7d5", "e4d5", "d8d5", "b1c3"]),
        ("slav", ["d2d4", "d7d5", "c2c4", "c7c6"]),
    ]
    positions: List[OpeningPosition] = []
    for name, moves in sequences:
        board = chess.Board()
        for move in moves:
            board.push_uci(move)
        positions.append(OpeningPosition(name=name, fen=board.fen()))
    positions.extend(
        [
            OpeningPosition(
                name="sharp_midgame_a",
                fen="r2q1k1r/2pnppb1/pp4pn/3N2Np/3P2bP/4B1P1/PPP1PPB1/R2Q1RK1 w - - 0 11",
            ),
            OpeningPosition(
                name="sharp_midgame_b",
                fen="r1bq1rk1/pp1n1pbp/2pp1np1/4p3/2PPP3/2N1BN1P/PPQ2PP1/R3KB1R w KQ - 2 9",
            ),
            OpeningPosition(
                name="queenside_tension",
                fen="2r2rk1/pp1q1ppp/2n1pn2/2bp4/3P4/2NBPN2/PPQ2PPP/2RR2K1 w - - 0 12",
            ),
        ]
    )
    return positions


def _play_game(
    profile_a: StrategyProfile,
    profile_b: StrategyProfile,
    opening: OpeningPosition,
    config: MatchConfig,
    player_a_white: bool,
) -> MatchGameResult:
    board = chess.Board(opening.fen)
    white_profile = _prepared_profile(profile_a if player_a_white else profile_b, config)
    black_profile = _prepared_profile(profile_b if player_a_white else profile_a, config)
    white_engine = EngineConfig(strategy_profile=white_profile)
    black_engine = EngineConfig(strategy_profile=black_profile)
    player_a_moves = 0
    player_b_moves = 0
    player_a_timeouts = 0
    player_b_timeouts = 0
    response_times_ms: List[float] = []

    for ply in range(config.max_plies):
        if board.is_game_over(claim_draw=True):
            break
        active_engine = white_engine if board.turn == chess.WHITE else black_engine
        player_is_a = player_a_white if board.turn == chess.WHITE else not player_a_white
        try:
            result = search_best_move(
                board,
                time_limit_ms=config.time_limit_ms,
                config=active_engine,
            )
        except Exception as exc:  # pragma: no cover - defensive
            return MatchGameResult(
                opening_name=opening.name,
                opening_fen=opening.fen,
                result="crash",
                score_a=0.0 if player_is_a else 1.0,
                plies=ply,
                player_a_color="white" if player_a_white else "black",
                player_a_moves=player_a_moves,
                player_b_moves=player_b_moves,
                player_a_crashes=1 if player_is_a else 0,
                player_b_crashes=0 if player_is_a else 1,
                response_times_ms=response_times_ms,
                error=str(exc),
            )
        response_times_ms.append(float(result.stats.elapsed_ms))
        if player_is_a:
            player_a_moves += 1
            if result.stats.elapsed_ms > config.timeout_threshold_ms():
                player_a_timeouts += 1
        else:
            player_b_moves += 1
            if result.stats.elapsed_ms > config.timeout_threshold_ms():
                player_b_timeouts += 1
        if result.move is None or result.move not in board.legal_moves:
            return MatchGameResult(
                opening_name=opening.name,
                opening_fen=opening.fen,
                result="illegal",
                score_a=0.0 if player_is_a else 1.0,
                plies=ply,
                player_a_color="white" if player_a_white else "black",
                player_a_moves=player_a_moves,
                player_b_moves=player_b_moves,
                player_a_timeouts=player_a_timeouts,
                player_b_timeouts=player_b_timeouts,
                response_times_ms=response_times_ms,
                error="engine returned no legal move",
            )
        board.push(result.move)

    adjudicated = False
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        adjudicated = True
        result_name, score_a = _adjudicate(
            board,
            white_profile,
            black_profile,
            player_a_white,
            config,
        )
    else:
        result_name, score_a = _score_from_outcome(outcome, player_a_white)
    return MatchGameResult(
        opening_name=opening.name,
        opening_fen=opening.fen,
        result=result_name,
        score_a=score_a,
        plies=len(board.move_stack),
        adjudicated=adjudicated,
        player_a_color="white" if player_a_white else "black",
        player_a_moves=player_a_moves,
        player_b_moves=player_b_moves,
        player_a_timeouts=player_a_timeouts,
        player_b_timeouts=player_b_timeouts,
        response_times_ms=response_times_ms,
    )


def _prepared_profile(profile: StrategyProfile, config: MatchConfig) -> StrategyProfile:
    if not config.force_internal_engine:
        return profile
    payload = profile.model_dump()
    payload["external_engine"]["enabled"] = False
    return StrategyProfile.model_validate(payload)


def _score_from_outcome(outcome: chess.Outcome, player_a_white: bool) -> tuple[str, float]:
    winner = outcome.winner
    if winner is None:
        return "draw", 0.5
    if winner == player_a_white:
        return "win", 1.0
    return "loss", 0.0


def _adjudicate(
    board: chess.Board,
    white_profile: StrategyProfile,
    black_profile: StrategyProfile,
    player_a_white: bool,
    config: MatchConfig,
) -> tuple[str, float]:
    white_view = evaluate_board(board, chess.WHITE, white_profile)
    black_view = evaluate_board(board, chess.BLACK, black_profile)
    combined = (white_view - black_view) / 2.0
    if combined >= config.adjudication_cp:
        white_score = 1.0
    elif combined <= -config.adjudication_cp:
        white_score = 0.0
    else:
        white_score = 0.5
    if white_score == 0.5:
        return "draw", 0.5
    if player_a_white:
        return ("win", 1.0) if white_score > 0.5 else ("loss", 0.0)
    return ("loss", 0.0) if white_score > 0.5 else ("win", 1.0)
