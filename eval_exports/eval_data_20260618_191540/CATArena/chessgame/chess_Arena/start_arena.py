#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import os
import json
from datetime import datetime
from arena import ChessArena
from config import ArenaConfig, create_sample_config, create_quick_config

def test_ai_connection(config: ArenaConfig):
    """测试AI连接"""
    print("Testing AI connections...")
    
    enabled_ais = config.get_enabled_ais()
    if not enabled_ais:
        print("No AIs configured!")
        return
    
    for ai_config in enabled_ais:
        ai_url = f"http://localhost:{ai_config['port']}"
        try:
            import requests
            response = requests.get(f"{ai_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print(f"✓ {ai_config['ai_name']} ({ai_url}) - {data.get('status', 'unknown')}")
            else:
                print(f"✗ {ai_config['ai_name']} ({ai_url}) - HTTP {response.status_code}")
        except Exception as e:
            print(f"✗ {ai_config['ai_name']} ({ai_url}) - {str(e)}")

def list_configured_ais(config: ArenaConfig):
    """列出配置的AI"""
    print("Configured AIs:")
    print("-" * 60)
    
    enabled_ais = config.get_enabled_ais()
    if not enabled_ais:
        print("No AIs configured!")
        return
    
    for ai_config in enabled_ais:
        status = "✓ Enabled" if ai_config.get("enabled", True) else "✗ Disabled"
        print(f"{ai_config['ai_name']:20} | {ai_config['ai_id']:15} | Port {ai_config['port']:5} | {ai_config.get('algorithm', 'simple'):10} | {status}")
        if ai_config.get("description"):
            print(f"{'':20} | {ai_config['description']}")

def run_tournament(config: ArenaConfig, quick_mode: bool = False, reports_dir: str = "reports"):
    """运行锦标赛"""
    if quick_mode:
        print("Loading quick test configuration...")
        config.load_quick_config()
    
    print("Starting Chess Arena Tournament...")
    print(f"Game Server: {config.get_game_server_url()}")
    print(f"Timeout: {config.get_timeout()} seconds")
    print(f"Max Moves: {config.get_max_moves()}")
    print(f"Reports Directory: {reports_dir}")
    
    # 列出参赛AI
    enabled_ais = config.get_enabled_ais()
    print(f"\nParticipating AIs ({len(enabled_ais)}):")
    for ai_config in enabled_ais:
        print(f"  - {ai_config['ai_name']} (Port {ai_config['port']}, {ai_config.get('algorithm', 'simple')})")
    
    # 创建竞技场并运行
    arena = ChessArena(config)
    
    print(f"\nTournament ID: {arena.tournament_id}")
    print("=" * 60)
    
    # 运行锦标赛
    report = arena.run_tournament()
    
    if report:
        # 保存报告到指定目录
        arena.save_report(report, reports_dir=reports_dir)
        
        print("\n" + "=" * 60)
        print("Tournament completed successfully!")
        
        # 显示简要结果
        print(f"\nResults Summary:")
        print(f"  Total Games: {report['total_games']}")
        print(f"  Average Game Duration: {report['avg_time']:.2f} seconds")
        
        print(f"\nAI Performance:")
        for ai_name, stats in report['ai_stats'].items():
            win_rate = (stats['wins'] / stats['total_games'] * 100) if stats['total_games'] > 0 else 0
            print(f"  {ai_name}: {stats['wins']}W-{stats['draws']}D-{stats['losses']}L ({win_rate:.1f}% win rate)")
        
        print(f"\nReports saved to: {reports_dir}/")
        return True
    else:
        print("\nTournament failed!")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Chess AI Arena Tournament")
    parser.add_argument("--create-config", action="store_true", help="Create sample configuration file")
    parser.add_argument("--list-ais", action="store_true", help="List configured AIs")
    parser.add_argument("--test-connection", action="store_true", help="Test AI connections")
    parser.add_argument("--quick", action="store_true", help="Run quick test tournament")
    parser.add_argument("--config", default="configs/arena_config.json", help="Configuration file path")
    parser.add_argument("--reports-dir", default="reports", help="Directory to save tournament reports")
    
    args = parser.parse_args()
    
    # 创建配置目录
    os.makedirs("configs", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs(args.reports_dir, exist_ok=True)

    
    
    if args.create_config:
        create_sample_config()
        print("Sample configuration created. Please edit configs/arena_config.json to customize settings.")
        return
    
    if args.quick:
        create_quick_config()
        print("Quick test configuration loaded.")
    
    # 加载配置
    try:
        config = ArenaConfig(args.config)
    except Exception as e:
        print(f"Failed to load configuration: {e}")
        print("Run with --create-config to create a sample configuration file.")
        return
    
    if args.list_ais:
        list_configured_ais(config)
        return
    
    if args.test_connection:
        test_ai_connection(config)
        return
    
    # 运行锦标赛
    success = run_tournament(config, args.quick, args.reports_dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 