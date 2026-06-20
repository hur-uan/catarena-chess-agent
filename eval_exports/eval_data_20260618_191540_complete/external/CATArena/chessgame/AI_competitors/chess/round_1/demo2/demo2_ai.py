import chess
import argparse
from flask import Flask, request, jsonify
from chess_ai import ChessAI

app = Flask(__name__)
chess_ai = ChessAI(depth=4)  # Initialize with depth 4 for good balance of speed and strategy

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "demo2_AI",
        "version": "1.0"
    })

@app.route('/move', methods=['POST'])
def get_move():
    """Endpoint to get AI's best move"""
    try:
        data = request.json
        fen = data.get('fen')
        algorithm = data.get('algorithm', 'minimax')
        
        if not fen:
            return jsonify({"error": "Missing FEN parameter"}), 400
        
        # Create board from FEN
        board = chess.Board(fen)
        
        # Get best move
        move = chess_ai.get_best_move(board, algorithm)
        
        if move:
            return jsonify({
                "move": move.uci(),
                "san": board.san(move),
                "status": "success"
            })
        else:
            return jsonify({"error": "No legal moves available"}), 400
    
    except ValueError as e:
        return jsonify({"error": f"Invalid FEN: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/evaluate', methods=['POST'])
def evaluate_position():
    """Endpoint to evaluate a position"""
    try:
        data = request.json
        fen = data.get('fen')
        
        if not fen:
            return jsonify({"error": "Missing FEN parameter"}), 400
        
        # Create board from FEN
        board = chess.Board(fen)
        
        # Evaluate position
        evaluation = chess_ai.evaluate_position(board)
        
        return jsonify({
            "evaluation": evaluation,
            "status": "success",
            "player_turn": "white" if board.turn == chess.WHITE else "black"
        })
    
    except ValueError as e:
        return jsonify({"error": f"Invalid FEN: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/legal_moves', methods=['POST'])
def get_legal_moves():
    """Endpoint to get all legal moves"""
    try:
        data = request.json
        fen = data.get('fen')
        
        if not fen:
            return jsonify({"error": "Missing FEN parameter"}), 400
        
        # Create board from FEN
        board = chess.Board(fen)
        
        # Get legal moves
        legal_moves = chess_ai.get_legal_moves(board)
        
        return jsonify({
            "legal_moves": legal_moves,
            "count": len(legal_moves),
            "status": "success"
        })
    
    except ValueError as e:
        return jsonify({"error": f"Invalid FEN: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='demo2_AI Chess AI Service')
    parser.add_argument('--port', type=int, default=52001, help='Port to run the service on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    # Start the server
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)