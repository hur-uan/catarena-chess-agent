#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能五子棋AI服务
实现三子连珠获胜机制的AI策略
"""

import argparse
import requests
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Dict, List, Tuple, Set, Optional
from collections import defaultdict

app = Flask(__name__)

class SmartGomokuAI:
    """智能五子棋AI - 基于三子连珠机制"""
    
    def __init__(self, ai_id: str, ai_name: str):
        self.ai_id = ai_id
        self.ai_name = ai_name
        self.active_games = {}
        self.lock = threading.Lock()
        self.version = "1.0"
        
    def join_game(self, game_id: str, my_color: str, game_server_url: str) -> Dict:
        """加入游戏"""
        with self.lock:
            if game_id in self.active_games:
                return {"status": "error", "message": "Already in this game"}
            
            # 获取游戏状态和禁手点
            try:
                state_response = requests.get(f"{game_server_url}/games/{game_id}/state", timeout=3)
                forbidden_response = requests.get(f"{game_server_url}/games/{game_id}/forbidden_points", timeout=3)
                
                if state_response.status_code == 200 and forbidden_response.status_code == 200:
                    state = state_response.json()
                    forbidden_data = forbidden_response.json()
                    
                    self.active_games[game_id] = {
                        "my_color": my_color,
                        "game_server_url": game_server_url,
                        "board_size": len(state["board"]),
                        "forbidden_points": set(tuple(p) for p in forbidden_data["forbidden_points"]),
                        "joined_at": datetime.now()
                    }
                    
                    return {
                        "status": "joined",
                        "ai_id": self.ai_id,
                        "game_id": game_id,
                        "my_color": my_color
                    }
                else:
                    return {"status": "error", "message": "Failed to get game info"}
            except Exception as e:
                return {"status": "error", "message": f"Connection error: {str(e)}"}
    
    def get_move(self, game_id: str, board: List[List[int]], current_player: str) -> Dict:
        """获取最佳落子位置"""
        with self.lock:
            if game_id not in self.active_games:
                return {"status": "error", "message": "Not in this game"}
            
            game_info = self.active_games[game_id]
            
            # 检查是否轮到我
            if current_player != game_info["my_color"]:
                return {"status": "error", "message": "Not my turn"}
            
            try:
                # 计算最佳落子
                start_time = time.time()
                best_move, reasoning = self.calculate_best_move(
                    board, 
                    current_player,
                    game_info["forbidden_points"],
                    game_info["board_size"]
                )
                
                elapsed = time.time() - start_time
                
                if best_move is None:
                    return {"status": "error", "message": "No valid moves available"}
                
                return {
                    "move": list(best_move),
                    "ai_id": self.ai_id,
                    "game_id": game_id,
                    "reasoning": f"{reasoning} (决策用时: {elapsed:.3f}s)"
                }
            except Exception as e:
                return {"status": "error", "message": f"Error calculating move: {str(e)}"}
    
    def leave_game(self, game_id: str) -> Dict:
        """离开游戏"""
        with self.lock:
            if game_id in self.active_games:
                del self.active_games[game_id]
                return {
                    "status": "left",
                    "ai_id": self.ai_id,
                    "game_id": game_id
                }
            return {"status": "error", "message": "Not in this game"}
    
    def calculate_best_move(self, board: List[List[int]], my_color: str, 
                           forbidden_points: Set[Tuple[int, int]], 
                           board_size: int) -> Tuple[Optional[Tuple[int, int]], str]:
        """计算最佳落子位置 - 核心AI逻辑"""
        
        my_value = 1 if my_color == "black" else 2
        opponent_value = 2 if my_color == "black" else 1
        
        # 统计当前三子连珠数量
        my_triplets = self.count_triplets(board, my_value, board_size)
        opponent_triplets = self.count_triplets(board, opponent_value, board_size)
        
        # 获取所有有效位置
        valid_moves = []
        for i in range(board_size):
            for j in range(board_size):
                if board[i][j] == 0 and (i, j) not in forbidden_points:
                    valid_moves.append((i, j))
        
        if not valid_moves:
            return None, "无有效落子点"
        
        # 评估每个位置
        best_move = None
        best_score = float('-inf')
        best_reasoning = ""
        
        for move in valid_moves:
            x, y = move
            score, reason = self.evaluate_move(
                board, x, y, my_value, opponent_value, 
                my_triplets, opponent_triplets, board_size
            )
            
            if score > best_score:
                best_score = score
                best_move = move
                best_reasoning = reason
        
        return best_move, best_reasoning
    
    def evaluate_move(self, board: List[List[int]], x: int, y: int, 
                     my_value: int, opponent_value: int,
                     current_my_triplets: int, current_opponent_triplets: int,
                     board_size: int) -> Tuple[float, str]:
        """评估某个位置的价值"""
        
        score = 0.0
        reasons = []
        
        # 模拟落子
        board[x][y] = my_value
        
        # 1. 计算此位置能形成的新三子连珠数量（最重要！）
        new_triplets = self.count_new_triplets_at(board, x, y, my_value, board_size)
        if new_triplets > 0:
            potential_total = current_my_triplets + new_triplets
            if potential_total >= 2:
                score += 10000  # 直接获胜
                reasons.append(f"获胜之手！形成第{potential_total}个三子连珠")
            else:
                score += new_triplets * 500  # 形成三子连珠很重要
                reasons.append(f"形成{new_triplets}个三子连珠")
        
        # 2. 检查是否能阻止对手获胜
        board[x][y] = opponent_value
        opponent_new_triplets = self.count_new_triplets_at(board, x, y, opponent_value, board_size)
        if opponent_new_triplets > 0:
            potential_opponent_total = current_opponent_triplets + opponent_new_triplets
            if potential_opponent_total >= 2:
                score += 8000  # 必须防守！
                reasons.append("阻止对手获胜")
            else:
                score += opponent_new_triplets * 300
                reasons.append(f"阻止对手形成三子连珠")
        
        # 恢复落子为我方
        board[x][y] = my_value
        
        # 3. 评估连续棋子数量（为形成三子连珠做准备）
        for dx, dy in [(1, 0), (0, 1), (1, 1), (1, -1)]:
            my_consecutive = self.count_consecutive(board, x, y, dx, dy, my_value, board_size)
            opponent_consecutive = self.count_consecutive(board, x, y, dx, dy, opponent_value, board_size)
            
            # 有两个连续子，下一步可能形成三子
            if my_consecutive == 2:
                score += 100
            # 有四个连续子（虽然不是获胜条件，但可能包含多个三子连珠）
            elif my_consecutive >= 4:
                score += 200
            
            # 防守对手的连续
            if opponent_consecutive == 2:
                score += 80
        
        # 4. 位置价值（中心区域更有价值）
        center = board_size // 2
        distance_to_center = abs(x - center) + abs(y - center)
        score += (board_size - distance_to_center) * 2
        
        # 5. 邻近性评估（靠近已有棋子）
        neighbors = self.count_neighbors(board, x, y, board_size)
        score += neighbors * 10
        
        # 恢复棋盘
        board[x][y] = 0
        
        reasoning = "; ".join(reasons) if reasons else f"位置评分: {score:.1f}"
        return score, reasoning
    
    def count_new_triplets_at(self, board: List[List[int]], x: int, y: int, 
                              player_value: int, board_size: int) -> int:
        """计算在(x,y)位置能形成多少个新的三子连珠"""
        new_triplets = set()
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        
        for dx, dy in directions:
            consecutive_positions = self.get_consecutive_positions(
                board, x, y, dx, dy, player_value, board_size
            )
            
            # 如果有3个或以上连续，检查所有三子组合
            if len(consecutive_positions) >= 3:
                for i in range(len(consecutive_positions) - 2):
                    triplet = tuple(sorted(consecutive_positions[i:i+3]))
                    new_triplets.add(triplet)
        
        return len(new_triplets)
    
    def count_triplets(self, board: List[List[int]], player_value: int, board_size: int) -> int:
        """统计当前棋盘上的三子连珠数量"""
        triplets = set()
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        
        for i in range(board_size):
            for j in range(board_size):
                if board[i][j] == player_value:
                    for dx, dy in directions:
                        consecutive = self.get_consecutive_positions(
                            board, i, j, dx, dy, player_value, board_size
                        )
                        if len(consecutive) >= 3:
                            for k in range(len(consecutive) - 2):
                                triplet = tuple(sorted(consecutive[k:k+3]))
                                triplets.add(triplet)
        
        return len(triplets)
    
    def get_consecutive_positions(self, board: List[List[int]], x: int, y: int,
                                  dx: int, dy: int, player_value: int, 
                                  board_size: int) -> List[Tuple[int, int]]:
        """获取某个方向上的连续棋子位置"""
        positions = [(x, y)]
        
        # 正向
        nx, ny = x + dx, y + dy
        while 0 <= nx < board_size and 0 <= ny < board_size and board[nx][ny] == player_value:
            positions.append((nx, ny))
            nx += dx
            ny += dy
        
        # 反向
        nx, ny = x - dx, y - dy
        while 0 <= nx < board_size and 0 <= ny < board_size and board[nx][ny] == player_value:
            positions.append((nx, ny))
            nx -= dx
            ny -= dy
        
        return positions
    
    def count_consecutive(self, board: List[List[int]], x: int, y: int,
                         dx: int, dy: int, player_value: int, board_size: int) -> int:
        """计算某个方向上的连续棋子数"""
        count = 1
        
        # 正向
        nx, ny = x + dx, y + dy
        while 0 <= nx < board_size and 0 <= ny < board_size and board[nx][ny] == player_value:
            count += 1
            nx += dx
            ny += dy
        
        # 反向
        nx, ny = x - dx, y - dy
        while 0 <= nx < board_size and 0 <= ny < board_size and board[nx][ny] == player_value:
            count += 1
            nx -= dx
            ny -= dy
        
        return count
    
    def count_neighbors(self, board: List[List[int]], x: int, y: int, board_size: int) -> int:
        """计算周围8个方向有多少个棋子"""
        count = 0
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < board_size and 0 <= ny < board_size and board[nx][ny] != 0:
                    count += 1
        return count
    
    def get_info(self) -> Dict:
        """获取AI信息"""
        return {
            "ai_id": self.ai_id,
            "name": self.ai_name,
            "version": self.version,
            "description": "智能五子棋AI - 专注于三子连珠策略",
            "capabilities": [
                "三子连珠识别",
                "防守策略",
                "位置评估",
                "禁手点规避"
            ]
        }

# 全局AI实例
ai_instance: Optional[SmartGomokuAI] = None

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
    return jsonify(ai_instance.get_info())

@app.route('/join_game', methods=['POST'])
def join_game():
    """加入游戏"""
    if not ai_instance:
        return jsonify({"error": "AI not initialized"}), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        my_color = data.get('my_color')
        game_server_url = data.get('game_server_url')
        
        if not all([game_id, my_color, game_server_url]):
            return jsonify({"error": "Missing required fields"}), 400
        
        result = ai_instance.join_game(game_id, my_color, game_server_url)
        
        if result.get("status") == "error":
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_move', methods=['POST'])
def get_move():
    """获取落子"""
    if not ai_instance:
        return jsonify({"error": "AI not initialized"}), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        board = data.get('board')
        current_player = data.get('current_player')
        
        if not all([game_id, board is not None, current_player]):
            return jsonify({"error": "Missing required fields"}), 400
        
        result = ai_instance.get_move(game_id, board, current_player)
        
        if result.get("status") == "error":
            return jsonify(result), 400
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/leave_game', methods=['POST'])
def leave_game():
    """离开游戏"""
    if not ai_instance:
        return jsonify({"error": "AI not initialized"}), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        if not game_id:
            return jsonify({"error": "Missing game_id"}), 400
        
        result = ai_instance.leave_game(game_id)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def main():
    parser = argparse.ArgumentParser(description='智能五子棋AI HTTP服务')
    parser.add_argument('--port', type=int, default=21000, help='监听端口 (默认: 21000)')
    parser.add_argument('--ai_id', type=str, default='SmartAI_Alpha', help='AI ID')
    parser.add_argument('--ai_name', type=str, default='智能AI Alpha', help='AI名称')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    global ai_instance
    ai_instance = SmartGomokuAI(args.ai_id, args.ai_name)
    
    print(f"启动智能五子棋AI服务...")
    print(f"AI ID: {args.ai_id}")
    print(f"AI名称: {args.ai_name}")
    print(f"端口: {args.port}")
    print(f"调试模式: {args.debug}")
    print(f"\n核心策略: 三子连珠获胜机制")
    print(f"API地址: http://localhost:{args.port}")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug, threaded=True)

if __name__ == '__main__':
    main()

