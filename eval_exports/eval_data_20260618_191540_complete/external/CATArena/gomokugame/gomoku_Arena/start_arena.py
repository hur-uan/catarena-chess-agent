#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import os
from arena import GomokuArena
from config import ArenaConfig

def main():
    parser = argparse.ArgumentParser(description='五子棋AI对战平台')
    parser.add_argument('--config', type=str, default='configs/arena_config.json', 
                       help='配置文件路径 (默认: configs/arena_config.json)')
    parser.add_argument('--timeout', type=int, default=None, 
                       help='AI响应超时时间(秒) (默认: 使用配置文件中的值)')
    parser.add_argument('--game-server', type=str, default=None,
                       help='游戏服务器地址 (默认: 使用配置文件中的值)')
    parser.add_argument('--ais', nargs='+', default=None,
                       help='指定要参赛的AI ID列表 (默认: 使用配置文件中的所有AI)')
    parser.add_argument('--rounds-per-match', type=int, default=None,
                       help='每对AI对战轮数 (默认: 使用配置文件中的值)')
    parser.add_argument('--create-config', action='store_true',
                       help='创建示例配置文件')
    parser.add_argument('--list-ais', action='store_true',
                       help='列出配置的AI')
    parser.add_argument('--add-ai', nargs=3, metavar=('AI_ID', 'AI_NAME', 'PORT'),
                       help='添加AI配置 (AI_ID AI_NAME PORT)')
    parser.add_argument('--remove-ai', type=str,
                       help='移除AI配置 (AI_ID)')
    
    args = parser.parse_args()
    
    # 创建配置文件
    if args.create_config:
        if args.config == "configs/quick_config.json":
            create_quick_config()
        else:
            create_sample_config()
        return
    
    # 加载配置
    try:
        config = ArenaConfig(args.config)
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return
    
    # 列出AI
    if args.list_ais:
        ais = config.get_ais()
        print("配置的AI列表:")
        for ai in ais:
            print(f"  - {ai['ai_name']} (ID: {ai['ai_id']}, 端口: {ai['port']})")
        return
    
    # 添加AI
    if args.add_ai:
        ai_id, ai_name, port = args.add_ai
        try:
            port = int(port)
            config.add_ai(ai_id, ai_name, port)
            print(f"AI {ai_name} 已添加到配置")
        except ValueError:
            print("端口必须是数字")
        return
    
    # 移除AI
    if args.remove_ai:
        config.remove_ai(args.remove_ai)
        print(f"AI {args.remove_ai} 已从配置中移除")
        return
    
    # 获取配置参数
    game_server_url = args.game_server or config.get_game_server_url()
    timeout = args.timeout or config.get_timeout()
    tournament_config = config.get_tournament_config()
    rounds_per_match = args.rounds_per_match or tournament_config.get("rounds_per_match", 2)
    
    # 创建对战平台
    arena = GomokuArena(game_server_url=game_server_url, timeout=timeout, rounds_per_match=rounds_per_match)
    
    # 添加AI
    all_ais = config.get_ais()
    if args.ais:
        # 只添加指定的AI
        selected_ais = [ai for ai in all_ais if ai['ai_id'] in args.ais]
        if len(selected_ais) != len(args.ais):
            missing_ais = set(args.ais) - set(ai['ai_id'] for ai in selected_ais)
            print(f"警告: 以下AI未找到: {missing_ais}")
    else:
        # 添加所有AI
        selected_ais = all_ais
    
    if not selected_ais:
        print("错误: 没有可用的AI")
        return
    
    print("=" * 60)
    print("五子棋AI对战平台")
    print("=" * 60)
    print(f"游戏服务器: {game_server_url}")
    print(f"超时时间: {timeout}秒")
    print(f"每对AI对战轮数: {rounds_per_match}")
    print(f"参赛AI数量: {len(selected_ais)}")
    
    for ai in selected_ais:
        arena.add_ai(ai['ai_id'], ai['ai_name'], ai['port'])
        print(f"  - {ai['ai_name']} (端口: {ai['port']})")
    
    print("\n开始锦标赛...")
    
    # 运行锦标赛
    report = arena.run_tournament()
    
    if report:
        # 保存报告
        arena.save_report(report)
        
        # 打印简要结果
        print("\n" + "=" * 60)
        print("锦标赛完成！")
        print("=" * 60)
        
        print(f"参赛AI数量: {len(report['participants'])}")
        print(f"总对局数: {report['total_games']}")
        print("\n最终排名:")
        
        # 按胜场数排序
        sorted_ais = sorted(
            report['ai_stats'].items(),
            key=lambda x: (x[1]['wins'], x[1]['draws']),
            reverse=True
        )
        
        for i, (ai_id, stats) in enumerate(sorted_ais, 1):
            print(f"{i}. {stats['name']} - 胜:{stats['wins']} 平:{stats['draws']} 负:{stats['losses']} "
                  f"(平均思考时间: {stats['avg_thinking_time']:.3f}秒)")
        
        print(f"\n详细报告已保存:")
        print(f"  - JSON格式: tournament_report_{report['tournament_id']}.json")
        print(f"  - 文本格式: tournament_report_{report['tournament_id']}.txt")
        print(f"  - 日志文件: arena.log")
    else:
        print("锦标赛运行失败")

if __name__ == "__main__":
    main() 