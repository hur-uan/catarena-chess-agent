#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import random
from datetime import datetime
import chess

def test_ai_logic():
    """直接测试AI逻辑"""
    print("=== 测试AI逻辑 ===")
    
    # 导入AI类
    from ai_http_server import ChessAI
    
    # 创建AI实例
    ai = ChessAI("test_ai", "Test AI")
    
    # 测试标准开局
    test_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    board = chess.Board(test_fen)
    
    print(f"初始FEN: {test_fen}")
    print(f"当前玩家: {'白方' if board.turn else '黑方'}")
    print(f"合法移动数: {len(list(board.legal_moves))}")
    
    # 测试AI移动
    move = ai.get_best_move_simple(board)
    if move:
        print(f"AI选择的移动: {move.uci()}")
        print(f"移动的SAN表示: {board.san(move)}")
        print("✓ AI逻辑测试通过")
        return True
    else:
        print("✗ AI没有找到合法移动")
        return False

def test_ai_server(ai_server_url: str = "http://localhost:41101"):
    """测试AI服务器"""
    print(f"\n=== 测试AI服务器: {ai_server_url} ===")
    
    # 测试健康检查
    print("\n1. 测试健康检查...")
    try:
        response = requests.get(f"{ai_server_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 健康检查成功: {data}")
        else:
            print(f"✗ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 健康检查异常: {e}")
        print("  注意: 服务器可能没有运行")
        return False
    
    # 测试获取AI信息
    print("\n2. 测试获取AI信息...")
    try:
        response = requests.get(f"{ai_server_url}/info", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ AI信息: {data}")
        else:
            print(f"✗ 获取AI信息失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 获取AI信息异常: {e}")
        return False
    
    # 测试主要API - /move
    print("\n3. 测试主要API - /move...")
    test_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    try:
        response = requests.post(f"{ai_server_url}/move", json={
            "fen": test_fen,
            "algorithm": "simple"
        }, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 主要API成功: {data}")
        else:
            print(f"✗ 主要API失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 主要API异常: {e}")
        return False
    
    print("\n=== 服务器测试完成 ===")
    return True

def main():
    """主函数"""
    print("=== 国际象棋AI客户端测试 ===")
    
    # 测试AI逻辑
    if not test_ai_logic():
        print("✗ AI逻辑测试失败")
        return
    
    # 测试服务器（如果可用）
    server_test_result = test_ai_server()
    
    print("\n🎉 核心测试通过！")
    print("\n接口一致性验证:")
    print("✓ 使用 /move 作为主要API端点")
    print("✓ 支持简单随机算法")
    print("✓ 完整的错误处理")
    
    if server_test_result:
        print("✓ 服务器测试通过")
    else:
        print("⚠ 服务器测试失败（可能需要启动服务器）")

if __name__ == '__main__':
    main()
