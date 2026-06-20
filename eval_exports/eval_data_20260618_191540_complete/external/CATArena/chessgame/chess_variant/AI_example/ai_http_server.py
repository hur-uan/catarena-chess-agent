#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import random
import argparse
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Tuple, Optional, Dict
import chess
import chess.engine

app = Flask(__name__)

class ChessAI:
    """国际象棋AI核心逻辑"""
    
    def __init__(self, ai_id: str, ai_name: str = None, game_server_url: str = "http://localhost:9021"):
        self.ai_id = ai_id
        self.ai_name = ai_name or f"Chess AI {ai_id}"
        self.game_server_url = game_server_url
        self.active_games = {}  # game_id -> game_info
        self.thinking_time = 1.0
    
    def get_best_move_simple(self, board: chess.Board) -> Optional[chess.Move]:
        """简单的AI算法：随机选择合法移动"""
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None
        
        return random.choice(legal_moves)
    
    def find_best_move(self, fen: str, algorithm: str = "simple") -> Optional[str]:
        """寻找最佳移动"""
        try:
            board = chess.Board(fen)
        except ValueError:
            return None
        
        if board.is_game_over():
            return None
        
        best_move = self.get_best_move_simple(board)
        return best_move.uci() if best_move else None

    def pick_move_from_server(self, game_id: str) -> Optional[str]:
        """从游戏服务器获取移动"""
        try:
            # 获取状态
            st = requests.get(f"{self.game_server_url}/games/{game_id}/state", timeout=5).json()
            
            # 读取游戏信息
            game_info = {}
            if "mutated_piece_type" in st:
                game_info["mutated_piece"] = st["mutated_piece_type"]
            if "obstacles" in st:
                game_info["obstacles"] = st["obstacles"]
            
            print(f"[AI] Game info: {game_info}")

            # 获取当前可走步
            lm = requests.get(f"{self.game_server_url}/games/{game_id}/legal_moves", timeout=5).json()
            legal = lm.get("legal_moves", [])
            if not legal:
                return None
            
            # 简单选择：随机其一
            return random.choice(legal)["uci"]
        except Exception as e:
            print("[AI] pick_move error:", e)
            return None

# 全局AI实例
ai_instance = None

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "ai_id": ai_instance.ai_id if ai_instance else "unknown",
        "active_games": len(ai_instance.active_games) if ai_instance else 0,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/info', methods=['GET'])
def get_ai_info():
    """获取AI信息"""
    return jsonify({
        "ai_id": ai_instance.ai_id if ai_instance else "unknown",
        "name": ai_instance.ai_name if ai_instance else "unknown",
        "version": "1.0",
        "description": "A simple Chess AI with random strategy",
        "capabilities": ["simple_move", "legal_moves"]
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    """加入游戏"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        my_color = data.get('my_color')  # "white" or "black"
        game_server_url = data.get('game_server_url', "http://localhost:9021")
        
        if not game_id or not my_color:
            return jsonify({"error": "game_id and my_color are required"}), 400
        
        if my_color not in ['white', 'black']:
            return jsonify({"error": "my_color must be 'white' or 'black'"}), 400
        
        # 更新AI实例的游戏服务器URL
        ai_instance.game_server_url = game_server_url
        
        # 记录游戏信息
        ai_instance.active_games[game_id] = {
            "my_color": my_color,
            "joined_at": datetime.now().isoformat()
        }
        
        print(f"AI {ai_instance.ai_id} 加入游戏 {game_id}，颜色: {my_color}")
        
        return jsonify({
            "status": "joined",
            "ai_id": ai_instance.ai_id,
            "game_id": game_id,
            "my_color": my_color
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
            return jsonify({"error": "game_id is required"}), 400
        
        if game_id in ai_instance.active_games:
            del ai_instance.active_games[game_id]
            print(f"AI {ai_instance.ai_id} 离开游戏 {game_id}")
        
        return jsonify({
            "status": "left",
            "ai_id": ai_instance.ai_id,
            "game_id": game_id
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games', methods=['GET'])
def list_games():
    """列出当前参与的游戏"""
    return jsonify({
        "ai_id": ai_instance.ai_id,
        "active_games": ai_instance.active_games
    })

@app.route('/move', methods=['POST'])
def get_move():
    """获取移动（主要API）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        fen = data.get('fen')
        algorithm = data.get('algorithm', 'simple')
        
        if not fen:
            return jsonify({"error": "FEN string is required"}), 400
        
        # 解析FEN
        try:
            board = chess.Board(fen)
        except ValueError as e:
            return jsonify({"error": f"Invalid FEN: {str(e)}"}), 400
        
        # 检查游戏是否结束
        if board.is_game_over():
            return jsonify({
                "error": "Game is over",
                "result": board.result()
            }), 400
        
        # 获取AI移动
        start_time = time.time()
        best_move = ai_instance.get_best_move_simple(board)
        thinking_time = time.time() - start_time
        
        if best_move is None:
            return jsonify({"error": "No legal moves available"}), 400
        
        # 获取移动的SAN表示
        san_move = board.san(best_move)
        
        return jsonify({
            "ai_id": ai_instance.ai_id,
            "ai_name": ai_instance.ai_name,
            "move": best_move.uci(),
            "san": san_move,
            "from_square": chess.square_name(best_move.from_square),
            "to_square": chess.square_name(best_move.to_square),
            "promotion": chess.piece_symbol(best_move.promotion) if best_move.promotion else None,
            "algorithm": algorithm,
            "thinking_time": round(thinking_time, 3),
            "evaluation": 0.0,
            "timestamp": datetime.now().isoformat()
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
    parser = argparse.ArgumentParser(description='国际象棋AI HTTP服务器')
    parser.add_argument('--port', type=int, default=41101, help='监听端口 (默认: 41101)')
    parser.add_argument('--ai_id', type=str, default=None, help='AI标识符')
    parser.add_argument('--ai_name', type=str, default=None, help='AI名称')
    parser.add_argument('--game_server', type=str, default='http://localhost:9021', help='游戏服务器地址')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    # 生成AI ID
    ai_id = args.ai_id or f"ChessAI_{random.randint(1000, 9999)}"
    
    # 创建AI实例
    global ai_instance
    ai_instance = ChessAI(ai_id, args.ai_name, args.game_server)
    
    print(f"=== 国际象棋AI HTTP服务器 ===")
    print(f"AI ID: {ai_id}")
    print(f"AI名称: {ai_instance.ai_name}")
    print(f"端口: {args.port}")
    print(f"游戏服务器: {args.game_server}")
    print(f"调试模式: {args.debug}")
    print("")
    print("可用端点:")
    print("  GET  /health      - 健康检查")
    print("  GET  /info        - AI信息")
    print("  POST /join_game   - 加入游戏")
    print("  POST /leave_game  - 离开游戏")
    print("  GET  /games       - 列出游戏")
    print("  POST /move        - 获取移动(主要API)")
    print("")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()


