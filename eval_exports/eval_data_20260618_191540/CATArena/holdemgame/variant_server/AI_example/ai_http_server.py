from flask import Flask, request, jsonify
import random

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "Example AI is running"})

@app.route('/action', methods=['POST'])
def make_decision():
    game_state = request.json
    valid_actions = game_state.get('valid_actions', [])
    
    # Choose a random valid action
    if valid_actions:
        action = random.choice(valid_actions)
        return jsonify(action)
    else:
        return jsonify({"action": "fold", "amount": 0})

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True, help='Port to run the HTTP service on')
    args = parser.parse_args()
    app.run(host='0.0.0.0', port=args.port)