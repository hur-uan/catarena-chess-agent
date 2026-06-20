from flask import Flask, request, jsonify
import numpy as np

app = Flask(__name__)

# AI ID and name
AI_ID = "demo2_AI"
AI_NAME = "Demo2 AI"
AI_VERSION = "1.0"
AI_DESCRIPTION = "A strategic Gomoku AI with advanced decision-making capabilities."
AI_CAPABILITIES = ["winning_priority", "defense_priority", "threat_detection"]

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "ai_id": AI_ID,
        "active_games": 0
    })

@app.route('/info', methods=['GET'])
def ai_info():
    return jsonify({
        "ai_id": AI_ID,
        "name": AI_NAME,
        "version": AI_VERSION,
        "description": AI_DESCRIPTION,
        "capabilities": AI_CAPABILITIES
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    data = request.get_json()
    game_id = data.get('game_id')
    my_color = data.get('my_color')
    game_server_url = data.get('game_server_url')
    
    return jsonify({
        "status": "joined",
        "ai_id": AI_ID,
        "game_id": game_id,
        "my_color": my_color
    })

@app.route('/get_move', methods=['POST'])
def get_move():
    data = request.get_json()
    game_id = data.get('game_id')
    board = data.get('board')
    current_player = data.get('current_player')
    
    # Convert board to numpy array for easier manipulation
    board_array = np.array(board)
    
    # Implement AI logic here
    # For now, return a random valid move
    empty_positions = np.argwhere(board_array == 0)
    if len(empty_positions) > 0:
        move = empty_positions[0].tolist()
    else:
        move = [-1, -1]  # No valid move
    
    return jsonify({
        "move": move,
        "ai_id": AI_ID,
        "game_id": game_id,
        "reasoning": "Random move for initial implementation."
    })

@app.route('/leave_game', methods=['POST'])
def leave_game():
    data = request.get_json()
    game_id = data.get('game_id')
    
    return jsonify({
        "status": "left",
        "ai_id": AI_ID,
        "game_id": game_id
    })

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True, help='Port to run the HTTP service on.')
    args = parser.parse_args()
    
    app.run(host='0.0.0.0', port=args.port)