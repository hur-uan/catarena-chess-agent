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

class demo2SeedAI:
    """Enhanced Bridge AI with strategic bidding and playing logic"""
    
    def __init__(self, ai_id: str, ai_name: str = None, game_server_url: str = "http://localhost:9030"):
        self.ai_id = ai_id
        self.ai_name = ai_name or f"demo2"
        self.game_server_url = game_server_url
        self.active_games = {}  # game_id -> game_info
        self.bidding_strategy = self._initialize_bidding_strategy()
        self.playing_strategy = self._initialize_playing_strategy()
    
    def _initialize_bidding_strategy(self) -> dict:
        """Initialize advanced bidding strategy parameters"""
        return {
            'opening_threshold': 13,  # 13+ points to open
            'min_response': 6,        # Minimum points to respond
            'support_points': 3,      # Points needed for basic support
            'game_threshold': 25,     # Combined points for game
            'slam_threshold': 33,     # Combined points for slam
            'preemptive_level': {     # Preemptive level based on suit length
                6: 2,  # 6-card suit → level 2
                7: 3,  # 7-card suit → level 3
                8: 4   # 8-card suit → level 4
            }
        }
    
    def _initialize_playing_strategy(self) -> dict:
        """Initialize advanced playing strategy parameters"""
        return {
            'honor_lead_probability': 0.7,  # Probability to lead with honors
            'finesse_probability': 0.6,     # Probability to attempt finesse
            'hold_up_threshold': 2,          # Number of stoppers to hold up
            'signal_strength': True         # Use strength signals
        }
    
    def join_game(self, game_id: str, player_id: int):
        """Join a game"""
        try:
            join_data = {
                "player_id": player_id,
                "player_name": self.ai_name
            }
            response = requests.post(f"{self.game_server_url}/games/{game_id}/join", json=join_data)
            
            if response.status_code == 200:
                self.active_games[game_id] = {
                    "player_id": player_id,
                    "game_id": game_id,
                    "joined_at": datetime.now(),
                    "hand_history": [],
                    "bidding_history": [],
                    "played_cards": []
                }
                print(f"AI {self.ai_id} joined game {game_id} as player {player_id}")
                return True
            else:
                print(f"Join failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"Join error: {e}")
            return False
    
    def leave_game(self, game_id: str):
        """Leave a game"""
        if game_id in self.active_games:
            del self.active_games[game_id]
            print(f"AI {self.ai_id} left game {game_id}")
    
    def get_action(self, game_id: str, game_state: dict) -> Optional[dict]:
        """Get AI action with enhanced strategy"""
        if game_id not in self.active_games:
            print(f"Not in game {game_id}")
            return None
        
        my_player_id = self.active_games[game_id]["player_id"]
        phase = game_state.get('phase', 'unknown')
        
        # Update game history
        self._update_game_history(game_id, game_state)
        
        if phase == 'bidding':
            return self.make_bid(game_state, my_player_id)
        elif phase == 'playing':
            current_player_id = game_state.get('current_player_id', my_player_id)
            return self.play_card(game_state, current_player_id)
        else:
            print(f"Unknown phase: {phase}")
            return None
    
    def _update_game_history(self, game_id: str, game_state: dict):
        """Update game history for strategy analysis"""
        game_data = self.active_games[game_id]
        
        # Update hand history
        my_hand = self.find_my_hand(game_state, game_data['player_id'])
        if my_hand and (not game_data['hand_history'] or my_hand != game_data['hand_history'][-1]):
            game_data['hand_history'].append(my_hand)
        
        # Update bidding history
        bidding = game_state.get('bidding', {})
        calls = bidding.get('calls', [])
        if calls != game_data['bidding_history']:
            game_data['bidding_history'] = calls.copy()
    
    def _evaluate_hand(self, hand: List[dict]) -> Tuple[int, dict]:
        """Advanced hand evaluation: HCP + distribution points + suit quality"""
        if not hand:
            return (0, {})
        
        # High Card Points (HCP)
        hcp_values = {'A':4, 'K':3, 'Q':2, 'J':1}
        hcp = sum(hcp_values.get(card.get('rank', ''), 0) for card in hand)
        
        # Distribution points
        suit_counts = self._count_suits(hand)
        dist_points = 0
        for suit, count in suit_counts.items():
            if count <= 2:  # Short suits
                dist_points += (2 - count + 1)  # 2=1pt, 1=2pt, 0=3pt
            elif count >= 5:  # Long suits
                dist_points += (count - 4)  # 5=1pt, 6=2pt, etc.
        
        # Suit quality evaluation
        suit_quality = {}
        for suit, count in suit_counts.items():
            honors = 0
            for card in hand:
                if card.get('suit') == suit and card.get('rank') in ['A', 'K', 'Q', 'J', 'T']:
                    honors += 1
            suit_quality[suit] = {
                'length': count,
                'honors': honors,
                'quality': (count / 13) + (honors / 5)  # Combined quality score
            }
        
        total_points = hcp + dist_points
        return (total_points, {'hcp': hcp, 'dist_points': dist_points, 
                              'suit_counts': suit_counts, 'suit_quality': suit_quality})
    
    def _count_suits(self, hand: List[dict]) -> dict:
        """Count cards in each suit"""
        counts = {'C':0, 'D':0, 'H':0, 'S':0, 'NT':0}
        for card in hand:
            suit = card.get('suit', '')
            if suit in counts:
                counts[suit] += 1
        return counts
    
    def make_bid(self, game_state: dict, player_id: int) -> Optional[dict]:
        """Advanced bidding strategy"""
        legal_actions = self.get_legal_actions(game_state, player_id)
        if not legal_actions:
            return None
        
        my_hand = self.find_my_hand(game_state, player_id)
        if not my_hand:
            return self._find_pass_action(legal_actions)
        
        # Evaluate hand strength
        total_points, hand_details = self._evaluate_hand(my_hand)
        suit_counts = hand_details['suit_counts']
        suit_quality = hand_details['suit_quality']
        
        # Get bidding history
        bidding = game_state.get('bidding', {})
        calls = bidding.get('calls', [])
        our_team = player_id % 2  # 0 and 2 are N-S, 1 and 3 are E-W
        
        # Determine bidding strategy based on position and history
        if not calls:  # First to bid
            return self._opening_bid(legal_actions, total_points, suit_counts, suit_quality)
        else:
            partner_bid = self._find_partner_bid(calls, our_team)
            opponents_bid = self._find_opponents_bid(calls, our_team)
            
            if partner_bid:
                return self._respond_to_bid(legal_actions, total_points, suit_counts, 
                                          suit_quality, partner_bid, opponents_bid)
            elif opponents_bid:
                return self._competitive_bid(legal_actions, total_points, suit_counts, 
                                           suit_quality, opponents_bid)
            else:
                # Everyone passed so far
                return self._opening_bid(legal_actions, total_points, suit_counts, suit_quality)
    
    def _opening_bid(self, legal_actions: List[dict], points: int, 
                     suit_counts: dict, suit_quality: dict) -> dict:
        """Determine opening bid"""
        # Preemptive bidding strategy
        for suit in ['S', 'H', 'D', 'C']:  # Higher suits first
            count = suit_counts.get(suit, 0)
            if count >= 6 and points < self.bidding_strategy['opening_threshold']:
                # Weak hand with long suit - preempt
                preempt_level = self.bidding_strategy['preemptive_level'].get(count, 0)
                if preempt_level > 0:
                    bid_action = self._find_bid_action(legal_actions, preempt_level, suit)
                    if bid_action:
                        return bid_action
        
        # Normal opening bids
        if points >= self.bidding_strategy['opening_threshold']:
            # Find best suit
            best_suit = None
            max_quality = -1
            for suit in ['S', 'H', 'D', 'C']:  # Majors first
                quality = suit_quality.get(suit, {}).get('quality', 0)
                if quality > max_quality and suit_counts.get(suit, 0) >= 4:
                    max_quality = quality
                    best_suit = suit
            
            # No major suit, check minors
            if not best_suit:
                for suit in ['D', 'C']:
                    if suit_counts.get(suit, 0) >= 4:
                        best_suit = suit
                        break
            
            # 1NT with balanced hand
            if not best_suit and points >= 15 and points <= 17:
                # Check balanced distribution
                if all(count in [2, 3, 4] for count in suit_counts.values()):
                    nt_bid = self._find_bid_action(legal_actions, 1, 'NT')
                    if nt_bid:
                        return nt_bid
            
            # Make bid if we found a suit
            if best_suit:
                bid_action = self._find_bid_action(legal_actions, 1, best_suit)
                if bid_action:
                    return bid_action
        
        # Default to pass
        return self._find_pass_action(legal_actions)
    
    def _respond_to_bid(self, legal_actions: List[dict], points: int, suit_counts: dict, 
                        suit_quality: dict, partner_bid: dict, opponents_bid: dict) -> dict:
        """Respond to partner's bid"""
        # Simple support for now
        partner_suit = partner_bid.get('suit')
        partner_level = partner_bid.get('level', 1)
        
        # Support with fit
        if partner_suit and partner_suit != 'NT' and suit_counts.get(partner_suit, 0) >= 3:
            support_level = min(partner_level + 1, 4) if points >= self.bidding_strategy['support_points'] else partner_level
            bid_action = self._find_bid_action(legal_actions, support_level, partner_suit)
            if bid_action:
                return bid_action
        
        # New suit with enough points
        if points >= self.bidding_strategy['min_response']:
            # Find our best suit
            for suit in ['S', 'H', 'D', 'C']:
                if suit != partner_suit and suit_counts.get(suit, 0) >= 4:
                    bid_action = self._find_bid_action(legal_actions, 1, suit)
                    if bid_action:
                        return bid_action
            
            # NT response
            if points >= 8 and points <= 10:
                nt_bid = self._find_bid_action(legal_actions, partner_level, 'NT')
                if nt_bid:
                    return nt_bid
        
        # Pass if insufficient points
        return self._find_pass_action(legal_actions)
    
    def _competitive_bid(self, legal_actions: List[dict], points: int, 
                         suit_counts: dict, suit_quality: dict, opponents_bid: dict) -> dict:
        """Bid against opponents"""
        opp_level = opponents_bid.get('level', 1)
        opp_suit = opponents_bid.get('suit', '')
        
        # Overcall with good suit
        if points >= 10:
            for suit in ['S', 'H', 'D', 'C']:
                if suit != opp_suit and suit_counts.get(suit, 0) >= 5:
                    # Bid one level higher in our suit
                    bid_action = self._find_bid_action(legal_actions, opp_level, suit)
                    if not bid_action and opp_level < 7:
                        bid_action = self._find_bid_action(legal_actions, opp_level + 1, suit)
                    if bid_action:
                        return bid_action
            
            # Double for takeout with support for unbid suits
            if points >= 13 and self._has_support_for_unbid(opp_suit, suit_counts):
                for action in legal_actions:
                    if action.get('call_type') == 'double':
                        return action
        
        return self._find_pass_action(legal_actions)
    
    def _has_support_for_unbid(self, opp_suit: str, suit_counts: dict) -> bool:
        """Check if we have support for unbid suits"""
        unbid_suits = [s for s in ['S', 'H', 'D', 'C'] if s != opp_suit]
        return all(suit_counts.get(suit, 0) >= 3 for suit in unbid_suits[:2])
    
    def _find_partner_bid(self, calls: List[dict], our_team: int) -> Optional[dict]:
        """Find partner's last bid"""
        # Simplified: find last bid from our team
        for call in reversed(calls):
            if call.get('team') == our_team and call.get('call_type') == 'bid':
                return call
        return None
    
    def _find_opponents_bid(self, calls: List[dict], our_team: int) -> Optional[dict]:
        """Find opponents' last bid"""
        # Simplified: find last bid from opponents
        for call in reversed(calls):
            if call.get('team') != our_team and call.get('call_type') == 'bid':
                return call
        return None
    
    def _find_bid_action(self, legal_actions: List[dict], level: int, suit: str) -> Optional[dict]:
        """Find specific bid action in legal actions"""
        for action in legal_actions:
            if (action.get('call_type') == 'bid' and 
                action.get('level') == level and 
                action.get('suit') == suit):
                return action
        return None
    
    def _find_pass_action(self, legal_actions: List[dict]) -> dict:
        """Find pass action in legal actions"""
        for action in legal_actions:
            if action.get('call_type') == 'pass':
                return action
        return legal_actions[0] if legal_actions else None
    
    def play_card(self, game_state: dict, player_id: int) -> Optional[dict]:
        """Advanced card playing strategy"""
        legal_actions = self.get_legal_actions(game_state, player_id)
        if not legal_actions:
            return None
        
        my_hand = self.find_my_hand(game_state, player_id)
        if not my_hand:
            return self._default_play(legal_actions)
        
        current_trick = game_state.get('current_trick', [])
        contract = game_state.get('bidding', {}).get('contract', {})
        trump_suit = contract.get('suit') if contract else None
        
        # Track played cards
        game_id = game_state.get('game_id', '')
        if game_id in self.active_games:
            for trick in game_state.get('tricks_won', []):
                for player, card in trick.get('cards', []):
                    if card not in self.active_games[game_id]['played_cards']:
                        self.active_games[game_id]['played_cards'].append(card)
            
            for player, card in current_trick:
                if card not in self.active_games[game_id]['played_cards']:
                    self.active_games[game_id]['played_cards'].append(card)
        
        if current_trick:
            led_card_str = current_trick[0][1] if current_trick else None
            led_suit = led_card_str[-1] if led_card_str else None
            
            if led_suit:
                return self._follow_suit_strategy(my_hand, led_suit, trump_suit, legal_actions, current_trick)
            else:
                return self._lead_card_strategy(my_hand, trump_suit, legal_actions, game_state)
        else:
            return self._lead_card_strategy(my_hand, trump_suit, legal_actions, game_state)
    
    def _lead_card_strategy(self, hand: List[dict], trump_suit: str, 
                           legal_actions: List[dict], game_state: dict) -> dict:
        """Advanced opening lead strategy"""
        # Evaluate contract and choose appropriate lead
        contract = game_state.get('bidding', {}).get('contract', {})
        contract_suit = contract.get('suit', '')
        contract_level = contract.get('level', 1)
        
        # From bidding history, determine if opponents have strong suit
        if contract_suit and contract_suit != 'NT' and contract_suit != trump_suit:
            # Lead trump to reduce their ruffing power
            trump_cards = [card for card in hand if card.get('suit') == trump_suit]
            if trump_cards and random.random() < 0.4:
                return self._select_card_action(legal_actions, self._choose_lowest_card(trump_cards))
        
        # Lead from longest suit
        suit_counts = self._count_suits(hand)
        longest_suit = max(suit_counts, key=lambda k: suit_counts[k] if k != trump_suit else 0)
        
        # Prefer major suits
        for suit in ['S', 'H', 'D', 'C']:
            if suit_counts[suit] == suit_counts[longest_suit] and suit != trump_suit:
                longest_suit = suit
                break
        
        # Choose lead from longest suit
        suit_cards = [card for card in hand if card.get('suit') == longest_suit]
        
        if len(suit_cards) >= 3 and any(card.get('rank') in ['A', 'K', 'Q'] for card in suit_cards):
            # Lead top of sequence
            honors = sorted([card for card in suit_cards if card.get('rank') in ['A', 'K', 'Q', 'J', 'T']], 
                           key=lambda c: self.card_value(c), reverse=True)
            if len(honors) >= 2 and self._is_sequence(honors[:2]):
                return self._select_card_action(legal_actions, honors[0])
            elif random.random() < self.playing_strategy['honor_lead_probability'] and honors:
                return self._select_card_action(legal_actions, honors[0])
            else:
                # Lead low
                return self._select_card_action(legal_actions, self._choose_lowest_card(suit_cards))
        else:
            # Lead fourth best
            if len(suit_cards) >= 4:
                sorted_cards = sorted(suit_cards, key=lambda c: self.card_value(c))
                return self._select_card_action(legal_actions, sorted_cards[3])
            else:
                # Lead lowest
                return self._select_card_action(legal_actions, self._choose_lowest_card(suit_cards))
    
    def _follow_suit_strategy(self, hand: List[dict], led_suit: str, trump_suit: str, 
                             legal_actions: List[dict], current_trick: list) -> dict:
        """Advanced strategy for following suit"""
        same_suit = [card for card in hand if card.get('suit') == led_suit]
        
        if same_suit:
            # We have cards in led suit
            trick_cards = [card for player, card in current_trick]
            led_rank = current_trick[0][1][:-1] if current_trick else ''
            
            # Evaluate if we can win this trick
            our_team = self.active_games.get(game_state.get('game_id', ''), {}).get('player_id', 0) % 2
            trick_winner = self._predict_trick_winner(current_trick, led_suit, trump_suit, our_team)
            
            if trick_winner == our_team:
                # We're winning, play low
                return self._select_card_action(legal_actions, self._choose_lowest_card(same_suit))
            else:
                # We're losing, try to win or play appropriately
                highest_in_trick = max([self._parse_card_value(card) for player, card in current_trick], default=0)
                higher_cards = [card for card in same_suit if self._parse_card_value(self._card_to_string(card)) > highest_in_trick]
                
                if higher_cards:
                    # Play lowest card that can win
                    return self._select_card_action(legal_actions, self._choose_lowest_card(higher_cards))
                else:
                    # Play lowest card
                    return self._select_card_action(legal_actions, self._choose_lowest_card(same_suit))
        else:
            # No cards in led suit
            if trump_suit and any(card.get('suit') == trump_suit for card in hand):
                # Decide whether to trump
                tricks_won = game_state.get('tricks_won', [0, 0])
                our_team = self.active_games.get(game_state.get('game_id', ''), {}).get('player_id', 0) % 2
                contract = game_state.get('bidding', {}).get('contract', {})
                required_tricks = contract.get('level', 1) + 6
                
                if tricks_won[our_team] < required_tricks and random.random() < 0.3:
                    # Need more tricks, try to ruff
                    trump_cards = [card for card in hand if card.get('suit') == trump_suit]
                    return self._select_card_action(legal_actions, self._choose_lowest_card(trump_cards))
                else:
                    # Discard
                    return self._discard_strategy(hand, legal_actions, trump_suit)
            else:
                # Discard
                return self._discard_strategy(hand, legal_actions, trump_suit)
    
    def _discard_strategy(self, hand: List[dict], legal_actions: List[dict], trump_suit: str) -> dict:
        """Strategy for discarding"""
        # Discard from weakest suit
        suit_counts = self._count_suits(hand)
        weak_suits = sorted([s for s in ['S', 'H', 'D', 'C'] if s != trump_suit], 
                           key=lambda s: suit_counts[s])
        
        for suit in weak_suits:
            suit_cards = [card for card in hand if card.get('suit') == suit]
            if suit_cards:
                return self._select_card_action(legal_actions, self._choose_lowest_card(suit_cards))
        
        # Fallback
        return self._default_play(legal_actions)
    
    def _predict_trick_winner(self, current_trick: list, led_suit: str, trump_suit: str, our_team: int) -> int:
        """Predict who will win current trick"""
        if not current_trick:
            return -1
        
        highest_value = 0
        winner_player = current_trick[0][0]
        
        for player, card in current_trick:
            card_value = self._parse_card_value(card)
            suit = card[-1]
            
            # Trump beats led suit
            if suit == trump_suit and led_suit != trump_suit:
                card_value += 100  # Make trump cards higher
            elif suit != led_suit and suit != trump_suit:
                card_value = 0  # This card can't win
            
            if card_value > highest_value:
                highest_value = card_value
                winner_player = player
        
        return winner_player % 2
    
    def _parse_card_value(self, card_str: str) -> int:
        """Parse card string to numerical value"""
        if not card_str or len(card_str) < 2:
            return 0
        
        rank = card_str[:-1]
        rank_values = {'2':2, '3':3, '4':4, '5':5, '6':6, '7':7, '8':8, '9':9, 
                       'T':10, 'J':11, 'Q':12, 'K':13, 'A':14}
        return rank_values.get(rank, 0)
    
    def _card_to_string(self, card: dict) -> str:
        """Convert card dict to string representation"""
        return f"{card.get('rank', '')}{card.get('suit', '')}"
    
    def _is_sequence(self, cards: List[dict]) -> bool:
        """Check if cards form a sequence"""
        if len(cards) < 2:
            return False
        
        values = [self.card_value(card) for card in cards]
        for i in range(1, len(values)):
            if values[i-1] - values[i] != 1:
                return False
        return True
    
    def _choose_lowest_card(self, cards: List[dict]) -> dict:
        """Choose lowest card"""
        return min(cards, key=lambda c: self.card_value(c))
    
    def _choose_highest_card(self, cards: List[dict]) -> dict:
        """Choose highest card"""
        return max(cards, key=lambda c: self.card_value(c))
    
    def _select_card_action(self, legal_actions: List[dict], card: dict) -> dict:
        """Find legal action matching card"""
        card_str = f"{card.get('rank', '')}{card.get('suit', '')}"
        for action in legal_actions:
            if action.get('type') == 'play' and action.get('card') == card_str:
                return action
        
        # Fallback to first legal action
        return legal_actions[0] if legal_actions else None
    
    def _default_play(self, legal_actions: List[dict]) -> dict:
        """Default play when no strategy applies"""
        for action in legal_actions:
            if action.get('type') == 'play':
                return action
        return legal_actions[0] if legal_actions else None
    
    def find_my_hand(self, game_state: dict, player_id: int) -> Optional[List[dict]]:
        """Find current player's hand"""
        players = game_state.get('players', [])
        if player_id < len(players):
            player_info = players[player_id]
            if isinstance(player_info, dict) and 'hand' in player_info:
                return player_info['hand']
        return None
    
    def get_legal_actions(self, game_state: dict, player_id: int) -> List[dict]:
        """Get legal actions from game server"""
        try:
            game_id = game_state.get('game_id', '')
            if not game_id:
                return []
            
            url = f"{self.game_server_url}/games/{game_id}/legal_actions"
            params = {"player_id": player_id}
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return response.json().get('legal_actions', [])
            else:
                print(f"Failed to get legal actions: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error getting legal actions: {e}")
            return []
    
    def card_value(self, card: dict) -> int:
        """Advanced card value calculation"""
        rank = card.get('rank', '2')
        suit = card.get('suit', 'C')
        
        # Base rank values
        rank_values = {
            '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 
            'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
        }
        
        # Suit strength multiplier (majors > minors)
        suit_multiplier = 1.2 if suit in ['S', 'H'] else 1.0
        
        # Honor bonus
        honor_bonus = 0.5 if rank in ['A', 'K', 'Q', 'J'] else 0
        
        return (rank_values.get(rank, 2) + honor_bonus) * suit_multiplier


# Global AI instance
bridge_ai = None

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "ai_id": bridge_ai.ai_id if bridge_ai else "unknown"})

@app.route('/info', methods=['GET'])
def info():
    """AI information endpoint"""
    if not bridge_ai:
        return jsonify({"error": "AI not initialized"}), 500
    
    return jsonify({
        "ai_id": bridge_ai.ai_id,
        "ai_name": bridge_ai.ai_name,
        "game_server_url": bridge_ai.game_server_url,
        "active_games": len(bridge_ai.active_games)
    })

@app.route('/join_game', methods=['POST'])
def join_game():
    """Join game endpoint"""
    if not bridge_ai:
        return jsonify({"error": "AI not initialized"}), 500
    
    data = request.get_json()
    game_id = data.get('game_id')
    player_id = data.get('player_id')
    
    if not game_id or player_id is None:
        return jsonify({"error": "Missing game_id or player_id"}), 400
    
    success = bridge_ai.join_game(game_id, player_id)
    
    if success:
        return jsonify({"status": "joined", "game_id": game_id, "player_id": player_id})
    else:
        return jsonify({"error": "Failed to join game"}), 500

@app.route('/get_action', methods=['POST'])
def get_action():
    """Get AI action endpoint"""
    if not bridge_ai:
        return jsonify({"error": "AI not initialized"}), 500
    
    data = request.get_json()
    game_id = data.get('game_id')
    game_state = data.get('game_state', {})
    
    if not game_id:
        return jsonify({"error": "Missing game_id"}), 400
    
    action = bridge_ai.get_action(game_id, game_state)
    
    if action:
        return jsonify(action)
    else:
        return jsonify({"error": "No action available"}), 400

@app.route('/leave_game', methods=['POST'])
def leave_game():
    """Leave game endpoint"""
    if not bridge_ai:
        return jsonify({"error": "AI not initialized"}), 500
    
    data = request.get_json()
    game_id = data.get('game_id')
    
    if not game_id:
        return jsonify({"error": "Missing game_id"}), 400
    
    bridge_ai.leave_game(game_id)
    return jsonify({"status": "left", "game_id": game_id})

@app.route('/games', methods=['GET'])
def list_games():
    """List active games endpoint"""
    if not bridge_ai:
        return jsonify({"error": "AI not initialized"}), 500
    
    return jsonify({
        "active_games": list(bridge_ai.active_games.keys()),
        "game_count": len(bridge_ai.active_games)
    })


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='demo2 Seed Bridge AI HTTP Server')
    parser.add_argument('--port', type=int, default=50015, help='Server port')
    parser.add_argument('--ai_id', type=str, default='demo2', help='AI ID')
    parser.add_argument('--ai_name', type=str, default='demo2', help='AI name')
    parser.add_argument('--game_server', type=str, default='http://localhost:9030', help='Game server URL')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    
    args = parser.parse_args()
    
    global bridge_ai
    bridge_ai = demo2SeedAI(
        ai_id=args.ai_id,
        ai_name=args.ai_name,
        game_server_url=args.game_server
    )
    
    print("=== demo2 Seed Bridge AI HTTP Server ===")
    print(f"AI ID: {bridge_ai.ai_id}")
    print(f"AI Name: {bridge_ai.ai_name}")
    print(f"Port: {args.port}")
    print(f"Game Server: {bridge_ai.game_server_url}")
    print(f"Debug Mode: {args.debug}")
    print("Available Endpoints:")
    print("  GET  /health      - Health check")
    print("  GET  /info        - AI information")
    print("  POST /join_game   - Join game")
    print("  POST /get_action  - Get AI action")
    print("  POST /leave_game  - Leave game")
    print("  GET  /games       - List active games")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug, threaded=True)


if __name__ == '__main__':
    main()