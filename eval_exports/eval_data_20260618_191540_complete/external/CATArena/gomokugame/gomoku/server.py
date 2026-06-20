#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Dict, List, Tuple, Optional

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
        self.started_from_endgame = False
        self.endgame_file = None
    
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
        
        # 检查胜负
        if self.check_win(x, y, player_value):
            self.game_status = f"{player}_win"
        elif self.is_board_full():
            self.game_status = "draw"
        else:
            # 切换玩家
            self.current_player = "white" if player == "black" else "black"
        
        return True, "Move successful"
    
    def check_win(self, x: int, y: int, player_value: int) -> bool:
        """检查是否获胜"""
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]  # 四个检测方向
        
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
    
    def check_win_condition(self) -> bool:
        """检查当前棋盘是否有胜利条件"""
        for x in range(self.board_size):
            for y in range(self.board_size):
                if self.board[x][y] != 0:
                    if self.check_win(x, y, self.board[x][y]):
                        return True
        return False
    
    def get_state(self) -> Dict:
        """获取游戏状态"""
        return {
            "current_player": self.current_player,
            "board": self.board,
            "last_move": self.last_move,
            "game_status": self.game_status
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
    """创建新游戏，可选从残局开始"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player_black = data.get('player_black')
        player_white = data.get('player_white')
        end_game = data.get('end_game')  # 残局文件路径
        
        if not player_black or not player_white:
            return jsonify({"error": "Both players must be specified"}), 400
        
        game_id = f"gomoku_{str(uuid.uuid4())[:8]}"
        game = GomokuGame(game_id, player_black, player_white, BOARD_SIZE)
        
        # 如果提供了残局文件，从残局开始
        if end_game:
            try:
                # 读取残局文件
                with open(end_game, 'r') as f:
                    endgame_data = json.load(f)
                
                # 获取残局棋盘状态和历史走法
                endgame_info = endgame_data.get('endgame', {})
                board_state = endgame_info.get('board')
                history = endgame_info.get('history', [])
                
                if not board_state:
                    return jsonify({"error": "Invalid endgame file: board state not found"}), 400
                
                # 设置棋盘状态
                game.board = [row[:] for row in board_state]  # 深拷贝
                
                # 记录历史走法
                game.moves_history = history
                
                # 更新当前玩家
                game.current_player = endgame_info.get('current_player', 'black')
                
                # 检查游戏状态
                if game.check_win_condition():
                    game.game_status = f"{game.current_player}_win"
                elif game.is_board_full():
                    game.game_status = "draw"
                
                # 记录这是从残局开始的游戏
                game.started_from_endgame = True
                game.endgame_file = end_game
                
                # 将游戏添加到游戏字典中
                games[game_id] = game
                
                return jsonify({
                    "game_id": game_id,
                    "first_player": game.current_player,
                    "board_size": BOARD_SIZE,
                    "board": game.board,
                    "history": history,
                    "message": "Game created from endgame successfully"
                }), 201
            
            except FileNotFoundError:
                return jsonify({"error": f"Endgame file not found: {end_game}"}), 404
            except json.JSONDecodeError:
                return jsonify({"error": f"Invalid JSON in endgame file: {end_game}"}), 400
            except Exception as e:
                return jsonify({"error": f"Error loading endgame: {str(e)}"}), 500
        
        # 正常创建新游戏
        games[game_id] = game
        
        return jsonify({
            "game_id": game_id,
            "first_player": "black",
            "board_size": BOARD_SIZE
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
                "game_status": game.game_status
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
        "board_size": BOARD_SIZE
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def main():
    parser = argparse.ArgumentParser(description='五子棋HTTP服务器')
    parser.add_argument('--port', type=int, default=9000, help='监听端口 (默认: 9000)')
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