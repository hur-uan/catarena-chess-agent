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

class Demo1ChessAI:
    """Advanced Chess AI with sophisticated evaluation and search algorithms"""
    
    def __init__(self, ai_id: str, ai_name: str = None, game_server_url: str = "http://localhost:9020"):
        self.ai_id = ai_id
        self.ai_name = ai_name or f"demo1_AI_{ai_id}"
        self.game_server_url = game_server_url
        self.active_games = {}
        self.thinking_time = 2.0
        
        # Piece values for evaluation
        self.piece_values = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 20000
        }
        
        # Position tables for piece-square evaluation
        self.pawn_table = [
            0,  0,  0,  0,  0,  0,  0,  0,
            50, 50, 50, 50, 50, 50, 50, 50,
            10, 10, 20, 30, 30, 20, 10, 10,
            5,  5, 10, 25, 25, 10,  5,  5,
            0,  0,  0, 20, 20,  0,  0,  0,
            5, -5,-10,  0,  0,-10, -5,  5,
            5, 10, 10,-20,-20, 10, 10,  5,
            0,  0,  0,  0,  0,  0,  0,  0
        ]
        
        self.knight_table = [
            -50,-40,-30,-30,-30,-30,-40,-50,
            -40,-20,  0,  0,  0,  0,-20,-40,
            -30,  0, 10, 15, 15, 10,  0,-30,
            -30,  5, 15, 20, 20, 15,  5,-30,
            -30,  0, 15, 20, 20, 15,  0,-30,
            -30,  5, 10, 15, 15, 10,  5,-30,
            -40,-20,  0,  5,  5,  0,-20,-40,
            -50,-40,-30,-30,-30,-30,-40,-50
        ]
        
        self.bishop_table = [
            -20,-10,-10,-10,-10,-10,-10,-20,
            -10,  0,  0,  0,  0,  0,  0,-10,
            -10,  0,  5, 10, 10,  5,  0,-10,
            -10,  5,  5, 10, 10,  5,  5,-10,
            -10,  0, 10, 10, 10, 10,  0,-10,
            -10, 10, 10, 10, 10, 10, 10,-10,
            -10,  5,  0,  0,  0,  0,  5,-10,
            -20,-10,-10,-10,-10,-10,-10,-20
        ]
        
        self.rook_table = [
            0,  0,  0,  0,  0,  0,  0,  0,
            5, 10, 10, 10, 10, 10, 10,  5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            -5,  0,  0,  0,  0,  0,  0, -5,
            0,  0,  0,  5,  5,  0,  0,  0
        ]
        
        self.queen_table = [
            -20,-10,-10, -5, -5,-10,-10,-20,
            -10,  0,  0,  0,  0,  0,  0,-10,
            -10,  0,  5,  5,  5,  5,  0,-10,
            -5,  0,  5,  5,  5,  5,  0, -5,
            0,  0,  5,  5,  5,  5,  0, -5,
            -10,  5,  5,  5,  5,  5,  0,-10,
            -10,  0,  5,  0,  0,  0,  0,-10,
            -20,-10,-10, -5, -5,-10,-10,-20
        ]
        
        self.king_middle_game_table = [
            -30,-40,-40,-50,-50,-40,-40,-30,
            -30,-40,-40,-50,-50,-40,-40,-30,
            -30,-40,-40,-50,-50,-40,-40,-30,
            -30,-40,-40,-50,-50,-40,-40,-30,
            -20,-30,-30,-40,-40,-30,-30,-20,
            -10,-20,-20,-20,-20,-20,-20,-10,
            20, 20,  0,  0,  0,  0, 20, 20,
            20, 30, 10,  0,  0, 10, 30, 20
        ]
        
        self.king_end_game_table = [
            -50,-40,-30,-20,-20,-30,-40,-50,
            -30,-20,-10,  0,  0,-10,-20,-30,
            -30,-10, 20, 30, 30, 20,-10,-30,
            -30,-10, 30, 40, 40, 30,-10,-30,
            -30,-10, 30, 40, 40, 30,-10,-30,
            -30,-10, 20, 30, 30, 20,-10,-30,
            -30,-30,  0,  0,  0,  0,-30,-30,
            -50,-30,-30,-30,-30,-30,-30,-50
        ]
    
    def get_piece_square_value(self, piece: chess.Piece, square: int, is_endgame: bool = False) -> int:
        """Get piece-square table value"""
        piece_type = piece.piece_type
        color = piece.color
        
        # Flip square for black pieces
        if not color:
            square = chess.square_mirror(square)
        
        if piece_type == chess.PAWN:
            return self.pawn_table[square]
        elif piece_type == chess.KNIGHT:
            return self.knight_table[square]
        elif piece_type == chess.BISHOP:
            return self.bishop_table[square]
        elif piece_type == chess.ROOK:
            return self.rook_table[square]
        elif piece_type == chess.QUEEN:
            return self.queen_table[square]
        elif piece_type == chess.KING:
            if is_endgame:
                return self.king_end_game_table[square]
            else:
                return self.king_middle_game_table[square]
        
        return 0
    
    def is_endgame(self, board: chess.Board) -> bool:
        """Determine if position is endgame"""
        queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
        minors = (len(board.pieces(chess.BISHOP, chess.WHITE)) + len(board.pieces(chess.KNIGHT, chess.WHITE)) +
                 len(board.pieces(chess.BISHOP, chess.BLACK)) + len(board.pieces(chess.KNIGHT, chess.BLACK)))
        
        return queens == 0 or (queens == 2 and minors <= 1)
    
    def evaluate_position(self, board: chess.Board) -> float:
        """Advanced position evaluation"""
        if board.is_checkmate():
            return -30000 if board.turn else 30000
        
        if board.is_stalemate() or board.is_insufficient_material():
            return 0
        
        score = 0
        is_endgame = self.is_endgame(board)
        
        # Material and position evaluation
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece is not None:
                # Basic material value
                material_value = self.piece_values[piece.piece_type]
                
                # Position value
                position_value = self.get_piece_square_value(piece, square, is_endgame)
                
                total_value = material_value + position_value
                
                if piece.color:  # White
                    score += total_value
                else:  # Black
                    score -= total_value
        
        # Mobility evaluation
        white_mobility = len(list(board.legal_moves)) if board.turn else 0
        board.turn = not board.turn
        black_mobility = len(list(board.legal_moves)) if not board.turn else 0
        board.turn = not board.turn
        
        score += (white_mobility - black_mobility) * 10
        
        # King safety evaluation
        white_king_square = board.king(chess.WHITE)
        black_king_square = board.king(chess.BLACK)
        
        if white_king_square and not is_endgame:
            # Penalize exposed king in middle game
            king_file = chess.square_file(white_king_square)
            if king_file > 2 and king_file < 5:  # King in center
                score -= 50
        
        if black_king_square and not is_endgame:
            king_file = chess.square_file(black_king_square)
            if king_file > 2 and king_file < 5:
                score += 50
        
        # Pawn structure evaluation
        white_pawns = board.pieces(chess.PAWN, chess.WHITE)
        black_pawns = board.pieces(chess.PAWN, chess.BLACK)
        
        # Doubled pawns penalty
        for file in range(8):
            white_pawns_in_file = len([sq for sq in white_pawns if chess.square_file(sq) == file])
            black_pawns_in_file = len([sq for sq in black_pawns if chess.square_file(sq) == file])
            
            if white_pawns_in_file > 1:
                score -= 20 * (white_pawns_in_file - 1)
            if black_pawns_in_file > 1:
                score += 20 * (black_pawns_in_file - 1)
        
        # Isolated pawns penalty
        for square in white_pawns:
            file = chess.square_file(square)
            adjacent_files = [f for f in [file-1, file+1] if 0 <= f <= 7]
            has_adjacent_pawn = any(chess.square_file(sq) in adjacent_files for sq in white_pawns)
            if not has_adjacent_pawn:
                score -= 15
        
        for square in black_pawns:
            file = chess.square_file(square)
            adjacent_files = [f for f in [file-1, file+1] if 0 <= f <= 7]
            has_adjacent_pawn = any(chess.square_file(sq) in adjacent_files for sq in black_pawns)
            if not has_adjacent_pawn:
                score += 15
        
        # Control of center
        center_squares = [chess.E4, chess.E5, chess.D4, chess.D5]
        for square in center_squares:
            if board.is_attacked_by(chess.WHITE, square):
                score += 20
            if board.is_attacked_by(chess.BLACK, square):
                score -= 20
        
        return score
    
    def order_moves(self, board: chess.Board, moves: List[chess.Move]) -> List[chess.Move]:
        """Order moves for better alpha-beta pruning"""
        def move_priority(move):
            priority = 0
            
            # Captures
            if board.is_capture(move):
                captured_piece = board.piece_at(move.to_square)
                moving_piece = board.piece_at(move.from_square)
                if captured_piece and moving_piece:
                    # MVV-LVA (Most Valuable Victim - Least Valuable Attacker)
                    priority += self.piece_values[captured_piece.piece_type] - self.piece_values[moving_piece.piece_type] // 10
            
            # Checks
            board.push(move)
            if board.is_check():
                priority += 100
            board.pop()
            
            # Promotions
            if move.promotion:
                priority += 800
            
            # Castle
            if board.is_castling(move):
                priority += 50
            
            return priority
        
        return sorted(moves, key=move_priority, reverse=True)
    
    def minimax_alpha_beta(self, board: chess.Board, depth: int, alpha: float, beta: float, 
                          maximizing: bool, start_time: float) -> Tuple[float, Optional[chess.Move]]:
        """Minimax with alpha-beta pruning and time management"""
        # Time management
        if time.time() - start_time > self.thinking_time:
            return self.evaluate_position(board), None
        
        if depth == 0 or board.is_game_over():
            return self.evaluate_position(board), None
        
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return self.evaluate_position(board), None
        
        # Move ordering for better pruning
        legal_moves = self.order_moves(board, legal_moves)
        
        best_move = None
        
        if maximizing:
            max_eval = float('-inf')
            for move in legal_moves:
                board.push(move)
                eval_score, _ = self.minimax_alpha_beta(board, depth - 1, alpha, beta, False, start_time)
                board.pop()
                
                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move
                
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break  # Alpha-beta pruning
            
            return max_eval, best_move
        else:
            min_eval = float('inf')
            for move in legal_moves:
                board.push(move)
                eval_score, _ = self.minimax_alpha_beta(board, depth - 1, alpha, beta, True, start_time)
                board.pop()
                
                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move
                
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break  # Alpha-beta pruning
            
            return min_eval, best_move
    
    def get_best_move_advanced(self, board: chess.Board) -> Optional[chess.Move]:
        """Advanced move selection with iterative deepening"""
        if board.is_game_over():
            return None
        
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None
        
        if len(legal_moves) == 1:
            return legal_moves[0]
        
        start_time = time.time()
        best_move = None
        
        # Iterative deepening
        for depth in range(1, 6):  # Search depths 1-5
            if time.time() - start_time > self.thinking_time * 0.8:
                break
            
            _, move = self.minimax_alpha_beta(board, depth, float('-inf'), float('inf'), 
                                            board.turn, start_time)
            if move:
                best_move = move
        
        return best_move or random.choice(legal_moves)
    
    def get_opening_move(self, board: chess.Board) -> Optional[chess.Move]:
        """Simple opening book"""
        if board.fullmove_number <= 3:
            # Opening principles
            legal_moves = list(board.legal_moves)
            
            # Prefer center pawn moves
            center_moves = []
            for move in legal_moves:
                if move.to_square in [chess.E4, chess.D4, chess.E5, chess.D5]:
                    piece = board.piece_at(move.from_square)
                    if piece and piece.piece_type == chess.PAWN:
                        center_moves.append(move)
            
            if center_moves:
                return random.choice(center_moves)
            
            # Develop knights
            knight_moves = []
            for move in legal_moves:
                piece = board.piece_at(move.from_square)
                if piece and piece.piece_type == chess.KNIGHT:
                    # Prefer Nf3, Nc3, Nf6, Nc6
                    if move.to_square in [chess.F3, chess.C3, chess.F6, chess.C6]:
                        knight_moves.append(move)
            
            if knight_moves:
                return random.choice(knight_moves)
        
        return None
    
    def find_best_move(self, fen: str, algorithm: str = "advanced") -> Optional[str]:
        """Find the best move for given position"""
        try:
            board = chess.Board(fen)
        except ValueError:
            return None
        
        if board.is_game_over():
            return None
        
        # Try opening book first
        opening_move = self.get_opening_move(board)
        if opening_move:
            return opening_move.uci()
        
        # Use advanced algorithm
        best_move = self.get_best_move_advanced(board)
        return best_move.uci() if best_move else None

# Global AI instance
ai_instance = None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "ai_id": ai_instance.ai_id if ai_instance else "unknown",
        "ai_name": ai_instance.ai_name if ai_instance else "unknown",
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
        "description": "Demo1 Advanced Chess AI with sophisticated evaluation",
        "capabilities": ["advanced_search", "position_evaluation", "opening_book", "endgame_knowledge"]
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    """Join a game"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        game_id = data.get('game_id')
        my_color = data.get('my_color')
        game_server_url = data.get('game_server_url', "http://localhost:40000")
        
        if not game_id or not my_color:
            return jsonify({"error": "game_id and my_color are required"}), 400
        
        if my_color not in ['white', 'black']:
            return jsonify({"error": "my_color must be 'white' or 'black'"}), 400
        
        ai_instance.game_server_url = game_server_url
        ai_instance.active_games[game_id] = {
            "my_color": my_color,
            "joined_at": datetime.now().isoformat()
        }
        
        print(f"AI {ai_instance.ai_id} joined game {game_id} as {my_color}")
        
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
        fen = data.get('fen')
        current_player = data.get('current_player')
        
        if not game_id or fen is None or not current_player:
            return jsonify({"error": "game_id, fen, and current_player are required"}), 400
        
        if game_id not in ai_instance.active_games:
            return jsonify({"error": "Game not found or not joined"}), 404
        
        my_color = ai_instance.active_games[game_id]["my_color"]
        if current_player != my_color:
            return jsonify({"error": "Not my turn"}), 400
        
        best_move = ai_instance.find_best_move(fen, "advanced")
        
        if not best_move:
            return jsonify({"error": "No legal moves available"}), 400
        
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

@app.route('/move', methods=['POST'])
def get_move_legacy():
    """Get AI move (legacy API compatibility)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        fen = data.get('fen')
        algorithm = data.get('algorithm', 'advanced')
        
        if not fen:
            return jsonify({"error": "FEN string is required"}), 400
        
        try:
            board = chess.Board(fen)
        except ValueError as e:
            return jsonify({"error": f"Invalid FEN: {str(e)}"}), 400
        
        if board.is_game_over():
            return jsonify({
                "error": "Game is over",
                "result": board.result()
            }), 400
        
        start_time = time.time()
        best_move_uci = ai_instance.find_best_move(fen, algorithm)
        thinking_time = time.time() - start_time
        
        if best_move_uci is None:
            return jsonify({"error": "No legal moves available"}), 400
        
        best_move = chess.Move.from_uci(best_move_uci)
        san_move = board.san(best_move)
        
        return jsonify({
            "ai_id": ai_instance.ai_id,
            "ai_name": ai_instance.ai_name,
            "move": best_move_uci,
            "san": san_move,
            "from_square": chess.square_name(best_move.from_square),
            "to_square": chess.square_name(best_move.to_square),
            "promotion": chess.piece_symbol(best_move.promotion) if best_move.promotion else None,
            "algorithm": algorithm,
            "thinking_time": round(thinking_time, 3),
            "evaluation": round(ai_instance.evaluate_position(board), 2),
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
    parser = argparse.ArgumentParser(description='Demo1 Chess AI HTTP Server')
    parser.add_argument('--port', type=int, default=52003, help='Port to listen on (default: 52003)')
    parser.add_argument('--ai_id', type=str, default=None, help='AI identifier')
    parser.add_argument('--ai_name', type=str, default=None, help='AI name')
    parser.add_argument('--game_server', type=str, default='http://localhost:40000', help='Game server URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Generate AI ID
    ai_id = args.ai_id or f"demo1_AI_{random.randint(1000, 9999)}"
    
    # Create AI instance
    global ai_instance
    ai_instance = Demo1ChessAI(ai_id, args.ai_name, args.game_server)
    
    print(f"=== Demo1 Chess AI HTTP Server ===")
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
    print("  POST /move        - Get move (legacy API)")
    print("")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()