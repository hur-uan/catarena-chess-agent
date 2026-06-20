#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import uuid
import random
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Dict, List, Tuple, Optional, Set

app = Flask(__name__)

class GomokuGame:
    """五子棋游戏类"""
    
    def __init__(self, game_id: str, player_black: str, player_white: str, board_size: int = 15):
        self.game_id = game_id
        self.player_black = player_black
        self.player_white = player_white
        self.board_size = board_size
        self.board = [[0 for _ in range(board_size)] for _ in range(board_size)]
        self.current_player = "black"  # 黑方先手
        self.game_status = "ongoing"  # ongoing, black_win, white_win, draw
        self.moves_history = []
        self.last_move = None
        self.created_at = datetime.now()
        
        # 游戏属性
        self.forbidden_points = self._generate_forbidden_points()
        self.black_triplets = set()  # 黑方的三子连珠集合
        self.white_triplets = set()  # 白方的三子连珠集合
    
    def _generate_forbidden_points(self) -> Set[Tuple[int, int]]:
        """生成随机禁手点"""
        forbidden_points = set()
        total_points = self.board_size * self.board_size
        
        # 生成board_size数量的禁手点
        forbidden_count = min(self.board_size, total_points // 4)  # 最多占棋盘1/4
        
        while len(forbidden_points) < forbidden_count:
            x = random.randint(0, self.board_size - 1)
            y = random.randint(0, self.board_size - 1)
            forbidden_points.add((x, y))
        
        return forbidden_points
    
    def get_forbidden_points(self) -> List[List[int]]:
        """获取禁手点列表"""
        return [[x, y] for x, y in self.forbidden_points]
    
    def is_valid_move(self, player: str, position: List[int]) -> Tuple[bool, str]:
        """验证落子是否有效"""
        if self.game_status != "ongoing":
            return False, "Game is already over"
        
        if player != self.current_player:
            return False, "Not your turn"
        
        x, y = position
        if not (0 <= x < self.board_size and 0 <= y < self.board_size):
            return False, "Position out of board"
        
        if self.board[x][y] != 0:
            return False, "Position already occupied"
        
        # 检查特殊位置
        if (x, y) in self.forbidden_points:
            return False, "Position is forbidden"
        
        return True, "Valid move"
    
    def make_move(self, player: str, position: List[int]) -> Tuple[bool, str]:
        """执行落子"""
        is_valid, message = self.is_valid_move(player, position)
        if not is_valid:
            return False, message
        
        x, y = position
        player_value = 1 if player == "black" else 2
        self.board[x][y] = player_value
        
        # 记录历史
        self.moves_history.append({
            "player": player,
            "position": position,
            "timestamp": datetime.now().isoformat()
        })
        
        self.last_move = position
        
        # 检查特殊位置（虽然前面验证过，但再次确认）
        if (x, y) in self.forbidden_points:
            opponent = "white" if player == "black" else "black"
            self.game_status = f"{opponent}_win"
            return True, f"{player} hit forbidden point, {opponent} wins"
        
        # 检查新的三子连珠
        new_triplets = self.find_new_triplets(x, y, player_value)
        if player == "black":
            self.black_triplets.update(new_triplets)
        else:
            self.white_triplets.update(new_triplets)
        
        # 检查胜利条件
        if len(self.black_triplets) >= 2:
            self.game_status = "black_win"
        elif len(self.white_triplets) >= 2:
            self.game_status = "white_win"
        elif self.is_board_full():
            self.game_status = "draw"
        else:
            # 切换玩家
            self.current_player = "white" if player == "black" else "black"
        
        return True, "Move successful"
    
    def find_new_triplets(self, x: int, y: int, player_value: int) -> Set[Tuple[int, int, int, int]]:
        """寻找新形成的三子连珠"""
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]  # 四个检测方向
        new_triplets = set()
        
        for dx, dy in directions:
            # 检查这个方向上的连续子
            consecutive = self.get_consecutive_in_direction(x, y, dx, dy, player_value)
            
            # 如果连续子数>=3，检查是否形成新的三子连珠
            if len(consecutive) >= 3:
                # 检查所有可能的三子组合
                for i in range(len(consecutive) - 2):
                    triplet = tuple(sorted(consecutive[i:i+3]))
                    if len(triplet) == 3:
                        new_triplets.add(triplet)
        
        return new_triplets
    
    def get_consecutive_in_direction(self, x: int, y: int, dx: int, dy: int, player_value: int) -> List[Tuple[int, int]]:
        """获取某个方向上连续的棋子"""
        consecutive = [(x, y)]
        
        # 正向检测
        nx, ny = x + dx, y + dy
        while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
               self.board[nx][ny] == player_value):
            consecutive.append((nx, ny))
            nx += dx
            ny += dy
        
        # 反向检测
        nx, ny = x - dx, y - dy
        while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
               self.board[nx][ny] == player_value):
            consecutive.append((nx, ny))
            nx -= dx
            ny -= dy
        
        return consecutive
    
    def check_win(self, x: int, y: int, player_value: int) -> bool:
        """检查是否获胜（保留原方法用于兼容性）"""
        # 这个方法保留用于兼容
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        
        for dx, dy in directions:
            count = 1
            
            # 正向检测
            nx, ny = x + dx, y + dy
            while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                   self.board[nx][ny] == player_value):
                count += 1
                nx += dx
                ny += dy
            
            # 反向检测
            nx, ny = x - dx, y - dy
            while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                   self.board[nx][ny] == player_value):
                count += 1
                nx -= dx
                ny -= dy
            
            if count >= 5:
                return True
        
        return False
    
    def is_board_full(self) -> bool:
        """检查棋盘是否已满"""
        for row in self.board:
            if 0 in row:
                return False
        return True
    
    def get_state(self) -> Dict:
        """获取游戏状态"""
        return {
            "current_player": self.current_player,
            "board": self.board,
            "last_move": self.last_move,
            "game_status": self.game_status,
            "black_triplets_count": len(self.black_triplets),
            "white_triplets_count": len(self.white_triplets),
            "forbidden_points": self.get_forbidden_points(),
        }
    
    def get_history(self) -> Dict:
        """获取历史记录"""
        return {
            "moves": self.moves_history
        }

# 全局游戏存储
games: Dict[str, GomokuGame] = {}
BOARD_SIZE = 15  # 默认棋盘大小

@app.route('/games', methods=['POST'])
def create_game():
    """创建新游戏"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player_black = data.get('player_black')
        player_white = data.get('player_white')
        
        if not player_black or not player_white:
            return jsonify({"error": "Both players must be specified"}), 400
        
        game_id = f"gomoku_{str(uuid.uuid4())[:8]}"
        game = GomokuGame(game_id, player_black, player_white, BOARD_SIZE)
        games[game_id] = game
        
        return jsonify({
            "game_id": game_id,
            "first_player": "black",
            "board_size": BOARD_SIZE,
            "forbidden_points_count": len(game.forbidden_points)
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/state', methods=['GET'])
def get_game_state(game_id):
    """获取游戏状态"""
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    game = games[game_id]
    return jsonify(game.get_state())

@app.route('/games/<game_id>/forbidden_points', methods=['GET'])
def get_forbidden_points(game_id):
    """获取特殊位置信息"""
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    game = games[game_id]
    return jsonify({
        "game_id": game_id,
        "forbidden_points": game.get_forbidden_points(),
        "forbidden_points_count": len(game.forbidden_points)
    })

@app.route('/games/<game_id>/move', methods=['POST'])
def make_move(game_id):
    """提交落子"""
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player = data.get('player')
        position = data.get('position')
        
        if not player or position is None:
            return jsonify({"error": "Player and position must be specified"}), 400
        
        if player not in ['black', 'white']:
            return jsonify({"error": "Player must be 'black' or 'white'"}), 400
        
        if not isinstance(position, list) or len(position) != 2:
            return jsonify({"error": "Position must be a list with 2 elements"}), 400
        
        game = games[game_id]
        success, message = game.make_move(player, position)
        
        if success:
            return jsonify({
                "status": "valid_move",
                "game_status": game.game_status,
                "black_triplets_count": len(game.black_triplets),
                "white_triplets_count": len(game.white_triplets)
            })
        else:
            return jsonify({
                "status": "invalid_move",
                "error": message
            }), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/history', methods=['GET'])
def get_game_history(game_id):
    """获取游戏历史"""
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    game = games[game_id]
    return jsonify(game.get_history())

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "active_games": len(games),
        "board_size": BOARD_SIZE,
        "version": "gomoku_v1.0"
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def main():
    parser = argparse.ArgumentParser(description='五子棋HTTP服务器')
    parser.add_argument('--port', type=int, default=9001, help='监听端口 (默认: 9001)')
    parser.add_argument('--board_size', type=int, default=15, help='棋盘大小 (默认: 15)')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    global BOARD_SIZE
    BOARD_SIZE = args.board_size
    
    print(f"启动五子棋服务器...")
    print(f"端口: {args.port}")
    print(f"棋盘大小: {BOARD_SIZE}x{BOARD_SIZE}")
    print(f"调试模式: {args.debug}")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)

if __name__ == '__main__':
    main() 