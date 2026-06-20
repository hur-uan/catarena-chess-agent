#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import random
from typing import List, Dict, Optional

class AICoordinator:
    """AI对战协调器"""
    
    def __init__(self, game_server_url="http://localhost:9020"):
        self.game_server_url = game_server_url
        self.ai_services = []  # 存储AI服务信息
    
    def add_ai_service(self, ai_id: str, ai_url: str):
        """添加AI服务"""
        self.ai_services.append({
            "ai_id": ai_id,
            "url": ai_url
        })
        print(f"添加AI服务: {ai_id} -> {ai_url}")
    
    def create_game(self, player_white: str, player_black: str) -> Optional[str]:
        """创建游戏"""
        try:
            url = f"{self.game_server_url}/games"
            data = {
                "player_white": player_white,
                "player_black": player_black
            }
            
            response = requests.post(url, json=data)
            if response.status_code == 201:
                game_info = response.json()
                return game_info["game_id"]
            else:
                print(f"创建游戏失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"创建游戏时出错: {e}")
            return None
    
    def get_game_state(self, game_id: str) -> Optional[dict]:
        """获取游戏状态"""
        try:
            url = f"{self.game_server_url}/games/{game_id}/state"
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception:
            return None
    
    def make_move(self, game_id: str, player: str, move: str) -> bool:
        """在游戏中执行移动"""
        try:
            url = f"{self.game_server_url}/games/{game_id}/move"
            data = {
                "player": player,
                "move": move
            }
            
            response = requests.post(url, json=data)
            if response.status_code == 200:
                result = response.json()
                return result["status"] == "valid_move"
            else:
                return False
        except Exception:
            return False
    
    def join_ai_to_game(self, ai_url: str, game_id: str, my_color: str) -> bool:
        """让AI加入游戏"""
        try:
            url = f"{ai_url}/join_game"
            data = {
                "game_id": game_id,
                "my_color": my_color,
                "game_server_url": self.game_server_url
            }
            
            response = requests.post(url, json=data)
            return response.status_code == 200
        except Exception as e:
            print(f"AI加入游戏失败: {e}")
            return False
    
    def get_ai_move(self, ai_url: str, game_id: str, fen: str, current_player: str) -> Optional[str]:
        """获取AI的移动"""
        try:
            url = f"{ai_url}/move"
            data = {
                "fen": fen,
                "current_player": current_player
            }
            
            response = requests.post(url, json=data)
            if response.status_code == 200:
                result = response.json()
                return result["move"]
            else:
                print(f"获取AI移动失败: {response.status_code}")
                return None
        except Exception as e:
            print(f"获取AI移动时出错: {e}")
            return None
    
    def print_board(self, fen):
        """打印棋盘状态"""
        print(f"FEN: {fen}")
    
    def run_ai_vs_ai_game(self, ai1_id: str, ai2_id: str) -> bool:
        """运行AI对战"""
        print(f"=== AI对战: {ai1_id} vs {ai2_id} ===")
        
        # 查找AI服务
        ai1_service = None
        ai2_service = None
        
        for service in self.ai_services:
            if service["ai_id"] == ai1_id:
                ai1_service = service
            elif service["ai_id"] == ai2_id:
                ai2_service = service
        
        if not ai1_service or not ai2_service:
            print("找不到指定的AI服务")
            return False
        
        # 创建游戏
        game_id = self.create_game(ai1_id, ai2_id)
        if not game_id:
            print("创建游戏失败")
            return False
        
        print(f"游戏ID: {game_id}")
        
        # 让AI加入游戏
        if not self.join_ai_to_game(ai1_service["url"], game_id, "white"):
            print(f"{ai1_id} 加入游戏失败")
            return False
        
        if not self.join_ai_to_game(ai2_service["url"], game_id, "black"):
            print(f"{ai2_id} 加入游戏失败")
            return False
        
        # 开始游戏循环
        move_count = 0
        max_moves = 200  # 增加最大移动数，允许更长的对局
        
        while move_count < max_moves:
            # 获取游戏状态
            state = self.get_game_state(game_id)
            if not state:
                print("无法获取游戏状态")
                break
            
            current_player = state["current_player"]
            game_status = state["game_status"]
            current_fen = state["fen"]
            
            print(f"\n第{move_count + 1}步 - 当前玩家: {current_player}")
            
            # 检查游戏是否结束
            if game_status != "ongoing":
                print(f"游戏结束: {game_status}")
                break
            
            # 确定当前AI
            current_ai_service = ai1_service if current_player == "white" else ai2_service
            
            # 获取AI移动
            ai_move = self.get_ai_move(
                current_ai_service["url"], 
                game_id, 
                current_fen, 
                current_player
            )
            
            if ai_move is None:
                print(f"{current_ai_service['ai_id']} 无法获取移动")
                break
            
            # 执行移动
            if self.make_move(game_id, current_player, ai_move):
                print(f"{current_ai_service['ai_id']} 移动: {ai_move}")
                move_count += 1
            else:
                print(f"{current_ai_service['ai_id']} 移动失败")
                break
            
            # 短暂延迟
            time.sleep(1)
        
        # 获取最终状态
        final_state = self.get_game_state(game_id)
        if final_state:
            print(f"\n最终游戏状态: {final_state['game_status']}")
            print("最终棋盘:")
            self.print_board(final_state["fen"])
        
        print(f"\n游戏结束，共进行了 {move_count} 步")
        return True

def main():
    """主函数"""
    print("=== AI对战协调器 ===")
    
    # 创建协调器
    coordinator = AICoordinator()
    
    # 添加AI服务（假设有两个AI服务在运行）
    coordinator.add_ai_service("AI_Alpha", "http://localhost:48010")
    coordinator.add_ai_service("AI_Beta", "http://localhost:48010")
    
    # 运行AI对战
    coordinator.run_ai_vs_ai_game("AI_Alpha", "AI_Beta")

if __name__ == "__main__":
    main()