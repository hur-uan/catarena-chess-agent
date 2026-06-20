from flask import Flask, request, jsonify
import random
import argparse
from collections import defaultdict
import time

app = Flask(__name__)

# Hand rankings: higher value means stronger hand
HAND_RANKINGS = {
    'high_card': 1,
    'one_pair': 2,
    'two_pair': 3,
    'three_of_a_kind': 4,
    'straight': 5,
    'flush': 6,
    'full_house': 7,
    'four_of_a_kind': 8,
    'straight_flush': 9,
    'royal_flush': 10
}

# Pre-flop hand rankings based on position (conservative approach)
PRE_FLOP_RANKINGS = {
    # Strong hands - raise in any position
    ('A', 'A'): 10, ('K', 'K'): 10, ('Q', 'Q'): 10, ('A', 'K'): 9, ('A', 'Q'): 9,
    ('K', 'Q'): 9, ('J', 'J'): 9, ('A', 'J'): 8, ('K', 'J'): 8, ('Q', 'J'): 8,
    ('10', '10'): 8, ('A', '10'): 7, ('K', '10'): 7, ('Q', '10'): 7, ('J', '10'): 7,
    ('9', '9'): 7, ('8', '8'): 7, ('7', '7'): 6, ('6', '6'): 6, ('5', '5'): 6,
    ('4', '4'): 6, ('3', '3'): 5, ('2', '2'): 5,
    # Suited connectors
    ('A', 'K', 's'): 10, ('K', 'Q', 's'): 9, ('Q', 'J', 's'): 9, ('J', '10', 's'): 9,
    ('10', '9', 's'): 8, ('9', '8', 's'): 8, ('8', '7', 's'): 7, ('7', '6', 's'): 7,
    ('6', '5', 's'): 7, ('5', '4', 's'): 6, ('4', '3', 's'): 6, ('3', '2', 's'): 5,
    # Suited aces
    ('A', '9', 's'): 8, ('A', '8', 's'): 8, ('A', '7', 's'): 7, ('A', '6', 's'): 7,
    ('A', '5', 's'): 7, ('A', '4', 's'): 6, ('A', '3', 's'): 6, ('A', '2', 's'): 6
}

# Position multipliers (later positions get higher multipliers)
POSITION_MULTIPLIERS = {
    'early': 0.8,
    'middle': 1.0,
    'late': 1.2,
    'dealer': 1.3,
    'small_blind': 1.1,
    'big_blind': 1.1
}

# Tournament stage multipliers
STAGE_MULTIPLIERS = {
    'early': 0.8,    # Conservative play
    'middle': 1.0,   # Balanced play
    'late': 1.3,     # More aggressive
    'final': 1.5     # Very aggressive
}

class AIStrategy:
    def __init__(self):
        self.opponent_profiles = defaultdict(lambda: {
            'aggression': 0.5,  # 0-1 scale, 1 being most aggressive
            'fold_to_raise': 0.5,  # Probability of folding to raise
            'seen_hands': 0
        })
        self.tournament_stage = 'early'
        self.current_blind_level = 1
        self.my_stack_history = []
        self.opponent_stack_history = defaultdict(list)

    def update_tournament_stage(self, game_state):
        total_players = len(game_state['players'])
        active_players = sum(1 for p in game_state['players'].values() if p['state'] == 'active' and not p.get('is_eliminated', False))
        starting_players = len(game_state['players'])

        # Update stage based on remaining players
        if active_players == 1:
            self.tournament_stage = 'final'
        elif active_players / starting_players <= 0.3:
            self.tournament_stage = 'late'
        elif active_players / starting_players <= 0.6:
            self.tournament_stage = 'middle'
        else:
            self.tournament_stage = 'early'

        # Update blind level based on hand number
        players_count = len(game_state['players'])
        hands_per_level = players_count * 2
        self.current_blind_level = (game_state['hand_number'] // hands_per_level) + 1

    def get_position(self, game_state):
        players = list(game_state['players'].values())
        current_player_id = game_state['current_player']
        dealer_index = game_state['dealer_index']
        num_players = len(players)

        # Find current player index
        current_index = None
        for i, p in enumerate(players):
            if p['player_id'] == current_player_id:
                current_index = i
                break

        if current_index is None:
            return 'early'

        # Determine position relative to dealer
        positions = []
        for i in range(num_players):
            pos_index = (dealer_index + i + 1) % num_players
            positions.append(players[pos_index]['player_id'])

        pos = positions.index(current_player_id)

        if num_players <= 6:
            if pos == 0 or pos == 1:  # UTG, UTG+1
                return 'early'
            elif pos == 2 or pos == 3:  # MP, MP+1
                return 'middle'
            else:  # CO, BTN
                return 'late' if pos < num_players - 2 else 'dealer'
        else:
            if pos <= 2:  # UTG, UTG+1, UTG+2
                return 'early'
            elif pos <= 5:  # MP1-3
                return 'middle'
            else:  # CO, BTN
                return 'late' if pos < num_players - 2 else 'dealer'

    def evaluate_hand_strength(self, hole_cards, community_cards):
        # Convert cards to ranks and suits
        all_cards = hole_cards + community_cards
        ranks = [c[0] for c in all_cards]
        suits = [c[1] for c in all_cards]

        # Simple hand strength evaluation (placeholder for more complex logic)
        # This would be replaced with a proper poker hand evaluator
        if len(community_cards) == 0:  # Pre-flop
            return self.evaluate_preflop(hole_cards)
        elif len(community_cards) == 3:  # Flop
            return self.evaluate_flop(hole_cards, community_cards)
        elif len(community_cards) == 4:  # Turn
            return self.evaluate_turn(hole_cards, community_cards)
        else:  # River
            return self.evaluate_river(hole_cards, community_cards)

    def evaluate_preflop(self, hole_cards):
        # Extract ranks and check if suited
        r1, s1 = hole_cards[0][0], hole_cards[0][1]
        r2, s2 = hole_cards[1][0], hole_cards[1][1]
        suited = s1 == s2

        # Sort ranks for consistent lookup
        if self.rank_value(r1) > self.rank_value(r2):
            high_rank, low_rank = r1, r2
        else:
            high_rank, low_rank = r2, r1

        # Check for pairs
        if high_rank == low_rank:
            return PRE_FLOP_RANKINGS.get((high_rank, low_rank), 5)

        # Check for suited hands
        if suited:
            return PRE_FLOP_RANKINGS.get((high_rank, low_rank, 's'), PRE_FLOP_RANKINGS.get((high_rank, low_rank), 3))

        # Check for unsuited hands
        return PRE_FLOP_RANKINGS.get((high_rank, low_rank), 3)

    def evaluate_flop(self, hole_cards, community_cards):
        # Basic flop evaluation (simplified)
        preflop_strength = self.evaluate_preflop(hole_cards)
        return min(10, preflop_strength + 1)  # Placeholder logic

    def evaluate_turn(self, hole_cards, community_cards):
        # Basic turn evaluation (simplified)
        flop_strength = self.evaluate_flop(hole_cards, community_cards[:3])
        return min(10, flop_strength + 0.5)  # Placeholder logic

    def evaluate_river(self, hole_cards, community_cards):
        # Basic river evaluation (simplified)
        turn_strength = self.evaluate_turn(hole_cards, community_cards[:4])
        return min(10, turn_strength + 0.5)  # Placeholder logic

    def rank_value(self, rank):
        if rank == 'A': return 14
        if rank == 'K': return 13
        if rank == 'Q': return 12
        if rank == 'J': return 11
        if rank == 'T': return 10
        return int(rank)

    def calculate_pot_odds(self, game_state):
        current_player = game_state['players'][game_state['current_player']]
        current_bet = game_state['current_bet']
        pot_size = game_state['pot']
        to_call = current_bet - current_player['current_bet']

        if to_call <= 0:
            return 1.0  # No cost to continue

        # Calculate pot odds (percentage)
        return to_call / (pot_size + to_call)

    def make_decision(self, game_state):
        # Update tournament state
        self.update_tournament_stage(game_state)

        # Get basic game information
        valid_actions = game_state['valid_actions']
        current_player = game_state['players'][game_state['current_player']]
        hole_cards = current_player['hole_cards']
        community_cards = game_state['community_cards']
        pot_size = game_state['pot']
        current_bet = game_state['current_bet']
        my_chips = current_player['chips']
        my_current_bet = current_player['current_bet']
        to_call = current_bet - my_current_bet

        # Get strategic information
        hand_strength = self.evaluate_hand_strength(hole_cards, community_cards)
        position = self.get_position(game_state)
        pot_odds = self.calculate_pot_odds(game_state)

        # Get multipliers
        position_multiplier = POSITION_MULTIPLIERS.get(position, 1.0)
        stage_multiplier = STAGE_MULTIPLIERS.get(self.tournament_stage, 1.0)

        # Calculate adjusted hand strength
        adjusted_strength = hand_strength * position_multiplier * stage_multiplier

        # Check if we're short stacked
        small_blind = game_state['small_blind']
        stack_to_blind_ratio = my_chips / small_blind
        is_short_stack = stack_to_blind_ratio < 10

        # Rank valid actions by preference
        action_scores = {}

        # Check if we can check
        check_action = next((a for a in valid_actions if a['action'] == 'check'), None)
        if check_action and adjusted_strength > 5:
            action_scores['check'] = adjusted_strength

        # Evaluate call
        call_action = next((a for a in valid_actions if a['action'] == 'call'), None)
        if call_action:
            # Only call if hand strength is good or pot odds are favorable
            if adjusted_strength > 6 or (adjusted_strength > 4 and pot_odds < 0.3):
                action_scores['call'] = adjusted_strength + (0.5 if pot_odds < 0.2 else 0)

        # Evaluate raise
        raise_action = next((a for a in valid_actions if a['action'] == 'raise'), None)
        if raise_action:
            # Be more aggressive with strong hands, good position, or when short stacked
            if adjusted_strength > 8 or (adjusted_strength > 7 and position_multiplier > 1.0) or (is_short_stack and adjusted_strength > 6):
                strength_score = adjusted_strength
                # Higher strength leads to higher raise
                raise_score = strength_score + (position_multiplier - 1.0) * 2
                action_scores['raise'] = raise_score

        # Evaluate all-in
        all_in_action = next((a for a in valid_actions if a['action'] == 'all_in'), None)
        if all_in_action:
            # Go all-in with very strong hands or as a last resort
            if adjusted_strength > 9 or (is_short_stack and adjusted_strength > 7):
                action_scores['all_in'] = 10.0  # Highest priority

        # Evaluate fold
        fold_action = next((a for a in valid_actions if a['action'] == 'fold'), None)
        if fold_action:
            # Fold with weak hands, especially out of position
            if adjusted_strength < 4 or (adjusted_strength < 5 and position_multiplier < 1.0) or (pot_odds > 0.5 and adjusted_strength < 7):
                action_scores['fold'] = 1.0  # Lowest priority

        # Select best action
        if not action_scores:
            # If no actions scored, default to fold or check
            if check_action:
                return check_action
            return fold_action or valid_actions[0]

        best_action_name = max(action_scores.items(), key=lambda x: x[1])[0]

        # Find the corresponding action
        chosen_action = next((a for a in valid_actions if a['action'] == best_action_name), None)

        # Handle raise sizing
        if chosen_action and chosen_action['action'] == 'raise':
            # Determine raise amount based on hand strength and tournament stage
            min_raise = chosen_action['amount']['min']
            max_raise = chosen_action['amount']['max']

            # More aggressive raises with stronger hands
            if adjusted_strength > 9:
                # Strong hand - pot-sized raise
                raise_amount = min(max_raise, pot_size * 2)
            elif adjusted_strength > 7:
                # Medium-strong hand - half-pot raise
                raise_amount = min(max_raise, pot_size)
            else:
                # Minimum raise with marginal hands
                raise_amount = min_raise

            # Adjust for tournament stage
            if self.tournament_stage in ['late', 'final']:
                raise_amount = max(raise_amount, min_raise * 2)

            # Ensure we don't overbet
            raise_amount = min(raise_amount, max_raise)
            chosen_action['amount'] = raise_amount

        return chosen_action or valid_actions[0]  # Fallback to first valid action

# Initialize strategy
ai_strategy = AIStrategy()

@app.route('/action', methods=['POST'])
def get_action():
    start_time = time.time()
    game_state = request.get_json()

    try:
        # Make decision
        decision = ai_strategy.make_decision(game_state)
        return jsonify(decision)
    except Exception as e:
        # Fallback to safe action on error
        valid_actions = game_state.get('valid_actions', [])
        # Prefer check if possible, then fold
        check_action = next((a for a in valid_actions if a['action'] == 'check'), None)
        if check_action:
            return jsonify(check_action)
        fold_action = next((a for a in valid_actions if a['action'] == 'fold'), None)
        if fold_action:
            return jsonify(fold_action)
        # Return first valid action as last resort
        return jsonify(valid_actions[0] if valid_actions else {'action': 'fold', 'amount': 0})
    finally:
        # Log response time
        response_time = time.time() - start_time
        if response_time > 2.5:  # Warn if close to timeout
            print(f"WARNING: Slow response time: {response_time:.2f}s")

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "demo2_AI"})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Demo2 AI HTTP Server")
    parser.add_argument('--port', type=int, required=True, help='Port to listen on')
    args = parser.parse_args()

    app.run(host='0.0.0.0', port=args.port, threaded=True)
