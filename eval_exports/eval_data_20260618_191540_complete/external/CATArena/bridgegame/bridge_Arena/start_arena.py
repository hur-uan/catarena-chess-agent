#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import sys
import os
import json
from typing import Dict, List

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from arena import BridgeArena
from config import ArenaConfig, create_quick_config, create_duplicate_teams_config, create_mixed_teams_config

def main():
    """Main function for bridge arena"""
    parser = argparse.ArgumentParser(description='Bridge AI Tournament Platform')
    parser.add_argument('--config', type=str, default='configs/arena_config.json', 
                       help='Configuration file path')
    parser.add_argument('--server-url', type=str, default='http://localhost:9030',
                       help='Bridge game server URL')
    parser.add_argument('--timeout', type=int, default=10,
                       help='AI response timeout (seconds)')
    parser.add_argument('--rounds', type=int, default=2,
                       help='Rounds per match')
    parser.add_argument('--tournament-type', type=str, default='round_robin',
                       choices=['round_robin', 'duplicate'],
                       help='Tournament type: round_robin or duplicate')
    parser.add_argument('--create-config', type=str, choices=['quick', 'duplicate', 'mixed'],
                       help='Create specific configuration type')
    parser.add_argument('--list-configs', action='store_true',
                       help='List available configurations')
    parser.add_argument('--validate', action='store_true',
                       help='Validate configuration')
    
    args = parser.parse_args()
    
    # Handle configuration creation
    if args.create_config:
        if args.create_config == 'quick':
            config = create_quick_config()
            print(f"Quick configuration created: {config.config_file}")
        elif args.create_config == 'duplicate':
            config = create_duplicate_teams_config()
            print(f"Duplicate teams configuration created: {config.config_file}")
        elif args.create_config == 'mixed':
            config = create_mixed_teams_config()
            print(f"Mixed teams configuration created: {config.config_file}")
        return
    
    # Load configuration
    try:
        config = ArenaConfig(args.config)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return
    
    # Handle configuration listing
    if args.list_configs:
        print("=== AI Configurations ===")
        for ai_config in config.get_ai_configs():
            print(f"  {ai_config['ai_id']}: {ai_config['ai_name']} (Port: {ai_config['port']})")
        
        print("\n=== Team Configurations ===")
        for team_config in config.get_team_configs():
            print(f"  {team_config['team_id']}: {team_config['team_name']}")
            print(f"    Players: {team_config['player1']} + {team_config['player2']}")
        
        print(f"\n=== Server Configuration ===")
        server_config = config.get_game_server_config()
        print(f"  Server URL: {server_config['url']}")
        print(f"  Timeout: {server_config['timeout']}s")
        
        print(f"\n=== Tournament Configuration ===")
        tournament_config = config.get_tournament_config()
        print(f"  Rounds per match: {tournament_config['rounds_per_match']}")
        print(f"  Delay between games: {tournament_config['delay_between_games']}s")
        return
    
    # Handle configuration validation
    if args.validate:
        from config import validate_config
        if validate_config(config):
            print("Configuration validation passed")
        else:
            print("Configuration validation failed")
        return
    
    # Override configuration with command line arguments
    if args.server_url != 'http://localhost:50000':
        config.update_game_server_url(args.server_url)
    
    if args.timeout != 10:
        config.update_timeout(args.timeout)
    
    if args.rounds != 2:
        config.update_rounds_per_match(args.rounds)
    
    # Create arena
    server_config = config.get_game_server_config()
    tournament_config = config.get_tournament_config()
    
    arena = BridgeArena(
        game_server_url=server_config['url'],
        timeout=server_config['timeout'],
        rounds_per_match=tournament_config['rounds_per_match'],
        boards_per_match=tournament_config.get('boards_per_match', 12)
    )
    # Attach concurrency settings if present
    arena.max_parallel_matches = tournament_config.get('max_parallel_matches', 3)
    
    # Add AIs to arena
    ai_configs = config.get_ai_configs()
    ai_map = {}
    
    for ai_config in ai_configs:
        ai = arena.add_ai(
            ai_id=ai_config['ai_id'],
            ai_name=ai_config['ai_name'],
            port=ai_config['port']
        )
        ai_map[ai_config['ai_id']] = ai
    
    # Create teams
    team_configs = config.get_team_configs()
    
    if args.tournament_type == 'duplicate':
        # For duplicate format, create teams by duplicating AIs
        print("Creating duplicate teams (AA vs BB format)...")
        for ai_config in ai_configs:
            arena.create_duplicate_team(ai_map[ai_config['ai_id']])
    else:
        # For round robin, use configured teams
        print("Creating teams from configuration...")
        for team_config in team_configs:
            if team_config['player1'] in ai_map and team_config['player2'] in ai_map:
                arena.create_team(
                    team_id=team_config['team_id'],
                    team_name=team_config['team_name'],
                    ai1=ai_map[team_config['player1']],
                    ai2=ai_map[team_config['player2']]
                )
            else:
                print(f"Warning: Team {team_config['team_id']} has invalid AI references")
    
    # Check if we have enough teams
    if len(arena.teams) < 2:
        print("Error: Not enough teams to start tournament")
        print("Available teams:")
        for team in arena.teams:
            print(f"  {team.team_name}")
        return
    
    # Start tournament
    print(f"\n=== Starting Bridge Tournament ===")
    print(f"Tournament type: {args.tournament_type}")
    print(f"Number of teams: {len(arena.teams)}")
    print(f"Rounds per match: {tournament_config['rounds_per_match']}")
    print(f"Game server: {server_config['url']}")
    print()
    
    try:
        report = arena.run_tournament(tournament_type=args.tournament_type)
        
        if report:
            print("\n=== Tournament Results ===")
            print(f"Tournament ID: {report.get('tournament_id', 'Unknown')}")
            mode = report.get('mode', args.tournament_type)

            if mode == 'duplicate_round_robin' or args.tournament_type == 'duplicate':
                # Duplicate tournament prints VP standings and match summary
                standings = report.get('standings', [])
                matches = report.get('matches', [])
                print(f"Mode: Duplicate (Round-Robin)")
                print(f"Boards per match: {report.get('boards_per_match')}")
                print(f"Teams participated: {len(standings)}")
                print(f"Total matches: {len(matches)}")

                print("\n=== Standings (VP) ===")
                for i, (team_id, stats) in enumerate(standings, 1):
                    team_name = stats.get('team_name', team_id)
                    vp = stats.get('vp', 0)
                    imp_net = stats.get('imp_net', 0)
                    matches_played = stats.get('matches', 0)
                    print(f"{i}. {team_name}")
                    print(f"   Matches: {matches_played}, VP: {vp}, IMP Net: {imp_net}")
            else:
                # Round-robin simple totals
                print(f"Total games: {report.get('total_games', 0)}")
                print(f"Teams participated: {report.get('teams', 0)}")

                print("\n=== Team Rankings ===")
                rankings = report.get('team_rankings', [])
                for i, (team_id, stats) in enumerate(rankings, 1):
                    print(f"{i}. {stats['team_name']}")
                    print(f"   Wins: {stats['wins']}, Losses: {stats['losses']}, Ties: {stats['ties']}")
                    print(f"   Total Score: {stats['total_score']}, Games: {stats['games_played']}")

            print(f"\nTournament report saved to: reports/tournament_{report.get('tournament_id', 'unknown')}.json")
        else:
            print("Tournament failed to complete")
            
    except KeyboardInterrupt:
        print("\nTournament interrupted by user")
    except Exception as e:
        print(f"Tournament error: {e}")

if __name__ == '__main__':
    main()
