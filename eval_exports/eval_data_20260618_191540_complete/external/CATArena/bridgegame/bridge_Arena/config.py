#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from typing import Dict, List

# =============================================================================
# Environment Configuration
# =============================================================================

# Game server configuration
GAME_SERVER_CONFIG = {
    "url": "http://localhost:9030",  # Bridge server default port
    "timeout": 10,  # AI response timeout (seconds)
}

# Logging configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "file": "logs/arena.log",
    "console": True
}

# Tournament configuration
TOURNAMENT_CONFIG = {
    "rounds_per_match": 1,  # per match (ignored for duplicate RR)
    "boards_per_match": 12,  # Default to 12 boards per match
    "delay_between_games": 1,  # Delay between games (seconds)
    "max_games_per_team": 10,  # Maximum games per team
    "max_parallel_matches": 3  # Concurrent matches per round (for 6 teams, 3 matches)
}

# =============================================================================
# AI Configuration Dictionary
# =============================================================================

# Participating AI configurations
AI_CONFIGS = {
    "AI_Alpha": {
        "ai_id": "AI_Alpha",
        "ai_name": "Alpha AI",
        "port": 50001,
        "description": "Basic bridge AI"
    },
    "AI_Beta": {
        "ai_id": "AI_Beta", 
        "ai_name": "Beta AI",
        "port": 50002,
        "description": "Improved bridge AI"
    },
    "AI_Gamma": {
        "ai_id": "AI_Gamma",
        "ai_name": "Gamma AI", 
        "port": 50003,
        "description": "Advanced bridge AI"
    },
    "AI_Delta": {
        "ai_id": "AI_Delta",
        "ai_name": "Delta AI",
        "port": 50004,
        "description": "Expert bridge AI"
    }
}

# Quick AI configurations (for testing)
QUICK_AI_CONFIGS = {
    "AI_Test1": {
        "ai_id": "AI_Test1",
        "ai_name": "Test AI 1",
        "port": 50001,
        "description": "Test AI 1"
    },
    "AI_Test2": {
        "ai_id": "AI_Test2",
        "ai_name": "Test AI 2", 
        "port": 50002,
        "description": "Test AI 2"
    }
}

# Team configurations
TEAM_CONFIGS = {
    "Team_Alpha_Beta": {
        "team_id": "Team_Alpha_Beta",
        "team_name": "Alpha-Beta Team",
        "player1": "AI_Alpha",
        "player2": "AI_Beta",
        "description": "Alpha and Beta AI team"
    },
    "Team_Gamma_Delta": {
        "team_id": "Team_Gamma_Delta", 
        "team_name": "Gamma-Delta Team",
        "player1": "AI_Gamma",
        "player2": "AI_Delta",
        "description": "Gamma and Delta AI team"
    }
}

class ArenaConfig:
    """Bridge AI tournament platform configuration management"""
    
    def __init__(self, config_file: str = "configs/arena_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """Load configuration file"""
        default_config = {
            "game_server": GAME_SERVER_CONFIG,
            "logging": LOGGING_CONFIG,
            "tournament": TOURNAMENT_CONFIG,
            "ais": list(AI_CONFIGS.values()),
            "teams": list(TEAM_CONFIGS.values())
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Merge with default configuration
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                        elif isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                if sub_key not in config[key]:
                                    config[key][sub_key] = sub_value
                    return config
            except Exception as e:
                print(f"Error loading config file: {e}")
                return default_config
        else:
            # Create default config file
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            return default_config
    
    def save_config(self):
        """Save configuration to file"""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def get_game_server_config(self) -> Dict:
        """Get game server configuration"""
        return self.config.get("game_server", GAME_SERVER_CONFIG)
    
    def get_logging_config(self) -> Dict:
        """Get logging configuration"""
        return self.config.get("logging", LOGGING_CONFIG)
    
    def get_tournament_config(self) -> Dict:
        """Get tournament configuration"""
        return self.config.get("tournament", TOURNAMENT_CONFIG)
    
    def get_ai_configs(self) -> List[Dict]:
        """Get AI configurations"""
        return self.config.get("ais", list(AI_CONFIGS.values()))
    
    def get_team_configs(self) -> List[Dict]:
        """Get team configurations"""
        return self.config.get("teams", list(TEAM_CONFIGS.values()))
    
    def add_ai_config(self, ai_config: Dict):
        """Add AI configuration"""
        self.config["ais"].append(ai_config)
        self.save_config()
    
    def add_team_config(self, team_config: Dict):
        """Add team configuration"""
        self.config["teams"].append(team_config)
        self.save_config()
    
    def update_game_server_url(self, url: str):
        """Update game server URL"""
        self.config["game_server"]["url"] = url
        self.save_config()
    
    def update_timeout(self, timeout: int):
        """Update AI timeout"""
        self.config["game_server"]["timeout"] = timeout
        self.save_config()
    
    def update_rounds_per_match(self, rounds: int):
        """Update rounds per match"""
        self.config["tournament"]["rounds_per_match"] = rounds
        self.save_config()

# =============================================================================
# Quick Configuration Functions
# =============================================================================

def create_quick_config():
    """Create quick configuration for testing"""
    config = ArenaConfig("configs/quick_config.json")
    config.config["ais"] = list(QUICK_AI_CONFIGS.values())
    config.save_config()
    return config

def create_duplicate_teams_config():
    """Create configuration for duplicate teams (AA vs BB format)"""
    config = ArenaConfig("configs/duplicate_config.json")
    
    # Create duplicate teams
    duplicate_teams = []
    for ai_config in config.get_ai_configs():
        team_config = {
            "team_id": f"{ai_config['ai_id']}_duplicate",
            "team_name": f"{ai_config['ai_name']} Duplicate",
            "player1": ai_config['ai_id'],
            "player2": ai_config['ai_id'],
            "description": f"Duplicate team of {ai_config['ai_name']}"
        }
        duplicate_teams.append(team_config)
    
    config.config["teams"] = duplicate_teams
    config.save_config()
    return config

def create_mixed_teams_config():
    """Create configuration for mixed teams (AB vs CD format)"""
    config = ArenaConfig("configs/mixed_config.json")
    
    # Create mixed teams
    ai_configs = config.get_ai_configs()
    mixed_teams = []
    
    for i in range(0, len(ai_configs), 2):
        if i + 1 < len(ai_configs):
            ai1 = ai_configs[i]
            ai2 = ai_configs[i + 1]
            team_config = {
                "team_id": f"Team_{ai1['ai_id']}_{ai2['ai_id']}",
                "team_name": f"{ai1['ai_name']}-{ai2['ai_name']} Team",
                "player1": ai1['ai_id'],
                "player2": ai2['ai_id'],
                "description": f"Mixed team of {ai1['ai_name']} and {ai2['ai_name']}"
            }
            mixed_teams.append(team_config)
    
    config.config["teams"] = mixed_teams
    config.save_config()
    return config

# =============================================================================
# Configuration Validation
# =============================================================================

def validate_ai_config(ai_config: Dict) -> bool:
    """Validate AI configuration"""
    required_fields = ["ai_id", "ai_name", "port"]
    for field in required_fields:
        if field not in ai_config:
            print(f"Missing required field: {field}")
            return False
    
    if not isinstance(ai_config["port"], int) or ai_config["port"] <= 0:
        print("Port must be a positive integer")
        return False
    
    return True

def validate_team_config(team_config: Dict, ai_configs: List[Dict]) -> bool:
    """Validate team configuration"""
    required_fields = ["team_id", "team_name", "player1", "player2"]
    for field in required_fields:
        if field not in team_config:
            print(f"Missing required field: {field}")
            return False
    
    # Check if player1 and player2 exist in AI configs
    ai_ids = [ai["ai_id"] for ai in ai_configs]
    if team_config["player1"] not in ai_ids:
        print(f"Player1 {team_config['player1']} not found in AI configs")
        return False
    
    if team_config["player2"] not in ai_ids:
        print(f"Player2 {team_config['player2']} not found in AI configs")
        return False
    
    return True

def validate_config(config: ArenaConfig) -> bool:
    """Validate entire configuration"""
    ai_configs = config.get_ai_configs()
    team_configs = config.get_team_configs()
    
    # Validate AI configs
    for ai_config in ai_configs:
        if not validate_ai_config(ai_config):
            return False
    
    # Validate team configs
    for team_config in team_configs:
        if not validate_team_config(team_config, ai_configs):
            return False
    
    return True

if __name__ == "__main__":
    # Test configuration
    config = ArenaConfig()
    print("Default configuration loaded successfully")
    
    if validate_config(config):
        print("Configuration validation passed")
    else:
        print("Configuration validation failed")
