#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Dict, List, Tuple, Optional
import copy

app = Flask(__name__)

class FastGomokuAI:
    """快速五子棋AI - 优化版本，在保持竞争力的同时降低复杂度"""
    
    def __init__(self, ai_id: str, ai_name: str = "Fast Gomoku AI"):
        self.ai_id = ai_id
        self.ai_name = ai_name
        self.version = "2.0"
        self.description = "Fast and competitive Gomoku AI with optimized time complexity"
        self.capabilities = [
            "immediate_win_detection",
            "immediate_defense_detection", 
            "threat_building",
            "pattern_recognition",
            "minimax_search",
            "alpha_beta_pruning",
            "time_controlled"
        ]
        self.active_games = {}
        self.lock = threading.Lock()
        
        # 游戏常量
        self.BOARD_SIZE = 15
        self.EMPTY = 0
        self.BLACK = 1
        self.WHITE = 2
        self.DIRECTIONS = [(1, 0), (0, 1), (1, 1), (1, -1)]
        
        # 优化后的AI配置 - 降低复杂度
        self.MAX_DEPTH = 2  # 减少搜索深度从4到2
        self.MAX_TIME = 8.0  # 最大思考时间8秒，留2秒buffer
        self.MAX_CANDIDATES = 12  # 减少候选走法从20到12
        self.THREAT_THRESHOLD = 3
        
        # 简化的位置权重
        self.position_weights = self._init_simple_weights()
        
        # 优化的模式评分表
        self.patterns = self._init_optimized_patterns()
    
    def _init_simple_weights(self) -> List[List[int]]:
        """初始化简化的位置权重矩阵"""
        weights = []
        center = self.BOARD_SIZE // 2
        
        for i in range(self.BOARD_SIZE):
            row = []
            for j in range(self.BOARD_SIZE):
                # 简化的距离计算
                dist_to_center = abs(i - center) + abs(j - center)
                weight = max(1, 8 - dist_to_center)
                row.append(weight)
            weights.append(row)
        
        return weights
    
    def _init_optimized_patterns(self) -> Dict[str, int]:
        """初始化优化的棋型评分表"""
        return {
            # 关键模式 - 简化评分
            'five': 100000,
            'live_four': 10000,
            'dead_four': 1000,
            'live_three': 500,
            'dead_three': 50,
            'live_two': 10,
            'dead_two': 1
        }
    
    def get_move(self, game_id: str, board: List[List[int]], current_player: str) -> Tuple[int, int]:
        """获取最佳走法 - 带时间控制"""
        start_time = time.time()
        
        # 转换玩家颜色
        my_color = self.BLACK if current_player == "black" else self.WHITE
        opponent_color = self.WHITE if my_color == self.BLACK else self.BLACK
        
        # 第一步下中心附近
        if self._is_empty_board(board):
            center = self.BOARD_SIZE // 2
            return (center, center)
        
        # 立即获胜检测
        win_move = self._find_winning_move(board, my_color)
        if win_move:
            return win_move
        
        # 立即防守检测
        defend_move = self._find_winning_move(board, opponent_color)
        if defend_move:
            return defend_move
        
        # 使用迭代加深搜索，带时间控制
        best_move = self._iterative_deepening_search(
            board, my_color, opponent_color, start_time
        )
        
        elapsed_time = time.time() - start_time
        print(f"AI思考时间: {elapsed_time:.2f}秒, 选择位置: {best_move}")
        
        return best_move if best_move else self._get_smart_fallback(board)
    
    def _is_empty_board(self, board: List[List[int]]) -> bool:
        """检查是否为空棋盘"""
        for row in board:
            for cell in row:
                if cell != self.EMPTY:
                    return False
        return True
    
    def _find_winning_move(self, board: List[List[int]], color: int) -> Optional[Tuple[int, int]]:
        """寻找能够立即获胜的走法"""
        for i in range(self.BOARD_SIZE):
            for j in range(self.BOARD_SIZE):
                if board[i][j] == self.EMPTY:
                    board[i][j] = color
                    if self._check_win(board, i, j, color):
                        board[i][j] = self.EMPTY
                        return (i, j)
                    board[i][j] = self.EMPTY
        return None
    
    def _check_win(self, board: List[List[int]], x: int, y: int, color: int) -> bool:
        """检查指定位置是否能获胜"""
        for dx, dy in self.DIRECTIONS:
            count = 1
            
            # 正向计数
            nx, ny = x + dx, y + dy
            while (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE and 
                   board[nx][ny] == color):
                count += 1
                nx += dx
                ny += dy
            
            # 反向计数
            nx, ny = x - dx, y - dy
            while (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE and 
                   board[nx][ny] == color):
                count += 1
                nx -= dx
                ny -= dy
            
            if count >= 5:
                return True
        
        return False
    
    def _iterative_deepening_search(self, board: List[List[int]], my_color: int, 
                                  opponent_color: int, start_time: float) -> Optional[Tuple[int, int]]:
        """迭代加深搜索，带时间控制"""
        best_move = None
        
        # 从深度1开始搜索
        for depth in range(1, self.MAX_DEPTH + 1):
            if time.time() - start_time > self.MAX_TIME:
                break
            
            try:
                _, move = self._minimax_with_timeout(
                    board, depth, float('-inf'), float('inf'), 
                    True, my_color, opponent_color, start_time
                )
                if move:
                    best_move = move
            except TimeoutError:
                break
        
        return best_move
    
    def _minimax_with_timeout(self, board: List[List[int]], depth: int, alpha: float, 
                             beta: float, is_maximizing: bool, my_color: int, 
                             opponent_color: int, start_time: float) -> Tuple[float, Optional[Tuple[int, int]]]:
        """带超时的Minimax算法"""
        
        # 检查超时
        if time.time() - start_time > self.MAX_TIME:
            raise TimeoutError("Search timeout")
        
        # 终止条件
        if depth == 0 or self._is_game_over(board):
            return self._quick_evaluate(board, my_color, opponent_color), None
        
        best_move = None
        candidates = self._get_smart_candidates(board)
        
        if is_maximizing:
            max_eval = float('-inf')
            for move in candidates:
                x, y = move
                board[x][y] = my_color
                
                eval_score, _ = self._minimax_with_timeout(
                    board, depth - 1, alpha, beta, False, 
                    my_color, opponent_color, start_time
                )
                
                board[x][y] = self.EMPTY
                
                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move
                
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break  # Alpha-Beta剪枝
            
            return max_eval, best_move
        else:
            min_eval = float('inf')
            for move in candidates:
                x, y = move
                board[x][y] = opponent_color
                
                eval_score, _ = self._minimax_with_timeout(
                    board, depth - 1, alpha, beta, True, 
                    my_color, opponent_color, start_time
                )
                
                board[x][y] = self.EMPTY
                
                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move
                
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break  # Alpha-Beta剪枝
            
            return min_eval, best_move
    
    def _is_game_over(self, board: List[List[int]]) -> bool:
        """快速检查游戏是否结束"""
        # 只检查最近的几步是否有获胜
        for i in range(self.BOARD_SIZE):
            for j in range(self.BOARD_SIZE):
                if board[i][j] != self.EMPTY:
                    if self._check_win(board, i, j, board[i][j]):
                        return True
        return False
    
    def _get_smart_candidates(self, board: List[List[int]]) -> List[Tuple[int, int]]:
        """获取智能候选走法"""
        candidates = set()
        
        # 在已有棋子周围找候选位置
        for i in range(self.BOARD_SIZE):
            for j in range(self.BOARD_SIZE):
                if board[i][j] != self.EMPTY:
                    # 只检查距离为1的位置
                    for di in range(-1, 2):
                        for dj in range(-1, 2):
                            ni, nj = i + di, j + dj
                            if (0 <= ni < self.BOARD_SIZE and 0 <= nj < self.BOARD_SIZE and 
                                board[ni][nj] == self.EMPTY):
                                candidates.add((ni, nj))
        
        # 如果候选位置太少，扩展搜索范围
        if len(candidates) < 6:
            for i in range(self.BOARD_SIZE):
                for j in range(self.BOARD_SIZE):
                    if board[i][j] != self.EMPTY:
                        for di in range(-2, 3):
                            for dj in range(-2, 3):
                                ni, nj = i + di, j + dj
                                if (0 <= ni < self.BOARD_SIZE and 0 <= nj < self.BOARD_SIZE and 
                                    board[ni][nj] == self.EMPTY):
                                    candidates.add((ni, nj))
        
        # 按价值排序并限制数量
        candidates = list(candidates)
        candidates.sort(key=lambda pos: self._quick_position_value(board, pos[0], pos[1]), reverse=True)
        
        return candidates[:self.MAX_CANDIDATES]
    
    def _quick_evaluate(self, board: List[List[int]], my_color: int, opponent_color: int) -> float:
        """快速评估函数"""
        my_score = 0
        opponent_score = 0
        
        # 简化的评估 - 只检查连子情况
        for i in range(self.BOARD_SIZE):
            for j in range(self.BOARD_SIZE):
                if board[i][j] == my_color:
                    my_score += self._count_lines(board, i, j, my_color)
                elif board[i][j] == opponent_color:
                    opponent_score += self._count_lines(board, i, j, opponent_color)
        
        return my_score - opponent_score * 1.1  # 稍微偏重防守
    
    def _count_lines(self, board: List[List[int]], x: int, y: int, color: int) -> float:
        """快速计算线形价值"""
        score = 0
        
        for dx, dy in self.DIRECTIONS:
            count = 1
            blocks = 0
            
            # 正向
            nx, ny = x + dx, y + dy
            while (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE and 
                   board[nx][ny] == color):
                count += 1
                nx += dx 
                ny += dy
            
            if not (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE) or board[nx][ny] != self.EMPTY:
                blocks += 1
            
            # 反向
            nx, ny = x - dx, y - dy
            while (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE and 
                   board[nx][ny] == color):
                count += 1
                nx -= dx
                ny -= dy
            
            if not (0 <= nx < self.BOARD_SIZE and 0 <= ny < self.BOARD_SIZE) or board[nx][ny] != self.EMPTY:
                blocks += 1
            
            # 简化的评分
            if count >= 5:
                score += 10000
            elif count == 4:
                score += 1000 if blocks == 0 else 100
            elif count == 3:
                score += 100 if blocks == 0 else 10
            elif count == 2:
                score += 10 if blocks == 0 else 1
        
        return score
    
    def _quick_position_value(self, board: List[List[int]], x: int, y: int) -> float:
        """快速位置价值评估"""
        # 基础位置权重
        value = self.position_weights[x][y]
        
        # 检查周围是否有棋子
        neighbor_count = 0
        for di in range(-1, 2):
            for dj in range(-1, 2):
                ni, nj = x + di, y + dj
                if (0 <= ni < self.BOARD_SIZE and 0 <= nj < self.BOARD_SIZE and 
                    board[ni][nj] != self.EMPTY):
                    neighbor_count += 1
        
        # 有邻居的位置更有价值
        value += neighbor_count * 5
        
        return value
    
    def _get_smart_fallback(self, board: List[List[int]]) -> Tuple[int, int]:
        """智能后备走法"""
        # 寻找最有价值的空位
        best_pos = None
        best_value = -1
        
        for i in range(self.BOARD_SIZE):
            for j in range(self.BOARD_SIZE):
                if board[i][j] == self.EMPTY:
                    value = self._quick_position_value(board, i, j)
                    if value > best_value:
                        best_value = value
                        best_pos = (i, j)
        
        return best_pos if best_pos else (7, 7)

# 全局AI实例
ai_instance: Optional[FastGomokuAI] = None

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "ai_id": ai_instance.ai_id if ai_instance else "unknown",
        "active_games": len(ai_instance.active_games) if ai_instance else 0
    })

@app.route('/info', methods=['GET'])
def get_info():
    """获取AI信息"""
    if not ai_instance:
        return jsonify({"error": "AI not initialized"}), 500
    
    return jsonify({
        "ai_id": ai_instance.ai_id,
        "name": ai_instance.ai_name,
        "version": ai_instance.version,
        "description": ai_instance.description,
        "capabilities": ai_instance.capabilities
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    """加入游戏"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        my_color = data.get('my_color')
        game_server_url = data.get('game_server_url')
        
        if not all([game_id, my_color, game_server_url]):
            return jsonify({"error": "Missing required parameters"}), 400
        
        if my_color not in ['black', 'white']:
            return jsonify({"error": "Invalid color"}), 400
        
        with ai_instance.lock:
            ai_instance.active_games[game_id] = {
                "my_color": my_color,
                "game_server_url": game_server_url,
                "joined_at": datetime.now().isoformat()
            }
        
        return jsonify({
            "status": "joined",
            "ai_id": ai_instance.ai_id,
            "game_id": game_id,
            "my_color": my_color
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_move', methods=['POST'])
def get_move():
    """获取AI走法"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        board = data.get('board')
        current_player = data.get('current_player')
        
        if not all([game_id, board is not None, current_player]):
            return jsonify({"error": "Missing required parameters"}), 400
        
        if current_player not in ['black', 'white']:
            return jsonify({"error": "Invalid current_player"}), 400
        
        # 获取最佳走法
        move = ai_instance.get_move(game_id, board, current_player)
        
        reasoning = f"快速算法分析，选择位置 {move}"
        
        return jsonify({
            "move": list(move),
            "ai_id": ai_instance.ai_id,
            "game_id": game_id,
            "reasoning": reasoning
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/leave_game', methods=['POST'])
def leave_game():
    """离开游戏"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        if not game_id:
            return jsonify({"error": "Missing game_id"}), 400
        
        with ai_instance.lock:
            if game_id in ai_instance.active_games:
                del ai_instance.active_games[game_id]
        
        return jsonify({
            "status": "left",
            "ai_id": ai_instance.ai_id,
            "game_id": game_id
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def main():
    global ai_instance
    
    parser = argparse.ArgumentParser(description='快速五子棋AI服务器')
    parser.add_argument('--port', type=int, default=11001, help='监听端口 (默认: 11001)')
    parser.add_argument('--ai_id', type=str, default='FastGomoku', help='AI ID')
    parser.add_argument('--ai_name', type=str, default='Fast Gomoku AI', help='AI名称')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    # 初始化AI实例
    ai_instance = FastGomokuAI(args.ai_id, args.ai_name)
    
    print(f"启动快速五子棋AI服务器...")
    print(f"AI ID: {args.ai_id}")
    print(f"AI名称: {args.ai_name}")
    print(f"端口: {args.port}")
    print(f"最大搜索深度: {ai_instance.MAX_DEPTH}")
    print(f"最大思考时间: {ai_instance.MAX_TIME}秒")
    print(f"最大候选走法: {ai_instance.MAX_CANDIDATES}")
    print(f"调试模式: {args.debug}")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()
