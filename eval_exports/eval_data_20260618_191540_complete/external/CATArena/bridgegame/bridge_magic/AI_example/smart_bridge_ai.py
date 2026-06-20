#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
智能桥牌AI服务
包含策略性叫牌、卡牌交换和打牌逻辑
"""

import requests
import json
import time
import random
import argparse
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from typing import List, Tuple, Optional, Dict, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("smart_bridge_ai.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("SmartBridgeAI")

app = Flask(__name__)


class SmartBridgeAI:
    """智能桥牌AI - 包含高级策略"""

    def __init__(self, ai_id: str, ai_name: str = None, game_server_url: str = "http://localhost:9031"):
        self.ai_id = ai_id
        self.ai_name = ai_name or "Smart Bridge AI"
        self.game_server_url = game_server_url
        self.active_games = {}  # game_id -> game_info
        logger.info(f"AI初始化: {self.ai_id} - {self.ai_name}")

    def join_game(self, game_id: str, player_id: int, player_name: str):
        """加入游戏"""
        if game_id not in self.active_games:
            self.active_games[game_id] = {
                "player_id": player_id,
                "game_id": game_id,
                "joined_at": datetime.now(),
                "position": None,
                "partner_id": None,
                "bidding_history": [],
                "playing_history": [],
                "exchange_history": []
            }
        logger.info(f"AI {self.ai_id} 加入游戏 {game_id}, 玩家ID: {player_id}, 玩家名: {player_name}")
        return True

    def leave_game(self, game_id: str):
        """离开游戏"""
        if game_id in self.active_games:
            del self.active_games[game_id]
            logger.info(f"AI {self.ai_id} 离开游戏 {game_id}")

    def get_action(self, game_id: str, player_id: int, position: str, 
                   game_state: dict, legal_actions: List[dict]) -> Tuple[Optional[dict], str]:
        """获取AI动作"""
        phase = game_state.get('phase', 'unknown')
        
        # 更新游戏信息
        if game_id in self.active_games:
            if self.active_games[game_id].get('position') is None:
                self.active_games[game_id]['position'] = position
                # 设置搭档ID
                positions = ['N', 'E', 'S', 'W']
                pos_idx = positions.index(position)
                partner_pos_idx = (pos_idx + 2) % 4
                partner_position = positions[partner_pos_idx]
                
                for player in game_state.get('players', []):
                    if player.get('position') == partner_position:
                        self.active_games[game_id]['partner_id'] = player.get('player_id')
                        break
        
        # 找到我的玩家信息
        my_player_info = None
        for player in game_state.get('players', []):
            if player.get('player_id') == player_id:
                my_player_info = player
                break
        
        if not my_player_info:
            logger.warning(f"无法找到玩家信息 player_id={player_id}")
            return (random.choice(legal_actions) if legal_actions else None, "随机选择")
        
        # 根据阶段选择动作
        if phase == 'bidding':
            action = self.make_bid(game_state, player_id, legal_actions)
            reasoning = "基于手牌评估的策略性叫牌"
        elif phase == 'exchanging':
            action = self.request_exchange(game_state, player_id, legal_actions)
            reasoning = "策略性卡牌交换以优化搭档配合"
        elif phase == 'playing':
            action = self.play_card(game_state, player_id, legal_actions)
            reasoning = "基于墩数分析的策略性出牌"
        else:
            logger.warning(f"未知游戏阶段: {phase}")
            action = random.choice(legal_actions) if legal_actions else None
            reasoning = "随机动作（未知阶段）"
        
        # 更新历史
        if game_id in self.active_games and action:
            if phase == 'bidding':
                self.active_games[game_id]['bidding_history'].append(action)
            elif phase == 'playing':
                self.active_games[game_id]['playing_history'].append(action)
            elif phase == 'exchanging':
                self.active_games[game_id]['exchange_history'].append(action)
        
        return action, reasoning

    def find_my_hand(self, game_state: dict, player_id: int) -> List[dict]:
        """找到我的手牌"""
        players = game_state.get('players', [])
        for p in players:
            if p.get('player_id') == player_id:
                return p.get('hand', [])
        return []

    def calculate_hand_strength(self, hand: List[dict]) -> Dict[str, Any]:
        """计算手牌强度"""
        if not hand:
            return {
                "hcp": 0,
                "distribution_points": 0,
                "total_points": 0,
                "suit_lengths": {"S": 0, "H": 0, "D": 0, "C": 0},
                "suit_strengths": {"S": 0, "H": 0, "D": 0, "C": 0},
                "balanced": False,
                "longest_suit": None,
                "strongest_suit": None
            }
        
        # 大牌点
        hcp_values = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}
        hcp = sum(hcp_values.get(card.get('rank'), 0) for card in hand)
        
        # 花色长度和强度
        suit_lengths = {"S": 0, "H": 0, "D": 0, "C": 0}
        suit_strengths = {"S": 0, "H": 0, "D": 0, "C": 0}
        
        for card in hand:
            suit = card.get('suit')
            rank = card.get('rank')
            if suit in suit_lengths:
                suit_lengths[suit] += 1
                suit_strengths[suit] += hcp_values.get(rank, 0)
        
        # 牌型点
        distribution_points = 0
        for suit, length in suit_lengths.items():
            if length == 0:  # 缺门
                distribution_points += 3
            elif length == 1:  # 单张
                distribution_points += 2
            elif length == 2:  # 双张
                distribution_points += 1
        
        # 判断是否平衡牌型
        sorted_lengths = sorted(suit_lengths.values(), reverse=True)
        balanced = (
            sorted_lengths == [4, 3, 3, 3] or
            sorted_lengths == [4, 4, 3, 2] or
            sorted_lengths == [5, 3, 3, 2]
        )
        
        # 找出最长和最强的花色
        longest_suit = max(suit_lengths.items(), key=lambda x: x[1])[0] if hand else None
        strongest_suit = max(suit_strengths.items(), key=lambda x: x[1])[0] if hand else None
        
        total_points = hcp + distribution_points
        
        return {
            "hcp": hcp,
            "distribution_points": distribution_points,
            "total_points": total_points,
            "suit_lengths": suit_lengths,
            "suit_strengths": suit_strengths,
            "balanced": balanced,
            "longest_suit": longest_suit,
            "strongest_suit": strongest_suit
        }

    def make_bid(self, game_state: dict, player_id: int, legal_actions: List[dict]) -> Optional[dict]:
        """做出策略性叫牌"""
        if not legal_actions:
            logger.warning("没有合法叫牌动作")
            return None
        
        # 获取我的手牌并评估
        my_hand = self.find_my_hand(game_state, player_id)
        hand_analysis = self.calculate_hand_strength(my_hand)
        
        # 获取叫牌历史
        bidding = game_state.get('bidding', {})
        calls = bidding.get('calls', [])
        
        # 获取搭档ID
        partner_id = None
        for player in game_state.get('players', []):
            if player.get('player_id') != player_id:
                my_pos = None
                other_pos = player.get('position')
                for p in game_state.get('players', []):
                    if p.get('player_id') == player_id:
                        my_pos = p.get('position')
                        break
                
                if my_pos and other_pos:
                    positions = ['N', 'E', 'S', 'W']
                    if abs(positions.index(my_pos) - positions.index(other_pos)) == 2:
                        partner_id = player.get('player_id')
                        break
        
        # 获取搭档最后的叫牌
        partner_last_bid = None
        if partner_id:
            for call in reversed(calls):
                if call.get('player_id') == partner_id and call.get('call_type') == 'bid':
                    partner_last_bid = call
                    break
        
        # 检查是否是开叫
        is_opening = len(calls) == 0 or all(call.get('call_type') == 'pass' for call in calls)
        
        # 找到各种动作
        pass_action = next((a for a in legal_actions if a.get('call_type') == 'pass'), None)
        double_action = next((a for a in legal_actions if a.get('call_type') == 'double'), None)
        bid_actions = [a for a in legal_actions if a.get('call_type') == 'bid']
        
        # 按级别和花色排序
        suit_rank = {'C': 1, 'D': 2, 'H': 3, 'S': 4, 'NT': 5}
        bid_actions.sort(key=lambda x: (x.get('level', 0), suit_rank.get(x.get('suit', 'C'), 0)))
        
        # ============ 开叫策略 ============
        if is_opening:
            if hand_analysis['hcp'] >= 12:
                # 平衡牌型开叫1NT (15-17点)
                if (hand_analysis['balanced'] and 
                    15 <= hand_analysis['hcp'] <= 17):
                    nt_bid = next((b for b in bid_actions 
                                 if b.get('level') == 1 and b.get('suit') == 'NT'), None)
                    if nt_bid:
                        logger.info(f"开叫1NT，平衡牌型，{hand_analysis['hcp']}点")
                        return nt_bid
                
                # 5张以上高花开叫
                for suit in ['S', 'H']:
                    if hand_analysis['suit_lengths'][suit] >= 5:
                        suit_bid = next((b for b in bid_actions 
                                       if b.get('level') == 1 and b.get('suit') == suit), None)
                        if suit_bid:
                            logger.info(f"开叫1{suit}，{hand_analysis['suit_lengths'][suit]}张")
                            return suit_bid
                
                # 低花开叫（选择较长的）
                if hand_analysis['suit_lengths']['D'] >= hand_analysis['suit_lengths']['C']:
                    diamond_bid = next((b for b in bid_actions 
                                      if b.get('level') == 1 and b.get('suit') == 'D'), None)
                    if diamond_bid:
                        logger.info(f"开叫1D，{hand_analysis['suit_lengths']['D']}张")
                        return diamond_bid
                else:
                    club_bid = next((b for b in bid_actions 
                                   if b.get('level') == 1 and b.get('suit') == 'C'), None)
                    if club_bid:
                        logger.info(f"开叫1C，{hand_analysis['suit_lengths']['C']}张")
                        return club_bid
            
            logger.info(f"Pass，{hand_analysis['hcp']}点不足以开叫")
            return pass_action
        
        # ============ 应叫策略 ============
        elif partner_last_bid:
            partner_suit = partner_last_bid.get('suit')
            partner_level = partner_last_bid.get('level')
            
            # 支持搭档的高花（3张以上，6点以上）
            if partner_suit in ['H', 'S'] and hand_analysis['suit_lengths'][partner_suit] >= 3:
                if 6 <= hand_analysis['hcp'] <= 9 and partner_level == 1:
                    raise_bid = next((b for b in bid_actions 
                                    if b.get('level') == 2 and b.get('suit') == partner_suit), None)
                    if raise_bid:
                        logger.info(f"支持搭档{partner_suit}到2阶，{hand_analysis['hcp']}点")
                        return raise_bid
                
                elif 10 <= hand_analysis['hcp'] <= 12 and partner_level == 1:
                    raise_bid = next((b for b in bid_actions 
                                    if b.get('level') == 3 and b.get('suit') == partner_suit), None)
                    if raise_bid:
                        logger.info(f"支持搭档{partner_suit}到3阶，{hand_analysis['hcp']}点")
                        return raise_bid
                
                elif hand_analysis['hcp'] >= 13:
                    game_bid = next((b for b in bid_actions 
                                   if b.get('level') == 4 and b.get('suit') == partner_suit), None)
                    if game_bid:
                        logger.info(f"叫成局{partner_suit}，{hand_analysis['hcp']}点")
                        return game_bid
            
            # 平衡牌型应叫NT
            if hand_analysis['balanced']:
                if 6 <= hand_analysis['hcp'] <= 9:
                    nt_bid = next((b for b in bid_actions 
                                 if b.get('level') == 1 and b.get('suit') == 'NT'), None)
                    if nt_bid:
                        logger.info(f"应叫1NT，平衡，{hand_analysis['hcp']}点")
                        return nt_bid
                
                elif 10 <= hand_analysis['hcp'] <= 12:
                    nt_bid = next((b for b in bid_actions 
                                 if b.get('level') == 2 and b.get('suit') == 'NT'), None)
                    if nt_bid:
                        logger.info(f"应叫2NT，平衡，{hand_analysis['hcp']}点")
                        return nt_bid
                
                elif 13 <= hand_analysis['hcp'] <= 15:
                    nt_bid = next((b for b in bid_actions 
                                 if b.get('level') == 3 and b.get('suit') == 'NT'), None)
                    if nt_bid:
                        logger.info(f"应叫3NT成局，{hand_analysis['hcp']}点")
                        return nt_bid
            
            # 新花色应叫
            if 6 <= hand_analysis['hcp'] <= 9:
                for suit in ['S', 'H', 'D', 'C']:
                    if hand_analysis['suit_lengths'][suit] >= 4:
                        suit_bid = next((b for b in bid_actions 
                                       if b.get('level') == 1 and b.get('suit') == suit), None)
                        if suit_bid:
                            logger.info(f"应叫1{suit}，{hand_analysis['suit_lengths'][suit]}张，{hand_analysis['hcp']}点")
                            return suit_bid
        
        # ============ 竞争性叫牌 ============
        # 对对手加倍
        if double_action and hand_analysis['hcp'] >= 13:
            logger.info(f"加倍对手，{hand_analysis['hcp']}点")
            return double_action
        
        # ============ 默认策略 ============
        # 10点以上尝试叫牌
        if hand_analysis['hcp'] >= 10 and bid_actions:
            # 叫最长最强的花色
            best_suit = hand_analysis['strongest_suit']
            suit_bid = next((b for b in bid_actions if b.get('suit') == best_suit), None)
            if suit_bid:
                logger.info(f"叫{suit_bid.get('level')}{best_suit}，{hand_analysis['hcp']}点")
                return suit_bid
            
            # 否则叫最低的
            logger.info(f"叫最低牌阶，{hand_analysis['hcp']}点")
            return bid_actions[0]
        
        # 点数不足，Pass
        logger.info(f"Pass，{hand_analysis['hcp']}点")
        return pass_action

    def request_exchange(self, game_state: dict, player_id: int, legal_actions: List[dict]) -> Optional[dict]:
        """请求卡牌交换"""
        my_hand = self.find_my_hand(game_state, player_id)
        if not my_hand:
            logger.warning("没有手牌无法交换")
            return None
        
        # 获取合约信息
        bidding = game_state.get('bidding', {})
        contract = bidding.get('contract', {})
        contract_suit = contract.get('suit') if contract else None
        declarer_id = contract.get('declarer_id') if contract else None
        
        # 判断我是否是庄家方
        my_position = None
        for player in game_state.get('players', []):
            if player.get('player_id') == player_id:
                my_position = player.get('position')
                break
        
        is_declaring_side = False
        if declarer_id is not None:
            declarer_pos = None
            for player in game_state.get('players', []):
                if player.get('player_id') == declarer_id:
                    declarer_pos = player.get('position')
                    break
            
            if my_position and declarer_pos:
                positions = ['N', 'E', 'S', 'W']
                my_idx = positions.index(my_position)
                decl_idx = positions.index(declarer_pos)
                is_declaring_side = abs(my_idx - decl_idx) == 0 or abs(my_idx - decl_idx) == 2
        
        # 分析手牌
        hand_analysis = self.calculate_hand_strength(my_hand)
        rank_values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, 
                      '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        
        # ============ 策略1：有将合约 ============
        if contract_suit and contract_suit != 'NT':
            # 如果是庄家方
            if is_declaring_side:
                # 交换边花的单张或双张
                for suit in ['S', 'H', 'D', 'C']:
                    if suit != contract_suit:
                        if hand_analysis['suit_lengths'][suit] == 1:
                            # 交换单张
                            card = next((c for c in my_hand if c.get('suit') == suit), None)
                            if card:
                                card_str = f"{card['rank']}{card['suit']}"
                                logger.info(f"交换边花单张 {card_str}")
                                return {"type": "exchange", "card": card_str}
                        
                        elif hand_analysis['suit_lengths'][suit] == 2:
                            # 交换双张中的小牌
                            suit_cards = [c for c in my_hand if c.get('suit') == suit]
                            small_card = min(suit_cards, 
                                           key=lambda c: rank_values.get(c.get('rank'), 0))
                            card_str = f"{small_card['rank']}{small_card['suit']}"
                            logger.info(f"交换边花双张小牌 {card_str}")
                            return {"type": "exchange", "card": card_str}
                
                # 如果没有短门，交换将牌中的小牌（如果将牌多于5张）
                if hand_analysis['suit_lengths'][contract_suit] > 5:
                    trump_cards = [c for c in my_hand if c.get('suit') == contract_suit]
                    small_trump = min(trump_cards, 
                                    key=lambda c: rank_values.get(c.get('rank'), 0))
                    card_str = f"{small_trump['rank']}{small_trump['suit']}"
                    logger.info(f"交换多余将牌 {card_str}")
                    return {"type": "exchange", "card": card_str}
            
            # 如果是防守方
            else:
                # 交换最弱花色的大牌给搭档增强攻击力
                weakest_suit = min(hand_analysis['suit_lengths'].items(), 
                                 key=lambda x: (x[1], hand_analysis['suit_strengths'][x[0]]))[0]
                weakest_cards = [c for c in my_hand if c.get('suit') == weakest_suit]
                
                if weakest_cards:
                    # 交换最弱花色中的最大牌
                    best_card = max(weakest_cards, 
                                  key=lambda c: rank_values.get(c.get('rank'), 0))
                    card_str = f"{best_card['rank']}{best_card['suit']}"
                    logger.info(f"防守方交换弱花色大牌 {card_str} 增强搭档")
                    return {"type": "exchange", "card": card_str}
        
        # ============ 策略2：无将合约 ============
        elif contract_suit == 'NT':
            # 交换最弱花色的小牌
            weakest_suit = min(hand_analysis['suit_lengths'].items(), 
                             key=lambda x: (x[1], hand_analysis['suit_strengths'][x[0]]))[0]
            weakest_cards = [c for c in my_hand if c.get('suit') == weakest_suit]
            
            if weakest_cards:
                small_card = min(weakest_cards, 
                               key=lambda c: rank_values.get(c.get('rank'), 0))
                card_str = f"{small_card['rank']}{small_card['suit']}"
                logger.info(f"无将合约交换最弱花色小牌 {card_str}")
                return {"type": "exchange", "card": card_str}
        
        # ============ 默认策略 ============
        # 交换最小的牌
        smallest_card = min(my_hand, key=lambda c: rank_values.get(c.get('rank'), 0))
        card_str = f"{smallest_card['rank']}{smallest_card['suit']}"
        logger.info(f"默认策略：交换最小牌 {card_str}")
        return {"type": "exchange", "card": card_str}

    def play_card(self, game_state: dict, player_id: int, legal_actions: List[dict]) -> Optional[dict]:
        """打出一张牌"""
        if not legal_actions:
            logger.warning("没有合法出牌动作")
            return None
        
        # 获取合约信息
        bidding = game_state.get('bidding', {})
        contract = bidding.get('contract', {})
        contract_suit = contract.get('suit') if contract else None
        declarer_id = contract.get('declarer_id') if contract else None
        
        # 判断角色
        is_declarer = (player_id == declarer_id)
        
        # 获取当前墩
        current_trick = game_state.get('current_trick', [])
        
        # 获取我的手牌
        my_hand = self.find_my_hand(game_state, player_id)
        
        # 解析合法出牌
        legal_cards = []
        for action in legal_actions:
            if action.get('type') == 'play':
                card_str = action.get('card', '')
                if len(card_str) == 2:
                    rank, suit = card_str[0], card_str[1]
                    legal_cards.append({'rank': rank, 'suit': suit, 'card_str': card_str})
        
        rank_values = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
                      '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        
        # ============ 首攻 ============
        if not current_trick:
            if contract_suit == 'NT':
                # 无将首攻：攻最长花色
                suit_lengths = {}
                for card in legal_cards:
                    suit = card['suit']
                    suit_lengths[suit] = suit_lengths.get(suit, 0) + 1
                
                longest_suit = max(suit_lengths.items(), key=lambda x: x[1])[0]
                suit_cards = [c for c in legal_cards if c['suit'] == longest_suit]
                
                # 四大第四
                if len(suit_cards) >= 4:
                    suit_cards.sort(key=lambda c: rank_values.get(c['rank'], 0))
                    card_to_play = suit_cards[-4]
                    logger.info(f"无将首攻第四大 {card_to_play['card_str']}")
                    return {"type": "play", "card": card_to_play['card_str']}
                else:
                    card_to_play = max(suit_cards, key=lambda c: rank_values.get(c['rank'], 0))
                    logger.info(f"无将首攻最大 {card_to_play['card_str']}")
                    return {"type": "play", "card": card_to_play['card_str']}
            
            else:
                # 有将合约
                if is_declarer:
                    # 庄家：抽将
                    trump_cards = [c for c in legal_cards if c['suit'] == contract_suit]
                    if trump_cards:
                        card_to_play = max(trump_cards, key=lambda c: rank_values.get(c['rank'], 0))
                        logger.info(f"庄家抽将 {card_to_play['card_str']}")
                        return {"type": "play", "card": card_to_play['card_str']}
                else:
                    # 防守方：攻单张或短花色
                    suit_counts = {}
                    for card in my_hand:
                        suit = card.get('suit')
                        suit_counts[suit] = suit_counts.get(suit, 0) + 1
                    
                    # 找单张
                    singletons = [s for s, c in suit_counts.items() if c == 1]
                    if singletons:
                        singleton_cards = [c for c in legal_cards if c['suit'] in singletons]
                        if singleton_cards:
                            logger.info(f"防守首攻单张 {singleton_cards[0]['card_str']}")
                            return {"type": "play", "card": singleton_cards[0]['card_str']}
                    
                    # 攻短花色
                    short_suits = sorted(suit_counts.items(), key=lambda x: x[1])
                    for suit, _ in short_suits:
                        suit_cards = [c for c in legal_cards if c['suit'] == suit]
                        if suit_cards:
                            card_to_play = max(suit_cards, key=lambda c: rank_values.get(c['rank'], 0))
                            logger.info(f"防守首攻短花 {card_to_play['card_str']}")
                            return {"type": "play", "card": card_to_play['card_str']}
        
        # ============ 跟牌 ============
        else:
            led_card = current_trick[0][1]
            led_suit = led_card[1] if len(led_card) == 2 else None
            
            # 能跟出首攻花色
            following_cards = [c for c in legal_cards if c['suit'] == led_suit]
            
            if following_cards:
                # 判断当前赢牌者
                winning_card = current_trick[0][1]
                winning_player = current_trick[0][0]
                
                for play in current_trick[1:]:
                    play_card = play[1]
                    play_player = play[0]
                    play_suit = play_card[1] if len(play_card) == 2 else None
                    play_rank = play_card[0] if len(play_card) == 2 else None
                    
                    winning_suit = winning_card[1] if len(winning_card) == 2 else None
                    winning_rank = winning_card[0] if len(winning_card) == 2 else None
                    
                    # 将牌最大
                    if contract_suit and play_suit == contract_suit and winning_suit != contract_suit:
                        winning_card = play_card
                        winning_player = play_player
                    # 同花色比大小
                    elif play_suit == winning_suit:
                        if rank_values.get(play_rank, 0) > rank_values.get(winning_rank, 0):
                            winning_card = play_card
                            winning_player = play_player
                
                # 搭档赢，出小牌
                partner_id = None
                if player_id in self.active_games.get(game_state.get('game_id'), {}):
                    partner_id = self.active_games[game_state.get('game_id')].get('partner_id')
                
                if winning_player == partner_id:
                    card_to_play = min(following_cards, key=lambda c: rank_values.get(c['rank'], 0))
                    logger.info(f"搭档赢，出小牌 {card_to_play['card_str']}")
                    return {"type": "play", "card": card_to_play['card_str']}
                
                # 尝试赢牌
                winning_rank_value = rank_values.get(winning_card[0], 0) if len(winning_card) == 2 else 0
                winning_cards = [c for c in following_cards 
                               if rank_values.get(c['rank'], 0) > winning_rank_value]
                
                if winning_cards:
                    card_to_play = min(winning_cards, key=lambda c: rank_values.get(c['rank'], 0))
                    logger.info(f"出最小赢牌 {card_to_play['card_str']}")
                    return {"type": "play", "card": card_to_play['card_str']}
                
                # 赢不了，出小牌
                card_to_play = min(following_cards, key=lambda c: rank_values.get(c['rank'], 0))
                logger.info(f"赢不了，出小牌 {card_to_play['card_str']}")
                return {"type": "play", "card": card_to_play['card_str']}
            
            else:
                # 不能跟牌
                # 有将牌考虑将吃
                if contract_suit and contract_suit != 'NT':
                    trump_cards = [c for c in legal_cards if c['suit'] == contract_suit]
                    if trump_cards:
                        card_to_play = min(trump_cards, key=lambda c: rank_values.get(c['rank'], 0))
                        logger.info(f"将吃 {card_to_play['card_str']}")
                        return {"type": "play", "card": card_to_play['card_str']}
                
                # 垫牌：垫最短花色的小牌
                suit_counts = {}
                for card in my_hand:
                    suit = card.get('suit')
                    suit_counts[suit] = suit_counts.get(suit, 0) + 1
                
                sorted_suits = sorted(suit_counts.items(), key=lambda x: x[1])
                for suit, _ in sorted_suits:
                    suit_cards = [c for c in legal_cards if c['suit'] == suit]
                    if suit_cards:
                        card_to_play = min(suit_cards, key=lambda c: rank_values.get(c['rank'], 0))
                        logger.info(f"垫短花小牌 {card_to_play['card_str']}")
                        return {"type": "play", "card": card_to_play['card_str']}
        
        # 默认：出第一张
        logger.info(f"默认出第一张 {legal_actions[0].get('card')}")
        return legal_actions[0]


# Flask应用
ai = None


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    if ai:
        return jsonify({
            "status": "healthy",
            "ai_id": ai.ai_id,
            "active_games": len(ai.active_games)
        })
    else:
        return jsonify({"status": "unhealthy", "reason": "AI未初始化"}), 500


@app.route('/info', methods=['GET'])
def info():
    """获取AI信息"""
    if ai:
        return jsonify({
            "ai_id": ai.ai_id,
            "name": ai.ai_name,
            "version": "1.0",
            "description": "智能桥牌AI，包含高级叫牌、卡牌交换和打牌策略",
            "capabilities": [
                "标准叫牌系统",
                "策略性卡牌交换",
                "高级打牌策略",
                "搭档协作",
                "防守信号"
            ]
        })
    else:
        return jsonify({"error": "AI未初始化"}), 500


@app.route('/join_game', methods=['POST'])
def join_game():
    """加入游戏"""
    if not ai:
        return jsonify({"error": "AI未初始化"}), 500
    
    data = request.get_json()
    game_id = data.get('game_id')
    player_id = data.get('player_id')
    player_name = data.get('player_name')

    if game_id is None or player_id is None or player_name is None:
        return jsonify({"error": "缺少game_id、player_id或player_name"}), 400

    if ai.join_game(game_id, player_id, player_name):
        return jsonify({
            "status": "joined",
            "ai_id": ai.ai_id,
            "game_id": game_id,
            "player_id": player_id
        })
    else:
        return jsonify({"error": "加入游戏失败"}), 500


@app.route('/get_action', methods=['POST'])
def get_action():
    """获取AI动作"""
    if not ai:
        return jsonify({"error": "AI未初始化"}), 500
    
    data = request.get_json()
    game_id = data.get('game_id')
    player_id = data.get('player_id')
    position = data.get('position')
    game_state = data.get('game_state')
    legal_actions = data.get('legal_actions')

    if not all([game_id, player_id is not None, position, game_state, legal_actions is not None]):
        return jsonify({"error": "缺少必要字段"}), 400

    action, reasoning = ai.get_action(game_id, player_id, position, game_state, legal_actions)
    
    if action:
        return jsonify({
            "action": action,
            "ai_id": ai.ai_id,
            "game_id": game_id,
            "reasoning": reasoning
        })
    else:
        return jsonify({"error": "无法确定动作"}), 400


@app.route('/leave_game', methods=['POST'])
def leave_game():
    """离开游戏"""
    if not ai:
        return jsonify({"error": "AI未初始化"}), 500
    
    data = request.get_json()
    game_id = data.get('game_id')
    if not game_id:
        return jsonify({"error": "缺少game_id"}), 400
    
    ai.leave_game(game_id)
    return jsonify({
        "status": "left",
        "ai_id": ai.ai_id,
        "game_id": game_id
    })


def run(port=50006):
    """主函数"""
    parser = argparse.ArgumentParser(description='智能桥牌AI HTTP服务')
    parser.add_argument('--port', type=int, default=port, help='监听端口')
    parser.add_argument('--ai_id', type=str, default='smart_bridge_ai', help='AI ID')
    parser.add_argument('--ai_name', type=str, default='Smart Bridge AI', help='AI名称')
    args = parser.parse_args()

    global ai
    ai = SmartBridgeAI(ai_id=args.ai_id, ai_name=args.ai_name)
    
    logger.info(f"启动 {ai.ai_name} (ID: {ai.ai_id}) 端口 {args.port}...")
    app.run(host='0.0.0.0', port=args.port)


if __name__ == '__main__':
    run()

