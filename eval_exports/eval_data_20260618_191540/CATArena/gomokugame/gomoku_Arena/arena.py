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
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 配置日志
def setup_logging(log_file: str = "logs/arena.log"):
    """设置日志配置"""
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

@dataclass
class AIConfig:
    """AI配置信息"""
    ai_id: str
    ai_name: str
    port: int
    url: str

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
    game_history: Optional[Dict] = None  # 游戏历史记录
    final_state: Optional[Dict] = None   # 游戏最终状态

class GomokuArena:
    """五子棋AI对战平台"""
    
    def __init__(self, game_server_url: str = "http://localhost:10000", timeout: int = 10, rounds_per_match: int = 2):
        self.game_server_url = game_server_url
        self.timeout = timeout
        self.rounds_per_match = rounds_per_match
        self.ais: List[AIConfig] = []
        self.results: List[GameResult] = []
        self.tournament_id = None
        
        # 创建强健的HTTP会话
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def add_ai(self, ai_id: str, ai_name: str, port: int):
        """添加AI到对战平台"""
        ai_config = AIConfig(
            ai_id=ai_id,
            ai_name=ai_name,
            port=port,
            url=f"http://localhost:{port}"
        )
        self.ais.append(ai_config)
        logger.info(f"添加AI: {ai_name} (ID: {ai_id}, 端口: {port})")
        
    def check_ai_health(self, ai_config: AIConfig) -> bool:
        """检查AI服务健康状态"""
        try:
            response = self.session.get(f"{ai_config.url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return True
        except Exception as e:
            logger.warning(f"AI {ai_config.ai_name} 健康检查失败: {e}")
        return False
        
    def join_ai_to_game(self, ai_config: AIConfig, game_id: str, my_color: str) -> bool:
        """让AI加入游戏"""
        try:
            join_data = {
                "game_id": game_id,
                "my_color": my_color,
                "game_server_url": self.game_server_url
            }
            
            response = self.session.post(f"{ai_config.url}/join_game", json=join_data, timeout=5)
            if response.status_code == 200:
                logger.debug(f"AI {ai_config.ai_name} 成功加入游戏 {game_id}")
                return True
            else:
                logger.error(f"AI {ai_config.ai_name} 加入游戏失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"AI {ai_config.ai_name} 加入游戏异常: {e}")
            return False
    
    def get_ai_move(self, ai_config: AIConfig, game_id: str, board: List[List[int]], 
                   my_color: str) -> Tuple[Optional[List[int]], float]:
        """获取AI落子（带超时监控）"""
        start_time = time.time()
        
        try:
            # 获取落子
            move_data = {
                "game_id": game_id,
                "board": board,
                "current_player": my_color
            }
            
            # 使用线程池实现超时控制
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self.session.post, 
                    f"{ai_config.url}/get_move", 
                    json=move_data,
                    timeout=self.timeout + 5  # 给HTTP请求额外的5秒缓冲
                )
                
                try:
                    response = future.result(timeout=self.timeout)
                    end_time = time.time()
                    thinking_time = end_time - start_time
                    
                    if response.status_code == 200:
                        data = response.json()
                        move = data.get('move')
                        return move, thinking_time
                    else:
                        logger.error(f"AI {ai_config.ai_name} 返回错误: {response.status_code}")
                        return None, thinking_time
                        
                except TimeoutError:
                    logger.error(f"AI {ai_config.ai_name} 超时 ({self.timeout}秒)")
                    # 尝试取消future，避免后台请求继续运行
                    try:
                        future.cancel()
                    except:
                        pass
                    return None, self.timeout
                    
        except Exception as e:
            logger.error(f"AI {ai_config.ai_name} 请求失败: {e}")
            return None, time.time() - start_time
            
    def play_game(self, ai_black: AIConfig, ai_white: AIConfig) -> GameResult:
        """进行单局对战"""
        import uuid
        game_id = f"arena_{int(time.time())}_{uuid.uuid4().hex[:8]}_{ai_black.ai_id}_vs_{ai_white.ai_id}"
        logger.info(f"开始对战: {ai_black.ai_name} (黑) vs {ai_white.ai_name} (白) - {game_id}")
        
        # 创建游戏
        try:
            create_data = {
                "player_black": ai_black.ai_id,
                "player_white": ai_white.ai_id
            }
            response = self.session.post(f"{self.game_server_url}/games", json=create_data, timeout=10)
            if response.status_code not in [200, 201]:
                logger.error(f"创建游戏失败: {response.status_code}")
                return GameResult(
                    game_id=game_id,
                    player_black=ai_black.ai_id,
                    player_white=ai_white.ai_id,
                    winner=None,
                    black_moves=0,
                    white_moves=0,
                    black_avg_time=0,
                    white_avg_time=0,
                    game_duration=0,
                    end_reason="error",
                    game_history=None,
                    final_state=None
                )
            
            # 获取实际的游戏ID
            game_data = response.json()
            actual_game_id = game_data.get('game_id', game_id)
            logger.info(f"游戏创建成功: {actual_game_id}")
        except Exception as e:
            logger.error(f"创建游戏异常: {e}")
            return GameResult(
                game_id=game_id,
                player_black=ai_black.ai_id,
                player_white=ai_white.ai_id,
                winner=None,
                black_moves=0,
                white_moves=0,
                black_avg_time=0,
                white_avg_time=0,
                game_duration=0,
                end_reason="error"
            )
        
        # 让AI加入游戏
        logger.info(f"让AI加入游戏...")
        if not self.join_ai_to_game(ai_black, actual_game_id, "black"):
            logger.error(f"黑方AI {ai_black.ai_name} 加入游戏失败")
            return GameResult(
                game_id=actual_game_id,
                player_black=ai_black.ai_id,
                player_white=ai_white.ai_id,
                winner=ai_white.ai_id,  # 白方获胜
                black_moves=0,
                white_moves=0,
                black_avg_time=0,
                white_avg_time=0,
                game_duration=0,
                end_reason="error",
                game_history=None,
                final_state=None
            )
        
        if not self.join_ai_to_game(ai_white, actual_game_id, "white"):
            logger.error(f"白方AI {ai_white.ai_name} 加入游戏失败")
            return GameResult(
                game_id=actual_game_id,
                player_black=ai_black.ai_id,
                player_white=ai_white.ai_id,
                winner=ai_black.ai_id,  # 黑方获胜
                black_moves=0,
                white_moves=0,
                black_avg_time=0,
                white_avg_time=0,
                game_duration=0,
                end_reason="error",
                game_history=None,
                final_state=None
            )
        
        logger.info(f"AI加入游戏成功，开始对战")
        
        game_start_time = time.time()
        black_times = []
        white_times = []
        black_moves = 0
        white_moves = 0
        current_player = "black"
        
        while True:
            try:
                # 获取游戏状态
                response = self.session.get(f"{self.game_server_url}/games/{actual_game_id}/state", timeout=5)
                if response.status_code != 200:
                    logger.error(f"获取游戏状态失败: {response.status_code}")
                    break
                    
                state = response.json()
                board = state['board']
                game_status = state.get('game_status', 'ongoing')
                
                if game_status != 'ongoing':
                    # 游戏结束
                    winner = None
                    if game_status == 'black_win':
                        winner = ai_black.ai_id
                    elif game_status == 'white_win':
                        winner = ai_white.ai_id
                    
                    game_duration = time.time() - game_start_time
                    black_avg_time = sum(black_times) / len(black_times) if black_times else 0
                    white_avg_time = sum(white_times) / len(white_times) if white_times else 0
                    
                    # 获取游戏历史和最终状态
                    game_history = None
                    final_state = None
                    try:
                        # 获取游戏历史
                        history_response = requests.get(f"{self.game_server_url}/games/{actual_game_id}/history")
                        if history_response.status_code == 200:
                            game_history = history_response.json()
                        
                        # 获取最终状态
                        state_response = requests.get(f"{self.game_server_url}/games/{actual_game_id}/state")
                        if state_response.status_code == 200:
                            final_state = state_response.json()
                    except Exception as e:
                        logger.warning(f"获取游戏历史和状态失败: {e}")
                    
                    result = GameResult(
                        game_id=actual_game_id,
                        player_black=ai_black.ai_id,
                        player_white=ai_white.ai_id,
                        winner=winner,
                        black_moves=black_moves,
                        white_moves=white_moves,
                        black_avg_time=black_avg_time,
                        white_avg_time=white_avg_time,
                        game_duration=game_duration,
                        end_reason="win" if winner else "draw",
                        game_history=game_history,
                        final_state=final_state
                    )
                    
                    logger.info(f"游戏结束: {game_id} - 胜者: {winner or '平局'}")
                    return result
                
                # 当前玩家AI
                current_ai = ai_black if current_player == "black" else ai_white
                
                # 获取AI落子
                move, thinking_time = self.get_ai_move(
                    current_ai, actual_game_id, board, current_player
                )
                
                if move is None:
                    # AI超时或出错，对手获胜
                    winner = ai_white.ai_id if current_player == "black" else ai_black.ai_id
                    game_duration = time.time() - game_start_time
                    
                    # 获取游戏历史和最终状态
                    game_history = None
                    final_state = None
                    try:
                        # 获取游戏历史
                        history_response = requests.get(f"{self.game_server_url}/games/{actual_game_id}/history", timeout=5)
                        if history_response.status_code == 200:
                            game_history = history_response.json()
                        
                        # 获取最终状态
                        state_response = requests.get(f"{self.game_server_url}/games/{actual_game_id}/state", timeout=5)
                        if state_response.status_code == 200:
                            final_state = state_response.json()
                    except Exception as e:
                        logger.warning(f"获取游戏历史和状态失败: {e}")
                    
                    result = GameResult(
                        game_id=actual_game_id,
                        player_black=ai_black.ai_id,
                        player_white=ai_white.ai_id,
                        winner=winner,
                        black_moves=black_moves,
                        white_moves=white_moves,
                        black_avg_time=sum(black_times) / len(black_times) if black_times else 0,
                        white_avg_time=sum(white_times) / len(white_times) if white_times else 0,
                        game_duration=game_duration,
                        end_reason="timeout",
                        game_history=game_history,
                        final_state=final_state
                    )
                    
                    logger.info(f"游戏结束: {game_id} - {current_ai.ai_name} 超时，{winner} 获胜")
                    # 添加短暂延迟，确保资源清理
                    time.sleep(0.1)
                    return result
                
                # 记录思考时间
                if current_player == "black":
                    black_times.append(thinking_time)
                    black_moves += 1
                else:
                    white_times.append(thinking_time)
                    white_moves += 1
                
                # 提交落子
                move_data = {
                    "player": current_player,
                    "position": move
                }
                response = self.session.post(f"{self.game_server_url}/games/{actual_game_id}/move", json=move_data, timeout=5)
                
                if response.status_code != 200:
                    logger.error(f"落子失败: {response.status_code}")
                    break
                
                # 切换玩家
                current_player = "white" if current_player == "black" else "black"
                
            except Exception as e:
                logger.error(f"游戏进行中异常: {e}")
                break
        
        # 异常结束
        game_duration = time.time() - game_start_time
        
        # 获取游戏历史和最终状态
        game_history = None
        final_state = None
        try:
            # 获取游戏历史
            history_response = requests.get(f"{self.game_server_url}/games/{actual_game_id}/history")
            if history_response.status_code == 200:
                game_history = history_response.json()
            
            # 获取最终状态
            state_response = requests.get(f"{self.game_server_url}/games/{actual_game_id}/state")
            if state_response.status_code == 200:
                final_state = state_response.json()
        except Exception as e:
            logger.warning(f"获取游戏历史和状态失败: {e}")
        
        return GameResult(
            game_id=actual_game_id,
            player_black=ai_black.ai_id,
            player_white=ai_white.ai_id,
            winner=None,
            black_moves=black_moves,
            white_moves=white_moves,
            black_avg_time=sum(black_times) / len(black_times) if black_times else 0,
            white_avg_time=sum(white_times) / len(white_times) if white_times else 0,
            game_duration=game_duration,
            end_reason="error",
            game_history=game_history,
            final_state=final_state
        )
    
    def run_tournament(self) -> Dict:
        """运行锦标赛"""
        if len(self.ais) < 2:
            logger.error("至少需要2个AI才能开始锦标赛")
            return {}
        
        self.tournament_id = f"tournament_{int(time.time())}"
        logger.info(f"开始锦标赛: {self.tournament_id}")
        logger.info(f"参赛AI: {[ai.ai_name for ai in self.ais]}")
        
        # 检查所有AI健康状态
        logger.info("检查AI健康状态...")
        healthy_ais = []
        for ai in self.ais:
            if self.check_ai_health(ai):
                healthy_ais.append(ai)
                logger.info(f"✓ {ai.ai_name} 健康")
            else:
                logger.warning(f"✗ {ai.ai_name} 不健康，跳过")
        
        # if len(healthy_ais) < 2:
        #     logger.error("健康AI数量不足，无法开始锦标赛")
        #     return {}
        
        # self.ais = healthy_ais
        self.results = []
        
        # 循环赛：每个AI对战其他所有AI
        total_games = len(self.ais) * (len(self.ais) - 1) // 2
        current_game = 0
        
        for i in range(len(self.ais)):
            for j in range(i + 1, len(self.ais)):
                current_game += 1
                logger.info(f"进行第 {current_game}/{total_games} 局对战")
                
                # 每局对战指定轮数（交替交换黑白）
                for round_num in range(self.rounds_per_match):
                    if round_num % 2 == 0:
                        ai_black, ai_white = self.ais[i], self.ais[j]
                    else:
                        ai_black, ai_white = self.ais[j], self.ais[i]
                    
                    result = self.play_game(ai_black, ai_white)
                    self.results.append(result)
                    
                    # 短暂休息
                    # time.sleep(1)
        
        # 生成统计报告
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        """生成锦标赛报告"""
        if not self.results:
            return {}
        
        # 初始化统计
        ai_stats = {}
        for ai in self.ais:
            ai_stats[ai.ai_id] = {
                'name': ai.ai_name,
                'wins': 0,
                'draws': 0,
                'losses': 0,
                'total_time': 0,
                'total_moves': 0,
                'games_played': 0,
                'timeouts': 0
            }
        
        # 统计对战结果
        for result in self.results:
            # 统计黑方
            ai_stats[result.player_black]['games_played'] += 1
            ai_stats[result.player_black]['total_time'] += result.black_avg_time * result.black_moves
            ai_stats[result.player_black]['total_moves'] += result.black_moves
            
            # 统计白方
            ai_stats[result.player_white]['games_played'] += 1
            ai_stats[result.player_white]['total_time'] += result.white_avg_time * result.white_moves
            ai_stats[result.player_white]['total_moves'] += result.white_moves
            
            # 统计胜负
            if result.winner:
                if result.winner == result.player_black:
                    ai_stats[result.player_black]['wins'] += 1
                    ai_stats[result.player_white]['losses'] += 1
                else:
                    ai_stats[result.player_white]['wins'] += 1
                    ai_stats[result.player_black]['losses'] += 1
            else:
                ai_stats[result.player_black]['draws'] += 1
                ai_stats[result.player_white]['draws'] += 1

            # 统计超时（判定为因超时导致的失败方）
            if result.end_reason == 'timeout':
                timed_out_ai = None
                if result.winner == result.player_white:
                    timed_out_ai = result.player_black
                elif result.winner == result.player_black:
                    timed_out_ai = result.player_white
                if timed_out_ai and timed_out_ai in ai_stats:
                    ai_stats[timed_out_ai]['timeouts'] += 1
        
        # 计算平均思考时间
        for ai_id, stats in ai_stats.items():
            if stats['total_moves'] > 0:
                stats['avg_thinking_time'] = stats['total_time'] / stats['total_moves']
            else:
                stats['avg_thinking_time'] = 0
        
        # 生成胜负矩阵
        matrix = {}
        for ai in self.ais:
            matrix[ai.ai_id] = {}
            for other_ai in self.ais:
                if ai.ai_id == other_ai.ai_id:
                    matrix[ai.ai_id][other_ai.ai_id] = "-"
                else:
                    wins = 0
                    losses = 0
                    draws = 0
                    
                    for result in self.results:
                        if (result.player_black == ai.ai_id and result.player_white == other_ai.ai_id) or \
                           (result.player_black == other_ai.ai_id and result.player_white == ai.ai_id):
                            if result.winner == ai.ai_id:
                                wins += 1
                            elif result.winner == other_ai.ai_id:
                                losses += 1
                            else:
                                draws += 1
                    
                    matrix[ai.ai_id][other_ai.ai_id] = f"{wins}W/{draws}D/{losses}L"
        
        # 生成报告
        report = {
            'tournament_id': self.tournament_id,
            'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'participants': [{'id': ai.ai_id, 'name': ai.ai_name} for ai in self.ais],
            'total_games': len(self.results),
            'ai_stats': ai_stats,
            'matrix': matrix,
            'results': [
                {
                    'game_id': r.game_id,
                    'player_black': r.player_black,
                    'player_white': r.player_white,
                    'winner': r.winner,
                    'end_reason': r.end_reason,
                    'duration': round(r.game_duration, 2),
                    'game_history': r.game_history,
                    'final_state': r.final_state
                }
                for r in self.results
            ]
        }
        
        return report
    
    def save_report(self, report: Dict, filename: str = None):
        """保存报告到文件"""
        if not filename:
            filename = f"reports/tournament_report_{self.tournament_id}.json"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"报告已保存: {filename}")
        
        # 同时保存为易读的文本格式
        txt_filename = filename.replace('.json', '.txt')
        self.save_text_report(report, txt_filename)
        
        # 保存为CSV格式
        csv_filename = filename.replace('.json', '.csv')
        self.save_csv_report(report, csv_filename)
        
        # 保存详细报告（包含历史和状态信息）
        self.save_detailed_report(report)
    
    def save_text_report(self, report: Dict, filename: str):
        """保存文本格式报告"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("五子棋AI锦标赛报告\n")
            f.write("=" * 60 + "\n\n")
            
            f.write(f"锦标赛ID: {report['tournament_id']}\n")
            f.write(f"开始时间: {report['start_time']}\n")
            f.write(f"总对局数: {report['total_games']}\n\n")
            
            f.write("参赛AI:\n")
            for ai in report['participants']:
                f.write(f"  - {ai['name']} (ID: {ai['id']})\n")
            f.write("\n")
            
            f.write("AI统计:\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'AI名称':<15} {'胜':<4} {'平':<4} {'负':<4} {'总场次':<6} {'平均思考时间(秒)':<15}\n")
            f.write("-" * 80 + "\n")
            
            for ai_id, stats in report['ai_stats'].items():
                f.write(f"{stats['name']:<15} {stats['wins']:<4} {stats['draws']:<4} {stats['losses']:<4} "
                       f"{stats['games_played']:<6} {stats['avg_thinking_time']:<15.3f}\n")
            f.write("\n")
            
            f.write("胜负矩阵:\n")
            f.write("-" * 80 + "\n")
            # 表头
            f.write(f"{'AI名称':<15}")
            for ai in report['participants']:
                f.write(f"{ai['name']:<12}")
            f.write("\n")
            f.write("-" * 80 + "\n")
            
            # 矩阵内容
            for ai in report['participants']:
                f.write(f"{ai['name']:<15}")
                for other_ai in report['participants']:
                    if ai['id'] == other_ai['id']:
                        f.write(f"{'-':<12}")
                    else:
                        f.write(f"{report['matrix'][ai['id']][other_ai['id']]:<12}")
                f.write("\n")
            f.write("\n")
            
            f.write("详细对局记录:\n")
            f.write("-" * 80 + "\n")
            for i, result in enumerate(report['results'], 1):
                f.write(f"{i:2d}. {result['game_id']} - "
                       f"{result['player_black']} vs {result['player_white']} - "
                       f"胜者: {result['winner'] or '平局'} - "
                       f"时长: {result['duration']}秒 - "
                       f"结束原因: {result['end_reason']}\n")
                
                # 添加游戏历史和状态信息提示
                if result.get('game_history') or result.get('final_state'):
                    f.write(f"    详细数据: 包含游戏历史和最终状态信息 (JSON格式)\n")
    
    def save_csv_report(self, report: Dict, filename: str):
        """保存CSV格式报告 - 简洁的胜负矩阵格式"""
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # 获取AI名称列表
            ai_names = [ai['name'] for ai in report['participants']]
            
            # 写入表头
            header = ['AI vs AI'] + ai_names + ['总胜/平/负', '超时次数', '平均思考时间(秒)']
            writer.writerow(header)
            
            # 写入矩阵内容
            for ai in report['participants']:
                ai_name = ai['name']
                ai_id = ai['id']
                ai_stats = report['ai_stats'][ai_id]
                
                # 构建行数据
                row = [ai_name]
                
                # 添加与其他AI的对战结果
                for other_ai in report['participants']:
                    if ai['id'] == other_ai['id']:
                        row.append('-')  # 自己vs自己
                    else:
                        # 从矩阵中获取对战结果
                        matrix_result = report['matrix'][ai['id']][other_ai['id']]
                        # 解析 "1W/0D/1L" 格式为 "1/0/1" 格式
                        if 'W' in matrix_result and 'D' in matrix_result and 'L' in matrix_result:
                            # 使用正则表达式或简单字符串处理
                            import re
                            pattern = r'(\d+)W/(\d+)D/(\d+)L'
                            match = re.match(pattern, matrix_result)
                            if match:
                                wins, draws, losses = match.groups()
                                row.append(f"{wins}/{draws}/{losses}")
                            else:
                                row.append(matrix_result)
                        else:
                            row.append(matrix_result)
                
                # 添加总胜/平/负
                total_wins = ai_stats['wins']
                total_draws = ai_stats['draws']
                total_losses = ai_stats['losses']
                row.append(f"{total_wins}/{total_draws}/{total_losses}")
                
                # 添加超时次数
                timeout_count = ai_stats.get('timeouts', 0)
                row.append(str(timeout_count))

                # 添加平均思考时间（保留4位小数）
                avg_thinking_time = ai_stats['avg_thinking_time']
                row.append(f"{avg_thinking_time:.4f}")
                
                writer.writerow(row)
        
        logger.info(f"CSV报告已保存: {filename}")

    def save_detailed_report(self, report: Dict, filename: str = None):
        """保存详细报告到单独文件"""
        if not filename:
            filename = f"reports/tournament_report_history_{self.tournament_id}.json"
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # 提取详细的游戏历史和状态信息
        detailed_data = {
            'tournament_id': report['tournament_id'],
            'start_time': report['start_time'],
            'total_games': report['total_games'],
            'detailed_results': []
        }
        
        for result in report['results']:
            detailed_result = {
                'game_id': result['game_id'],
                'player_black': result['player_black'],
                'player_white': result['player_white'],
                'winner': result['winner'],
                'end_reason': result['end_reason'],
                'duration': result['duration'],
                'game_history': result.get('game_history'),
                'final_state': result.get('final_state')
            }
            detailed_data['detailed_results'].append(detailed_result)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(detailed_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"详细报告已保存: {filename}")
        
        return filename

def main():
    """主函数"""
    arena = GomokuArena(timeout=10)
    
    # 添加AI（可以配置多个）
    arena.add_ai("AI_Alpha", "Alpha AI", 11001)
    # arena.add_ai("AI_Beta", "Beta AI", 11002)
    # arena.add_ai("AI_Gamma", "Gamma AI", 11003)
    
    # 运行锦标赛
    report = arena.run_tournament()
    
    if report:
        # 保存报告
        arena.save_report(report)
        
        # 打印简要结果
        print("\n" + "=" * 60)
        print("锦标赛完成！")
        print("=" * 60)
        
        print(f"参赛AI数量: {len(report['participants'])}")
        print(f"总对局数: {report['total_games']}")
        print("\n最终排名:")
        
        # 按胜场数排序
        sorted_ais = sorted(
            report['ai_stats'].items(),
            key=lambda x: (x[1]['wins'], x[1]['draws']),
            reverse=True
        )
        
        for i, (ai_id, stats) in enumerate(sorted_ais, 1):
            print(f"{i}. {stats['name']} - 胜:{stats['wins']} 平:{stats['draws']} 负:{stats['losses']} "
                  f"(平均思考时间: {stats['avg_thinking_time']:.3f}秒)")
    else:
        print("锦标赛运行失败")

if __name__ == "__main__":
    main() 