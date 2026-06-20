#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import argparse
import random
import uuid
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===============================
# 卡牌类
# ===============================

class BridgeCard:
    """桥牌卡牌类"""
    
    # 花色定义
    SUITS = ['C', 'D', 'H', 'S']  # 梅花、方块、红心、黑桃
    SUIT_NAMES = {
        'C': 'Clubs',      # 梅花
        'D': 'Diamonds',   # 方块
        'H': 'Hearts',     # 红心
        'S': 'Spades'      # 黑桃
    }
    
    # 点数定义
    RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
    RANK_VALUES = {
        '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
        'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
    }
    
    def __init__(self, suit: str, rank: str):
        """初始化卡牌
        
        Args:
            suit: 花色 (C, D, H, S)
            rank: 点数 (2-9, T, J, Q, K, A)
        """
        if suit not in self.SUITS:
            raise ValueError(f"Invalid suit: {suit}")
        if rank not in self.RANKS:
            raise ValueError(f"Invalid rank: {rank}")
        
        self.suit = suit
        self.rank = rank
        self.suit_index = self.SUITS.index(suit)
        self.rank_index = self.RANKS.index(rank)
        self.card_id = 13 * self.suit_index + self.rank_index
        self.value = self.RANK_VALUES[rank]
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"{self.rank}{self.suit}"
    
    def __repr__(self) -> str:
        """表示"""
        return f"BridgeCard('{self.suit}', '{self.rank}')"
    
    def __eq__(self, other) -> bool:
        """相等比较"""
        if isinstance(other, BridgeCard):
            return self.suit == other.suit and self.rank == other.rank
        return False
    
    def __hash__(self) -> int:
        """哈希值"""
        return hash((self.suit, self.rank))
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "suit": self.suit,
            "rank": self.rank,
            "card_id": self.card_id,
            "value": self.value,
            "suit_name": self.SUIT_NAMES[self.suit]
        }
    
    @classmethod
    def from_card_id(cls, card_id: int) -> 'BridgeCard':
        """从卡牌ID创建卡牌"""
        if not 0 <= card_id < 52:
            raise ValueError(f"Invalid card_id: {card_id}")
        
        suit_index = card_id // 13
        rank_index = card_id % 13
        suit = cls.SUITS[suit_index]
        rank = cls.RANKS[rank_index]
        return cls(suit, rank)
    
    @classmethod
    def from_string(cls, card_str: str) -> 'BridgeCard':
        """从字符串创建卡牌 (如 "AS", "KH")"""
        if len(card_str) != 2:
            raise ValueError(f"Invalid card string: {card_str}")
        
        rank = card_str[0]
        suit = card_str[1]
        return cls(suit, rank)
    
    @classmethod
    def get_deck(cls) -> List['BridgeCard']:
        """获取完整的52张牌"""
        deck = []
        for suit in cls.SUITS:
            for rank in cls.RANKS:
                deck.append(cls(suit, rank))
        return deck
    
    @classmethod
    def get_suit_cards(cls, suit: str) -> List['BridgeCard']:
        """获取指定花色的所有牌"""
        if suit not in cls.SUITS:
            raise ValueError(f"Invalid suit: {suit}")
        
        return [cls(suit, rank) for rank in cls.RANKS]
    
    def is_higher_than(self, other: 'BridgeCard', trump_suit: Optional[str] = None) -> bool:
        """比较两张牌的大小
        
        Args:
            other: 另一张牌
            trump_suit: 王牌花色，None表示无王牌
        
        Returns:
            True if self > other
        """
        # 如果指定了王牌，王牌最大
        if trump_suit:
            if self.suit == trump_suit and other.suit != trump_suit:
                return True
            elif self.suit != trump_suit and other.suit == trump_suit:
                return False
            elif self.suit == trump_suit and other.suit == trump_suit:
                return self.value > other.value
        
        # 同花色比较点数
        if self.suit == other.suit:
            return self.value > other.value
        
        # 不同花色无法比较（除非有王牌）
        return False

# ===============================
# 玩家类
# ===============================

class BridgePlayer:
    """桥牌玩家类"""
    
    # 玩家位置
    POSITIONS = ['N', 'E', 'S', 'W']  # North, East, South, West
    POSITION_NAMES = {
        'N': 'North',
        'E': 'East', 
        'S': 'South',
        'W': 'West'
    }
    
    def __init__(self, player_id: int, name: str = None):
        """初始化玩家
        
        Args:
            player_id: 玩家ID (0-3)
            name: 玩家名称
        """
        if not 0 <= player_id <= 3:
            raise ValueError(f"Invalid player_id: {player_id}")
        
        self.player_id = player_id
        self.name = name or f"Player_{player_id}"
        self.position = self.POSITIONS[player_id]
        self.hand: List[BridgeCard] = []
        self.tricks_won = 0
        self.is_dummy = False  # 是否为明手
    
    def add_card(self, card: BridgeCard) -> None:
        """添加卡牌到手牌"""
        self.hand.append(card)
        # 按花色和点数排序
        self.hand.sort(key=lambda c: (c.suit_index, c.rank_index))
    
    def remove_card(self, card: BridgeCard) -> bool:
        """从手牌移除卡牌"""
        try:
            self.hand.remove(card)
            return True
        except ValueError:
            return False
    
    def has_card(self, card: BridgeCard) -> bool:
        """检查是否有指定卡牌"""
        return card in self.hand
    
    def get_cards_by_suit(self, suit: str) -> List[BridgeCard]:
        """获取指定花色的卡牌"""
        return [card for card in self.hand if card.suit == suit]
    
    def has_suit(self, suit: str) -> bool:
        """检查是否有指定花色的卡牌"""
        return any(card.suit == suit for card in self.hand)
    
    def get_legal_cards(self, led_suit: Optional[str] = None) -> List[BridgeCard]:
        """获取合法出牌
        
        Args:
            led_suit: 首轮花色，None表示首轮
        
        Returns:
            合法卡牌列表
        """
        if not led_suit:
            return self.hand.copy()
        
        # 如果有首轮花色，必须跟出
        cards_of_led_suit = self.get_cards_by_suit(led_suit)
        if cards_of_led_suit:
            return cards_of_led_suit
        
        # 没有首轮花色，可以出任意牌
        return self.hand.copy()
    
    def get_hand_summary(self) -> Dict[str, int]:
        """获取手牌摘要（各花色张数）"""
        summary = {'C': 0, 'D': 0, 'H': 0, 'S': 0}
        for card in self.hand:
            summary[card.suit] += 1
        return summary
    
    def get_high_card_points(self) -> int:
        """计算大牌点"""
        points = 0
        for card in self.hand:
            if card.rank == 'A':
                points += 4
            elif card.rank == 'K':
                points += 3
            elif card.rank == 'Q':
                points += 2
            elif card.rank == 'J':
                points += 1
        return points
    
    def get_distribution_points(self) -> int:
        """计算牌型点"""
        points = 0
        summary = self.get_hand_summary()
        
        for suit, count in summary.items():
            if count == 0:  # 缺门
                points += 3
            elif count == 1:  # 单张
                points += 2
            elif count == 2:  # 双张
                points += 1
        
        return points
    
    def get_total_points(self) -> int:
        """计算总点数"""
        return self.get_high_card_points() + self.get_distribution_points()
    
    def get_partner_id(self) -> int:
        """获取搭档ID"""
        return (self.player_id + 2) % 4
    
    def get_opponents_ids(self) -> List[int]:
        """获取对手ID列表"""
        return [(self.player_id + 1) % 4, (self.player_id + 3) % 4]
    
    def is_partner(self, other_player_id: int) -> bool:
        """检查是否为搭档"""
        return other_player_id == self.get_partner_id()
    
    def is_opponent(self, other_player_id: int) -> bool:
        """检查是否为对手"""
        return other_player_id in self.get_opponents_ids()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "player_id": self.player_id,
            "name": self.name,
            "position": self.position,
            "hand_size": len(self.hand),
            "hand": [card.to_dict() for card in self.hand],
            "hand_summary": self.get_hand_summary(),
            "high_card_points": self.get_high_card_points(),
            "distribution_points": self.get_distribution_points(),
            "total_points": self.get_total_points(),
            "tricks_won": self.tricks_won,
            "is_dummy": self.is_dummy
        }
    
    def to_dict_hidden(self) -> Dict[str, Any]:
        """转换为字典（隐藏手牌）"""
        return {
            "player_id": self.player_id,
            "name": self.name,
            "position": self.position,
            "hand_size": len(self.hand),
            "hand_summary": self.get_hand_summary(),
            "tricks_won": self.tricks_won,
            "is_dummy": self.is_dummy
        }
    
    def __str__(self) -> str:
        return f"{self.position}({self.name})"
    
    def __repr__(self) -> str:
        return f"BridgePlayer({self.player_id}, '{self.name}')"

# ===============================
# 叫牌系统
# ===============================

class BidLevel(Enum):
    """叫牌级别"""
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7

class BidSuit(Enum):
    """叫牌花色"""
    CLUBS = "C"
    DIAMONDS = "D"
    HEARTS = "H"
    SPADES = "S"
    NO_TRUMP = "NT"

class CallType(Enum):
    """叫牌类型"""
    PASS = "pass"
    BID = "bid"
    DOUBLE = "double"
    REDOUBLE = "redouble"

class CallAction:
    """叫牌动作基类"""
    
    def __init__(self, call_type: CallType, player_id: int):
        self.call_type = call_type
        self.player_id = player_id
        self.timestamp = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "call_type": self.call_type.value,
            "player_id": self.player_id,
            "timestamp": self.timestamp
        }
    
    def __str__(self) -> str:
        return f"{self.call_type.value}"
    
    def __eq__(self, other) -> bool:
        """比较两个CallAction是否相等"""
        if not isinstance(other, CallAction):
            return False
        return (self.call_type == other.call_type and 
                self.player_id == other.player_id)

class PassAction(CallAction):
    """过牌动作"""
    
    def __init__(self, player_id: int):
        super().__init__(CallType.PASS, player_id)
    
    def __str__(self) -> str:
        return "pass"

class BidAction(CallAction):
    """叫牌动作"""
    
    def __init__(self, player_id: int, level: BidLevel, suit: BidSuit):
        super().__init__(CallType.BID, player_id)
        self.level = level
        self.suit = suit
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result.update({
            "level": self.level.value,
            "suit": self.suit.value
        })
        return result
    
    def __str__(self) -> str:
        return f"{self.level.value}{self.suit.value}"
    
    def get_value(self, suit_order: List[str] = None) -> int:
        """获取叫牌价值（用于比较）
        
        Args:
            suit_order: 花色优先级顺序，None表示使用标准顺序
        """
        if suit_order is None:
            suit_values = {
                BidSuit.CLUBS: 0,
                BidSuit.DIAMONDS: 1,
                BidSuit.HEARTS: 2,
                BidSuit.SPADES: 3,
                BidSuit.NO_TRUMP: 4
            }
        else:
            # 使用魔改的花色顺序
            suit_values = {}
            for i, suit in enumerate(suit_order):
                suit_values[suit] = i
            suit_values['NT'] = 4  # NT总是最高优先级
        
        return self.level.value * 5 + suit_values.get(self.suit.value, 0)
    
    def __eq__(self, other) -> bool:
        """比较两个BidAction是否相等"""
        if not isinstance(other, BidAction):
            return False
        return (super().__eq__(other) and 
                self.level == other.level and 
                self.suit == other.suit)

class DoubleAction(CallAction):
    """加倍动作"""
    
    def __init__(self, player_id: int):
        super().__init__(CallType.DOUBLE, player_id)
    
    def __str__(self) -> str:
        return "double"

class RedoubleAction(CallAction):
    """再加倍动作"""
    
    def __init__(self, player_id: int):
        super().__init__(CallType.REDOUBLE, player_id)
    
    def __str__(self) -> str:
        return "redouble"

class CardExchange:
    """卡牌交换系统 - 支持多个搭档交换"""
    
    def __init__(self):
        self.exchange_requests: Dict[int, str] = {}  # player_id -> card_string
        self.exchanged_cards: Dict[int, str] = {}  # player_id -> received_card_string
        self.partnership_exchanges: Dict[str, bool] = {
            "NS": False,  # Player 0 and 2
            "EW": False   # Player 1 and 3
        }
    
    def add_exchange_request(self, player_id: int, card_string: str) -> bool:
        """添加交换请求"""
        # 检查玩家是否已经提交过请求
        if player_id in self.exchange_requests:
            return False
        
        # 检查搭档是否已经交换完成
        partnership = self._get_partnership(player_id)
        if self.partnership_exchanges[partnership]:
            return False
        
        self.exchange_requests[player_id] = card_string
        return True
    
    def _get_partnership(self, player_id: int) -> str:
        """获取玩家所属的搭档"""
        if player_id in [0, 2]:
            return "NS"
        else:
            return "EW"
    
    def is_partnership_ready(self, partnership: str) -> bool:
        """检查搭档是否准备好交换"""
        if self.partnership_exchanges[partnership]:
            return False
        
        if partnership == "NS":
            return 0 in self.exchange_requests and 2 in self.exchange_requests
        else:  # EW
            return 1 in self.exchange_requests and 3 in self.exchange_requests
    
    def execute_partnership_exchange(self, partnership: str) -> bool:
        """执行搭档间的卡牌交换"""
        if not self.is_partnership_ready(partnership):
            return False
        
        if partnership == "NS":
            player1, player2 = 0, 2
        else:  # EW
            player1, player2 = 1, 3
        
        card1 = self.exchange_requests[player1]
        card2 = self.exchange_requests[player2]
        
        # 交换卡牌
        self.exchanged_cards[player1] = card2
        self.exchanged_cards[player2] = card1
        
        # 标记搭档交换完成
        self.partnership_exchanges[partnership] = True
        
        return True
    
    def is_all_exchanges_completed(self) -> bool:
        """检查所有搭档是否都交换完成"""
        return self.partnership_exchanges["NS"] and self.partnership_exchanges["EW"]
    
    def get_exchange_status(self) -> Dict[str, Any]:
        """获取交换状态"""
        return {
            "exchange_requests": len(self.exchange_requests),
            "partnership_exchanges": self.partnership_exchanges,
            "all_completed": self.is_all_exchanges_completed(),
            "waiting_players": [pid for pid in range(4) if pid not in self.exchange_requests],
            "ns_ready": self.is_partnership_ready("NS"),
            "ew_ready": self.is_partnership_ready("EW")
        }
    
    def reset(self):
        """重置交换状态"""
        self.exchange_requests.clear()
        self.exchanged_cards.clear()
        self.partnership_exchanges = {"NS": False, "EW": False}

class BiddingHistory:
    """叫牌历史"""
    
    def __init__(self):
        self.calls: List[CallAction] = []
        self.current_player_id = 0  # 庄家开始
    
    def add_call(self, call: CallAction) -> None:
        """添加叫牌"""
        call.timestamp = len(self.calls)
        self.calls.append(call)
        self.current_player_id = (self.current_player_id + 1) % 4
    
    def get_last_bid(self) -> Optional[BidAction]:
        """获取最后一个叫牌"""
        for call in reversed(self.calls):
            if isinstance(call, BidAction):
                return call
        return None
    
    def get_last_double(self) -> Optional[DoubleAction]:
        """获取最后一个加倍"""
        for call in reversed(self.calls):
            if isinstance(call, DoubleAction):
                return call
        return None
    
    def get_last_redouble(self) -> Optional[RedoubleAction]:
        """获取最后一个再加倍"""
        for call in reversed(self.calls):
            if isinstance(call, RedoubleAction):
                return call
        return None
    
    def is_bidding_over(self) -> bool:
        """判断叫牌是否结束"""
        if len(self.calls) < 4:
            return False
        
        # 检查最后三个动作是否都是pass
        pass_count = 0
        for call in reversed(self.calls):
            if isinstance(call, PassAction):
                pass_count += 1
                if pass_count == 3:
                    return True
            else:
                break
        
        return False
    
    def get_contract(self) -> Optional[Dict[str, Any]]:
        """获取最终合约"""
        if not self.is_bidding_over():
            return None
        
        last_bid = self.get_last_bid()
        if not last_bid:
            return None
        
        # 确定庄家（最后一个叫牌者）
        declarer_id = last_bid.player_id
        
        # 确定加倍状态
        doubling = 1
        if self.get_last_redouble():
            doubling = 4
        elif self.get_last_double():
            doubling = 2
        
        return {
            "level": last_bid.level.value,
            "suit": last_bid.suit.value,
            "declarer_id": declarer_id,
            "doubling": doubling
        }
    
    def get_legal_calls(self, player_id: int, suit_order: List[str] = None) -> List[CallAction]:
        """获取合法叫牌
        
        Args:
            player_id: 玩家ID
            suit_order: 花色优先级顺序，None表示使用标准顺序
        """
        legal_calls = []
        
        # 总是可以过牌
        legal_calls.append(PassAction(player_id))
        
        last_bid = self.get_last_bid()
        last_double = self.get_last_double()
        last_redouble = self.get_last_redouble()
        
        # 可以叫牌
        if last_bid:
            min_value = last_bid.get_value(suit_order) + 1
        else:
            min_value = BidLevel.ONE.value * 5  # 1C
        
        for level in BidLevel:
            for suit in BidSuit:
                bid_value = level.value * 5 + {
                    BidSuit.CLUBS: 0,
                    BidSuit.DIAMONDS: 1,
                    BidSuit.HEARTS: 2,
                    BidSuit.SPADES: 3,
                    BidSuit.NO_TRUMP: 4
                }[suit]
                
                # 如果提供了魔改花色顺序，使用魔改顺序计算价值
                if suit_order and suit.value != 'NT':
                    try:
                        suit_index = suit_order.index(suit.value)
                        bid_value = level.value * 5 + suit_index
                    except ValueError:
                        # 如果花色不在魔改顺序中，使用默认值
                        pass
                
                if bid_value >= min_value:
                    legal_calls.append(BidAction(player_id, level, suit))
        
        # 可以加倍（只能对对手的叫牌加倍）
        if (last_bid and 
            last_bid.player_id % 2 != player_id % 2 and 
            not last_double and 
            not last_redouble):
            legal_calls.append(DoubleAction(player_id))
        
        # 可以再加倍（只能对对手的加倍再加倍）
        if (last_double and 
            last_double.player_id % 2 != player_id % 2 and 
            not last_redouble):
            legal_calls.append(RedoubleAction(player_id))
        
        return legal_calls
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "calls": [call.to_dict() for call in self.calls],
            "current_player_id": self.current_player_id,
            "is_bidding_over": self.is_bidding_over(),
            "contract": self.get_contract()
        }
    
    def __str__(self) -> str:
        calls_str = " ".join([str(call) for call in self.calls])
        return f"Bidding: {calls_str}"

# ===============================
# 游戏核心类
# ===============================

class BridgeGame:
    """魔改桥牌游戏类"""
    
    def __init__(self, game_id: str = None):
        """初始化游戏
        
        Args:
            game_id: 游戏ID，None则自动生成
        """
        self.game_id = game_id or f"bridge_magic_{str(uuid.uuid4())[:8]}"
        self.created_at = datetime.now()
        
        # 游戏状态
        self.phase = "waiting"  # waiting, bidding, exchanging, playing, finished
        self.dealer_id = 0  # 庄家位置
        self.current_player_id = 0  # 当前玩家
        
        # 玩家
        self.players: List[BridgePlayer] = []
        for i in range(4):
            self.players.append(BridgePlayer(i))
        
        # 叫牌
        self.bidding = BiddingHistory()
        
        # 魔改特色：花色优先级
        self.suit_order = self._generate_suit_order()
        
        # 魔改特色：卡牌交换
        self.card_exchange = CardExchange()
        
        # 打牌
        self.current_trick: List[Tuple[int, BridgeCard]] = []  # (player_id, card)
        self.tricks_history: List[List[Tuple[int, BridgeCard]]] = []
        self.trump_suit: Optional[str] = None
        self.contract: Optional[Dict[str, Any]] = None
        
        # 计分
        self.tricks_won = [0, 0]  # [NS, EW]
        self.score = [0, 0]  # [NS, EW]
        
        # 游戏设置
        self.board_id = 1
        self.vulnerability = [False, False]  # [NS, EW]
    
    def _generate_suit_order(self) -> List[str]:
        """生成固定花色优先级顺序"""
        return ['C', 'D', 'H', 'S']  # 梅花、方块、红桃、黑桃（标准桥牌顺序）
    
    def get_suit_order(self) -> Dict[str, Any]:
        """获取花色优先级顺序"""
        return {
            "suit_order": self.suit_order,
            "suit_names": {
                'C': 'Clubs',
                'D': 'Diamonds', 
                'H': 'Hearts',
                'S': 'Spades'
            },
            "description": "标准桥牌花色优先级顺序（从左到右，优先级递减）"
        }
    
    def add_player(self, player_id: int, name: str) -> bool:
        """添加玩家
        
        Args:
            player_id: 玩家ID (0-3)
            name: 玩家名称
        
        Returns:
            是否成功
        """
        if not 0 <= player_id <= 3:
            return False
        
        self.players[player_id].name = name
        return True
    
    def start_game(self) -> bool:
        """开始游戏"""
        if self.phase != "waiting":
            return False
        
        # 检查所有玩家都已加入
        for player in self.players:
            if not player.name or player.name.startswith("Player_"):
                return False
        
        # 发牌
        self._deal_cards()
        
        # 设置庄家
        self.dealer_id = (self.board_id - 1) % 4
        self.current_player_id = (self.dealer_id + 1) % 4  # 庄家左手开始叫牌
        
        # 设置有局方
        self._set_vulnerability()
        
        # 开始叫牌
        self.phase = "bidding"
        self.bidding.current_player_id = self.current_player_id
        
        return True
    
    def _deal_cards(self) -> None:
        """发牌"""
        # 创建并洗牌
        deck = BridgeCard.get_deck()
        random.shuffle(deck)
        
        # 发牌给每个玩家
        for i, card in enumerate(deck):
            player_id = i % 4
            self.players[player_id].add_card(card)
    
    def _set_vulnerability(self) -> None:
        """设置有局方"""
        # 简化的有局方规则
        board_mod = self.board_id % 16
        if board_mod in [2, 5, 12, 15]:
            self.vulnerability = [True, False]  # NS有局
        elif board_mod in [3, 6, 9, 16]:
            self.vulnerability = [False, True]  # EW有局
        elif board_mod in [4, 7, 10, 13]:
            self.vulnerability = [True, True]   # 双方有局
        else:
            self.vulnerability = [False, False]  # 双方无局
    
    def make_call(self, player_id: int, call_data: Dict[str, Any]) -> Tuple[bool, str]:
        """进行叫牌
        
        Args:
            player_id: 玩家ID
            call_data: 叫牌数据
        
        Returns:
            (是否成功, 消息)
        """
        if self.phase != "bidding":
            return False, "Not in bidding phase"
        
        if player_id != self.bidding.current_player_id:
            return False, "Not your turn"
        
        # 创建叫牌动作
        call_type = call_data.get('call_type')
        
        if call_type == 'pass':
            call = PassAction(player_id)
        elif call_type == 'bid':
            level = call_data.get('level')
            suit = call_data.get('suit')
            
            if not level or not suit:
                return False, "Missing level or suit for bid"
            
            try:
                bid_level = BidLevel(level)
                bid_suit = BidSuit(suit)
                call = BidAction(player_id, bid_level, bid_suit)
            except ValueError:
                return False, "Invalid level or suit"
        
        elif call_type == 'double':
            call = DoubleAction(player_id)
        elif call_type == 'redouble':
            call = RedoubleAction(player_id)
        else:
            return False, "Invalid call type"
        
        # 检查叫牌是否合法
        legal_calls = self.bidding.get_legal_calls(player_id, self.suit_order)
        if not any(call.__class__ == legal_call.__class__ and 
                  (not hasattr(call, 'level') or call.level == legal_call.level) and
                  (not hasattr(call, 'suit') or call.suit == legal_call.suit)
                  for legal_call in legal_calls):
            return False, "Illegal call"
        
        # 添加叫牌
        self.bidding.add_call(call)
        self.current_player_id = self.bidding.current_player_id
        
        # 检查叫牌是否结束
        if self.bidding.is_bidding_over():
            self.contract = self.bidding.get_contract()
            if self.contract:
                # 有合约：进入卡牌交换阶段
                self.phase = "exchanging"
                # 重置交换状态
                self.card_exchange.reset()
            else:
                # 没有合约（四家全部pass）：这幅牌作废
                self.phase = "finished"
        
        return True, "Call successful"
    
    def request_card_exchange(self, player_id: int, card_string: str) -> Tuple[bool, str]:
        """请求卡牌交换
        
        Args:
            player_id: 玩家ID
            card_string: 要交换的卡牌字符串
        
        Returns:
            (是否成功, 消息)
        """
        if self.phase != "exchanging":
            return False, "Not in exchanging phase"
        
        # 检查玩家是否有这张牌
        try:
            card = BridgeCard.from_string(card_string)
        except ValueError:
            return False, "Invalid card format"
        
        if not self.players[player_id].has_card(card):
            return False, "You don't have this card"
        
        # 添加交换请求
        if self.card_exchange.add_exchange_request(player_id, card_string):
            return True, "Exchange request submitted"
        else:
            return False, "Exchange already completed"
    
    def execute_card_exchange(self) -> Tuple[bool, str]:
        """执行卡牌交换
        
        Returns:
            (是否成功, 消息)
        """
        if self.phase != "exchanging":
            return False, "Not in exchanging phase"
        
        # 检查并执行NS搭档交换
        ns_exchanged = False
        if self.card_exchange.is_partnership_ready("NS"):
            if self.card_exchange.execute_partnership_exchange("NS"):
                # 实际交换NS搭档的卡牌
                self._apply_exchange_cards("NS")
                ns_exchanged = True
        
        # 检查并执行EW搭档交换
        ew_exchanged = False
        if self.card_exchange.is_partnership_ready("EW"):
            if self.card_exchange.execute_partnership_exchange("EW"):
                # 实际交换EW搭档的卡牌
                self._apply_exchange_cards("EW")
                ew_exchanged = True
        
        # 检查是否所有搭档都交换完成
        if self.card_exchange.is_all_exchanges_completed():
            # 进入打牌阶段（只有在有合约的情况下）
            if self.contract:
                self.phase = "playing"
                self.trump_suit = None if self.contract['suit'] == 'NT' else self.contract['suit']
                
                # 设置明手
                declarer_id = self.contract['declarer_id']
                dummy_id = (declarer_id + 2) % 4
                self.players[dummy_id].is_dummy = True
                
                # 庄家左手开始出牌
                self.current_player_id = (declarer_id + 1) % 4
                
                return True, "All card exchanges completed, entering playing phase"
            else:
                # 没有合约：游戏结束
                self.phase = "finished"
                return True, "All card exchanges completed, but no contract - game finished"
        elif ns_exchanged or ew_exchanged:
            return True, f"Partnership exchange completed (NS: {ns_exchanged}, EW: {ew_exchanged})"
        else:
            return False, "No partnerships ready for exchange"
    
    def _apply_exchange_cards(self, partnership: str):
        """应用搭档间的卡牌交换"""
        if partnership == "NS":
            player1, player2 = 0, 2
        else:  # EW
            player1, player2 = 1, 3
        
        # 获取交换的卡牌
        card1_str = self.card_exchange.exchange_requests[player1]
        card2_str = self.card_exchange.exchange_requests[player2]
        
        # 移除原卡牌
        old_card1 = BridgeCard.from_string(card1_str)
        old_card2 = BridgeCard.from_string(card2_str)
        self.players[player1].remove_card(old_card1)
        self.players[player2].remove_card(old_card2)
        
        # 添加新卡牌
        new_card1 = BridgeCard.from_string(card2_str)  # player1得到player2的卡牌
        new_card2 = BridgeCard.from_string(card1_str)  # player2得到player1的卡牌
        self.players[player1].add_card(new_card1)
        self.players[player2].add_card(new_card2)
    
    def play_card(self, player_id: int, card_str: str) -> Tuple[bool, str]:
        """出牌
        
        Args:
            player_id: 玩家ID
            card_str: 卡牌字符串 (如 "AS")
        
        Returns:
            (是否成功, 消息)
        """
        if self.phase != "playing":
            return False, "Not in playing phase"
        
        if player_id != self.current_player_id:
            return False, "Not your turn"
        
        # 创建卡牌
        try:
            card = BridgeCard.from_string(card_str)
        except ValueError:
            return False, "Invalid card format"
        
        # 检查玩家是否有这张牌
        if not self.players[player_id].has_card(card):
            return False, "You don't have this card"
        
        # 检查是否合法出牌
        led_suit = None
        if self.current_trick:
            led_suit = self.current_trick[0][1].suit
        
        legal_cards = self.players[player_id].get_legal_cards(led_suit)
        if card not in legal_cards:
            return False, "Illegal card play"
        
        # 出牌
        self.players[player_id].remove_card(card)
        self.current_trick.append((player_id, card))
        
        # 检查一墩是否结束
        if len(self.current_trick) == 4:
            self._complete_trick()
        else:
            # 下一个玩家
            self.current_player_id = (self.current_player_id + 1) % 4
        
        return True, "Card played successfully"
    
    def _complete_trick(self) -> None:
        """完成一墩"""
        # 确定赢墩者
        winner_id = self._get_trick_winner(self.current_trick)
        
        # 记录墩数
        if winner_id % 2 == 0:  # NS方
            self.tricks_won[0] += 1
        else:  # EW方
            self.tricks_won[1] += 1
        
        # 保存墩历史
        self.tricks_history.append(self.current_trick.copy())
        self.current_trick.clear()
        
        # 检查游戏是否结束
        if len(self.tricks_history) == 13:
            self._finish_game()
        else:
            # 赢墩者开始下一墩
            self.current_player_id = winner_id
    
    def _get_trick_winner(self, trick: List[Tuple[int, BridgeCard]]) -> int:
        """获取本墩赢家"""
        if not trick:
            return 0
        
        led_suit = trick[0][1].suit
        winner_id = trick[0][0]
        winner_card = trick[0][1]
        
        for player_id, card in trick[1:]:
            if card.is_higher_than(winner_card, self.trump_suit):
                winner_id = player_id
                winner_card = card
            elif (self.trump_suit and 
                  card.suit == self.trump_suit and 
                  winner_card.suit != self.trump_suit):
                winner_id = player_id
                winner_card = card
            elif (card.suit == led_suit and 
                  winner_card.suit != led_suit and 
                  (not self.trump_suit or winner_card.suit != self.trump_suit)):
                winner_id = player_id
                winner_card = card
        
        return winner_id
    
    def _finish_game(self) -> None:
        """结束游戏"""
        self.phase = "finished"
        
        if self.contract:
            # 计算得分
            declarer_id = self.contract['declarer_id']
            declarer_side = declarer_id % 2
            
            required_tricks = 6 + self.contract['level']
            made_tricks = self.tricks_won[declarer_side]
            
            if made_tricks >= required_tricks:
                # 完成合约
                self.score[declarer_side] = self._calculate_score(made_tricks - 6)
            else:
                # 宕掉
                self.score[1 - declarer_side] = self._calculate_penalty(required_tricks - made_tricks)
    
    def _calculate_score(self, overtricks: int) -> int:
        """计算完成合约得分"""
        if not self.contract:
            return 0
        
        level = self.contract['level']
        suit = self.contract['suit']
        doubling = self.contract['doubling']
        
        # 基础分
        if suit in ['C', 'D']:  # 小花色
            base_score = level * 20
        elif suit in ['H', 'S']:  # 大花色
            base_score = level * 30
        else:  # NT
            base_score = 30 + (level - 1) * 30
        
        # 加倍倍数
        score = base_score * doubling
        
        # 超墩分（简化版）
        score += overtricks * 30
        
        return score
    
    def _calculate_penalty(self, down_tricks: int) -> int:
        """计算罚分"""
        if not self.contract:
            return 0
        
        doubling = self.contract['doubling']
        declarer_id = self.contract['declarer_id']
        vulnerable = self.vulnerability[declarer_id % 2]
        
        # 简化的罚分计算
        if vulnerable:
            penalty = down_tricks * 100 * doubling
        else:
            penalty = down_tricks * 50 * doubling
        
        return penalty
    
    def get_legal_actions(self, player_id: int) -> List[Dict[str, Any]]:
        """获取合法动作"""
        actions = []
        
        if self.phase == "bidding" and player_id == self.bidding.current_player_id:
            legal_calls = self.bidding.get_legal_calls(player_id, self.suit_order)
            for call in legal_calls:
                action = {"type": "call", "call_type": call.call_type.value}
                if hasattr(call, 'level'):
                    action["level"] = call.level.value
                if hasattr(call, 'suit'):
                    action["suit"] = call.suit.value
                actions.append(action)
        
        elif self.phase == "exchanging":
            # 魔改特色：卡牌交换阶段
            # 检查是否已经提交过交换请求
            if player_id not in self.card_exchange.exchange_requests:
                # 检查搭档是否已经交换完成
                partnership = self.card_exchange._get_partnership(player_id)
                if not self.card_exchange.partnership_exchanges[partnership]:
                    # 可以提交交换请求
                    my_hand = self.players[player_id].hand
                    for card in my_hand:
                        actions.append({
                            "type": "exchange",
                            "card": str(card)
                        })
        
        elif self.phase == "playing" and player_id == self.current_player_id:
            led_suit = None
            if self.current_trick:
                led_suit = self.current_trick[0][1].suit
            
            legal_cards = self.players[player_id].get_legal_cards(led_suit)
            for card in legal_cards:
                actions.append({
                    "type": "play",
                    "card": str(card)
                })
        
        return actions
    
    def get_state(self, player_id: int) -> Dict[str, Any]:
        """获取游戏状态（针对特定玩家）"""
        state = {
            "game_id": self.game_id,
            "phase": self.phase,
            "dealer_id": self.dealer_id,
            "current_player_id": self.current_player_id,
            "board_id": self.board_id,
            "vulnerability": self.vulnerability,
            "players": [],
            "bidding": self.bidding.to_dict(),
            "current_trick": [(pid, str(card)) for pid, card in self.current_trick],
            "tricks_won": self.tricks_won,
            "score": self.score,
            "contract": self.contract,
            "trump_suit": self.trump_suit
        }
        
        # 魔改特色：添加花色优先级信息
        state["suit_order"] = self.get_suit_order()
        
        # 魔改特色：添加卡牌交换状态
        if self.phase == "exchanging":
            state["card_exchange"] = self.card_exchange.get_exchange_status()
            # 显示交换请求（只显示自己的）
            if player_id in self.card_exchange.exchange_requests:
                state["my_exchange_request"] = self.card_exchange.exchange_requests[player_id]
            else:
                state["my_exchange_request"] = None
        elif self.phase == "playing" or self.phase == "finished":
            # 在打牌阶段和结束后，显示交换结果
            if player_id in self.card_exchange.exchanged_cards:
                state["my_exchanged_card"] = self.card_exchange.exchanged_cards[player_id]
            state["exchange_history"] = {
                "exchange_requests": self.card_exchange.exchange_requests,
                "exchanged_cards": self.card_exchange.exchanged_cards,
                "partnership_exchanges": self.card_exchange.partnership_exchanges
            }
        
        # 添加玩家信息
        for i, player in enumerate(self.players):
            if i == player_id:
                # 显示自己的手牌
                state["players"].append(player.to_dict())
            else:
                # 隐藏其他玩家的手牌
                state["players"].append(player.to_dict_hidden())
        
        return state
    
    def get_history(self) -> Dict[str, Any]:
        """获取游戏历史"""
        history = {
            "game_id": self.game_id,
            "created_at": self.created_at.isoformat(),
            "phase": self.phase,
            
            # 魔改特色：花色优先级信息
            "suit_order": self.get_suit_order(),
            
            # 叫牌历史
            "bidding_history": self.bidding.to_dict(),
            
            # 魔改特色：交换阶段历史
            "exchange_history": {
                "exchange_requests": self.card_exchange.exchange_requests,
                "exchanged_cards": self.card_exchange.exchanged_cards,
                "partnership_exchanges": self.card_exchange.partnership_exchanges,
                "exchange_status": self.card_exchange.get_exchange_status()
            },
            
            # 打牌历史
            "tricks_history": [
                {
                    "trick_number": i + 1,
                    "cards": [(pid, str(card)) for pid, card in trick],
                    "winner": self._get_trick_winner(trick) if self.contract else None
                }
                for i, trick in enumerate(self.tricks_history)
            ],
            
            # 最终结果
            "final_score": self.score,
            "winner": 0 if self.score[0] > self.score[1] else 1 if self.score[1] > self.score[0] else None,
            
            # 游戏设置
            "board_id": self.board_id,
            "vulnerability": self.vulnerability,
            "dealer_id": self.dealer_id,
            
            # 合约信息
            "contract": self.contract,
            "trump_suit": self.trump_suit,
            
            # 玩家信息（最终状态）
            "players": [player.to_dict() for player in self.players]
        }
        
        return history

# ===============================
# HTTP API路由
# ===============================

# 全局游戏存储
games: Dict[str, BridgeGame] = {}

@app.route('/games', methods=['POST'])
def create_game():
    """创建新游戏"""
    try:
        data = request.get_json() or {}
        
        # 创建游戏
        game = BridgeGame()
        games[game.game_id] = game
        
        return jsonify({
            "game_id": game.game_id,
            "status": "created",
            "message": "Game created successfully"
        }), 201
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/join', methods=['POST'])
def join_game(game_id):
    """加入游戏"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player_id = data.get('player_id')
        player_name = data.get('player_name')
        
        if player_id is None or not player_name:
            return jsonify({"error": "Missing player_id or player_name"}), 400
        
        game = games[game_id]
        if not game.add_player(player_id, player_name):
            return jsonify({"error": "Invalid player_id or player already exists"}), 400
        
        return jsonify({
            "game_id": game_id,
            "player_id": player_id,
            "player_name": player_name,
            "status": "joined"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/start', methods=['POST'])
def start_game(game_id):
    """开始游戏"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        game = games[game_id]
        if not game.start_game():
            return jsonify({"error": "Cannot start game"}), 400
        
        return jsonify({
            "game_id": game_id,
            "status": "started",
            "dealer_id": game.dealer_id,
            "current_player_id": game.current_player_id,
            "phase": game.phase
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/state', methods=['GET'])
def get_game_state(game_id):
    """获取游戏状态"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        player_id = request.args.get('player_id', type=int)
        if player_id is None:
            return jsonify({"error": "Missing player_id parameter"}), 400
        
        game = games[game_id]
        state = game.get_state(player_id)
        
        return jsonify(state)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/call', methods=['POST'])
def make_call(game_id):
    """进行叫牌"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player_id = data.get('player_id')
        if player_id is None:
            return jsonify({"error": "Missing player_id"}), 400
        
        game = games[game_id]
        success, message = game.make_call(player_id, data)
        
        if success:
            return jsonify({
                "game_id": game_id,
                "player_id": player_id,
                "call_type": data.get('call_type'),
                "status": "success",
                "message": message
            })
        else:
            return jsonify({"error": message}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/play', methods=['POST'])
def play_card(game_id):
    """出牌"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player_id = data.get('player_id')
        card = data.get('card')
        
        if player_id is None or not card:
            return jsonify({"error": "Missing player_id or card"}), 400
        
        game = games[game_id]
        success, message = game.play_card(player_id, card)
        
        if success:
            return jsonify({
                "game_id": game_id,
                "player_id": player_id,
                "card": card,
                "status": "success",
                "message": message
            })
        else:
            return jsonify({"error": message}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/legal_actions', methods=['GET'])
def get_legal_actions(game_id):
    """获取合法动作"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        player_id = request.args.get('player_id', type=int)
        if player_id is None:
            return jsonify({"error": "Missing player_id parameter"}), 400
        
        game = games[game_id]
        legal_actions = game.get_legal_actions(player_id)
        
        return jsonify({
            "game_id": game_id,
            "player_id": player_id,
            "legal_actions": legal_actions
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/history', methods=['GET'])
def get_game_history(game_id):
    """获取游戏历史"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        game = games[game_id]
        history = game.get_history()
        
        return jsonify(history)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>', methods=['DELETE'])
def delete_game(game_id):
    """删除游戏"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        del games[game_id]
        
        return jsonify({
            "game_id": game_id,
            "status": "deleted"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games', methods=['GET'])
def list_games():
    """列出所有游戏"""
    try:
        game_list = []
        for game_id, game in games.items():
            game_list.append({
                "game_id": game_id,
                "phase": game.phase,
                "players": [player.name for player in game.players],
                "created_at": game.created_at.isoformat()
            })
        
        return jsonify({
            "games": game_list,
            "total": len(game_list)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "active_games": len(games),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/games/<game_id>/suit_order', methods=['GET'])
def get_suit_order(game_id):
    """获取花色优先级顺序（魔改特色）"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        game = games[game_id]
        suit_order = game.get_suit_order()
        
        return jsonify(suit_order)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/exchange', methods=['POST'])
def request_card_exchange(game_id):
    """请求卡牌交换（魔改特色）"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        player_id = data.get('player_id')
        card = data.get('card')
        
        if player_id is None or not card:
            return jsonify({"error": "Missing player_id or card"}), 400
        
        game = games[game_id]
        success, message = game.request_card_exchange(player_id, card)
        
        if success:
            return jsonify({
                "game_id": game_id,
                "player_id": player_id,
                "card": card,
                "status": "success",
                "message": message
            })
        else:
            return jsonify({"error": message}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/games/<game_id>/execute_exchange', methods=['POST'])
def execute_card_exchange(game_id):
    """执行卡牌交换（魔改特色）"""
    try:
        if game_id not in games:
            return jsonify({"error": "Game not found"}), 404
        
        game = games[game_id]
        success, message = game.execute_card_exchange()
        
        if success:
            return jsonify({
                "game_id": game_id,
                "status": "success",
                "message": message,
                "exchanged_cards": game.card_exchange.exchanged_cards
            })
        else:
            return jsonify({"error": message}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/info', methods=['GET'])
def server_info():
    """服务器信息"""
    return jsonify({
        "name": "Magic Bridge Game Server",
        "version": "1.0",
        "description": "HTTP server for Magic Bridge card game with standard suit order and card exchange",
        "protocol": "HTTP RESTful",
        "default_port": 9031,
        "features": [
            "4-player bridge game",
            "Standard suit order",
            "Card exchange between partners (magic feature)",
            "Bidding phase",
            "Playing phase", 
            "Scoring system",
            "Game history"
        ]
    })

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='魔改桥牌HTTP服务器')
    parser.add_argument('--port', type=int, default=9031, help='监听端口 (默认: 9031)')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='监听地址 (默认: 0.0.0.0)')
    
    args = parser.parse_args()
    
    print(f"=== Magic Bridge HTTP Server ===")
    print(f"Port: {args.port}")
    print(f"Host: {args.host}")
    print(f"Debug: {args.debug}")
    print("")
    print("Available endpoints:")
    print("  POST /games                    - Create game")
    print("  POST /games/{id}/join          - Join game")
    print("  POST /games/{id}/start         - Start game")
    print("  GET  /games/{id}/state         - Get game state")
    print("  POST /games/{id}/call          - Make call")
    print("  POST /games/{id}/play          - Play card")
    print("  GET  /games/{id}/legal_actions - Get legal actions")
    print("  GET  /games/{id}/history       - Get game history")
    print("  DELETE /games/{id}             - Delete game")
    print("  GET  /games                    - List games")
    print("  GET  /health                   - Health check")
    print("  GET  /info                     - Server info")
    print("")
    print("Magic Bridge Features:")
    print("  GET  /games/{id}/suit_order    - Get standard suit order")
    print("  POST /games/{id}/exchange      - Request card exchange")
    print("  POST /games/{id}/execute_exchange - Execute card exchange")
    print("")
    
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == '__main__':
    main()