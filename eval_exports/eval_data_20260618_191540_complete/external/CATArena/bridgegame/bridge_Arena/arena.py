#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import time
import json
import logging
import threading
import csv
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import signal
import sys
import os
from collections import defaultdict

_log_ctx = threading.local()

class ResponseTimeTracker:
    """跟踪每个AI的响应时间统计"""
    def __init__(self):
        self._lock = threading.Lock()
        self._response_times = defaultdict(list)  # ai_name -> [response_times]
        self._total_requests = defaultdict(int)   # ai_name -> count
        self._last_log_time = time.time()
        self._log_interval = 60  # 每60秒输出一次统计
    
    def record_response_time(self, ai_name: str, response_time: float):
        """记录AI的响应时间"""
        with self._lock:
            self._response_times[ai_name].append(response_time)
            self._total_requests[ai_name] += 1
            
            # 定期输出统计信息
            current_time = time.time()
            if current_time - self._last_log_time >= self._log_interval:
                self._log_statistics()
                self._last_log_time = current_time
    
    def _log_statistics(self):
        """输出响应时间统计信息"""
        if not self._response_times:
            return
            
        logger.info("=== AI响应时间统计 ===")
        for ai_name in sorted(self._response_times.keys()):
            times = self._response_times[ai_name]
            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                total_requests = self._total_requests[ai_name]
                logger.info(f"AI {ai_name}: 总请求={total_requests}, 平均={avg_time:.6f}s, 最小={min_time:.6f}s, 最大={max_time:.6f}s")
        logger.info("========================")
    
    def get_statistics(self) -> Dict[str, float]:
        """获取所有AI的平均响应时间统计（按模型分组）"""
        with self._lock:
            model_stats = {}
            for ai_name in self._response_times.keys():
                times = self._response_times[ai_name]
                if times:
                    # 提取模型名称（去掉位置信息）
                    model_name = ai_name.split(' (')[0]  # 去掉 (North) 或 (South)
                    
                    avg_time = sum(times) / len(times)
                    total_requests = self._total_requests[ai_name]
                    
                    if model_name in model_stats:
                        # 如果模型已存在，计算加权平均
                        old_total = model_stats[model_name]['total_requests']
                        old_avg = model_stats[model_name]['avg_time']
                        new_total = old_total + total_requests
                        new_avg = (old_avg * old_total + avg_time * total_requests) / new_total
                        model_stats[model_name] = {
                            'avg_time': new_avg,
                            'total_requests': new_total
                        }
                    else:
                        model_stats[model_name] = {
                            'avg_time': avg_time,
                            'total_requests': total_requests
                        }
            return model_stats
    
    def force_log_statistics(self):
        """强制输出当前统计信息"""
        self._log_statistics()

# 全局响应时间跟踪器
response_time_tracker = ResponseTimeTracker()

class SafeExtraFormatter(logging.Formatter):
    """Formatter that safely injects missing extra fields used in format string."""
    def format(self, record):
        for k in ("match_id", "game_id", "room"):
            if not hasattr(record, k):
                setattr(record, k, "-")
        return super().format(record)

class ContextFilter(logging.Filter):
    """Populate log record with thread-local context (match_id, game_id, room)."""
    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "match_id", getattr(_log_ctx, "match_id", "-"))
        setattr(record, "game_id", getattr(_log_ctx, "game_id", "-"))
        setattr(record, "room", getattr(_log_ctx, "room", "-"))
        return True

def set_log_context(match_id: Optional[str] = None, game_id: Optional[str] = None, room: Optional[str] = None):
    """Set thread-local logging context; only non-None values will update."""
    if match_id is not None:
        _log_ctx.match_id = match_id
    if game_id is not None:
        _log_ctx.game_id = game_id
    if room is not None:
        _log_ctx.room = room

# Configure logging
def setup_logging(log_file: str = "logs/arena.log"):
    """Setup logging configuration with contextual, thread-safe formatting."""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if setup called multiple times
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        stream_handler = logging.StreamHandler()

        fmt = '%(asctime)s - %(levelname)s - [%(threadName)s] [match:%(match_id)s game:%(game_id)s room:%(room)s] %(message)s'
        formatter = SafeExtraFormatter(fmt)
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        context_filter = ContextFilter()
        file_handler.addFilter(context_filter)
        stream_handler.addFilter(context_filter)

        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)

    return logger

logger = setup_logging()

@dataclass
class AIConfig:
    """AI configuration information"""
    ai_id: str
    ai_name: str
    port: int
    url: str

@dataclass
class TeamConfig:
    """Team configuration for bridge (2v2)"""
    team_id: str
    team_name: str
    player1: AIConfig
    player2: AIConfig

@dataclass
class GameResult:
    """Single game result"""
    game_id: str
    team_ns: str  # North-South team
    team_ew: str  # East-West team
    winner: Optional[str]  # None for tie
    ns_score: int
    ew_score: int
    game_duration: float
    end_reason: str  # "win", "draw", "timeout", "error"
    bidding_history: List[Dict]
    tricks_history: List[Dict]
    game_history: Optional[Dict] = None  # 游戏历史信息
    final_state: Optional[Dict] = None   # 最终游戏状态

class BridgeArena:
    """Bridge AI tournament platform"""
    
    def __init__(self, game_server_url: str = "http://localhost:50000", timeout: int = 10, rounds_per_match: int = 2, boards_per_match: int = 4):
        self.game_server_url = game_server_url
        self.timeout = timeout
        self.rounds_per_match = rounds_per_match
        self.boards_per_match = boards_per_match
        self.teams: List[TeamConfig] = []
        self.results: List[GameResult] = []
        self.tournament_id = None
        self.session_id: Optional[str] = None
        self.standings: Dict[str, Dict] = {}
        self.max_parallel_matches: int = 3

    # ---------------------- Per-action JSON logging ----------------------
    def _event_log_path(self, game_id: str) -> str:
        base = os.path.join('logs', 'games')
        # Place events under session folder if available
        if self.session_id:
            d = os.path.join(base, str(self.session_id))
        else:
            d = base
        os.makedirs(d, exist_ok=True)
        # Use .json extension as requested
        return os.path.join(d, f"{game_id}.json")

    def _log_action_event(self, game_id: str, event_type: str, payload: Dict):
        try:
            evt = {
                "ts": datetime.utcnow().isoformat() + "Z",
                "event": event_type,
                "match_id": getattr(_log_ctx, 'match_id', '-'),
                "room": getattr(_log_ctx, 'room', '-'),
                "game_id": game_id,
            }
            evt.update(payload or {})
            path = self._event_log_path(game_id)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(evt, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write action event: {e}")
        
    def add_ai(self, ai_id: str, ai_name: str, port: int):
        """Add AI to tournament platform"""
        ai_config = AIConfig(
            ai_id=ai_id,
            ai_name=ai_name,
            port=port,
            url=f"http://localhost:{port}"
        )
        logger.info(f"Added AI: {ai_name} (ID: {ai_id}, Port: {port})")
        return ai_config
        
    def create_team(self, team_id: str, team_name: str, ai1: AIConfig, ai2: AIConfig):
        """Create a team with two AIs"""
        team = TeamConfig(
            team_id=team_id,
            team_name=team_name,
            player1=ai1,
            player2=ai2
        )
        self.teams.append(team)
        logger.info(f"Created team: {team_name} (ID: {team_id}) with {ai1.ai_name} and {ai2.ai_name}")
        
    def create_duplicate_team(self, ai: AIConfig, team_id: str = None, team_name: str = None):
        """Create a team by duplicating one AI (AA vs BB format)"""
        if team_id is None:
            team_id = f"{ai.ai_id}_duplicate"
        if team_name is None:
            team_name = f"{ai.ai_name} Duplicate"
            
        # Create duplicate AI configs. Use separate ports to support AIs that
        # run single-seat per process (e.g., AI_example). Second seat defaults to port+1.
        ai1 = AIConfig(
            ai_id=f"{ai.ai_id}_1",
            ai_name=f"{ai.ai_name} (North)",
            port=ai.port,
            url=ai.url
        )
        ai2 = AIConfig(
            ai_id=f"{ai.ai_id}_2", 
            ai_name=f"{ai.ai_name} (South)",
            port=ai.port + 1,
            url=f"http://localhost:{ai.port + 1}"
        )
        
        team = TeamConfig(
            team_id=team_id,
            team_name=team_name,
            player1=ai1,
            player2=ai2
        )
        self.teams.append(team)
        logger.info(f"Created duplicate team: {team_name} (ID: {team_id}) with {ai.ai_name} duplicated")
        return team
        
    def check_ai_health(self, ai_config: AIConfig) -> bool:
        """Check AI service health status"""
        try:
            response = requests.get(f"{ai_config.url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('status') in ['healthy', 'ok'] 
        except Exception as e:
            logger.warning(f"AI {ai_config.ai_name} health check failed: {e}")
        return False
    
    def _get_game_history(self, game_id: str) -> Optional[Dict]:
        """获取游戏历史信息"""
        try:
            response = requests.get(f"{self.game_server_url}/games/{game_id}/history", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get game history: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting game history: {e}")
            return None
    
    def _get_game_state(self, game_id: str, player_id: int = 0) -> Optional[Dict]:
        """获取游戏状态信息"""
        try:
            response = requests.get(f"{self.game_server_url}/games/{game_id}/state?player_id={player_id}", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get game state: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting game state: {e}")
            return None
        
    def join_ai_to_game(self, ai_config: AIConfig, game_id: str, position: str) -> bool:
        """Let AI join the game

        Align with AI_example: Arena calls AI `/join_game` with { game_id, player_id }.
        The AI will join the game server and cache active_games. Arena won't
        directly call the game server /join unless AI is unreachable.
        """
        # Map position to player_id (server order is N=0, E=1, S=2, W=3)
        position_to_id = {"north": 0, "east": 1, "south": 2, "west": 3}
        player_id = position_to_id.get(position, 0)

        # Preferred: notify AI to join (many AIs expect to manage their own active_games)
        ai_join_payload = {"game_id": game_id, "player_id": player_id}

        # Step 1: ask AI to join (best-effort, with a compatibility retry)
        try:
            ai_resp = requests.post(f"{ai_config.url}/join_game", json=ai_join_payload, timeout=5)
            if ai_resp.status_code == 200:
                logger.debug(f"AI {ai_config.ai_name} acknowledged join for {game_id} as {position} (player_id: {player_id})")
            else:
                logger.warning(f"AI {ai_config.ai_name} /join_game returned {ai_resp.status_code}: {ai_resp.text}")
                # Compatibility retry: some AIs only read form/query instead of JSON
                if ai_resp.status_code == 400 and isinstance(ai_resp.text, str) and 'Missing' in ai_resp.text:
                    try:
                        from requests.utils import quote
                        alt_url = f"{ai_config.url}/join_game?game_id={quote(str(game_id))}&player_id={player_id}&player_name={quote(ai_config.ai_name)}"
                        ai_resp2 = requests.post(alt_url, data=ai_join_payload, timeout=5)
                        if ai_resp2.status_code == 200:
                            logger.debug(f"AI {ai_config.ai_name} join retry (form/query) succeeded for {game_id}")
                        else:
                            logger.warning(f"AI {ai_config.ai_name} join retry still failed: {ai_resp2.status_code}: {ai_resp2.text}")
                    except Exception as re:
                        logger.warning(f"AI {ai_config.ai_name} join retry error: {re}")
        except Exception as e:
            logger.warning(f"AI {ai_config.ai_name} /join_game error: {e}.")

        # Ensure the seat is joined on the game server as a fallback
        try:
            payload = {"player_id": player_id, "player_name": ai_config.ai_name}
            gs_resp = requests.post(f"{self.game_server_url}/games/{game_id}/join", json=payload, timeout=5)
            if gs_resp.status_code != 200:
                logger.warning(f"Fallback join to game server failed for {ai_config.ai_name} (seat {position}, id {player_id}): {gs_resp.status_code} - {gs_resp.text}")
        except Exception as e:
            logger.warning(f"Fallback join error for {ai_config.ai_name} at {position}: {e}")

        return True
    
    def get_ai_action(self, ai_config: AIConfig, game_id: str, game_state: Dict, position: str) -> Tuple[Optional[Dict], float]:
        """Get AI action (bid or play card)

        Request payload strictly follows develop_instruction.md:
        {
          "game_id": str,
          "player_id": int,
          "position": "north|east|south|west",
          "game_state": {...},
          "legal_actions": [...]
        }

        Response supports the dev-guide format primarily:
        {
          "action": {...},
          "ai_id": str,
          "game_id": str,
          "reasoning": str
        }
        For backward compatibility, a raw action object is also accepted.
        """
        try:
            start_time = time.time()
            
            # Map position to player_id (server order is N=0, E=1, S=2, W=3)
            position_to_id = {"north": 0, "east": 1, "south": 2, "west": 3}
            player_id = position_to_id.get(position, 0)

            # Attempt to fetch legal actions for this player to help AIs that expect them in request
            legal_actions: List[Dict] = []
            try:
                la_resp = requests.get(f"{self.game_server_url}/games/{game_id}/legal_actions?player_id={player_id}", timeout=5)
                if la_resp.status_code == 200:
                    legal_actions = la_resp.json().get('legal_actions', [])
            except Exception:
                pass

            # Primary payload: include player_id, position, and legal_actions for compatibility
            action_data = {
                "game_id": game_id,
                "player_id": player_id,
                "position": position,
                "game_state": game_state,
                "legal_actions": legal_actions,
            }
            
            logger.info(f"Requesting action from {ai_config.ai_name}")
            response = requests.post(f"{ai_config.url}/get_action", json=action_data, timeout=self.timeout)
            thinking_time = time.time() - start_time
            
            if response.status_code == 200:
                data = None
                try:
                    data = response.json()
                except Exception:
                    data = None

                action: Optional[Dict] = None
                reasoning: Optional[str] = None
                if isinstance(data, dict):
                    # Primary: dev-guide format with explicit action wrapper
                    if 'action' in data and isinstance(data['action'], dict):
                        action = data['action']
                        reasoning = data.get('reasoning')
                        # Log ai_id/game_id if present for traceability
                        if data.get('ai_id'):
                            logger.debug(f"AI meta: ai_id={data.get('ai_id')}, game_id={data.get('game_id')}")
                    else:
                        # Backward compat: entire payload might be an action object
                        if 'type' in data:
                            action = data
                elif isinstance(data, list):
                    # Unexpected list payload; not supported
                    action = None

                if action:
                    # 记录响应时间到统计跟踪器
                    response_time_tracker.record_response_time(ai_config.ai_name, thinking_time)
                    
                    if reasoning:
                        logger.info(f"AI {ai_config.ai_name} responded in {thinking_time:.2f}s, reasoning: {reasoning}")
                    else:
                        logger.info(f"AI {ai_config.ai_name} responded in {thinking_time:.2f}s")
                    return action, thinking_time
                else:
                    # 记录响应时间到统计跟踪器（即使返回无效动作）
                    response_time_tracker.record_response_time(ai_config.ai_name, thinking_time)
                    logger.error(f"AI {ai_config.ai_name} returned invalid action payload: {data}")
                    return None, thinking_time
            else:
                # Fallback: try minimal payload (older AIs expect to fetch legal actions themselves)
                logger.error(f"AI {ai_config.ai_name} action request failed: {response.status_code} - {response.text}")
                try:
                    minimal_payload = {"game_id": game_id, "game_state": game_state}
                    response2 = requests.post(f"{ai_config.url}/get_action", json=minimal_payload, timeout=self.timeout)
                    if response2.status_code == 200:
                        data = response2.json()
                        action = data.get('action') if isinstance(data, dict) and 'action' in data else (data if isinstance(data, dict) else None)
                        if action:
                            # 记录响应时间到统计跟踪器
                            response_time_tracker.record_response_time(ai_config.ai_name, thinking_time)
                            return action, thinking_time
                except Exception:
                    pass
                # 记录响应时间到统计跟踪器（fallback失败）
                response_time_tracker.record_response_time(ai_config.ai_name, thinking_time)
                return None, thinking_time
                
        except TimeoutError:
            # 记录超时时间到统计跟踪器
            response_time_tracker.record_response_time(ai_config.ai_name, self.timeout)
            logger.error(f"AI {ai_config.ai_name} action timeout")
            return None, self.timeout
        except Exception as e:
            # 记录异常情况下的响应时间（设为0表示立即失败）
            response_time_tracker.record_response_time(ai_config.ai_name, 0)
            logger.error(f"AI {ai_config.ai_name} action error: {e}")
            return None, 0
    
    def play_game(self, team_ns: TeamConfig, team_ew: TeamConfig, init_params: Optional[Dict] = None, context: Optional[Dict] = None) -> GameResult:
        """Play a bridge game between two teams"""
        # Initialize thread-local log context
        ctx = context or {}
        set_log_context(match_id=ctx.get('match_id'), room=ctx.get('room'))
        game_id = f"game_{int(time.time())}_{team_ns.team_id}_vs_{team_ew.team_id}"
        logger.info(f"Starting game: {game_id}")
        logger.info(f"NS Team: {team_ns.team_name} vs EW Team: {team_ew.team_name}")
        
        # Create game
        try:
            response = requests.post(f"{self.game_server_url}/games", json=(init_params or {}), timeout=5)
            if response.status_code not in [200, 201]:
                logger.error(f"Failed to create game: {response.status_code}")
                return GameResult(
                    game_id=game_id,
                    team_ns=team_ns.team_id,
                    team_ew=team_ew.team_id,
                    winner=team_ew.team_id,  # EW wins by default
                    ns_score=0,
                    ew_score=100,
                    game_duration=0,
                    end_reason="error",
                    bidding_history=[],
                    tricks_history=[],
                    game_history=None,
                    final_state=None
                )
            
            # Get the actual game ID from response
            game_data = response.json()
            actual_game_id = game_data.get('game_id', game_id)
            # Update context with the actual game_id
            set_log_context(game_id=actual_game_id)
            logger.info(f"Created game with ID: {actual_game_id}")
            
        except Exception as e:
            logger.error(f"Create game error: {e}")
            return GameResult(
                game_id=game_id,
                team_ns=team_ns.team_id,
                team_ew=team_ew.team_id,
                winner=team_ew.team_id,
                ns_score=0,
                ew_score=100,
                game_duration=0,
                end_reason="error",
                bidding_history=[],
                tricks_history=[],
                game_history=None,
                final_state=None
            )
        
        # Join AIs to game
        positions = [
            (team_ns.player1, "north"),
            (team_ns.player2, "south"), 
            (team_ew.player1, "east"),
            (team_ew.player2, "west")
        ]
        
        for ai, position in positions:
            if not self.join_ai_to_game(ai, actual_game_id, position):
                logger.error(f"AI {ai.ai_name} failed to join game")
                winner = team_ew.team_id if position in ["north", "south"] else team_ns.team_id
                return GameResult(
                    game_id=game_id,
                    team_ns=team_ns.team_id,
                    team_ew=team_ew.team_id,
                    winner=winner,
                    ns_score=100 if winner == team_ns.team_id else 0,
                    ew_score=100 if winner == team_ew.team_id else 0,
                    game_duration=0,
                    end_reason="error",
                    bidding_history=[],
                    tricks_history=[],
                    game_history=None,
                    final_state=None
                )
        
        logger.info(f"AIs joined game successfully, starting match")
        logger.info("=" * 50)
        
        # Start the game
        try:
            response = requests.post(f"{self.game_server_url}/games/{actual_game_id}/start", timeout=5)
            if response.status_code != 200:
                logger.error(f"Failed to start game: {response.status_code}")
                return GameResult(
                    game_id=actual_game_id,
                    team_ns=team_ns.team_id,
                    team_ew=team_ew.team_id,
                    winner=team_ew.team_id,
                    ns_score=0,
                    ew_score=100,
                    game_duration=0,
                    end_reason="error",
                    bidding_history=[],
                    tricks_history=[],
                    game_history=None,
                    final_state=None
                )
        except Exception as e:
            logger.error(f"Start game error: {e}")
            return GameResult(
                game_id=actual_game_id,
                team_ns=team_ns.team_id,
                team_ew=team_ew.team_id,
                winner=team_ew.team_id,
                ns_score=0,
                ew_score=100,
                game_duration=0,
                end_reason="error",
                bidding_history=[],
                tricks_history=[],
                game_history=None,
                final_state=None
            )
        
        game_start_time = time.time()
        bidding_history = []
        tricks_history = []
        
        # Game loop
        while True:
            try:
                # Get a quick state snapshot to learn whose turn it is
                response_snap = requests.get(f"{self.game_server_url}/games/{actual_game_id}/state?player_id=0")
                if response_snap.status_code != 200:
                    logger.error(f"Failed to get game state snapshot: {response_snap.status_code}")
                    break

                snap = response_snap.json()
                phase = snap.get('phase', 'unknown')
                
                logger.info(f"Game phase: {phase}, current player: {snap.get('current_player_id', 0)}")

                # Magic server exchanging phase support
                if phase == 'exchanging':
                    try:
                        # Fetch suit order for logging (also present in state for magic server)
                        try:
                            resp_so = requests.get(f"{self.game_server_url}/games/{actual_game_id}/suit_order", timeout=3)
                            if resp_so.status_code == 200:
                                logger.info(f"Suit order: {resp_so.json().get('suit_order')}")
                        except Exception:
                            pass
                        # For each seat, check if it still needs to exchange and ask its AI
                        pid_by_pos = {"north": 0, "east": 1, "south": 2, "west": 3}
                        for ai, pos in positions:
                            pid = pid_by_pos[pos]
                            la = requests.get(f"{self.game_server_url}/games/{actual_game_id}/legal_actions?player_id={pid}", timeout=5)
                            if la.status_code != 200:
                                continue
                            legal_actions = la.json().get('legal_actions', [])
                            if not any(a.get('type') == 'exchange' for a in legal_actions):
                                continue
                            # Fetch state from the player's perspective
                            st_resp = requests.get(f"{self.game_server_url}/games/{actual_game_id}/state?player_id={pid}", timeout=5)
                            if st_resp.status_code != 200:
                                continue
                            state_for_ai = st_resp.json()
                            # Ask AI for exchange action
                            action, thinking_time = self.get_ai_action(ai, actual_game_id, state_for_ai, pos)
                            # Forfeit immediately if AI fails to provide a valid exchange action
                            if action is None or action.get('type') != 'exchange' or 'card' not in action:
                                winner = team_ew.team_id if pos in ["north", "south"] else team_ns.team_id
                                game_duration = time.time() - game_start_time
                                game_history = self._get_game_history(actual_game_id)
                                final_state = self._get_game_state(actual_game_id, 0)
                                logger.error(f"{ai.ai_name} at {pos} failed to provide exchange action; forfeit.")
                                return GameResult(
                                    game_id=game_id,
                                    team_ns=team_ns.team_id,
                                    team_ew=team_ew.team_id,
                                    winner=winner,
                                    ns_score=100 if winner == team_ns.team_id else 0,
                                    ew_score=100 if winner == team_ew.team_id else 0,
                                    game_duration=game_duration,
                                    end_reason="forfeit_exchange",
                                    bidding_history=bidding_history,
                                    tricks_history=tricks_history,
                                    game_history=game_history,
                                    final_state=final_state
                                )
                            payload = {"player_id": pid, "card": action['card']}
                            rr = requests.post(f"{self.game_server_url}/games/{actual_game_id}/exchange", json=payload, timeout=5)
                            if rr.status_code == 200:
                                logger.info(f"Exchange submitted by {ai.ai_name} ({pos}): {action['card']}")
                            else:
                                winner = team_ew.team_id if pos in ["north", "south"] else team_ns.team_id
                                game_duration = time.time() - game_start_time
                                game_history = self._get_game_history(actual_game_id)
                                final_state = self._get_game_state(actual_game_id, 0)
                                logger.error(f"Exchange submit failed for {pos}: {rr.status_code} - {rr.text}; forfeit.")
                                return GameResult(
                                    game_id=game_id,
                                    team_ns=team_ns.team_id,
                                    team_ew=team_ew.team_id,
                                    winner=winner,
                                    ns_score=100 if winner == team_ns.team_id else 0,
                                    ew_score=100 if winner == team_ew.team_id else 0,
                                    game_duration=game_duration,
                                    end_reason="forfeit_exchange",
                                    bidding_history=bidding_history,
                                    tricks_history=tricks_history,
                                    game_history=game_history,
                                    final_state=final_state
                                )
                        # Attempt to execute exchanges if partnerships are ready
                        er = requests.post(f"{self.game_server_url}/games/{actual_game_id}/execute_exchange", timeout=5)
                        if er.status_code == 200:
                            logger.info(f"Execute exchange: {er.json().get('message')}")
                        time.sleep(0.2)
                        continue
                    except Exception as e:
                        logger.error(f"Exchanging phase error: {e}")
                        break
                
                if phase == 'finished':
                    # Game finished
                    # Use the latest snapshot retrieved above
                    final_score = snap.get('score', [0, 0])
                    ns_score = final_score[0]
                    ew_score = final_score[1]
                    
                    winner = None
                    if ns_score > ew_score:
                        winner = team_ns.team_id
                    elif ew_score > ns_score:
                        winner = team_ew.team_id
                    
                    game_duration = time.time() - game_start_time
                    
                    # 获取游戏历史和最终状态
                    game_history = self._get_game_history(actual_game_id)
                    final_state = self._get_game_state(actual_game_id, 0)
                    
                    result = GameResult(
                        game_id=game_id,
                        team_ns=team_ns.team_id,
                        team_ew=team_ew.team_id,
                        winner=winner,
                        ns_score=ns_score,
                        ew_score=ew_score,
                        game_duration=game_duration,
                        end_reason="win",
                        bidding_history=bidding_history,
                        tricks_history=tricks_history,
                        game_history=game_history,
                        final_state=final_state
                    )
                    
                    logger.info("=" * 50)
                    logger.info(f"Game finished: {game_id} - Winner: {winner or 'Tie'} | Score NS {ns_score} - EW {ew_score}")
                    return result
                
                # Get current player info
                current_player_id = snap.get('current_player_id', 0)
                current_position = ["north", "east", "south", "west"][current_player_id]
                current_ai = None
                
                # Find current AI
                for ai, pos in positions:
                    if pos == current_position:
                        current_ai = ai
                        break
                
                if current_ai is None:
                    logger.error(f"Could not find AI for position {current_position}")
                    break
                
                logger.info(f"Current AI: {current_ai.ai_name} at position {current_position}")
                
                # Fetch state from the current player's perspective, so AI sees its own hand
                st_resp = requests.get(f"{self.game_server_url}/games/{actual_game_id}/state?player_id={current_player_id}", timeout=5)
                if st_resp.status_code != 200:
                    logger.error(f"Failed to get player {current_player_id} view of state: {st_resp.status_code}")
                    break
                state_for_ai = st_resp.json()
                # Get AI action
                action, thinking_time = self.get_ai_action(current_ai, actual_game_id, state_for_ai, current_position)
                
                if action is None:
                    # AI timeout or error, opponent wins
                    winner = team_ew.team_id if current_position in ["north", "south"] else team_ns.team_id
                    game_duration = time.time() - game_start_time
                    
                    # 获取游戏历史和最终状态
                    game_history = self._get_game_history(actual_game_id)
                    final_state = self._get_game_state(actual_game_id, 0)
                    
                    result = GameResult(
                        game_id=game_id,
                        team_ns=team_ns.team_id,
                        team_ew=team_ew.team_id,
                        winner=winner,
                        ns_score=100 if winner == team_ns.team_id else 0,
                        ew_score=100 if winner == team_ew.team_id else 0,
                        game_duration=game_duration,
                        end_reason="timeout",
                        bidding_history=bidding_history,
                        tricks_history=tricks_history,
                        game_history=game_history,
                        final_state=final_state
                    )
                    
                    logger.info(f"Game ended: {game_id} - {current_ai.ai_name} timeout, {winner} wins")
                    return result
                
                logger.info(f"AI {current_ai.ai_name} action: {action}")
                
                # Submit action to game server
                if phase == 'bidding':
                    # Add player_id to action
                    action_with_player = action.copy()
                    action_with_player['player_id'] = current_player_id
                    logger.info(f"Submitting bidding action: {action.get('call_type', 'unknown')}")
                    response = requests.post(f"{self.game_server_url}/games/{actual_game_id}/call", json=action_with_player, timeout=5)
                    if response.status_code == 200:
                        bidding_history.append(action)
                        logger.info(f"Bidding action successful")
                        # Write bid event to JSONL
                        self._log_action_event(actual_game_id, "bid", {
                            "player_id": current_player_id,
                            "position": current_position,
                            "ai_id": getattr(current_ai, 'ai_id', None),
                            "ai_name": getattr(current_ai, 'ai_name', None),
                            "action": action,
                        })
                    else:
                        logger.error(f"Bidding action failed: {response.status_code} - {response.text}")
                elif phase == 'exchanging':
                    # Magic Bridge exchanging phase: request partner card exchange
                    action_with_player = action.copy()
                    action_with_player['player_id'] = current_player_id
                    logger.info(f"Submitting exchange request: {action.get('card', 'unknown')}")
                    # Submit exchange request
                    response = requests.post(
                        f"{self.game_server_url}/games/{actual_game_id}/exchange",
                        json=action_with_player,
                        timeout=5,
                    )
                    if response.status_code == 200:
                        logger.info("Exchange request accepted")
                        # Write exchange event to JSONL
                        self._log_action_event(
                            actual_game_id,
                            "exchange",
                            {
                                "player_id": current_player_id,
                                "position": current_position,
                                "ai_id": getattr(current_ai, 'ai_id', None),
                                "ai_name": getattr(current_ai, 'ai_name', None),
                                "action": action,
                            },
                        )
                        # Best-effort trigger of partnership exchange if ready (server is allowed to auto-execute)
                        try:
                            requests.post(
                                f"{self.game_server_url}/games/{actual_game_id}/execute_exchange",
                                json={"player_id": current_player_id},
                                timeout=3,
                            )
                        except Exception:
                            pass
                    else:
                        logger.error(f"Exchange request failed: {response.status_code} - {response.text}")
                elif phase == 'playing':
                    # Add player_id to action
                    action_with_player = action.copy()
                    action_with_player['player_id'] = current_player_id
                    logger.info(f"Submitting playing action: {action.get('card', 'unknown')}")
                    response = requests.post(f"{self.game_server_url}/games/{actual_game_id}/play", json=action_with_player, timeout=5)
                    if response.status_code == 200:
                        # Check if trick is complete
                        trick_data = response.json()
                        logger.info(f"Playing action successful")
                        # Write play event to JSONL
                        self._log_action_event(actual_game_id, "play", {
                            "player_id": current_player_id,
                            "position": current_position,
                            "ai_id": getattr(current_ai, 'ai_id', None),
                            "ai_name": getattr(current_ai, 'ai_name', None),
                            "action": action,
                            "trick_complete": trick_data.get('trick_complete'),
                            "trick": trick_data.get('trick'),
                        })
                        if trick_data.get('trick_complete'):
                            tricks_history.append(trick_data.get('trick', []))
                            logger.info(f"Trick completed")
                    else:
                        logger.error(f"Playing action failed: {response.status_code} - {response.text}")
                else:
                    logger.warning(f"Unknown phase: {phase}")
                    break
                
                if response.status_code != 200:
                    logger.error(f"Action submission failed: {response.status_code} - {response.text}")
                    break
                
                # Brief pause
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Game loop error: {e}")
                break
        
        # Error ending
        game_duration = time.time() - game_start_time
        
        # 获取游戏历史和最终状态
        game_history = self._get_game_history(actual_game_id)
        final_state = self._get_game_state(actual_game_id, 0)
        
        return GameResult(
            game_id=game_id,
            team_ns=team_ns.team_id,
            team_ew=team_ew.team_id,
            winner=None,
            ns_score=0,
            ew_score=0,
            game_duration=game_duration,
            end_reason="error",
            bidding_history=bidding_history,
            tricks_history=tricks_history,
            game_history=game_history,
            final_state=final_state
        )
    
    def run_tournament(self, tournament_type: str = "round_robin") -> Dict:
        """Run tournament
        
        Args:
            tournament_type: "round_robin" for all teams vs all teams, 
                           "duplicate" for AA vs BB format
        """
        if len(self.teams) < 2:
            logger.error("At least 2 teams needed to start tournament")
            return {}
        
        self.tournament_id = f"tournament_{int(time.time())}"
        # Derive numeric session id from tournament id for logging directory
        try:
            self.session_id = str(int(self.tournament_id.split('_')[-1]))
        except Exception:
            self.session_id = None
        logger.info(f"Starting tournament: {self.tournament_id}")
        logger.info(f"Participating teams: {[team.team_name for team in self.teams]}")
        
        # Check all AI health status
        logger.info("Checking AI health status...")
        healthy_teams = []
        for team in self.teams:
            ai1_healthy = self.check_ai_health(team.player1)
            ai2_healthy = self.check_ai_health(team.player2)
            
            if ai1_healthy and ai2_healthy:
                healthy_teams.append(team)
                logger.info(f"✓ {team.team_name} healthy")
            else:
                logger.warning(f"✗ {team.team_name} unhealthy - AI1: {ai1_healthy}, AI2: {ai2_healthy}")
        
        # if len(healthy_teams) < 2:
        #     logger.error("Not enough healthy teams, cannot start tournament")
        #     return {}
        
        # self.teams = healthy_teams
        self.results = []
        
        if tournament_type == "round_robin":
            # Round robin: each team vs all other teams
            total_games = len(self.teams) * (len(self.teams) - 1) // 2
            current_game = 0
            
            for i in range(len(self.teams)):
                for j in range(i + 1, len(self.teams)):
                    current_game += 1
                    logger.info(f"Playing game {current_game}/{total_games}")
                    
                    # Each match has specified rounds
                    for round_num in range(self.rounds_per_match):
                        if round_num == 0:
                            team_ns, team_ew = self.teams[i], self.teams[j]
                        else:
                            team_ns, team_ew = self.teams[j], self.teams[i]
                        
                        result = self.play_game(team_ns, team_ew)
                        self.results.append(result)
                        
                        # Brief rest between games
                        time.sleep(1)
        
        elif tournament_type == "duplicate":
            # New semantics: duplicate-style with open/closed rooms and VP standings
            return self.run_duplicate_round_robin()
        
        # Generate statistics report
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """Generate tournament report"""
        if not self.results:
            return {"error": "No results to report"}
        
        # Calculate team statistics
        team_stats = {}
        for team in self.teams:
            team_stats[team.team_id] = {
                "team_name": team.team_name,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "total_score": 0,
                "games_played": 0
            }
        
        # Process results
        for result in self.results:
            # NS team stats
            team_stats[result.team_ns]["games_played"] += 1
            team_stats[result.team_ns]["total_score"] += result.ns_score
            
            # EW team stats
            team_stats[result.team_ew]["games_played"] += 1
            team_stats[result.team_ew]["total_score"] += result.ew_score
            
            if result.winner == result.team_ns:
                team_stats[result.team_ns]["wins"] += 1
                team_stats[result.team_ew]["losses"] += 1
            elif result.winner == result.team_ew:
                team_stats[result.team_ew]["wins"] += 1
                team_stats[result.team_ns]["losses"] += 1
            else:
                team_stats[result.team_ns]["ties"] += 1
                team_stats[result.team_ew]["ties"] += 1
        
        # Sort teams by wins
        sorted_teams = sorted(team_stats.items(), key=lambda x: x[1]["wins"], reverse=True)
        
        report = {
            "tournament_id": self.tournament_id,
            "total_games": len(self.results),
            "teams": len(self.teams),
            "team_rankings": sorted_teams,
            "detailed_results": [
                {
                    "game_id": r.game_id,
                    "ns_team": r.team_ns,
                    "ew_team": r.team_ew,
                    "winner": r.winner,
                    "ns_score": r.ns_score,
                    "ew_score": r.ew_score,
                    "duration": r.game_duration,
                    "end_reason": r.end_reason,
                    "game_history": r.game_history,
                    "final_state": r.final_state
                }
                for r in self.results
            ]
        }
        
        # Save report to file
        report_file = f"reports/tournament_{self.tournament_id}.json"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Tournament report saved to {report_file}")
        # Log final rankings for round-robin
        logger.info("Final Rankings (Round Robin):")
        for i, (team_id, stats) in enumerate(sorted_teams, start=1):
            logger.info(
                f"{i}. {stats['team_name']} | Wins={stats['wins']} Losses={stats['losses']}"
                f" Ties={stats['ties']} TotalScore={stats['total_score']} Games={stats['games_played']}"
            )
        
        # 保存详细报告到单独文件
        self.save_detailed_report(report)
        
        return report

    # ===================== Duplicate tournament with IMP/VP =====================
    def _init_standings(self):
        self.standings = {}
        for t in self.teams:
            # Skip BYE team from standings
            if t.team_id == "BYE":
                continue
            self.standings[t.team_id] = {
                "team_name": t.team_name,
                "matches": 0,
                "vp": 0.0,
                "imp_net": 0,
            }

    def _update_standings(self, match_summary: Dict):
        a = match_summary["team_a"]
        b = match_summary["team_b"]
        imp = match_summary["imp_diff"]
        vp_a = match_summary["vp_a"]
        vp_b = match_summary["vp_b"]
        
        # Skip BYE team updates
        if a != "BYE":
            self.standings[a]["matches"] += 1
            self.standings[a]["vp"] += vp_a
            self.standings[a]["imp_net"] += imp
        if b != "BYE":
            self.standings[b]["matches"] += 1
            self.standings[b]["vp"] += vp_b
            self.standings[b]["imp_net"] -= imp

    def play_duplicate_match(self, team_a: TeamConfig, team_b: TeamConfig, boards: int) -> Dict:
        # Safety check: ensure no BYE team is involved
        if team_a.team_id == "BYE" or team_b.team_id == "BYE":
            logger.error(f"Attempted to play match with BYE team: {team_a.team_name} vs {team_b.team_name}")
            raise ValueError("Cannot play match with BYE team")
            
        from bridge_scoring import points_to_imp, imp_to_vp20
        match_id = f"match_{int(time.time())}_{team_a.team_id}_vs_{team_b.team_id}"
        # Set match-level logging context for this thread (board loop/logs here)
        set_log_context(match_id=match_id)
        logger.info(f"Starting duplicate match {match_id} with {boards} boards: {team_a.team_name} vs {team_b.team_name}")
        imp_diff = 0
        board_details = []
        for b in range(1, boards + 1):
            seed = int(time.time()) ^ (b * 1315423911)
            init = {"seed": seed, "board_id": b}
            # Run open/closed rooms in parallel for this board
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as ex:
                fut_open = ex.submit(self.play_game, team_a, team_b, init, {"match_id": match_id, "room": "open"})
                fut_closed = ex.submit(self.play_game, team_b, team_a, init, {"match_id": match_id, "room": "closed"})
                open_result = fut_open.result()
                closed_result = fut_closed.result()
            s_open_ns = open_result.ns_score
            s_closed_ns = closed_result.ns_score
            d_points = s_open_ns - s_closed_ns
            imp = points_to_imp(d_points)
            imp_diff += imp
            logger.info(f"Board {b}/{boards} seed={seed} points_diff={d_points} IMP={imp} | open_ns={s_open_ns} closed_ns={s_closed_ns}")
            board_details.append({
                "board": b,
                "seed": seed,
                "open": {"game_id": open_result.game_id, "ns_score": s_open_ns},
                "closed": {"game_id": closed_result.game_id, "ns_score": s_closed_ns},
                "points_diff": d_points,
                "imp": imp
            })
        vp_a, vp_b = imp_to_vp20(imp_diff, boards)
        logger.info(f"Match {match_id} finished: IMP_diff={imp_diff}, VP={vp_a}-{vp_b}")
        
        # 输出比赛结束时的响应时间统计
        response_time_tracker.force_log_statistics()
        
        return {
            "match_id": match_id,
            "team_a": team_a.team_id,
            "team_b": team_b.team_id,
            "boards": boards,
            "imp_diff": imp_diff,
            "vp_a": vp_a,
            "vp_b": vp_b,
            "boards_detail": board_details
        }

    def run_duplicate_round_robin(self) -> Dict:
        if len(self.teams) < 2:
            logger.error("At least 2 teams needed to start duplicate tournament")
            return {}
        self._init_standings()
        
        # Handle odd number of teams by adding a "bye" team
        original_teams = self.teams.copy()
        n = len(self.teams)
        if n % 2 != 0:
            logger.info(f"Odd number of teams ({n}), adding bye team for round-robin scheduling")
            # Create a bye team that will be skipped in matches
            bye_team = TeamConfig(
                team_id="BYE",
                team_name="BYE",
                player1=None,
                player2=None
            )
            self.teams.append(bye_team)
            n = len(self.teams)
        
        # Build round-robin schedule using Berger algorithm
        idxs = list(range(n))
        rounds = n - 1
        match_summaries = []
        total_matches = n * (n - 1) // 2
        
        # Generate rounds: each round has n/2 matches
        for r in range(rounds):
            pairs = []
            for k in range(n // 2):
                a = idxs[k]
                b = idxs[n - 1 - k]
                if a != b:
                    pairs.append((a, b))
            # Rotate (keep first fixed)
            idxs = [idxs[0]] + [idxs[-1]] + idxs[1:-1]
            
            # Filter out BYE matches and log the round
            valid_pairs = []
            bye_pairs = []
            for (i, j) in pairs:
                if self.teams[i].team_id == "BYE" or self.teams[j].team_id == "BYE":
                    bye_pairs.append((i, j))
                else:
                    valid_pairs.append((i, j))
            
            logger.info(f"Round {r+1}/{rounds}: Valid matches: {[(self.teams[i].team_name, self.teams[j].team_name) for i,j in valid_pairs]}")
            if bye_pairs:
                logger.info(f"Round {r+1}/{rounds}: BYE matches (skipped): {[(self.teams[i].team_name, self.teams[j].team_name) for i,j in bye_pairs]}")
            
            # Run valid matches in this round in parallel
            if valid_pairs:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                max_workers = max(1, getattr(self, 'max_parallel_matches', 3))
                with ThreadPoolExecutor(max_workers=min(max_workers, len(valid_pairs))) as ex:
                    future_map = {}
                    for (i, j) in valid_pairs:
                        future = ex.submit(self.play_duplicate_match, self.teams[i], self.teams[j], self.boards_per_match)
                        future_map[future] = (i, j)
                    for fut in as_completed(future_map):
                        summ = fut.result()
                        match_summaries.append(summ)
                        self._update_standings(summ)
            else:
                logger.info(f"Round {r+1}/{rounds}: No valid matches to play")
        ranking = sorted(self.standings.items(), key=lambda kv: (-kv[1]["vp"], -kv[1]["imp_net"]))
        
        # Verify BYE team handling
        bye_in_standings = any(team_id == "BYE" for team_id in self.standings.keys())
        if bye_in_standings:
            logger.warning("BYE team found in standings - this should not happen!")
        else:
            logger.info("BYE team correctly excluded from standings")
        
        report = {
            "tournament_id": self.tournament_id,
            "mode": "duplicate_round_robin",
            "boards_per_match": self.boards_per_match,
            "standings": ranking,
            "matches": match_summaries,
            "total_teams": len(original_teams),
            "bye_team_used": len(self.teams) > len(original_teams)
        }
        report_file = f"reports/tournament_{self.tournament_id}.json"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Duplicate tournament report saved to {report_file}")
        
        # 输出锦标赛结束时的最终响应时间统计
        logger.info("=== 锦标赛结束 - 最终AI响应时间统计 ===")
        response_time_tracker.force_log_statistics()
        
        # 获取响应时间统计并添加到报告中
        response_time_stats = response_time_tracker.get_statistics()
        if response_time_stats:
            report['response_time_statistics'] = {}
            for model_name, data in response_time_stats.items():
                report['response_time_statistics'][model_name] = {
                    'avg_response_time_seconds': round(data['avg_time'], 6),
                    'total_requests': data['total_requests']
                }
            
            # 重新保存包含响应时间统计的报告
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"包含响应时间统计的报告已更新: {report_file}")
        
        # Log final standings for audit
        logger.info("Final Standings (VP):")
        for i, (team_id, stats) in enumerate(ranking, start=1):
            logger.info(f"{i}. {stats['team_name']} | Matches={stats['matches']} VP={stats['vp']} IMP_Net={stats['imp_net']}")
        return report
    
    def save_detailed_report(self, report: Dict, filename: str = None):
        """保存详细报告到单独文件"""
        if not filename:
            filename = f"reports/tournament_report_history_{self.tournament_id}.json"
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        detailed_data = {
            'tournament_id': report['tournament_id'],
            'total_games': report['total_games'],
            'teams': report['teams'],
            'detailed_results': []
        }
        
        for result in report['detailed_results']:
            detailed_result = {
                'game_id': result['game_id'],
                'ns_team': result['ns_team'],
                'ew_team': result['ew_team'],
                'winner': result['winner'],
                'ns_score': result['ns_score'],
                'ew_score': result['ew_score'],
                'duration': result['duration'],
                'end_reason': result['end_reason'],
                'game_history': result.get('game_history'),
                'final_state': result.get('final_state')
            }
            detailed_data['detailed_results'].append(detailed_result)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(detailed_data, f, ensure_ascii=False, indent=2)
        logger.info(f"详细报告已保存: {filename}")
        return filename
    
    def get_response_time_statistics(self) -> Dict[str, Dict]:
        """获取当前所有AI的响应时间统计信息"""
        return response_time_tracker.get_statistics()
