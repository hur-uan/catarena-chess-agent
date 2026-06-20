from flask import Flask, request, jsonify
import random
import argparse
from itertools import combinations

app = Flask(__name__)

# 牌面定义
SUITS = 'shdc'
RANKS = '23456789TJQKA'

class Card:
    def __init__(self, card_str):
        self.rank = card_str[0]
        self.suit = card_str[1]
        self.rank_value = RANKS.index(self.rank)
    
    def __str__(self):
        return f"{self.rank}{self.suit}"

def get_hand_strength(hole_cards, community_cards):
    """计算手牌强度，返回0-1之间的值"""
    if not hole_cards:
        return 0.0
    
    # 转换为Card对象
    hole = [Card(card) for card in hole_cards]
    community = [Card(card) for card in community_cards]
    
    # 计算最佳5张牌组合
    all_cards = hole + community
    if len(all_cards) < 5:
        return evaluate_preflop_hand(hole)
    
    best_hand_value = 0
    for combo in combinations(all_cards, 5):
        hand_value = evaluate_hand(list(combo))
        best_hand_value = max(best_hand_value, hand_value)
    
    return best_hand_value

def evaluate_preflop_hand(hole_cards):
    """评估翻牌前手牌强度"""
    if len(hole_cards) != 2:
        return 0.0
    
    card1, card2 = hole_cards
    rank1, rank2 = card1.rank_value, card2.rank_value
    
    # 同花
    suited = card1.suit == card2.suit
    
    # 对子
    if rank1 == rank2:
        pair_value = rank1
        # 对子强度：AA=0.95, KK=0.92, QQ=0.89, JJ=0.86, TT=0.83, 99=0.80, 88=0.77, 77=0.74, 66=0.71, 55=0.68, 44=0.65, 33=0.62, 22=0.59
        return 0.59 + (pair_value / 13.0) * 0.36
    
    # 高牌
    high_card = max(rank1, rank2)
    low_card = min(rank1, rank2)
    
    # 同花高牌强度
    if suited:
        # AKs=0.85, AQs=0.82, AJs=0.79, ATs=0.76, KQs=0.73, KJs=0.70, QJs=0.67, JTs=0.64, T9s=0.61, 98s=0.58, 87s=0.55, 76s=0.52, 65s=0.49, 54s=0.46
        if high_card == 12 and low_card == 11:  # AKs
            return 0.85
        elif high_card == 12 and low_card == 10:  # AQs
            return 0.82
        elif high_card == 12 and low_card == 9:   # AJs
            return 0.79
        elif high_card == 12 and low_card == 8:   # ATs
            return 0.76
        elif high_card == 11 and low_card == 10:  # KQs
            return 0.73
        elif high_card == 11 and low_card == 9:   # KJs
            return 0.70
        elif high_card == 10 and low_card == 9:   # QJs
            return 0.67
        elif high_card == 9 and low_card == 8:    # JTs
            return 0.64
        elif high_card == 8 and low_card == 7:    # T9s
            return 0.61
        elif high_card == 7 and low_card == 6:    # 98s
            return 0.58
        elif high_card == 6 and low_card == 5:    # 87s
            return 0.55
        elif high_card == 5 and low_card == 4:    # 76s
            return 0.52
        elif high_card == 4 and low_card == 3:    # 65s
            return 0.49
        elif high_card == 3 and low_card == 2:    # 54s
            return 0.46
        else:
            # 其他同花牌
            return 0.3 + (high_card / 13.0) * 0.15
    
    # 非同花高牌强度
    else:
        # AK=0.75, AQ=0.72, AJ=0.69, AT=0.66, KQ=0.63, KJ=0.60, QJ=0.57, JT=0.54, T9=0.51, 98=0.48, 87=0.45, 76=0.42, 65=0.39, 54=0.36
        if high_card == 12 and low_card == 11:  # AK
            return 0.75
        elif high_card == 12 and low_card == 10:  # AQ
            return 0.72
        elif high_card == 12 and low_card == 9:   # AJ
            return 0.69
        elif high_card == 12 and low_card == 8:   # AT
            return 0.66
        elif high_card == 11 and low_card == 10:  # KQ
            return 0.63
        elif high_card == 11 and low_card == 9:   # KJ
            return 0.60
        elif high_card == 10 and low_card == 9:   # QJ
            return 0.57
        elif high_card == 9 and low_card == 8:    # JT
            return 0.54
        elif high_card == 8 and low_card == 7:    # T9
            return 0.51
        elif high_card == 7 and low_card == 6:    # 98
            return 0.48
        elif high_card == 6 and low_card == 5:    # 87
            return 0.45
        elif high_card == 5 and low_card == 4:    # 76
            return 0.42
        elif high_card == 4 and low_card == 3:    # 65
            return 0.39
        elif high_card == 3 and low_card == 2:    # 54
            return 0.36
        else:
            # 其他非同花牌
            return 0.2 + (high_card / 13.0) * 0.15

def evaluate_hand(cards):
    """评估5张牌的手牌强度，返回0-1之间的值"""
    if len(cards) != 5:
        return 0.0
    
    ranks = [card.rank_value for card in cards]
    suits = [card.suit for card in cards]
    
    # 统计牌面
    rank_counts = {}
    for rank in ranks:
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
    
    counts = sorted(rank_counts.values(), reverse=True)
    unique_ranks = sorted(rank_counts.keys(), reverse=True)
    
    # 同花
    is_flush = len(set(suits)) == 1
    
    # 顺子
    is_straight = False
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            is_straight = True
        # A-2-3-4-5顺子
        elif unique_ranks == [12, 3, 2, 1, 0]:
            is_straight = True
    
    # 手牌类型评估
    if is_straight and is_flush:
        if unique_ranks[0] == 12 and unique_ranks[1] == 11:  # 皇家同花顺
            return 1.0
        else:  # 同花顺
            return 0.95
    elif counts[0] == 4:  # 四条
        return 0.9
    elif counts[0] == 3 and counts[1] == 2:  # 葫芦
        return 0.85
    elif is_flush:  # 同花
        return 0.8
    elif is_straight:  # 顺子
        return 0.75
    elif counts[0] == 3:  # 三条
        return 0.7
    elif counts[0] == 2 and counts[1] == 2:  # 两对
        return 0.65
    elif counts[0] == 2:  # 一对
        return 0.6
    else:  # 高牌
        return 0.5

def get_position_factor(player_id, players, dealer_index):
    """计算位置因子"""
    player_list = list(players.keys())
    if player_id not in player_list:
        return 1.0
    
    player_index = player_list.index(player_id)
    dealer_pos = player_list.index(dealer_index) if dealer_index in player_list else 0
    
    # 计算相对位置
    relative_pos = (player_index - dealer_pos) % len(player_list)
    position_ratio = relative_pos / len(player_list)
    
    # 位置因子：按钮位=1.2，后位=1.1，中位=1.0，前位=0.9，盲注位=0.8
    if position_ratio < 0.2:  # 盲注位
        return 0.8
    elif position_ratio < 0.4:  # 前位
        return 0.9
    elif position_ratio < 0.6:  # 中位
        return 1.0
    elif position_ratio < 0.8:  # 后位
        return 1.1
    else:  # 按钮位
        return 1.2

def calculate_pot_odds(current_bet, pot_size, player_chips):
    """计算底池赔率"""
    if current_bet == 0:
        return float('inf')
    
    call_amount = min(current_bet, player_chips)
    if call_amount == 0:
        return 0
    
    return pot_size / call_amount

def get_aggression_factor(hand_strength, position_factor, pot_odds, phase):
    """计算激进因子"""
    base_aggression = hand_strength * position_factor
    
    # 根据游戏阶段调整
    if phase == 'preflop':
        base_aggression *= 1.1  # 翻牌前更激进
    elif phase == 'flop':
        base_aggression *= 1.0
    elif phase == 'turn':
        base_aggression *= 0.9  # 转牌更保守
    elif phase == 'river':
        base_aggression *= 0.8  # 河牌最保守
    
    # 根据底池赔率调整
    if pot_odds > 4:  # 很好的底池赔率
        base_aggression *= 1.2
    elif pot_odds > 2:  # 不错的底池赔率
        base_aggression *= 1.1
    elif pot_odds < 1:  # 差的底池赔率
        base_aggression *= 0.8
    
    return min(base_aggression, 1.5)  # 限制最大激进因子

@app.route('/action', methods=['POST'])
def get_action():
    game_state = request.get_json()
    
    valid_actions = game_state.get('valid_actions', [])
    if not valid_actions:
        return jsonify({"action": "fold"})
    
    # 获取游戏状态信息
    players = game_state.get('players', {})
    current_player = game_state.get('current_player')
    phase = game_state.get('phase', 'preflop')
    pot = game_state.get('pot', 0)
    current_bet = game_state.get('current_bet', 0)
    community_cards = game_state.get('community_cards', [])
    dealer_index = game_state.get('dealer_index', 0)
    
    if not current_player or current_player not in players:
        return jsonify(valid_actions[0])
    
    player_info = players[current_player]
    hole_cards = player_info.get('hole_cards', [])
    player_chips = player_info.get('chips', 0)
    
    # 计算手牌强度
    hand_strength = get_hand_strength(hole_cards, community_cards)
    
    # 计算位置因子
    position_factor = get_position_factor(current_player, players, dealer_index)
    
    # 计算底池赔率
    pot_odds = calculate_pot_odds(current_bet, pot, player_chips)
    
    # 计算激进因子
    aggression_factor = get_aggression_factor(hand_strength, position_factor, pot_odds, phase)
    
    # 决策逻辑
    call_action = next((a for a in valid_actions if a['action'] == 'call'), None)
    check_action = next((a for a in valid_actions if a['action'] == 'check'), None)
    raise_action = next((a for a in valid_actions if a['action'] == 'raise'), None)
    fold_action = next((a for a in valid_actions if a['action'] == 'fold'), None)
    all_in_action = next((a for a in valid_actions if a['action'] == 'all_in'), None)
    
    # 根据激进因子和手牌强度做决策
    decision_threshold = 0.5
    
    # 超强牌（手牌强度 > 0.8）
    if hand_strength > 0.8:
        if raise_action and aggression_factor > 0.7:
            min_raise = raise_action['amount']['min']
            max_raise = raise_action['amount']['max']
            # 根据手牌强度决定加注大小
            if hand_strength > 0.9:
                raise_amount = int(min_raise + (max_raise - min_raise) * 0.8)
            else:
                raise_amount = int(min_raise + (max_raise - min_raise) * 0.5)
            return jsonify({"action": "raise", "amount": raise_amount})
        elif call_action:
            return jsonify(call_action)
        elif check_action:
            return jsonify(check_action)
    
    # 强牌（手牌强度 > 0.6）
    elif hand_strength > 0.6:
        if raise_action and aggression_factor > 0.6:
            min_raise = raise_action['amount']['min']
            raise_amount = int(min_raise + (raise_action['amount']['max'] - min_raise) * 0.3)
            return jsonify({"action": "raise", "amount": raise_amount})
        elif call_action:
            return jsonify(call_action)
        elif check_action:
            return jsonify(check_action)
    
    # 中等牌（手牌强度 > 0.4）
    elif hand_strength > 0.4:
        # 根据底池赔率决定
        if pot_odds > 3 and call_action:
            return jsonify(call_action)
        elif check_action:
            return jsonify(check_action)
        elif call_action and aggression_factor > 0.5:
            return jsonify(call_action)
    
    # 弱牌（手牌强度 <= 0.4）
    else:
        # 只有在很好的底池赔率或位置优势时才跟注
        if pot_odds > 5 and call_action:
            return jsonify(call_action)
        elif check_action:
            return jsonify(check_action)
    
    # 默认弃牌
    if fold_action:
        return jsonify(fold_action)
    else:
        return jsonify(valid_actions[0])

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Strong Baseline AI HTTP Server")
    parser.add_argument('--port', type=int, default=51012, help='Port to listen on')
    args = parser.parse_args()
    
    app.run(host='0.0.0.0', port=args.port)
