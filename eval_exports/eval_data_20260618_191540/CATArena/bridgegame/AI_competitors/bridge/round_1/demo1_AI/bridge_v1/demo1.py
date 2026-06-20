#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import random
import argparse
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Tuple, Optional, Dict, Set
from collections import defaultdict

app = Flask(__name__)

class AdvancedBridgeAI:
    """Advanced Bridge AI with strategic bidding and playing"""
    
    def __init__(self, ai_id: str, ai_name: str = None, game_server_url: str = "http://localhost:9030"):
        self.ai_id = ai_id
        self.ai_name = ai_name or f"demo1 AI {ai_id}"
        self.game_server_url = game_server_url
        self.active_games = {}  # game_id -> game_info
        
        # Card values for high card points
        self.hcp_values = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}
        self.rank_order = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, 
                          '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        self.suit_order = {'C': 0, 'D': 1, 'H': 2, 'S': 3, 'NT': 4}
    
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
                    "joined_at": datetime.now()
                }
                print(f"AI {self.ai_id} joined game {game_id}, player ID: {player_id}")
                return True
            else:
                print(f"AI {self.ai_id} failed to join game: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"AI {self.ai_id} join game exception: {e}")
            return False
    
    def leave_game(self, game_id: str):
        """Leave a game"""
        if game_id in self.active_games:
            del self.active_games[game_id]
            print(f"AI {self.ai_id} left game {game_id}")
    
    def get_action(self, game_id: str, game_state: dict) -> Optional[dict]:
        """Get AI action"""
        if game_id not in self.active_games:
            print(f"AI {self.ai_id} not in game {game_id}")
            return None
        
        my_player_id = self.active_games[game_id]["player_id"]
        phase = game_state.get('phase', 'unknown')
        
        if phase == 'bidding':
            return self.make_bid(game_state, my_player_id)
        elif phase == 'playing':
            current_player_id = game_state.get('current_player_id', my_player_id)
            return self.play_card(game_state, current_player_id)
        else:
            print(f"Unknown game phase: {phase}")
            return None
    
    def calculate_hand_strength(self, hand: List[dict]) -> dict:
        """Calculate comprehensive hand strength"""
        if not hand:
            return {"hcp": 0, "distribution": [0, 0, 0, 0], "total_points": 0}
        
        # Count high card points
        hcp = 0
        suit_counts = {'C': 0, 'D': 0, 'H': 0, 'S': 0}
        suit_honors = {'C': [], 'D': [], 'H': [], 'S': []}
        
        for card in hand:
            suit = card.get('suit', 'C')
            rank = card.get('rank', '2')
            
            suit_counts[suit] += 1
            if rank in self.hcp_values:
                hcp += self.hcp_values[rank]
                suit_honors[suit].append(rank)
        
        # Calculate distribution points
        distribution = [suit_counts['C'], suit_counts['D'], suit_counts['H'], suit_counts['S']]
        dist_points = 0
        
        for count in distribution:
            if count == 0:  # Void
                dist_points += 3
            elif count == 1:  # Singleton
                dist_points += 2
            elif count == 2:  # Doubleton
                dist_points += 1
        
        # Adjust for honor concentration
        honor_adjustment = 0
        for suit, honors in suit_honors.items():
            if suit_counts[suit] <= 2 and len(honors) >= 2:
                honor_adjustment -= 1  # Penalty for honors in short suits
        
        total_points = hcp + dist_points + honor_adjustment
        
        return {
            "hcp": hcp,
            "distribution": distribution,
            "dist_points": dist_points,
            "total_points": total_points,
            "suit_counts": suit_counts,
            "suit_honors": suit_honors
        }
    
    def find_longest_suits(self, hand_analysis: dict) -> List[str]:
        """Find the longest suits in order"""
        suit_counts = hand_analysis["suit_counts"]
        suits_by_length = sorted(suit_counts.items(), key=lambda x: (-x[1], -self.suit_order[x[0]]))
        return [suit for suit, count in suits_by_length if count >= 4]
    
    def evaluate_bid_level(self, hand_analysis: dict, partner_bid: Optional[dict] = None) -> int:
        """Determine appropriate bid level"""
        total_points = hand_analysis["total_points"]
        
        if partner_bid:
            # Partner has bid, adjust expectations
            if total_points >= 6:  # Support with 6+ points
                if total_points >= 10:
                    return 2  # Game try
                else:
                    return 1  # Simple support
        else:
            # Opening bid evaluation
            if total_points >= 22:
                return 2  # Strong opening
            elif total_points >= 13:
                return 1  # Standard opening
        
        return 0  # Pass
    
    def make_bid(self, game_state: dict, player_id: int) -> Optional[dict]:
        """Make a strategic bid"""
        try:
            legal_actions = self.get_legal_actions(game_state, player_id)
            if not legal_actions:
                return None
            
            # Get hand information
            my_hand = self.find_my_hand(game_state, player_id)
            if not my_hand:
                return self.safe_pass(legal_actions)
            
            hand_analysis = self.calculate_hand_strength(my_hand)
            bidding = game_state.get('bidding', {})
            calls = bidding.get('calls', [])
            
            # Analyze bidding history
            partner_calls = []
            opponent_calls = []
            my_position = player_id
            
            for i, call in enumerate(calls):
                caller_pos = (bidding.get('dealer_id', 0) + i) % 4
                if (caller_pos - my_position) % 2 == 0:  # Partner
                    partner_calls.append(call)
                else:  # Opponent
                    opponent_calls.append(call)
            
            # Strategic bidding logic
            if len(calls) == 0 or all(call.get('call_type') == 'pass' for call in calls[-3:]):
                # Opening position or after passes
                return self.make_opening_bid(hand_analysis, legal_actions)
            else:
                # Responding or competitive bidding
                return self.make_response_bid(hand_analysis, calls, legal_actions, partner_calls, opponent_calls)
                
        except Exception as e:
            print(f"AI {self.ai_id} bidding error: {e}")
            return self.safe_pass(legal_actions)
    
    def make_opening_bid(self, hand_analysis: dict, legal_actions: List[dict]) -> Optional[dict]:
        """Make opening bid"""
        total_points = hand_analysis["total_points"]
        
        if total_points < 13:
            return self.safe_pass(legal_actions)
        
        # Find best suit to bid
        longest_suits = self.find_longest_suits(hand_analysis)
        
        if longest_suits:
            # Bid longest suit
            suit = longest_suits[0]
            level = 1
            
            # Look for the bid
            for action in legal_actions:
                if (action.get('call_type') == 'bid' and 
                    action.get('level') == level and 
                    action.get('suit') == suit):
                    print(f"AI {self.ai_id} opening {level}{suit} with {total_points} points")
                    return action
        
        # Try 1NT with balanced hand
        if (12 <= hand_analysis["hcp"] <= 14 and 
            self.is_balanced_hand(hand_analysis["distribution"])):
            for action in legal_actions:
                if (action.get('call_type') == 'bid' and 
                    action.get('level') == 1 and 
                    action.get('suit') == 'NT'):
                    print(f"AI {self.ai_id} opening 1NT with {hand_analysis['hcp']} HCP")
                    return action
        
        # Try any 1-level bid
        for suit in ['C', 'D', 'H', 'S']:
            for action in legal_actions:
                if (action.get('call_type') == 'bid' and 
                    action.get('level') == 1 and 
                    action.get('suit') == suit):
                    print(f"AI {self.ai_id} opening 1{suit} with {total_points} points")
                    return action
        
        return self.safe_pass(legal_actions)
    
    def make_response_bid(self, hand_analysis: dict, calls: List[dict], legal_actions: List[dict], 
                         partner_calls: List[dict], opponent_calls: List[dict]) -> Optional[dict]:
        """Make response bid"""
        total_points = hand_analysis["total_points"]
        
        # If partner has bid, consider support
        if partner_calls and partner_calls[-1].get('call_type') == 'bid':
            partner_suit = partner_calls[-1].get('suit')
            partner_level = partner_calls[-1].get('level', 1)
            
            if partner_suit and partner_suit != 'NT':
                suit_support = hand_analysis["suit_counts"].get(partner_suit, 0)
                
                # Support partner with 3+ cards and 6+ points
                if suit_support >= 3 and total_points >= 6:
                    support_level = partner_level + (1 if total_points >= 10 else 0)
                    
                    for action in legal_actions:
                        if (action.get('call_type') == 'bid' and 
                            action.get('level') == support_level and 
                            action.get('suit') == partner_suit):
                            print(f"AI {self.ai_id} supporting partner's {partner_suit} with {total_points} points")
                            return action
        
        # Competitive bidding - be more conservative
        if opponent_calls and any(call.get('call_type') == 'bid' for call in opponent_calls):
            if total_points < 8:
                return self.safe_pass(legal_actions)
        
        # Try to bid our longest suit if we have enough points
        if total_points >= 8:
            longest_suits = self.find_longest_suits(hand_analysis)
            if longest_suits:
                suit = longest_suits[0]
                
                # Find minimum legal bid in our suit
                for level in [1, 2, 3]:
                    for action in legal_actions:
                        if (action.get('call_type') == 'bid' and 
                            action.get('level') == level and 
                            action.get('suit') == suit):
                            print(f"AI {self.ai_id} bidding {level}{suit} with {total_points} points")
                            return action
        
        return self.safe_pass(legal_actions)
    
    def is_balanced_hand(self, distribution: List[int]) -> bool:
        """Check if hand is balanced (suitable for NT)"""
        sorted_dist = sorted(distribution, reverse=True)
        return sorted_dist in [[4,3,3,3], [4,4,3,2], [5,3,3,2]]
    
    def safe_pass(self, legal_actions: List[dict]) -> Optional[dict]:
        """Safely pass"""
        for action in legal_actions:
            if action.get('call_type') == 'pass':
                return action
        return legal_actions[0] if legal_actions else None
    
    def play_card(self, game_state: dict, player_id: int) -> Optional[dict]:
        """Play a card strategically"""
        try:
            legal_actions = self.get_legal_actions(game_state, player_id)
            if not legal_actions:
                return None
            
            my_hand = self.find_my_hand(game_state, player_id)
            if not my_hand:
                return legal_actions[0] if legal_actions else None
            
            current_trick = game_state.get('current_trick', [])
            contract = game_state.get('bidding', {}).get('contract')
            trump_suit = contract.get('suit') if contract and contract.get('suit') != 'NT' else None
            
            # Determine our partnership
            my_partnership = player_id % 2
            tricks_won = game_state.get('tricks_won', [0, 0])
            
            if not current_trick:
                # Leading
                return self.lead_card(my_hand, legal_actions, trump_suit, game_state)
            else:
                # Following
                return self.follow_card(my_hand, legal_actions, current_trick, trump_suit, my_partnership, game_state)
                
        except Exception as e:
            print(f"AI {self.ai_id} playing error: {e}")
            return legal_actions[0] if legal_actions else None
    
    def lead_card(self, my_hand: List[dict], legal_actions: List[dict], trump_suit: Optional[str], game_state: dict) -> Optional[dict]:
        """Strategic opening lead"""
        # Prefer leading from longest suit
        hand_analysis = self.calculate_hand_strength(my_hand)
        suit_counts = hand_analysis["suit_counts"]
        
        # Find longest non-trump suit
        longest_suit = None
        max_length = 0
        
        for suit, count in suit_counts.items():
            if suit != trump_suit and count > max_length:
                max_length = count
                longest_suit = suit
        
        if longest_suit and max_length >= 4:
            # Lead from longest suit - prefer top of sequence or low
            suit_cards = [card for card in my_hand if card.get('suit') == longest_suit]
            suit_cards.sort(key=lambda c: self.rank_order[c.get('rank', '2')], reverse=True)
            
            # Lead top of sequence or fourth highest
            if len(suit_cards) >= 4:
                lead_card = suit_cards[3]  # Fourth highest
            else:
                lead_card = suit_cards[-1]  # Lowest
            
            card_str = f"{lead_card['rank']}{lead_card['suit']}"
            for action in legal_actions:
                if action.get('type') == 'play' and action.get('card') == card_str:
                    print(f"AI {self.ai_id} leading {card_str} from longest suit")
                    return action
        
        # Default: lead lowest card
        lowest_card = min(my_hand, key=lambda c: self.rank_order[c.get('rank', '2')])
        card_str = f"{lowest_card['rank']}{lowest_card['suit']}"
        
        for action in legal_actions:
            if action.get('type') == 'play' and action.get('card') == card_str:
                return action
        
        return legal_actions[0] if legal_actions else None
    
    def follow_card(self, my_hand: List[dict], legal_actions: List[dict], current_trick: List, 
                   trump_suit: Optional[str], my_partnership: int, game_state: dict) -> Optional[dict]:
        """Strategic card following"""
        if not current_trick:
            return legal_actions[0] if legal_actions else None
        
        led_card_str = current_trick[0][1]
        led_suit = led_card_str[-1]
        
        # Analyze trick situation
        winning_card = self.get_winning_card(current_trick, trump_suit)
        winning_player = winning_card[0] if winning_card else current_trick[0][0]
        partner_winning = (winning_player % 2) == my_partnership
        
        # Get cards I can play in led suit
        same_suit_cards = [card for card in my_hand if card.get('suit') == led_suit]
        
        if same_suit_cards:
            # Must follow suit
            if partner_winning:
                # Partner winning, play low
                lowest_card = min(same_suit_cards, key=lambda c: self.rank_order[c.get('rank', '2')])
                card_str = f"{lowest_card['rank']}{lowest_card['suit']}"
            else:
                # Try to win the trick
                if winning_card:
                    winning_rank = self.rank_order[winning_card[1][:-1]]
                    higher_cards = [card for card in same_suit_cards 
                                  if self.rank_order[card.get('rank', '2')] > winning_rank]
                    if higher_cards:
                        # Play lowest card that wins
                        best_card = min(higher_cards, key=lambda c: self.rank_order[c.get('rank', '2')])
                        card_str = f"{best_card['rank']}{best_card['suit']}"
                    else:
                        # Can't win, play low
                        lowest_card = min(same_suit_cards, key=lambda c: self.rank_order[c.get('rank', '2')])
                        card_str = f"{lowest_card['rank']}{lowest_card['suit']}"
                else:
                    # Play highest card
                    highest_card = max(same_suit_cards, key=lambda c: self.rank_order[c.get('rank', '2')])
                    card_str = f"{highest_card['rank']}{highest_card['suit']}"
        else:
            # Can't follow suit - discard or trump
            if trump_suit and not partner_winning:
                # Try to trump
                trump_cards = [card for card in my_hand if card.get('suit') == trump_suit]
                if trump_cards:
                    # Trump with lowest trump
                    lowest_trump = min(trump_cards, key=lambda c: self.rank_order[c.get('rank', '2')])
                    card_str = f"{lowest_trump['rank']}{lowest_trump['suit']}"
                else:
                    # Discard lowest card
                    lowest_card = min(my_hand, key=lambda c: self.rank_order[c.get('rank', '2')])
                    card_str = f"{lowest_card['rank']}{lowest_card['suit']}"
            else:
                # Discard lowest card
                lowest_card = min(my_hand, key=lambda c: self.rank_order[c.get('rank', '2')])
                card_str = f"{lowest_card['rank']}{lowest_card['suit']}"
        
        # Find and return the action
        for action in legal_actions:
            if action.get('type') == 'play' and action.get('card') == card_str:
                print(f"AI {self.ai_id} playing {card_str}")
                return action
        
        return legal_actions[0] if legal_actions else None
    
    def get_winning_card(self, current_trick: List, trump_suit: Optional[str]) -> Optional[Tuple[int, str]]:
        """Determine which card is currently winning the trick"""
        if not current_trick:
            return None
        
        led_suit = current_trick[0][1][-1]
        winning_card = current_trick[0]
        
        for player_id, card_str in current_trick:
            card_suit = card_str[-1]
            card_rank = card_str[:-1]
            
            current_winning_suit = winning_card[1][-1]
            current_winning_rank = winning_card[1][:-1]
            
            # Trump beats non-trump
            if trump_suit:
                if card_suit == trump_suit and current_winning_suit != trump_suit:
                    winning_card = (player_id, card_str)
                elif card_suit == trump_suit and current_winning_suit == trump_suit:
                    if self.rank_order[card_rank] > self.rank_order[current_winning_rank]:
                        winning_card = (player_id, card_str)
                elif card_suit == led_suit and current_winning_suit == led_suit:
                    if self.rank_order[card_rank] > self.rank_order[current_winning_rank]:
                        winning_card = (player_id, card_str)
            else:
                # No trump - highest card of led suit wins
                if card_suit == led_suit and current_winning_suit == led_suit:
                    if self.rank_order[card_rank] > self.rank_order[current_winning_rank]:
                        winning_card = (player_id, card_str)
        
        return winning_card
    
    def find_my_hand(self, game_state: dict, player_id: int) -> Optional[List[dict]]:
        """Find my hand"""
        players = game_state.get('players', [])
        if player_id < len(players):
            player_info = players[player_id]
            if isinstance(player_info, dict) and 'hand' in player_info:
                return player_info['hand']
        return None
    
    def get_legal_actions(self, game_state: dict, player_id: int) -> List[dict]:
        """Get legal actions"""
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


# Global AI instance
bridge_ai = None

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "healthy", "ai_id": bridge_ai.ai_id if bridge_ai else "unknown"})

@app.route('/info', methods=['GET'])
def info():
    """Get AI info"""
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
    """Join game"""
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
    """Get AI action"""
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
    """Leave game"""
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
    """List active games"""
    if not bridge_ai:
        return jsonify({"error": "AI not initialized"}), 500
    
    return jsonify({
        "active_games": list(bridge_ai.active_games.keys()),
        "game_count": len(bridge_ai.active_games)
    })


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Advanced Bridge AI HTTP Server')
    parser.add_argument('--port', type=int, default=50017, help='Server port')
    parser.add_argument('--ai_id', type=str, default='demo1', help='AI ID')
    parser.add_argument('--ai_name', type=str, help='AI name')
    parser.add_argument('--game_server', type=str, default='http://localhost:9030', help='Game server URL')
    parser.add_argument('--debug', action='store_true', help='Debug mode')
    
    args = parser.parse_args()
    
    global bridge_ai
    bridge_ai = AdvancedBridgeAI(
        ai_id=args.ai_id,
        ai_name=args.ai_name,
        game_server_url=args.game_server
    )
    
    print("=== demo1 Advanced Bridge AI HTTP Server ===")
    print(f"AI ID: {bridge_ai.ai_id}")
    print(f"AI Name: {bridge_ai.ai_name}")
    print(f"Port: {args.port}")
    print(f"Game Server: {bridge_ai.game_server_url}")
    print(f"Debug Mode: {args.debug}")
    print("Available endpoints:")
    print("  GET  /health      - Health check")
    print("  GET  /info        - AI info")
    print("  POST /join_game   - Join game")
    print("  POST /get_action  - Get action")
    print("  POST /leave_game  - Leave game")
    print("  GET  /games       - List games")
    
    app.run(host='0.0.0.0', port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()