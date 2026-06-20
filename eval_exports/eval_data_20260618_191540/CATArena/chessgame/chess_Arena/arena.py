#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import time
import json
import logging
import threading
import csv
import signal
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import chess
from config import ArenaConfig

# 配置日志
def setup_logging(log_config: Dict):
    """设置日志配置"""
    log_file = log_config.get("file", "logs/arena.log")
    log_level = getattr(logging, log_config.get("level", "INFO"))
    console_output = log_config.get("console", True)
    
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    handlers = [logging.FileHandler(log_file, encoding='utf-8')]
    if console_output:
        handlers.append(logging.StreamHandler())
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    return logging.getLogger(__name__)

@dataclass
class AIConfig:
    """AI配置信息"""
    ai_id: str
    ai_name: str
    port: int
    url: str
    algorithm: str = "simple"  # simple, minimax
    description: str = ""

@dataclass
class GameResult:
    """单局游戏结果"""
    game_id: str
    player_black: str
    player_white: str
    winner: Optional[str]  # None表示平局
    black_moves: int
    white_moves: int
    black_avg_time: float
    white_avg_time: float
    game_duration: float
    end_reason: str  # "win", "draw", "timeout", "error"
    moves_history: List[Dict]
    final_fen: str
    moves_count: int = 0
    # 复盘所需：完整历史与最终状态
    game_history: Optional[Dict] = None
    final_state: Optional[Dict] = None

class ChessArena:
    """国际象棋AI对战平台"""
    
    def __init__(self, config: ArenaConfig = None):
        if config is None:
            config = ArenaConfig()
        
        self.config = config
        self.game_server_url = config.get_game_server_url()
        self.timeout = config.get_timeout()
        self.max_moves = config.get_max_moves()
        self.tournament_config = config.get_tournament_config()
        self.reports_config = config.get_reports_config()
        self.error_handling_config = config.get_error_handling_config()
        
        # 设置日志
        self.logger = setup_logging(config.get_logging_config())
        
        # 初始化数据
        self.ais: List[AIConfig] = []
        self.results: List[GameResult] = []
        self.tournament_id = f"chess_tournament_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 从配置加载AI
        self._load_ais_from_config()
        
    def _load_ais_from_config(self):
        """从配置加载AI"""
        enabled_ais = self.config.get_enabled_ais()
        for ai_config in enabled_ais:
            self.add_ai(
                ai_id=ai_config["ai_id"],
                ai_name=ai_config["ai_name"],
                port=ai_config["port"],
                algorithm=ai_config.get("algorithm", "simple"),
                description=ai_config.get("description", "")
            )
        
    # 获取对局历史
    def _get_game_history(self, game_id: str) -> Optional[Dict]:
        try:
            resp = requests.get(f"{self.game_server_url}/games/{game_id}/history", timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            self.logger.warning(f"获取历史失败 HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            self.logger.error(f"获取历史异常: {e}")
        return None

    # 获取对局最终状态
    def _get_game_state(self, game_id: str) -> Optional[Dict]:
        try:
            resp = requests.get(f"{self.game_server_url}/games/{game_id}/state", timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            self.logger.warning(f"获取状态失败 HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            self.logger.error(f"获取状态异常: {e}")
        return None

    def add_ai(self, ai_id: str, ai_name: str, port: int, algorithm: str = "simple", description: str = ""):
        """添加AI到对战平台"""
        ai_config = AIConfig(
            ai_id=ai_id,
            ai_name=ai_name,
            port=port,
            url=f"http://localhost:{port}",
            algorithm=algorithm,
            description=description
        )
        self.ais.append(ai_config)
        self.logger.info(f"添加AI: {ai_name} (ID: {ai_id}, 端口: {port}, 算法: {algorithm})")
        
    def check_ai_health(self, ai_config: AIConfig) -> bool:
        """检查AI服务健康状态"""
        try:
            response = requests.get(f"{ai_config.url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('status') == 'healthy'
        except Exception as e:
            self.logger.warning(f"AI {ai_config.ai_name} 健康检查失败: {e}")
            # 即便失败也强制加入对战
            return False
        # 即便失败也强制加入对战
        return True
        
    def create_game(self) -> Tuple[Optional[str], bool]:
        """创建新游戏"""
        try:
            data = {
                "player_white": "Arena_White",
                "player_black": "Arena_Black"
            }
            self.logger.debug(f"Creating game with data: {data}")
            response = requests.post(f"{self.game_server_url}/games", json=data, timeout=self.timeout)
            self.logger.debug(f"Game creation response: {response.status_code}")
            
            if response.status_code in [200, 201]:
                result = response.json()
                game_id = result.get('game_id')
                self.logger.debug(f"Game created successfully: {game_id}")
                return game_id, True
            else:
                self.logger.error(f"Game creation failed with status {response.status_code}: {response.text}")
        except Exception as e:
            self.logger.error(f"创建游戏失败: {e}")
        return None, False
        
    def get_ai_move(self, ai_config: AIConfig, fen: str, game_id: str, current_player: str) -> Tuple[Optional[str], float, Optional[str]]:
        """获取AI移动"""
        start_time = time.time()
        try:
            data = {
                "fen": fen,
                "algorithm": ai_config.algorithm,
                "game_id": game_id,
                "current_player": current_player
            }
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    requests.post, 
                    f"{ai_config.url}/move", 
                    json=data, 
                    timeout=self.timeout
                )
               
                response = future.result(timeout=self.timeout)
                
                if response.status_code == 200:
                    result = response.json()
                    move = result.get('move')
                    thinking_time = time.time() - start_time
                    return move, thinking_time, None
                else:
                    return None, time.time() - start_time, f"HTTP {response.status_code}"
                    
        except TimeoutError:
            return None, time.time() - start_time, "timeout"
        except Exception as e:
            return None, time.time() - start_time, str(e)
        
    def play_game(self, ai_black: AIConfig, ai_white: AIConfig, delay_between_steps=0) -> GameResult:
        """进行单局游戏"""
        game_id, success = self.create_game()
        if not success:
            return GameResult(
                game_id="error",
                player_black=ai_black.ai_name,
                player_white=ai_white.ai_name,
                winner=None,
                black_moves=0,
                white_moves=0,
                black_avg_time=0,
                white_avg_time=0,
                game_duration=0,
                end_reason="error",
                moves_history=[],
                final_fen="",
                moves_count=0
            )
        
        self.logger.info(f"开始游戏 {game_id}: {ai_white.ai_name} vs {ai_black.ai_name}")
        
        # 游戏状态
        black_moves = []
        white_moves = []
        black_times = []
        white_times = []
        moves_history = []
        
        game_start_time = time.time()
        move_count = 0
        
        try:
            # 获取初始状态
            response = requests.get(f"{self.game_server_url}/games/{game_id}/state", timeout=self.timeout)
            if response.status_code != 200:
                raise Exception("获取游戏状态失败")
            
            state = response.json()
            current_fen = state['fen']
            end_reason = None
            while move_count < self.max_moves:
                if delay_between_steps > 0: 
                    time.sleep(delay_between_steps)
                # 检查游戏是否结束
                if state['game_status'] != 'ongoing':
                    break
                
                # 确定当前玩家
                current_player = state['current_player']
                current_ai = ai_white if current_player == 'white' else ai_black
                
                # 获取AI移动
                move, thinking_time, error = self.get_ai_move(current_ai, current_fen, game_id, current_player)
                
                if error:
                    self.logger.error(f"AI {current_ai.ai_name} 移动失败: {error}")
                    
                    # 根据错误处理配置决定胜负
                    should_lose = False
                    if "Failed to get valid move after attempts".lower() in error.lower():
                        should_lose = True
                        end_reason = "invalid_move_for_LLM"
                        break
                    if "timeout" in error.lower() or self.error_handling_config.get("timeout_is_loss", False):
                        should_lose = True
                        end_reason = "timeout"
                    elif "http" in error.lower() or self.error_handling_config.get("http_error_is_loss", False):
                        should_lose = True
                        end_reason = "http_error"
                    elif "connection" in error.lower() or self.error_handling_config.get("connection_error_is_loss", False):
                        should_lose = True
                        end_reason = "connection_error"
                    elif "invalid" in error.lower() or self.error_handling_config.get("invalid_move_is_loss", False):
                        should_lose = True
                        end_reason = "invalid_move"
                    elif move is None or "None" in error.lower():
                        should_lose = True
                        end_reason = "none_move"
                    
                    if should_lose:
                        # 当前AI失败，对手获胜
                        winner = ai_black.ai_name if current_player == 'white' else ai_white.ai_name
                        end_reason = "unknown_error" if end_reason is None else end_reason
                        break
                    else:
                        # 传统处理方式：平局
                        break
                
                if not move:
                    self.logger.error(f"AI {current_ai.ai_name} 返回空移动")
                    
                    # 根据错误处理配置决定胜负
                    if self.error_handling_config.get("invalid_move_is_loss", False) or move is None:
                        should_lose = True
                        winner = ai_black.ai_name if current_player == 'white' else ai_white.ai_name
                        end_reason = "invalid_move" if end_reason is None else end_reason
                        break
                    
                    if should_lose:
                        # 当前AI失败，对手获胜
                        winner = ai_black.ai_name if current_player == 'white' else ai_white.ai_name
                        end_reason = "error_loss" if end_reason is None else end_reason
                        break
                    else:
                        # 传统处理方式：平局
                        max_moves = "ai_draw"
                        break
                
                # 记录移动
                if current_player == 'white':
                    white_moves.append(move)
                    white_times.append(thinking_time)
                else:
                    black_moves.append(move)
                    black_times.append(thinking_time)
                
                moves_history.append({
                    'player': current_player,
                    'move': move,
                    'thinking_time': thinking_time,
                    'timestamp': datetime.now().isoformat()
                })
                
                # 执行移动
                move_data = {
                    "player": current_player,
                    "move": move
                }
                response = requests.post(f"{self.game_server_url}/games/{game_id}/move", json=move_data, timeout=self.timeout)
                
                if response.status_code != 200:
                    raise Exception("执行移动失败")
                
                # 更新状态
                response = requests.get(f"{self.game_server_url}/games/{game_id}/state", timeout=self.timeout)
                if response.status_code != 200:
                    raise Exception("获取游戏状态失败")
                
                state = response.json()
                current_fen = state['fen']
                move_count += 1
                
                self.logger.debug(f"移动 {move_count}: {current_player} {move}")
            
            # 确定游戏结果
            if 'winner' not in locals():
                winner = None
            if 'end_reason' not in locals():
                end_reason = "timeout"
            
            if state['game_status'] == 'ongoing':
                end_reason = "max_moves" if end_reason is None else end_reason
            elif state['game_status'] == 'white_win':
                winner = ai_white.ai_name
                end_reason = "win"
            elif state['game_status'] == 'black_win':
                winner = ai_black.ai_name
                end_reason = "win"
            elif "draw" in  state['game_status'] :
                end_reason = state['game_status']
            
            game_duration = time.time() - game_start_time
            
            # 计算平均时间
            black_avg_time = sum(black_times) / len(black_times) if black_times else 0
            white_avg_time = sum(white_times) / len(white_times) if white_times else 0
            
            # 获取历史与最终状态用于复盘
            game_history = self._get_game_history(game_id)
            final_state = self._get_game_state(game_id)

            result = GameResult(
                game_id=game_id,
                player_black=ai_black.ai_name,
                player_white=ai_white.ai_name,
                winner=winner,
                black_moves=len(black_moves),
                white_moves=len(white_moves),
                black_avg_time=black_avg_time,
                white_avg_time=white_avg_time,
                game_duration=game_duration,
                end_reason=end_reason,
                moves_history=moves_history,
                final_fen=current_fen,
                moves_count=move_count,
                game_history=game_history,
                final_state=final_state
            )
            
            self.logger.info(f"游戏结束 {game_id}: 胜者={winner or '平局'}, 原因={end_reason}, 时长={game_duration:.2f}秒")
            return result
            
        except Exception as e:
            self.logger.error(f"游戏 {game_id} 异常: {e}")
            # 异常时也尝试拉取历史与状态
            game_history = self._get_game_history(game_id)
            final_state = self._get_game_state(game_id)
            return GameResult(
                game_id=game_id,
                player_black=ai_black.ai_name,
                player_white=ai_white.ai_name,
                winner=None,
                black_moves=len(black_moves),
                white_moves=len(white_moves),
                black_avg_time=sum(black_times) / len(black_times) if black_times else 0,
                white_avg_time=sum(white_times) / len(white_times) if white_times else 0,
                game_duration=time.time() - game_start_time,
                end_reason="error",
                moves_history=moves_history,
                final_fen=current_fen if 'current_fen' in locals() else "",
                moves_count=move_count,
                game_history=game_history,
                final_state=final_state
            )
        
    def run_tournament(self) -> Dict:
        """运行锦标赛"""
        self.logger.info("开始国际象棋AI锦标赛")
        
        # 检查AI健康状态
        healthy_ais = []
        for ai in self.ais:
            if self.check_ai_health(ai):
                healthy_ais.append(ai)
                self.logger.info(f"✓ {ai.ai_name} 健康检查通过")
            else:
                self.logger.error(f"✗ {ai.ai_name} 健康检查失败")
        
        # if len(healthy_ais) < 2:
        #     self.logger.error("健康AI数量不足，无法开始锦标赛")
        #     return None
        
        # self.ais = healthy_ais
        self.results = []
        
        # 运行循环赛
        rounds_per_match = self.tournament_config.get("rounds_per_match", 2)
        delay_between_games = self.tournament_config.get("delay_between_games", 1)
        delay_between_steps = self.tournament_config.get("delay_between_steps", 0)
        
        # 原串行代码如下，已注释
        # for i, ai1 in enumerate(self.ais):
        #     for j, ai2 in enumerate(self.ais):
        #         if i >= j:  # 避免重复对战
        #             continue
        #         
        #         for round_num in range(rounds_per_match):
        #             self.logger.info(f"第{round_num + 1}轮: {ai1.ai_name} vs {ai2.ai_name}")
        #             
        #             # 白棋 vs 黑棋
        #             result1 = self.play_game(ai2, ai1)  # ai2黑棋, ai1白棋
        #             self.results.append(result1)
        #             
        #             if delay_between_games > 0:
        #                 time.sleep(delay_between_games)
        #             
        #             # 黑棋 vs 白棋（交换颜色）
        #             result2 = self.play_game(ai1, ai2)  # ai1黑棋, ai2白棋
        #             self.results.append(result2)
        #             
        #             if delay_between_games > 0:
        #                 time.sleep(delay_between_games)

        # 新并行化实现：一口气开启所有对战
        from concurrent.futures import ThreadPoolExecutor, as_completed

        match_tasks = []
        for i, ai1 in enumerate(self.ais):
            for j, ai2 in enumerate(self.ais):
                if i >= j:
                    continue
                for round_num in range(rounds_per_match):
                    # 记录两种颜色对局
                    match_tasks.append({
                        "white": ai1,
                        "black": ai2,
                        "desc": f"第{round_num + 1}轮: {ai1.ai_name} vs {ai2.ai_name}"
                    })
                    match_tasks.append({
                        "white": ai2,
                        "black": ai1,
                        "desc": f"第{round_num + 1}轮: {ai2.ai_name} vs {ai1.ai_name}"
                    })

        def play_and_log(ai_black, ai_white, desc):
            self.logger.info(desc)
            result = self.play_game(ai_black, ai_white, delay_between_steps=delay_between_steps)
            return result

        # 控制最大并发数，避免资源爆炸
        max_workers = min(96, len(match_tasks)) if len(match_tasks) > 0 else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_match = {}
            # 启动时，相邻两次游戏设置启动间隔
            for idx, task in enumerate(match_tasks):
                future = executor.submit(play_and_log, task["black"], task["white"], task["desc"])
                future_to_match[future] = task
                if idx < len(match_tasks) - 1:
                    time.sleep(delay_between_games)  # 启动间隔delay_between_games秒
            for future in as_completed(future_to_match):
                result = future.result()
                self.results.append(result)
                if delay_between_games > 0:
                    time.sleep(delay_between_games)
        
        # 生成报告
        report = self.generate_report()
        return report
        
    def generate_report(self) -> Dict:
        """生成锦标赛报告"""
        if not self.results:
            return None
        
        # 统计AI表现
        ai_stats = {}
        for ai in self.ais:
            ai_stats[ai.ai_name] = {
                'wins': 0,
                'draws': 0,
                'losses': 0,
                'total_games': 0,
                'total_time': 0,
                'total_moves': 0
            }
        
        # 胜负矩阵
        matrix = {}
        for ai1 in self.ais:
            matrix[ai1.ai_name] = {}
            for ai2 in self.ais:
                matrix[ai1.ai_name][ai2.ai_name] = {'wins': 0, 'draws': 0, 'losses': 0}
        
        # 分析结果
        for result in self.results:
            # 更新AI统计
            for ai_name in [result.player_white, result.player_black]:
                if ai_name in ai_stats:
                    ai_stats[ai_name]['total_games'] += 1
                    ai_stats[ai_name]['total_moves'] += result.moves_count
                    if ai_name == result.player_white:
                        ai_stats[ai_name]['total_time'] += result.white_avg_time
                    else:
                        ai_stats[ai_name]['total_time'] += result.black_avg_time
            
            # 更新胜负统计
            if result.winner:
                if result.winner in ai_stats:
                    ai_stats[result.winner]['wins'] += 1
                
                # 更新失败者的损失统计
                loser = result.player_black if result.winner == result.player_white else result.player_white
                if loser in ai_stats:
                    ai_stats[loser]['losses'] += 1
                
                # 更新胜负矩阵
                if result.winner in matrix and loser in matrix[result.winner]:
                    matrix[result.winner][loser]['wins'] += 1
                    matrix[loser][result.winner]['losses'] += 1
            else:
                # 平局
                for ai_name in [result.player_white, result.player_black]:
                    if ai_name in ai_stats:
                        ai_stats[ai_name]['draws'] += 1
                
                # 更新矩阵
                if result.player_white in matrix and result.player_black in matrix[result.player_white]:
                    matrix[result.player_white][result.player_black]['draws'] += 1
                    matrix[result.player_black][result.player_white]['draws'] += 1

        # 计算平均时间
        for ai_name, stats in ai_stats.items():
            if stats['total_games'] > 0:
                stats['avg_time'] = stats['total_time'] / stats['total_games']
            else:
                stats['avg_time'] = 0

        # 计算平均得分
        for ai_name, stats in ai_stats.items():
            if stats['total_games'] > 0:
                stats['avg_score'] = (stats['wins'] * 1.0 + stats['draws'] * 0.5) / stats['total_games']
            else:
                stats['avg_score'] = 0
        
        # 计算总游戏数
        total_games = len(self.results)
        avg_time = sum(r.game_duration for r in self.results) / total_games if total_games > 0 else 0
        
        report = {
            'tournament_id': self.tournament_id,
            'timestamp': datetime.now().isoformat(),
            'participants': [ai.ai_name for ai in self.ais],
            'total_games': total_games,
            'avg_time': avg_time,
            'ai_stats': ai_stats,
            'matrix': matrix,
            'results': [
                {
                    'game_id': r.game_id,
                    'player_white': r.player_white,
                    'player_black': r.player_black,
                    'winner': r.winner,
                    'end_reason': r.end_reason,
                    'game_duration': r.game_duration,
                    'moves_count': r.moves_count,
                    'black_avg_time': r.black_avg_time,
                    'white_avg_time': r.white_avg_time,
                    'game_history': r.game_history,
                    'final_state': r.final_state
                }
                for r in self.results
            ]
        }
        
        return report
        
    def save_report(self, report: Dict, filename: str = None, reports_dir: str = "reports"):
        """保存报告"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{reports_dir}/chess_arena_report_{timestamp}"
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 保存JSON报告
        if self.reports_config.get("save_json", True):
            json_filename = f"{filename}.json"
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.logger.info(f"JSON报告已保存: {json_filename}")
        
        # 保存TXT报告
        if self.reports_config.get("save_txt", True):
            txt_filename = f"{filename}.txt"
            self.save_text_report(report, txt_filename)
            self.logger.info(f"TXT报告已保存: {txt_filename}")
        
        # 保存CSV报告
        if self.reports_config.get("save_csv", True):
            csv_filename = f"{filename}.csv"
            self.save_csv_report(report, csv_filename)
            self.logger.info(f"CSV报告已保存: {csv_filename}")
        
        # 保存详细报告（包含历史和状态信息）
        self.save_detailed_report(report, reports_dir=reports_dir)
    
    def save_text_report(self, report: Dict, filename: str):
        """保存文本格式报告"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("国际象棋AI锦标赛报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"锦标赛ID: {report['tournament_id']}\n")
            f.write(f"时间: {report['timestamp']}\n")
            f.write(f"参与AI: {', '.join(report['participants'])}\n")
            f.write(f"总游戏数: {report['total_games']}\n")
            f.write(f"平均游戏时长: {report['avg_time']:.2f}秒\n\n")
            
            f.write("AI统计:\n")
            f.write("-" * 30 + "\n")
            for ai_name, stats in report['ai_stats'].items():
                f.write(f"{ai_name}:\n")
                f.write(f"  胜场: {stats['wins']}\n")
                f.write(f"  平场: {stats['draws']}\n")
                f.write(f"  负场: {stats['losses']}\n")
                f.write(f"  总游戏数: {stats['total_games']}\n")
                f.write(f"  平均思考时间: {stats['avg_time']:.3f}秒\n")
                f.write(f"  平均得分: {stats['avg_score']:.3f}\n\n")
            
            f.write("胜负矩阵:\n")
            f.write("-" * 30 + "\n")
            for ai1 in report['participants']:
                f.write(f"{ai1:>15}")
            f.write("\n")
            
            for ai1 in report['participants']:
                f.write(f"{ai1:>15}")
                for ai2 in report['participants']:
                    if ai1 == ai2:
                        f.write(f"{'--':>15}")
                    else:
                        matrix = report['matrix'][ai1][ai2]
                        f.write(f"{matrix['wins']}-{matrix['draws']}-{matrix['losses']:>15}")
                f.write("\n")
            
            f.write("\n游戏详情:\n")
            f.write("-" * 30 + "\n")
            for i, result in enumerate(report['results'], 1):
                f.write(f"游戏 {i}: {result['player_white']} vs {result['player_black']}\n")
                f.write(f"  胜者: {result['winner'] or '平局'}\n")
                f.write(f"  结束原因: {result['end_reason']}\n")
                f.write(f"  游戏时长: {result['game_duration']:.2f}秒\n")
                f.write(f"  移动数: {result['moves_count']}\n\n")
    
    def save_csv_report(self, report: Dict, filename: str):
        """保存CSV格式报告"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 写入胜负矩阵、总胜平负、平均得分和平均思考时间
            header = ['胜负矩阵'] + report['participants'] + ['总胜平负', '平均得分', '平均思考时间(秒)']
            writer.writerow(header)
            
            for ai1 in report['participants']:
                row = [ai1]
                for ai2 in report['participants']:
                    if ai1 == ai2:
                        row.append('--')
                    else:
                        matrix = report['matrix'][ai1][ai2]
                        row.append(f"{matrix['wins']}-{matrix['draws']}-{matrix['losses']}")
                
                # 添加总胜平负
                stats = report['ai_stats'][ai1]
                row.append(f"{stats['wins']}-{stats['draws']}-{stats['losses']}")
                
                # 添加平均得分
                row.append(f"{stats['avg_score']:.3f}")
                
                # 添加平均思考时间
                row.append(f"{stats['avg_time']:.3f}")
                writer.writerow(row)

    def save_detailed_report(self, report: Dict, filename: str = None, reports_dir: str = "reports"):
        """保存详细报告到单独文件"""
        if not filename:
            filename = f"{reports_dir}/tournament_report_history_{self.tournament_id}.json"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 提取详细的游戏历史和状态信息
        detailed_data = {
            'tournament_id': report['tournament_id'],
            'timestamp': report['timestamp'],
            'participants': report['participants'],
            'total_games': report['total_games'],
            'avg_time': report['avg_time'],
            'detailed_results': []
        }
        
        for result in report['results']:
            detailed_result = {
                'game_id': result['game_id'],
                'player_white': result['player_white'],
                'player_black': result['player_black'],
                'winner': result['winner'],
                'end_reason': result['end_reason'],
                'game_duration': result['game_duration'],
                'moves_count': result['moves_count'],
                'black_avg_time': result['black_avg_time'],
                'white_avg_time': result['white_avg_time'],
                'game_history': result.get('game_history'),
                'final_state': result.get('final_state')
            }
            detailed_data['detailed_results'].append(detailed_result)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(detailed_data, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"详细报告已保存: {filename}")
        
        return filename

def main():
    """主函数"""
    # 创建配置
    config = ArenaConfig()
    
    # 创建竞技场
    arena = ChessArena(config)
    
    # 运行锦标赛
    report = arena.run_tournament()
    
    if report:
        # 保存报告
        arena.save_report(report)
        print("锦标赛完成！报告已保存。")
    else:
        print("锦标赛失败！")

if __name__ == "__main__":
    main() 