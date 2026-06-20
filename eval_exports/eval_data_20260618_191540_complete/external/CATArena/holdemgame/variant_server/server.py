import random
import logging
from flask import Flask, request, jsonify
from werkzeug.serving import run_simple
import uuid
import argparse
import datetime

# --- Logging Setup ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Card and Deck Logic ---
SUITS = 'shdc'
RANKS = '6789TJQKA'

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def __str__(self):
        return f"{self.rank}{self.suit}"

    def __repr__(self):
        return self.__str__()

    def to_dict(self):
        return str(self)

class Deck:
    def __init__(self):
        self.cards = [Card(rank, suit) for rank in RANKS for suit in SUITS]
        self.shuffle()

    def shuffle(self):
        random.shuffle(self.cards)

    def deal(self):
        if not self.cards:
            raise ValueError("Deck is empty")
        return self.cards.pop()

# --- Hand Evaluation ---
def get_hand_value(hand):
    if not hand:
        return 0, []
    
    ranks = ''.join(sorted([card.rank for card in hand], key=lambda r: RANKS.index(r), reverse=True))
    suits = {card.suit for card in hand}
    
    is_flush = len(suits) == 1
    
    is_straight = False
    unique_ranks = sorted(list(set(ranks)), key=lambda r: RANKS.index(r))
    is_special_straight = False
    if len(unique_ranks) >= 5:
        # Check for standard straights
        for i in range(len(unique_ranks) - 4):
            if RANKS.index(unique_ranks[i+4]) - RANKS.index(unique_ranks[i]) == 4:
                is_straight = True
                break
        # Ace-low straight (A-6-7-8-9)
        if not is_straight and {'A', '6', '7', '8', '9'}.issubset(set(r.rank for r in hand)):
            ranks = '9876A' + ''.join(r for r in ranks if r not in '9876A')
            is_straight = True
            is_special_straight = True


    rank_counts = {rank: ranks.count(rank) for rank in set(ranks)}
    counts = sorted(rank_counts.values(), reverse=True)
    
    
    # Tie-breaking by ordering ranks based on their counts
    sorted_ranks_by_freq = sorted(rank_counts.keys(), key=lambda r: (rank_counts[r], RANKS.index(r)), reverse=True)
    
    if is_special_straight:
        # In A-6-7-8-9, 'A' is the lowest card. Move it to the end for tie-breaking.
        if 'A' in sorted_ranks_by_freq:
            sorted_ranks_by_freq.remove('A')
            sorted_ranks_by_freq.append('A')

    
    if is_straight and is_flush:
        if set('TJQKA').issubset(set(ranks)):
            return 9, sorted_ranks_by_freq  # Royal Flush
        return 8, sorted_ranks_by_freq      # Straight Flush
    if counts[0] == 4:
        return 7, sorted_ranks_by_freq      # Four of a Kind
    if is_flush:
        return 6, sorted_ranks_by_freq      # Flush
    if counts[0] == 3 and counts[1] >= 2:
        return 5, sorted_ranks_by_freq      # Full House
    if is_straight:
        return 4, sorted_ranks_by_freq      # Straight
    if counts[0] == 3:
        return 3, sorted_ranks_by_freq      # Three of a Kind
    if counts[0] == 2 and counts[1] == 2:
        return 2, sorted_ranks_by_freq      # Two Pair
    if counts[0] == 2:
        return 1, sorted_ranks_by_freq      # One Pair
    return 0, sorted_ranks_by_freq          # High Card


def get_best_hand(hole_cards, community_cards):
    all_cards = hole_cards + community_cards
    if len(all_cards) < 5:
        return 0, [], []

    best_hand_value = (-1, [])
    best_hand_cards = []

    from itertools import combinations
    for combo in combinations(all_cards, 5):
        hand_value = get_hand_value(list(combo))
        if hand_value > best_hand_value:
            best_hand_value = hand_value
            best_hand_cards = list(combo)
            
    return best_hand_value[0], best_hand_value[1], best_hand_cards

# --- Player and Game Logic ---
class Player:
    def __init__(self, player_id, name, chips):
        self.player_id = player_id
        self.name = name
        self.chips = chips
        self.hole_cards = []
        self.state = 'waiting'  # waiting, active, folded, all_in, out
        self.current_bet = 0 # Bet in the current street
        self.hand_bet = 0 # Total bet in the current hand
        self.is_dealer = False
        self.is_small_blind = False
        self.is_big_blind = False
        self.has_acted_in_current_state = False

    def to_dict(self, show_cards=False):
        return {
            "player_id": self.player_id,
            "name": self.name,
            "chips": self.chips,
            "hole_cards": [card.to_dict() for card in self.hole_cards] if show_cards else [],
            "state": self.state,
            "current_bet": self.current_bet,
            "hand_bet": self.hand_bet,
            "is_dealer": self.is_dealer,
            "is_small_blind": self.is_small_blind,
            "is_big_blind": self.is_big_blind,
        }

class Game:
    def __init__(self, game_id, small_blind, big_blind, max_players):
        self.game_id = game_id
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.max_players = max_players
        self.players = {}
        self.phase = 'pending'  # pending, preflop, flop, turn, river, showdown, finished
        self.hand_number = 0
        self.pot = 0 # Total pot for display
        self.pots = [] # List of pots: [{'amount': X, 'eligible_players': [p_id]}]
        self.community_cards = []
        self.current_bet = 0 # Highest bet in the current street
        self.min_raise = self.big_blind
        self.dealer_index = -1
        self.current_player_index = -1
        self.action_history = []
        self.full_history = []
        self.deck = Deck()
        self.active_players = []
        self.last_raiser = None

    def add_player(self, player_id, name, chips):
        if len(self.players) >= self.max_players:
            return False, "Game is full"
        if player_id in self.players:
            return False, "Player ID already exists"
        self.players[player_id] = Player(player_id, name, chips)
        logging.info(f"Player {name} ({player_id}) added to game {self.game_id}")
        return True, "Player added"

    def start_game(self):
        if len(self.players) < 2:
            return False, "Not enough players to start"
        if self.phase != 'pending':
            return False, "Game already started"
        
        self.hand_number = 1
        self.dealer_index = random.randint(0, len(self.players) - 1)
        self._start_hand()
        logging.info(f"Game {self.game_id} started with {len(self.players)} players.")
        return True, "Game started"

    def _start_hand(self):
        players_with_chips = [p for p in self.players.values() if p.chips > 0]
        if len(players_with_chips) <= 1:
            self.phase = 'finished'
            winner = players_with_chips[0] if players_with_chips else None
            logging.info(f"Game {self.game_id} is finished. Winner is {winner.name if winner else 'nobody'}.")
            return

        self.deck = Deck()
        self.pot = 0
        self.pots = []
        self.community_cards = []
        self.action_history = []

        current_hand_history = {
            "hand_number": self.hand_number,
            "players": {},
            "actions": [],
            "community_cards": {},
            "result": {}
        }

        for player in self.players.values():
            player.hole_cards = []
            player.state = 'active' if player.chips > 0 else 'out'
            player.current_bet = 0
            player.hand_bet = 0
            player.is_dealer = False
            player.is_small_blind = False
            player.is_big_blind = False
            player.has_acted_in_current_state = False

        self.active_players = [p for p in self.players.values() if p.state != 'out']
        
        self.dealer_index = (self.dealer_index + 1) % len(self.active_players)
        sb_index = (self.dealer_index + 1) % len(self.active_players)
        bb_index = (self.dealer_index + 2) % len(self.active_players)

        self.active_players[self.dealer_index].is_dealer = True
        
        sb_player = self.active_players[sb_index]
        sb_player.is_small_blind = True
        sb_amount = min(self.small_blind, sb_player.chips)
        self._force_bet(sb_player, sb_amount, "small_blind")

        bb_player = self.active_players[bb_index]
        bb_player.is_big_blind = True
        bb_amount = min(self.big_blind, bb_player.chips)
        self._force_bet(bb_player, bb_amount, "big_blind")

        self.current_bet = self.big_blind
        self.min_raise = self.big_blind

        for player in self.active_players:
            player.hole_cards = [self.deck.deal(), self.deck.deal()]
            current_hand_history["players"][player.player_id] = {
                "name": player.name,
                "initial_chips": player.chips + player.hand_bet,
                "hole_cards": [str(c) for c in player.hole_cards]
            }

        self.full_history.append(current_hand_history)

        self.current_player_index = (bb_index + 1) % len(self.active_players)
        self.last_raiser = bb_player
        self.phase = 'preflop'
        logging.info(f"Hand #{self.hand_number} started. Dealer: {self.active_players[self.dealer_index].name}")

    def _force_bet(self, player, amount, blind_type):
        actual_bet_amount = min(amount, player.chips) # <--- 新行
        player.chips -= actual_bet_amount
        player.current_bet = actual_bet_amount
        player.hand_bet = actual_bet_amount
        self.pot += actual_bet_amount
        if player.chips == 0:
            player.state = 'all_in'
        player.has_acted_in_current_state = False
        action_record = {"player_id": player.player_id, "action": blind_type, "amount": actual_bet_amount, "phase": "preflop"}
        self.action_history.append(action_record)
        self.full_history.append({"actions": [action_record]})


    def get_state(self, player_id=None):
        players_state = {}
        for p_id, p in self.players.items():
            show_cards = (p_id == player_id) or (self.phase == 'showdown')
            players_state[p_id] = p.to_dict(show_cards=show_cards)

        current_player_id = self.active_players[self.current_player_index].player_id if self.current_player_index != -1 and self.phase not in ['finished', 'showdown'] else None

        return {
            "game_id": self.game_id,
            "phase": self.phase,
            "hand_number": self.hand_number,
            "pot": self.pot,
            "community_cards": [card.to_dict() for card in self.community_cards],
            "current_bet": self.current_bet,
            "min_raise": self.min_raise,
            "current_player": current_player_id,
            "players": players_state,
            "action_history": self.action_history,
            "dealer_index": self.dealer_index,
            "small_blind": self.small_blind,
            "big_blind": self.big_blind,
        }

    def get_valid_actions(self, player_id):
        if self.phase in ['pending', 'showdown', 'finished']:
            return []
            
        player = self.players.get(player_id)
        if not player or self.current_player_index == -1 or player.player_id != self.active_players[self.current_player_index].player_id:
            return []

        actions = []
        can_check = player.current_bet == self.current_bet
        
        actions.append({"action": "fold", "amount": 0})
        if can_check:
            actions.append({"action": "check", "amount": 0})
        else:
            call_amount = min(self.current_bet - player.current_bet, player.chips)
            actions.append({"action": "call", "amount": call_amount})

        if player.chips > (self.current_bet - player.current_bet):
            min_raise_amount = self.current_bet + self.min_raise
            max_raise_amount = player.chips + player.current_bet
            actions.append({"action": "raise", "amount": {"min": min_raise_amount, "max": max_raise_amount}})

        actions.append({"action": "all_in", "amount": player.chips})
        return actions

    def _get_next_active_player_index(self):
        for i in range(1, len(self.active_players) + 1):
            next_index = (self.current_player_index + i) % len(self.active_players)
            player = self.active_players[next_index]
            if player.state == 'active':
                return next_index
        return -1

    def _all_players_acted(self):
        active_in_hand = [p for p in self.active_players if p.state != 'folded']
        active_not_allin = [p for p in active_in_hand if p.state != 'all_in']

        if not active_not_allin:
            return True


        all_acted = all(p.has_acted_in_current_state for p in active_not_allin)
        
        # Everyone has acted if their current bet is the same, or they are all-in
        bet_levels = {p.current_bet for p in active_not_allin}
        if  all_acted and all(p.current_bet == self.current_bet for p in active_not_allin):
            return True
        return False
        
        
        

    def _end_betting_round(self):
        for p in self.active_players:
            p.current_bet = 0
            p.has_acted_in_current_state = False
        
        self.current_bet = 0
        self.min_raise = self.big_blind
        
        first_to_act_index = -1
        for i in range(1, len(self.active_players) + 1):
            idx = (self.dealer_index + i) % len(self.active_players)
            if self.active_players[idx].state == 'active':
                first_to_act_index = idx
                break
        
        self.current_player_index = first_to_act_index
        self.last_raiser = None


    def _process_showdown(self):
        self.phase = 'showdown'
        logging.info(f"--- Showdown for Hand #{self.hand_number} ---")

        contenders = [p for p in self.active_players if p.state != 'folded']
        if not contenders:
            return

        if len(contenders) == 1:
            winner = contenders[0]
            winner.chips += self.pot
            logging.info(f"{winner.name} wins {self.pot} chips.")
            win_event = {"event": "win", "player_id": winner.player_id, "amount": self.pot}
            self.action_history.append(win_event)
            if self.full_history: self.full_history[-1]['result'] = {"winners": [win_event]}
            self.pot = 0
            return

        self._calculate_pots()

        best_hands = {}
        for player in contenders:
            hand_rank, ranks, best_5_cards = get_best_hand(player.hole_cards, self.community_cards)
            best_hands[player.player_id] = (hand_rank, ranks, best_5_cards, player)
            logging.info(f"{player.name} has {[str(c) for c in best_5_cards]} (Rank: {hand_rank}) with tie-breaker ranks: {ranks}")

        all_win_events = []
        for i, pot in enumerate(self.pots):
            pot_amount = pot['amount']
            eligible_players_ids = pot['eligible_players']
            
            if pot_amount == 0:
                continue

            logging.info(f"Awarding Pot #{i+1} ({pot_amount}) to eligible players: {eligible_players_ids}")

            pot_contenders = {p_id: best_hands[p_id] for p_id in eligible_players_ids if p_id in best_hands}
            if not pot_contenders:
                continue

            sorted_pot_players = sorted(pot_contenders.values(), key=lambda x: (x[0], x[1]), reverse=True)
            best_hand_val = (sorted_pot_players[0][0], sorted_pot_players[0][1])
            winners = [p for p in sorted_pot_players if (p[0], p[1]) == best_hand_val]

            win_amount_per_winner = pot_amount / len(winners)
            winner_names = [w[3].name for w in winners]
            logging.info(f"Pot #{i+1} winners: {winner_names} win {win_amount_per_winner:.2f} each.")

            for winner_data in winners:
                winner_player = winner_data[3]
                winner_player.chips += win_amount_per_winner
                win_event = {
                    "event": "win", 
                    "player_id": winner_player.player_id, 
                    "name": winner_player.name,
                    "amount": win_amount_per_winner, 
                    "pot_index": i,
                    "hand": [str(c) for c in winner_data[2]]
                }
                all_win_events.append(win_event)

        self.action_history.extend(all_win_events)
        if self.full_history: self.full_history[-1]['result'] = {"winners": all_win_events}
        self.pot = 0
        self.pots = []

    def _calculate_pots(self):
        self.pots = []
        # contenders = [p for p in self.active_players if p.state != 'folded']
        
        # investments = {p.player_id: p.hand_bet for p in contenders}
        all_contributors = [p for p in self.players.values() if p.hand_bet > 0]
        investments = {p.player_id: p.hand_bet for p in all_contributors}
        
        if not investments:
            return

        sorted_investment_levels = sorted(list(set(investments.values())))
        
        last_level = 0
        for level in sorted_investment_levels:
            if level == 0:
                continue
            
            pot_amount = 0
            eligible_players = []
            
            contribution_per_player = level - last_level
            
            for p_id, investment in investments.items():
                if investment >= level:
                    pot_amount += contribution_per_player
                    if p_id not in eligible_players:
                        eligible_players.append(p_id)

            if pot_amount > 0:
                self.pots.append({'amount': pot_amount, 'eligible_players': eligible_players})
            
            last_level = level

    def _advance_phase(self):
        self._end_betting_round()
        
        active_in_hand = [p for p in self.active_players if p.state != 'folded']
        non_all_in_players = [p for p in active_in_hand if p.state != 'all_in']
        
        if len(active_in_hand) > 1 and len(non_all_in_players) < 2:
            # All remaining players are all-in or there's one active player left, deal all cards
            while self.phase != 'river':
                if self.phase == 'preflop': self.phase = 'flop'; self._deal_community_card(3)
                elif self.phase == 'flop': self.phase = 'turn'; self._deal_community_card(1)
                elif self.phase == 'turn': self.phase = 'river'; self._deal_community_card(1)
            self._process_showdown()
            return

        if self.phase == 'preflop':
            self.phase = 'flop'
            self._deal_community_card(3)
        elif self.phase == 'flop':
            self.phase = 'turn'
            self._deal_community_card(1)
        elif self.phase == 'turn':
            self.phase = 'river'
            self._deal_community_card(1)
        elif self.phase == 'river':
            self._process_showdown()

    def _deal_community_card(self, count=1):
        new_cards = [self.deck.deal() for _ in range(count)]
        self.community_cards.extend(new_cards)
        logging.info(f"--- {self.phase.capitalize()} --- Community cards: {[str(c) for c in self.community_cards]}")
        if self.full_history:
            if self.phase == 'flop':
                self.full_history[-1]['community_cards']['flop'] = [str(c) for c in new_cards]
            else:
                self.full_history[-1]['community_cards'][self.phase] = str(new_cards[0])


    def perform_action(self, player_id, action, amount=0):
        if not isinstance(amount, int):
            return False, "Bet amount must be an integer"
        player = self.players.get(player_id)
        if not player or self.current_player_index == -1 or player.player_id != self.active_players[self.current_player_index].player_id:
            return False, "Not your turn"

        valid_actions = self.get_valid_actions(player_id)
        action_names = [a['action'] for a in valid_actions]

        if action not in action_names:
            return False, f"Invalid action: {action}"

        action_record = {"player_id": player_id, "action": action, "amount": amount, "phase": self.phase}
        
        if action == 'fold':
            player.state = 'folded'
        elif action == 'check':
            player.has_acted_in_current_state = True
            pass
        elif action == 'call':
            call_amount = min(self.current_bet - player.current_bet, player.chips)
            player.chips -= call_amount
            player.current_bet += call_amount
            player.hand_bet += call_amount
            self.pot += call_amount
            action_record['amount'] = call_amount
            player.has_acted_in_current_state = True
            if player.chips == 0:
                player.state = 'all_in'
        elif action == 'raise':
            total_bet_for_street = amount
            raise_amount = total_bet_for_street - self.current_bet
            amount_to_pot = total_bet_for_street - player.current_bet

            if amount_to_pot > player.chips:
                return False, "Not enough chips to raise"
            if raise_amount < self.min_raise and (player.chips > amount_to_pot):
                 return False, f"Raise must be at least {self.min_raise} more than the current bet"

            player.chips -= amount_to_pot
            player.current_bet = total_bet_for_street
            player.hand_bet += amount_to_pot
            self.pot += amount_to_pot
            player.has_acted_in_current_state = True
            self.min_raise = raise_amount
            self.current_bet = total_bet_for_street
            self.last_raiser = player
            if player.chips == 0:
                player.state = 'all_in'
        elif action == 'all_in':
            amount_all_in = player.chips
            if player.current_bet + amount_all_in > self.current_bet:
                self.last_raiser = player
                self.min_raise = player.current_bet + amount_all_in - self.current_bet
                self.current_bet = player.current_bet + amount_all_in
            player.has_acted_in_current_state = True
            player.hand_bet += amount_all_in
            self.pot += amount_all_in
            player.current_bet += amount_all_in
            player.chips = 0
            player.state = 'all_in'
            action_record['amount'] = amount_all_in


        if self.full_history: self.full_history[-1]['actions'].append(action_record)
        self.action_history.append(action_record)
        logging.info(f"Player {player.name} action: {action} {amount}")

        active_players_not_folded = [p for p in self.active_players if p.state != 'folded']
        if len(active_players_not_folded) == 1:
            winner = active_players_not_folded[0]
            winner.chips += self.pot
            logging.info(f"{winner.name} wins {self.pot} as others folded.")
            win_event = {"event": "win", "player_id": winner.player_id, "amount": self.pot}
            self.action_history.append(win_event)
            if self.full_history: self.full_history[-1]['result'] = {"winners": [win_event]}
            self.phase = 'showdown'
            return True, "Action successful"

        self.current_player_index = self._get_next_active_player_index()

        if self.current_player_index == -1 or self._all_players_acted():
            self._advance_phase()

        return True, "Action successful"

    def next_hand(self):
        if self.phase == 'finished':
            return False, "Game is already finished."
        if self.phase != 'showdown':
            return False, "Current hand is not finished"
        
        self.hand_number += 1
        self._start_hand()
        return True, "Next hand started"

    def update_blinds(self, small_blind, big_blind):
        self.small_blind = small_blind
        self.big_blind = big_blind
        logging.info(f"Game {self.game_id} blinds updated to {small_blind}/{big_blind}")
        return True, "Blinds updated"

# --- Flask App ---
app = Flask(__name__)
games = {}

@app.route('/games', methods=['POST'])
def create_game():
    data = request.get_json()
    game_id = f"holdem_{uuid.uuid4().hex[:6]}"
    small_blind = data.get('small_blind', 5)
    big_blind = data.get('big_blind', 10)
    max_players = data.get('max_players', 10)
    
    games[game_id] = Game(game_id, small_blind, big_blind, max_players)
    logging.info(f"New game created: {game_id}")
    
    return jsonify({
        "game_id": game_id,
        "small_blind": small_blind,
        "big_blind": big_blind,
        "max_players": max_players
    }), 201

@app.route('/games/<game_id>/players', methods=['POST'])
def add_player_to_game(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404
    
    data = request.get_json()
    player_id = data.get('player_id')
    name = data.get('name')
    chips = data.get('chips', 1000)

    success, message = game.add_player(player_id, name, chips)
    if not success:
        return jsonify({"error": message}), 400
        
    return jsonify({
        "status": "player_added",
        "player_id": player_id,
        "name": name,
        "chips": chips
    }), 200

@app.route('/games/<game_id>/start', methods=['POST'])
def start_game_endpoint(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404

    success, message = game.start_game()
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({
        "status": "game_started",
        "game_id": game_id,
        "hand_number": game.hand_number
    }), 200

@app.route('/games/<game_id>/state', methods=['GET'])
def get_game_state(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404
    
    player_id = request.args.get('player_id')
    return jsonify(game.get_state(player_id)), 200

@app.route('/games/<game_id>/actions', methods=['GET'])
def get_player_actions(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404
        
    player_id = request.args.get('player_id')
    if not player_id:
        return jsonify({"error": "player_id is required"}), 400

    return jsonify({"valid_actions": game.get_valid_actions(player_id)}), 200

@app.route('/games/<game_id>/action', methods=['POST'])
def perform_player_action(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404

    data = request.get_json()
    player_id = data.get('player_id')
    action = data.get('action')
    amount = data.get('amount', 0)

    success, message = game.perform_action(player_id, action, amount)
    if not success:
        return jsonify({"error": message}), 400
        
    return jsonify({"status": "action_successful", "message": message}), 200

@app.route('/games/<game_id>/next_hand', methods=['POST'])
def next_hand_endpoint(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404

    success, message = game.next_hand()
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"status": "next_hand_started", "hand_number": game.hand_number}), 200

@app.route('/games/<game_id>/history', methods=['GET'])
def get_game_history(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404
        
    return jsonify({
        "action_history": game.action_history,
        "hand_number": game.hand_number
    }), 200

@app.route('/games/<game_id>/full_history', methods=['GET'])
def get_full_game_history(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404
        
    return jsonify(game.full_history), 200

@app.route('/games/<game_id>/blinds', methods=['POST'])
def update_game_blinds(game_id):
    game = games.get(game_id)
    if not game:
        return jsonify({"error": "Game not found"}), 404
    
    data = request.get_json()
    small_blind = data.get('small_blind')
    big_blind = data.get('big_blind')

    if small_blind is None or big_blind is None:
        return jsonify({"error": "small_blind and big_blind are required"}), 400

    success, message = game.update_blinds(small_blind, big_blind)
    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"status": "blinds_updated", "message": message}), 200


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "active_games": len(games),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }), 200

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Texas Hold'em HTTP Server")
    parser.add_argument('--port', type=int, default=30000, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()

    run_simple('0.0.0.0', args.port, app, use_reloader=args.debug, use_debugger=args.debug)
