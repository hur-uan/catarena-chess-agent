#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Dict, List, Tuple, Optional
import chess

app = Flask(__name__)

class ChessGame:
    """国际象棋游戏类"""
    
    def __init__(self, game_id: str, player_white: str, player_black: str):
        self.game_id = game_id
        self.player_white = player_white
        self.player_black = player_black
        self.board = chess.Board()  # 使用python-chess的Board
        self.game_status = "ongoing"  # ongoing, white_win, black_win, draw
        self.moves_history = []
        self.last_move = None
        self.created_at = datetime.now()
        self.started_from_endgame = False
        self.endgame_file = None
        self.current_player = "white"  # 默认白方先行
    
    def get_current_player(self) -> str:
        """获取当前玩家"""
        return "white" if self.board.turn else "black"
    
    def get_player_id(self, color: str) -> str:
        """根据颜色获取玩家ID"""
        return self.player_white if color == "white" else self.player_black
    
    def is_valid_move(self, player: str, move_uci: str) -> Tuple[bool, str]:
        """验证移动是否有效"""
        if self.game_status != "ongoing":
            return False, "Game is already over"
        
        current_player = self.get_current_player()
        if player != current_player:
            return False, "Not your turn"
        
        try:
            move = chess.Move.from_uci(move_uci)
            if move not in self.board.legal_moves:
                return False, "Invalid move"
            return True, "Valid move"
        except ValueError:
            return False, "Invalid move format"
    
    def make_move(self, player: str, move_uci: str) -> Tuple[bool, str]:
        """执行移动"""
        is_valid, message = self.is_valid_move(player, move_uci)
        if not is_valid:
            return False, message
        
        try:
            move = chess.Move.from_uci(move_uci)
            # 获取SAN表示（在移动执行前）
            san_move = self.board.san(move)
            self.board.push(move)
            
            # 记录历史
            self.moves_history.append({
                "player": player,
                "move": move_uci
            })
            
            self.last_move = move_uci
            
            # 检查游戏状态
            if self.board.is_checkmate():
                self.game_status = f"{player}_win"
            elif self.board.is_stalemate():
                self.game_status = "draw_stalemate"
            elif self.board.is_insufficient_material():
                self.game_status = "draw_insufficient_material"
            elif self.board.is_fivefold_repetition():
                self.game_status = "draw_fivefold_repetition"
            elif self.board.is_seventyfive_moves():
                self.game_status = "draw_seventyfive_moves"
            
            return True, "Move successful"
        except Exception as e:
            return False, f"Move execution failed: {str(e)}"
    
    def get_state(self) -> Dict:
        """获取游戏状态"""
        return {
            "current_player": self.get_current_player(),
            "fen": self.board.fen(),
            "last_move": self.last_move,
            "game_status": self.game_status,
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "legal_moves": [move.uci() for move in self.board.legal_moves]
        }
    
    def get_history(self) -> Dict:
        """获取历史记录"""
        return {
            "moves": self.moves_history
        }
    
    def get_board_visual(self) -> str:
        """获取棋盘可视化"""
        return str(self.board)

# 全局游戏存储
games: Dict[str, ChessGame] = {}

@app.route('/games', methods=['POST'])
def create_game():
    """创建新游戏，可选从残局开始"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player_white = data.get('player_white')
        player_black = data.get('player_black')
        end_game = data.get('end_game')  # 残局文件路径
        
        if not player_white or not player_black:
            return jsonify({"error": "Both players must be specified"}), 400
        
        game_id = f"chess_{str(uuid.uuid4())[:8]}"
        game = ChessGame(game_id, player_white, player_black)
        
        # 如果提供了残局文件，从残局开始
        if end_game:
            try:
                # 读取残局文件
                with open(end_game, 'r') as f:
                    endgame_data = json.load(f)
                
                # 获取残局FEN和历史走法
                endgame_info = endgame_data.get('endgame', {})
                fen = endgame_info.get('fen')
                history = endgame_info.get('history', [])
                
                if not fen:
                    return jsonify({"error": "Invalid endgame file: FEN not found"}), 400
                
                # 设置棋盘状态
                game.board = chess.Board(fen)
                
                # 记录历史走法
                game.moves_history = history
                
                # 更新游戏状态
                game.current_player = "white" if game.board.turn == chess.WHITE else "black"
                
                # 检查游戏状态
                if game.board.is_checkmate():
                    game.game_status = f"{game.current_player}_win"
                elif game.board.is_stalemate():
                    game.game_status = "draw_stalemate"
                elif game.board.is_insufficient_material():
                    game.game_status = "draw_insufficient_material"
                elif game.board.is_fivefold_repetition():
                    game.game_status = "draw_fivefold_repetition"
                elif game.board.is_seventyfive_moves():
                    game.game_status = "draw_seventyfive_moves"
                
                # 记录这是从残局开始的游戏
                game.started_from_endgame = True
                game.endgame_file = end_game
                
                # 将游戏添加到游戏字典中
                games[game_id] = game
                
                return jsonify({
                    "game_id": game_id,
                    "first_player": game.current_player,
                    "fen": game.board.fen(),
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
            "first_player": "white",
            "fen": game.board.fen(),
            "message": "Game created successfully"
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
    """提交移动"""
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player = data.get('player')
        move = data.get('move')
        
        if not player or not move:
            return jsonify({"error": "Player and move must be specified"}), 400
        
        if player not in ['white', 'black']:
            return jsonify({"error": "Player must be 'white' or 'black'"}), 400
        
        game = games[game_id]
        success, message = game.make_move(player, move)
        
        if success:
            return jsonify({
                "status": "valid_move",
                "game_status": game.game_status,
                "message": message,
                "new_state": game.get_state()
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

@app.route('/games/<game_id>/board', methods=['GET'])
def get_board_visual(game_id):
    """获取棋盘可视化"""
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    game = games[game_id]
    return jsonify({
        "game_id": game_id,
        "board_visual": game.get_board_visual(),
        "fen": game.board.fen()
    })

@app.route('/games/<game_id>/legal_moves', methods=['GET'])
def get_legal_moves(game_id):
    """获取合法移动"""
    if game_id not in games:
        return jsonify({"error": "Game not found"}), 404
    
    game = games[game_id]
    legal_moves = list(game.board.legal_moves)
    
    moves_info = []
    for move in legal_moves:
        moves_info.append({
            "uci": move.uci(),
            "san": game.board.san(move),
            "from_square": chess.square_name(move.from_square),
            "to_square": chess.square_name(move.to_square),
            "promotion": chess.piece_symbol(move.promotion) if move.promotion else None
        })
    
    return jsonify({
        "game_id": game_id,
        "current_player": game.get_current_player(),
        "legal_moves": moves_info
    })

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "active_games": len(games),
        "server": "Chess HTTP Server",
        "version": "1.0",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/games', methods=['GET'])
def list_games():
    """列出所有游戏"""
    games_info = []
    for game_id, game in games.items():
        games_info.append({
            "game_id": game_id,
            "player_white": game.player_white,
            "player_black": game.player_black,
            "game_status": game.game_status,
            "current_player": game.get_current_player(),
            "moves_count": len(game.moves_history),
            "created_at": game.created_at.isoformat()
        })
    
    return jsonify({
        "games": games_info,
        "total_games": len(games)
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def main():
    parser = argparse.ArgumentParser(description='国际象棋HTTP服务器')
    parser.add_argument('--port', type=int, default=9020, help='监听端口 (默认: 9020)')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    print(f"=== 国际象棋HTTP服务器 ===")
    print(f"端口: {args.port}")
    print(f"调试模式: {args.debug}")
    print(f"服务器地址: http://localhost:{args.port}")
    print("")
    print("可用端点:")
    print("  POST /games              - 创建新游戏")
    print("  GET  /games              - 列出所有游戏")
    print("  GET  /games/{id}/state   - 获取游戏状态")
    print("  POST /games/{id}/move    - 提交移动")
    print("  GET  /games/{id}/history - 获取游戏历史")
    print("  GET  /games/{id}/board   - 获取棋盘可视化")
    print("  GET  /games/{id}/legal_moves - 获取合法移动")
    print("  GET  /health             - 健康检查")
    print("")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)

if __name__ == '__main__':
    main() 