#!/usr/bin/env python3
"""
Demo1 AI - Advanced Texas Hold'em AI
A competitive poker AI implementing sophisticated strategies including:
- Hand strength evaluation with position awareness
- Pot odds and implied odds calculations
- Opponent modeling and betting pattern analysis
- Bluffing and semi-bluffing strategies
- Tournament-specific adjustments for blind levels
"""

from flask import Flask, request, jsonify
import argparse
import logging
import json
import random
import math
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict
from itertools import combinations

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('demo1_AI')

class PokerAI:
    def __init__(self):
        self.name = "demo1_AI"
        self.opponent_stats = defaultdict(lambda: {
            'hands_played': 0,
            'vpip': 0,  # Voluntarily Put money In Pot
            'pfr': 0,   # Pre-Flop Raise
            'aggression': 0,
            'fold_to_bet': 0,
            'recent_actions': []
        })
        self.hand_history = []
        
    def evaluate_hand_strength(self, hole_cards: List[str], community_cards: List[str]) -> float:
        """Evaluate hand strength from 0.0 to 1.0"""
        all_cards = hole_cards + community_cards
        
        if len(community_cards) == 0:
            # Pre-flop hand strength
            return self._preflop_hand_strength(hole_cards)
        else:
            # Post-flop hand strength
            return self._postflop_hand_strength(all_cards)
    
    def _preflop_hand_strength(self, hole_cards: List[str]) -> float:
        """Evaluate pre-flop hand strength using Chen formula and adjustments"""
        if len(hole_cards) != 2:
            return 0.0
            
        card1, card2 = hole_cards
        rank1, suit1 = self._parse_card(card1)
        rank2, suit2 = self._parse_card(card2)
        
        # Chen formula base
        high_card = max(rank1, rank2)
        low_card = min(rank1, rank2)
        
        # Base score for highest card
        if high_card == 14:  # Ace
            score = 10
        elif high_card == 13:  # King
            score = 8
        elif high_card == 12:  # Queen
            score = 7
        elif high_card == 11:  # Jack
            score = 6
        else:
            score = max(high_card / 2, 0)
        
        # Pair bonus
        if rank1 == rank2:
            score = max(score * 2, 5)
            if rank1 >= 10:
                score += 2
        
        # Suited bonus
        if suit1 == suit2:
            score += 2
        
        # Gap penalty
        gap = abs(rank1 - rank2) - 1
        if gap == 1:
            score -= 1
        elif gap == 2:
            score -= 2
        elif gap == 3:
            score -= 4
        elif gap >= 4:
            score -= 5
        
        # Straight potential
        if gap <= 3 and low_card >= 5:
            score += 1
        
        # Normalize to 0-1 range
        return min(score / 20, 1.0)
    
    def _postflop_hand_strength(self, all_cards: List[str]) -> float:
        """Evaluate post-flop hand strength"""
        if len(all_cards) < 5:
            return 0.5
            
        # Get best 5-card hand
        best_hand = self._get_best_hand(all_cards)
        hand_rank = self._rank_hand(best_hand)
        
        # Normalize hand rank (0-8 scale to 0-1)
        return hand_rank / 8.0
    
    def _parse_card(self, card: str) -> Tuple[int, str]:
        """Parse card string into rank and suit"""
        rank_map = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, 
                   '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        return rank_map[card[0]], card[1]
    
    def _get_best_hand(self, cards: List[str]) -> List[str]:
        """Get best 5-card hand from available cards"""
        if len(cards) <= 5:
            return cards
        
        best_hand = None
        best_rank = -1
        
        for combo in combinations(cards, 5):
            rank = self._rank_hand(list(combo))
            if rank > best_rank:
                best_rank = rank
                best_hand = list(combo)
        
        return best_hand or cards[:5]
    
    def _rank_hand(self, hand: List[str]) -> int:
        """Rank a 5-card hand (0=high card, 8=straight flush)"""
        if len(hand) != 5:
            return 0
            
        ranks = [self._parse_card(card)[0] for card in hand]
        suits = [self._parse_card(card)[1] for card in hand]
        
        ranks.sort(reverse=True)
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        counts = sorted(rank_counts.values(), reverse=True)
        is_flush = len(set(suits)) == 1
        is_straight = self._is_straight(ranks)
        
        if is_straight and is_flush:
            return 8  # Straight flush
        elif counts == [4, 1]:
            return 7  # Four of a kind
        elif counts == [3, 2]:
            return 6  # Full house
        elif is_flush:
            return 5  # Flush
        elif is_straight:
            return 4  # Straight
        elif counts == [3, 1, 1]:
            return 3  # Three of a kind
        elif counts == [2, 2, 1]:
            return 2  # Two pair
        elif counts == [2, 1, 1, 1]:
            return 1  # One pair
        else:
            return 0  # High card
    
    def _is_straight(self, ranks: List[int]) -> bool:
        """Check if ranks form a straight"""
        ranks = sorted(set(ranks))
        if len(ranks) != 5:
            return False
        
        # Check normal straight
        if ranks[-1] - ranks[0] == 4:
            return True
        
        # Check A-2-3-4-5 straight
        if ranks == [2, 3, 4, 5, 14]:
            return True
        
        return False
    
    def calculate_pot_odds(self, pot: int, bet_to_call: int) -> float:
        """Calculate pot odds"""
        if bet_to_call <= 0:
            return float('inf')
        return pot / bet_to_call
    
    def estimate_win_probability(self, hole_cards: List[str], community_cards: List[str], 
                               num_opponents: int) -> float:
        """Estimate win probability using Monte Carlo simulation (simplified)"""
        hand_strength = self.evaluate_hand_strength(hole_cards, community_cards)
        
        # Adjust for number of opponents
        win_prob = hand_strength ** (num_opponents * 0.5)  # Less aggressive reduction
        
        # Pre-flop adjustments
        if len(community_cards) == 0:
            # High pairs and premium hands
            if self._is_premium_hand(hole_cards):
                win_prob = max(win_prob, 0.75)
            elif self._is_strong_hand(hole_cards):
                win_prob = max(win_prob, 0.6)
        
        return min(win_prob, 0.95)
    
    def _is_premium_hand(self, hole_cards: List[str]) -> bool:
        """Check if hand is premium (AA, KK, QQ, AK)"""
        if len(hole_cards) != 2:
            return False
            
        rank1, suit1 = self._parse_card(hole_cards[0])
        rank2, suit2 = self._parse_card(hole_cards[1])
        
        # Pocket pairs AA, KK, QQ
        if rank1 == rank2 and rank1 >= 12:
            return True
        
        # AK suited or unsuited
        if {rank1, rank2} == {14, 13}:
            return True
        
        return False
    
    def _is_strong_hand(self, hole_cards: List[str]) -> bool:
        """Check if hand is strong"""
        if len(hole_cards) != 2:
            return False
            
        rank1, suit1 = self._parse_card(hole_cards[0])
        rank2, suit2 = self._parse_card(hole_cards[1])
        
        # High pairs
        if rank1 == rank2 and rank1 >= 9:
            return True
        
        # High suited connectors
        if suit1 == suit2:
            if min(rank1, rank2) >= 10 or abs(rank1 - rank2) <= 1:
                return True
        
        # Broadway cards
        if min(rank1, rank2) >= 10:
            return True
        
        return False
    
    def analyze_position(self, current_player: str, players: Dict, dealer_index: int) -> str:
        """Analyze position relative to dealer"""
        player_list = list(players.keys())
        active_players = [p for p in player_list if players[p]['state'] == 'active']
        
        if current_player not in active_players:
            return 'unknown'
        
        num_active = len(active_players)
        player_index = active_players.index(current_player)
        
        # Determine position
        if num_active <= 2:
            return 'heads_up'
        elif player_index <= 2:
            return 'early'
        elif player_index <= num_active // 2:
            return 'middle'
        else:
            return 'late'
    
    def update_opponent_stats(self, game_state: Dict):
        """Update opponent statistics for modeling"""
        action_history = game_state.get('action_history', [])
        current_phase = game_state.get('phase', 'preflop')
        
        for action in action_history:
            player_id = action.get('player_id')
            action_type = action.get('action')
            
            if player_id and player_id != self.name:
                stats = self.opponent_stats[player_id]
                stats['hands_played'] += 1
                stats['recent_actions'].append(action_type)
                
                # Keep only recent actions
                if len(stats['recent_actions']) > 10:
                    stats['recent_actions'] = stats['recent_actions'][-10:]
                
                # Update VPIP (Voluntarily Put money In Pot)
                if action_type in ['call', 'raise', 'all_in'] and current_phase == 'preflop':
                    stats['vpip'] += 1
                
                # Update PFR (Pre-Flop Raise)
                if action_type in ['raise', 'all_in'] and current_phase == 'preflop':
                    stats['pfr'] += 1
                
                # Update aggression
                if action_type in ['raise', 'all_in']:
                    stats['aggression'] += 1
                elif action_type == 'fold':
                    stats['fold_to_bet'] += 1
    
    def get_opponent_tendency(self, player_id: str) -> str:
        """Get opponent playing tendency"""
        if player_id not in self.opponent_stats:
            return 'unknown'
        
        stats = self.opponent_stats[player_id]
        hands = max(stats['hands_played'], 1)
        
        vpip_rate = stats['vpip'] / hands
        aggression_rate = stats['aggression'] / hands
        
        if vpip_rate > 0.3 and aggression_rate > 0.2:
            return 'aggressive'
        elif vpip_rate < 0.15:
            return 'tight'
        elif aggression_rate < 0.1:
            return 'passive'
        else:
            return 'balanced'
    
    def calculate_bet_size(self, game_state: Dict, action_type: str) -> int:
        """Calculate optimal bet size"""
        pot = game_state.get('pot', 0)
        current_bet = game_state.get('current_bet', 0)
        my_chips = 0
        
        players = game_state.get('players', {})
        for player_id, player_info in players.items():
            if player_id == game_state.get('current_player'):
                my_chips = player_info.get('chips', 0)
                my_current_bet = player_info.get('current_bet', 0)
                break
        
        if action_type == 'raise':
            # Get valid raise range
            valid_actions = game_state.get('valid_actions', [])
            raise_action = next((a for a in valid_actions if a['action'] == 'raise'), None)
            
            if raise_action and isinstance(raise_action.get('amount'), dict):
                min_raise = raise_action['amount']['min']
                max_raise = raise_action['amount']['max']
            else:
                min_raise = game_state.get('min_raise', current_bet * 2)
                max_raise = my_chips
            
            # Standard raise sizes
            pot_size_raise = pot + current_bet
            half_pot_raise = (pot + current_bet) // 2
            
            # Choose raise size based on hand strength and position
            hole_cards = []
            community_cards = game_state.get('community_cards', [])
            
            for player_id, player_info in players.items():
                if player_id == game_state.get('current_player'):
                    hole_cards = player_info.get('hole_cards', [])
                    break
            
            hand_strength = self.evaluate_hand_strength(hole_cards, community_cards)
            
            if hand_strength > 0.8:
                # Strong hand - bet for value
                target = min(pot_size_raise, max_raise)
            elif hand_strength > 0.6:
                # Good hand - moderate bet
                target = min(half_pot_raise, max_raise)
            else:
                # Bluff or semi-bluff - smaller bet
                target = min_raise
            
            return max(min_raise, min(target, max_raise))
        
        return current_bet
    
    def should_bluff(self, game_state: Dict) -> bool:
        """Determine if we should bluff"""
        # Simple bluffing logic
        community_cards = game_state.get('community_cards', [])
        pot = game_state.get('pot', 0)
        
        # Don't bluff pre-flop or with small pots
        if len(community_cards) == 0 or pot < 100:
            return False
        
        # Bluff occasionally on scary boards
        if len(community_cards) >= 3:
            # Check for flush/straight possibilities
            suits = [card[1] for card in community_cards]
            ranks = [self._parse_card(card)[0] for card in community_cards]
            
            # Flush draw on board
            if len(set(suits)) <= 2:
                return random.random() < 0.3
            
            # Straight possibilities
            if max(ranks) - min(ranks) <= 4:
                return random.random() < 0.25
        
        return random.random() < 0.1
    
    def make_decision(self, game_state: Dict) -> Dict[str, Any]:
        """Main decision-making function"""
        try:
            # Update opponent stats
            self.update_opponent_stats(game_state)
            
            valid_actions = game_state.get('valid_actions', [])
            if not valid_actions:
                return {"action": "fold", "amount": 0}
            
            # Get game information
            hole_cards = []
            my_chips = 0
            my_current_bet = 0
            current_player = game_state.get('current_player')
            
            players = game_state.get('players', {})
            for player_id, player_info in players.items():
                if player_id == current_player:
                    hole_cards = player_info.get('hole_cards', [])
                    my_chips = player_info.get('chips', 0)
                    my_current_bet = player_info.get('current_bet', 0)
                    break
            
            community_cards = game_state.get('community_cards', [])
            pot = game_state.get('pot', 0)
            current_bet = game_state.get('current_bet', 0)
            phase = game_state.get('phase', 'preflop')
            
            # Calculate hand strength and win probability
            hand_strength = self.evaluate_hand_strength(hole_cards, community_cards)
            num_opponents = len([p for p in players.values() if p['state'] == 'active']) - 1
            win_prob = self.estimate_win_probability(hole_cards, community_cards, num_opponents)
            
            # Get position
            dealer_index = game_state.get('dealer_index', 0)
            position = self.analyze_position(current_player, players, dealer_index)
            
            # Calculate pot odds if we need to call
            bet_to_call = current_bet - my_current_bet
            pot_odds = self.calculate_pot_odds(pot, bet_to_call) if bet_to_call > 0 else float('inf')
            
            # Find available actions
            fold_action = next((a for a in valid_actions if a['action'] == 'fold'), None)
            check_action = next((a for a in valid_actions if a['action'] == 'check'), None)
            call_action = next((a for a in valid_actions if a['action'] == 'call'), None)
            raise_action = next((a for a in valid_actions if a['action'] == 'raise'), None)
            all_in_action = next((a for a in valid_actions if a['action'] == 'all_in'), None)
            
            # Decision logic
            logger.info(f"Hand: {hole_cards}, Strength: {hand_strength:.3f}, Win prob: {win_prob:.3f}, Position: {position}")
            
            # Premium hands - always aggressive
            if self._is_premium_hand(hole_cards):
                if raise_action:
                    amount = self.calculate_bet_size(game_state, 'raise')
                    logger.info(f"Premium hand - raising to {amount}")
                    return {"action": "raise", "amount": amount}
                elif call_action:
                    logger.info("Premium hand - calling")
                    return call_action
                elif check_action:
                    logger.info("Premium hand - checking")
                    return check_action
            
            # Very strong hands - always bet/raise for value
            elif hand_strength > 0.8 or win_prob > 0.75:
                if raise_action:
                    amount = self.calculate_bet_size(game_state, 'raise')
                    logger.info(f"Very strong hand - raising to {amount}")
                    return {"action": "raise", "amount": amount}
                elif call_action:
                    logger.info("Very strong hand - calling")
                    return call_action
                elif check_action:
                    logger.info("Very strong hand - checking")
                    return check_action
            
            # Strong hands - bet for value or call
            elif hand_strength > 0.6 or win_prob > 0.55:
                if check_action and position in ['early', 'middle'] and bet_to_call == 0:
                    logger.info("Strong hand - checking in early/middle position")
                    return check_action
                elif raise_action and (position == 'late' or bet_to_call == 0):
                    amount = self.calculate_bet_size(game_state, 'raise')
                    logger.info(f"Strong hand - raising to {amount}")
                    return {"action": "raise", "amount": amount}
                elif call_action and pot_odds > 2:
                    logger.info("Strong hand - calling with good pot odds")
                    return call_action
                elif check_action:
                    logger.info("Strong hand - checking")
                    return check_action
            
            # Marginal hands - position and pot odds dependent
            elif hand_strength > 0.35 or win_prob > 0.25:
                if check_action:
                    logger.info("Marginal hand - checking")
                    return check_action
                elif call_action and pot_odds > 3 and bet_to_call < my_chips * 0.15:
                    logger.info("Marginal hand - calling with good pot odds")
                    return call_action
                elif position == 'late' and self.should_bluff(game_state) and raise_action:
                    amount = self.calculate_bet_size(game_state, 'raise')
                    logger.info(f"Marginal hand - bluffing from late position, raising to {amount}")
                    return {"action": "raise", "amount": amount}
            
            # Weak hands - mostly fold unless great pot odds
            else:
                if check_action:
                    logger.info("Weak hand - checking")
                    return check_action
                elif call_action and pot_odds > 6 and bet_to_call < my_chips * 0.05:
                    logger.info("Weak hand - calling with great pot odds")
                    return call_action
            
            # Default to fold
            if fold_action:
                logger.info("Folding")
                return fold_action
            
            # Fallback to first valid action
            logger.info("Fallback to first valid action")
            return valid_actions[0]
            
        except Exception as e:
            logger.error(f"Error in decision making: {e}")
            # Safe fallback
            fold_action = next((a for a in valid_actions if a['action'] == 'fold'), None)
            if fold_action:
                return fold_action
            return valid_actions[0] if valid_actions else {"action": "fold", "amount": 0}

# Global AI instance
poker_ai = PokerAI()

@app.route('/action', methods=['POST'])
def get_action():
    """Main action endpoint"""
    try:
        game_state = request.get_json()
        if not game_state:
            return jsonify({"error": "No game state provided"}), 400
        
        logger.info(f"Received game state for hand {game_state.get('hand_number', 'unknown')}")
        
        # Make decision
        decision = poker_ai.make_decision(game_state)
        
        logger.info(f"Decision: {decision}")
        return jsonify(decision)
        
    except Exception as e:
        logger.error(f"Error processing action request: {e}")
        return jsonify({"action": "fold", "amount": 0})

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "ai_name": poker_ai.name,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get AI statistics"""
    return jsonify({
        "ai_name": poker_ai.name,
        "opponent_stats": dict(poker_ai.opponent_stats),
        "hands_analyzed": len(poker_ai.hand_history)
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Demo1 AI - Advanced Texas Hold'em AI")
    parser.add_argument('--port', type=int, default=9013, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    logger.info(f"Starting {poker_ai.name} on port {args.port}")
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)