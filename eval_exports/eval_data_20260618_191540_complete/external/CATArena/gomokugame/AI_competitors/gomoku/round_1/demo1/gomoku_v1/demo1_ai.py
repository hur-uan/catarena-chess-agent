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

app = Flask(__name__)

class Demo1GomokuAI:
    """Advanced Gomoku AI with strategic algorithms"""
    
    def __init__(self, ai_id: str, ai_name: str = None, game_server_url: str = "http://localhost:10000"):
        self.ai_id = ai_id
        self.ai_name = ai_name or f"Demo1 AI {ai_id}"
        self.game_server_url = game_server_url
        self.board_size = 15
        self.active_games = {}  # game_id -> game_info
        
        # Pattern scores for evaluation
        self.patterns = {
            # Winning patterns
            'five': 100000,
            'open_four': 10000,
            'four': 1000,
            'open_three': 500,
            'three': 100,
            'open_two': 50,
            'two': 10,
            'one': 1
        }
    
    def find_best_move(self, board: List[List[int]], my_color: str) -> List[int]:
        """Find the best move using advanced strategy"""
        my_value = 1 if my_color == "black" else 2
        opponent_value = 2 if my_color == "black" else 1
        
        # 1. Check for immediate win
        winning_move = self.find_winning_move(board, my_value)
        if winning_move:
            return winning_move
        
        # 2. Block opponent's winning move
        blocking_move = self.find_winning_move(board, opponent_value)
        if blocking_move:
            return blocking_move
        
        # 3. Look for critical threats (open four, etc.)
        critical_move = self.find_critical_move(board, my_value, opponent_value)
        if critical_move:
            return critical_move
        
        # 4. Use minimax with alpha-beta pruning for strategic move
        best_move = self.minimax_move(board, my_value, opponent_value, depth=3)
        if best_move:
            return best_move
        
        # 5. Fallback to center or adjacent moves
        return self.get_strategic_fallback(board)
    
    def find_winning_move(self, board: List[List[int]], player_value: int) -> Optional[List[int]]:
        """Find immediate winning move"""
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i][j] == 0:
                    board[i][j] = player_value
                    if self.check_win(board, i, j, player_value):
                        board[i][j] = 0
                        return [i, j]
                    board[i][j] = 0
        return None
    
    def find_critical_move(self, board: List[List[int]], my_value: int, opponent_value: int) -> Optional[List[int]]:
        """Find critical moves like open four, double three, etc."""
        # Check for open four opportunities
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i][j] == 0:
                    if self.creates_open_four(board, i, j, my_value):
                        return [i, j]
        
        # Block opponent's open four
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i][j] == 0:
                    if self.creates_open_four(board, i, j, opponent_value):
                        return [i, j]
        
        # Look for double three opportunities
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i][j] == 0:
                    if self.creates_double_three(board, i, j, my_value):
                        return [i, j]
        
        return None
    
    def creates_open_four(self, board: List[List[int]], x: int, y: int, player_value: int) -> bool:
        """Check if placing a stone creates an open four"""
        board[x][y] = player_value
        result = False
        
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            open_ends = 0
            
            # Count in positive direction
            nx, ny = x + dx, y + dy
            while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                   board[nx][ny] == player_value):
                count += 1
                nx += dx
                ny += dy
            
            # Check if end is open
            if (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                board[nx][ny] == 0):
                open_ends += 1
            
            # Count in negative direction
            nx, ny = x - dx, y - dy
            while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                   board[nx][ny] == player_value):
                count += 1
                nx -= dx
                ny -= dy
            
            # Check if other end is open
            if (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                board[nx][ny] == 0):
                open_ends += 1
            
            if count == 4 and open_ends >= 1:
                result = True
                break
        
        board[x][y] = 0
        return result
    
    def creates_double_three(self, board: List[List[int]], x: int, y: int, player_value: int) -> bool:
        """Check if placing a stone creates double three (two open threes)"""
        board[x][y] = player_value
        open_threes = 0
        
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            if self.is_open_three_in_direction(board, x, y, dx, dy, player_value):
                open_threes += 1
        
        board[x][y] = 0
        return open_threes >= 2
    
    def is_open_three_in_direction(self, board: List[List[int]], x: int, y: int, dx: int, dy: int, player_value: int) -> bool:
        """Check if there's an open three in a specific direction"""
        count = 1
        open_ends = 0
        
        # Count in positive direction
        nx, ny = x + dx, y + dy
        while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
               board[nx][ny] == player_value):
            count += 1
            nx += dx
            ny += dy
        
        if (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
            board[nx][ny] == 0):
            open_ends += 1
        
        # Count in negative direction
        nx, ny = x - dx, y - dy
        while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
               board[nx][ny] == player_value):
            count += 1
            nx -= dx
            ny -= dy
        
        if (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
            board[nx][ny] == 0):
            open_ends += 1
        
        return count == 3 and open_ends == 2
    
    def minimax_move(self, board: List[List[int]], my_value: int, opponent_value: int, depth: int) -> Optional[List[int]]:
        """Use minimax algorithm to find best move"""
        best_score = float('-inf')
        best_move = None
        
        # Get candidate moves (positions near existing stones)
        candidates = self.get_candidate_moves(board)
        if not candidates:
            return None
        
        # Limit candidates for performance
        candidates = candidates[:20]
        
        for move in candidates:
            x, y = move
            board[x][y] = my_value
            score = self.minimax(board, depth - 1, False, my_value, opponent_value, float('-inf'), float('inf'))
            board[x][y] = 0
            
            if score > best_score:
                best_score = score
                best_move = move
        
        return best_move
    
    def minimax(self, board: List[List[int]], depth: int, is_maximizing: bool, my_value: int, opponent_value: int, alpha: float, beta: float) -> float:
        """Minimax algorithm with alpha-beta pruning"""
        if depth == 0:
            return self.evaluate_board(board, my_value, opponent_value)
        
        candidates = self.get_candidate_moves(board)
        if not candidates:
            return self.evaluate_board(board, my_value, opponent_value)
        
        # Limit candidates for performance
        candidates = candidates[:10]
        
        if is_maximizing:
            max_eval = float('-inf')
            for move in candidates:
                x, y = move
                board[x][y] = my_value
                eval_score = self.minimax(board, depth - 1, False, my_value, opponent_value, alpha, beta)
                board[x][y] = 0
                max_eval = max(max_eval, eval_score)
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for move in candidates:
                x, y = move
                board[x][y] = opponent_value
                eval_score = self.minimax(board, depth - 1, True, my_value, opponent_value, alpha, beta)
                board[x][y] = 0
                min_eval = min(min_eval, eval_score)
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval
    
    def get_candidate_moves(self, board: List[List[int]]) -> List[List[int]]:
        """Get candidate moves (positions near existing stones)"""
        candidates = []
        occupied = set()
        
        # Find all occupied positions
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i][j] != 0:
                    occupied.add((i, j))
        
        # If no stones on board, start from center
        if not occupied:
            center = self.board_size // 2
            return [[center, center]]
        
        # Find positions adjacent to occupied positions
        candidate_set = set()
        for i, j in occupied:
            for di in [-2, -1, 0, 1, 2]:
                for dj in [-2, -1, 0, 1, 2]:
                    ni, nj = i + di, j + dj
                    if (0 <= ni < self.board_size and 0 <= nj < self.board_size and 
                        board[ni][nj] == 0 and (ni, nj) not in candidate_set):
                        candidate_set.add((ni, nj))
        
        candidates = [[i, j] for i, j in candidate_set]
        
        # Sort by evaluation score
        candidates.sort(key=lambda pos: self.evaluate_position(board, pos[0], pos[1]), reverse=True)
        
        return candidates
    
    def evaluate_position(self, board: List[List[int]], x: int, y: int) -> float:
        """Evaluate the strategic value of a position"""
        score = 0
        
        # Distance from center bonus
        center = self.board_size // 2
        distance_from_center = abs(x - center) + abs(y - center)
        score += max(0, 10 - distance_from_center)
        
        # Check patterns in all directions
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dx, dy in directions:
            for player_value in [1, 2]:
                pattern_score = self.evaluate_line_pattern(board, x, y, dx, dy, player_value)
                if player_value == 1:  # Assume we're black for evaluation
                    score += pattern_score
                else:
                    score += pattern_score * 0.9  # Slightly less weight for blocking
        
        return score
    
    def evaluate_line_pattern(self, board: List[List[int]], x: int, y: int, dx: int, dy: int, player_value: int) -> float:
        """Evaluate pattern in a specific direction"""
        # Simulate placing the stone
        original = board[x][y]
        board[x][y] = player_value
        
        count = 1
        open_ends = 0
        
        # Count in positive direction
        nx, ny = x + dx, y + dy
        while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
               board[nx][ny] == player_value):
            count += 1
            nx += dx
            ny += dy
        
        if (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
            board[nx][ny] == 0):
            open_ends += 1
        
        # Count in negative direction
        nx, ny = x - dx, y - dy
        while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
               board[nx][ny] == player_value):
            count += 1
            nx -= dx
            ny -= dy
        
        if (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
            board[nx][ny] == 0):
            open_ends += 1
        
        # Restore original value
        board[x][y] = original
        
        # Score based on count and openness
        if count >= 5:
            return self.patterns['five']
        elif count == 4:
            return self.patterns['open_four'] if open_ends >= 1 else self.patterns['four']
        elif count == 3:
            return self.patterns['open_three'] if open_ends == 2 else self.patterns['three']
        elif count == 2:
            return self.patterns['open_two'] if open_ends == 2 else self.patterns['two']
        else:
            return self.patterns['one']
    
    def evaluate_board(self, board: List[List[int]], my_value: int, opponent_value: int) -> float:
        """Evaluate the entire board position"""
        my_score = 0
        opponent_score = 0
        
        # Evaluate all positions
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i][j] != 0:
                    pos_score = self.evaluate_position_patterns(board, i, j, board[i][j])
                    if board[i][j] == my_value:
                        my_score += pos_score
                    else:
                        opponent_score += pos_score
        
        return my_score - opponent_score
    
    def evaluate_position_patterns(self, board: List[List[int]], x: int, y: int, player_value: int) -> float:
        """Evaluate patterns around a specific position"""
        score = 0
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        
        for dx, dy in directions:
            count = 1
            open_ends = 0
            
            # Count in positive direction
            nx, ny = x + dx, y + dy
            while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                   board[nx][ny] == player_value):
                count += 1
                nx += dx
                ny += dy
            
            if (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                board[nx][ny] == 0):
                open_ends += 1
            
            # Count in negative direction
            nx, ny = x - dx, y - dy
            while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                   board[nx][ny] == player_value):
                count += 1
                nx -= dx
                ny -= dy
            
            if (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                board[nx][ny] == 0):
                open_ends += 1
            
            # Score based on pattern
            if count >= 5:
                score += self.patterns['five']
            elif count == 4:
                score += self.patterns['open_four'] if open_ends >= 1 else self.patterns['four']
            elif count == 3:
                score += self.patterns['open_three'] if open_ends == 2 else self.patterns['three']
            elif count == 2:
                score += self.patterns['open_two'] if open_ends == 2 else self.patterns['two']
        
        return score
    
    def get_strategic_fallback(self, board: List[List[int]]) -> List[int]:
        """Get a strategic fallback move"""
        # Check if board is empty, start from center
        empty_count = sum(row.count(0) for row in board)
        if empty_count == self.board_size * self.board_size:
            center = self.board_size // 2
            return [center, center]
        
        # Find positions near existing stones
        candidates = self.get_candidate_moves(board)
        if candidates:
            return candidates[0]
        
        # Ultimate fallback - random empty position
        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i][j] == 0:
                    return [i, j]
        
        return [0, 0]
    
    def check_win(self, board: List[List[int]], x: int, y: int, player_value: int) -> bool:
        """Check if the move results in a win"""
        directions = [(1, 0), (0, 1), (1, 1), (1, -1)]
        
        for dx, dy in directions:
            count = 1
            
            # Count in positive direction
            nx, ny = x + dx, y + dy
            while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                   board[nx][ny] == player_value):
                count += 1
                nx += dx
                ny += dy
            
            # Count in negative direction
            nx, ny = x - dx, y - dy
            while (0 <= nx < self.board_size and 0 <= ny < self.board_size and 
                   board[nx][ny] == player_value):
                count += 1
                nx -= dx
                ny -= dy
            
            if count >= 5:
                return True
        
        return False

# Global AI instance
ai_instance = None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "ai_id": ai_instance.ai_id if ai_instance else "unknown",
        "active_games": len(ai_instance.active_games) if ai_instance else 0,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/info', methods=['GET'])
def get_ai_info():
    """Get AI information"""
    return jsonify({
        "ai_id": ai_instance.ai_id if ai_instance else "unknown",
        "name": ai_instance.ai_name if ai_instance else "unknown",
        "version": "1.0",
        "description": "Advanced Gomoku AI with strategic algorithms including minimax, pattern recognition, and threat detection",
        "capabilities": ["winning_move", "blocking_move", "threat_detection", "pattern_recognition", "minimax_search", "strategic_evaluation"]
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    """Join a game"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        my_color = data.get('my_color')  # "black" or "white"
        game_server_url = data.get('game_server_url', "http://localhost:10000")
        
        if not game_id or not my_color:
            return jsonify({"error": "game_id and my_color are required"}), 400
        
        if my_color not in ['black', 'white']:
            return jsonify({"error": "my_color must be 'black' or 'white'"}), 400
        
        # Update AI instance game server URL
        ai_instance.game_server_url = game_server_url
        
        # Record game information
        ai_instance.active_games[game_id] = {
            "my_color": my_color,
            "joined_at": datetime.now().isoformat()
        }
        
        print(f"AI {ai_instance.ai_id} joined game {game_id}, color: {my_color}")
        
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
    """Get AI's next move"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        board = data.get('board')
        current_player = data.get('current_player')
        
        if not game_id or board is None or not current_player:
            return jsonify({"error": "game_id, board, and current_player are required"}), 400
        
        # Check if it's my turn
        if game_id not in ai_instance.active_games:
            return jsonify({"error": "Game not found or not joined"}), 404
        
        my_color = ai_instance.active_games[game_id]["my_color"]
        if current_player != my_color:
            return jsonify({"error": "Not my turn"}), 400
        
        # Find best move
        best_move = ai_instance.find_best_move(board, my_color)
        
        print(f"AI {ai_instance.ai_id} in game {game_id} plays: {best_move}")
        
        return jsonify({
            "move": best_move,
            "ai_id": ai_instance.ai_id,
            "game_id": game_id,
            "reasoning": "Advanced strategic analysis applied"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/leave_game', methods=['POST'])
def leave_game():
    """Leave a game"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        if not game_id:
            return jsonify({"error": "game_id is required"}), 400
        
        if game_id in ai_instance.active_games:
            del ai_instance.active_games[game_id]
            print(f"AI {ai_instance.ai_id} left game {game_id}")
        
        return jsonify({
            "status": "left",
            "ai_id": ai_instance.ai_id,
            "game_id": game_id
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games', methods=['GET'])
def list_games():
    """List current active games"""
    return jsonify({
        "ai_id": ai_instance.ai_id,
        "active_games": ai_instance.active_games
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

def main():
    parser = argparse.ArgumentParser(description='Demo1 Gomoku AI HTTP Server')
    parser.add_argument('--port', type=int, default=50009, help='Listen port (default: 50009)')
    parser.add_argument('--ai_id', type=str, default=None, help='AI identifier')
    parser.add_argument('--ai_name', type=str, default=None, help='AI name')
    parser.add_argument('--game_server', type=str, default='http://localhost:10000', help='Game server URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Generate AI ID
    ai_id = args.ai_id or "demo1_AI"
    
    # Create AI instance
    global ai_instance
    ai_instance = Demo1GomokuAI(ai_id, args.ai_name, args.game_server)
    
    print(f"=== Demo1 Gomoku AI HTTP Server ===")
    print(f"AI ID: {ai_id}")
    print(f"AI Name: {ai_instance.ai_name}")
    print(f"Port: {args.port}")
    print(f"Game Server: {args.game_server}")
    print(f"Debug Mode: {args.debug}")
    print("")
    print("Available endpoints:")
    print("  GET  /health      - Health check")
    print("  GET  /info        - AI information")
    print("  POST /join_game   - Join game")
    print("  POST /get_move    - Get move")
    print("  POST /leave_game  - Leave game")
    print("  GET  /games       - List games")
    print("")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()