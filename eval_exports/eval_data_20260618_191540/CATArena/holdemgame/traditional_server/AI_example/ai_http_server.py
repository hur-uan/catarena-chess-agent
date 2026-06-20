
from flask import Flask, request, jsonify
import random
import argparse

app = Flask(__name__)

@app.route('/action', methods=['POST'])
def get_action():
    game_state = request.get_json()
    
    valid_actions = game_state.get('valid_actions', [])
    if not valid_actions:
        return jsonify({"action": "fold"}) # Should not happen in a real game

    # Simple AI logic: 
    # 70% chance to call/check, 20% chance to raise, 10% chance to fold.
    # This is a very basic strategy.
    
    action_choice = random.random()
    
    # Prioritize call/check
    call_action = next((a for a in valid_actions if a['action'] == 'call'), None)
    check_action = next((a for a in valid_actions if a['action'] == 'check'), None)
    raise_action = next((a for a in valid_actions if a['action'] == 'raise'), None)
    fold_action = next((a for a in valid_actions if a['action'] == 'fold'), None)

    if action_choice < 0.7 and (call_action or check_action):
        if check_action:
            return jsonify(check_action)
        return jsonify(call_action)
    elif action_choice < 0.9 and raise_action:
        # Raise the minimum amount
        min_raise = raise_action['amount']['min']
        return jsonify({"action": "raise", "amount": min_raise})
    elif fold_action:
        return jsonify(fold_action)
    else: # Fallback to the first available action
        return jsonify(valid_actions[0])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Simple AI HTTP Server")
    parser.add_argument('--port', type=int, default=51012, help='Port to listen on')
    args = parser.parse_args()
    
    app.run(host='0.0.0.0', port=args.port)
