#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from typing import Dict, List

# =============================================================================
# 环境配置
# =============================================================================

# 游戏服务器配置
GAME_SERVER_CONFIG = {
    "url": "http://localhost:40000",
    "timeout": 10,  # AI响应超时时间(秒)
    "max_moves": 200
}

# 日志配置
LOGGING_CONFIG = {
    "level": "INFO",
    "file": "logs/arena.log",
    "console": True
}

# 锦标赛配置
TOURNAMENT_CONFIG = {
    "rounds_per_match": 2,  # 每对AI对战轮数
    "delay_between_games": 1,  # 对局间隔（秒）
    "max_games_per_ai": 10,  # 每个AI最大对局数
    "timeout_per_move": 10,  # 每步超时时间（秒）
    "max_game_duration": 3600  # 单局最大时长（秒）
}

# 报告配置
REPORTS_CONFIG = {
    "save_json": True,
    "save_txt": True,
    "save_csv": True,
    "output_dir": "reports"
}

# =============================================================================
# AI配置字典
# =============================================================================

# 参赛AI配置
AI_CONFIGS = {
    "SimpleAI_1": {
        "ai_id": "SimpleAI_1",
        "ai_name": "Simple Chess AI 1",
        "port": 40001,
        "algorithm": "simple",
        "description": "简单随机AI 1",
        "enabled": True
    },
    "MinimaxAI_1": {
        "ai_id": "MinimaxAI_1", 
        "ai_name": "Minimax Chess AI 1",
        "port": 40002,
        "algorithm": "minimax",
        "description": "Minimax算法AI 1",
        "enabled": True
    },
    "SimpleAI_2": {
        "ai_id": "SimpleAI_2",
        "ai_name": "Simple Chess AI 2", 
        "port": 40003,
        "algorithm": "simple",
        "description": "简单随机AI 2",
        "enabled": True
    }
}

# 快速AI配置（用于测试）
QUICK_AI_CONFIGS = {
    "TestAI_1": {
        "ai_id": "TestAI_1",
        "ai_name": "Test AI 1",
        "port": 40001,
        "algorithm": "simple",
        "description": "测试AI 1",
        "enabled": True
    },
    "TestAI_2": {
        "ai_id": "TestAI_2",
        "ai_name": "Test AI 2", 
        "port": 40002,
        "algorithm": "minimax",
        "description": "测试AI 2",
        "enabled": True
    },
    "TestAI_3": {
        "ai_id": "TestAI_3",
        "ai_name": "Test AI 3", 
        "port": 40003,
        "algorithm": "simple",
        "description": "测试AI 3",
        "enabled": True
    }
}

class ArenaConfig:
    """国际象棋AI对战平台配置管理"""
    
    def __init__(self, config_file: str = "configs/arena_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """加载配置文件"""
        default_config = {
            "game_server": GAME_SERVER_CONFIG,
            "logging": LOGGING_CONFIG,
            "tournament": TOURNAMENT_CONFIG,
            "reports": REPORTS_CONFIG,
            "ais": list(AI_CONFIGS.values())
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                        elif isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                if sub_key not in config[key]:
                                    config[key][sub_key] = sub_value
                    return config
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return default_config
        else:
            # 创建默认配置文件
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: Dict = None):
        """保存配置文件"""
        if config is None:
            config = self.config
        
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get_game_server_url(self) -> str:
        """获取游戏服务器URL"""
        return self.config["game_server"]["url"]
    
    def get_timeout(self) -> int:
        """获取超时时间"""
        return self.config["game_server"]["timeout"]
    
    def get_max_moves(self) -> int:
        """获取最大移动数"""
        return self.config["game_server"]["max_moves"]
    
    def get_ais(self) -> List[Dict]:
        """获取所有AI配置"""
        return self.config["ais"]
    
    def get_enabled_ais(self) -> List[Dict]:
        """获取启用的AI配置"""
        return [ai for ai in self.config["ais"] if ai.get("enabled", True)]
    
    def get_ai_config(self, ai_id: str) -> Dict:
        """获取指定AI的配置"""
        for ai in self.config["ais"]:
            if ai["ai_id"] == ai_id:
                return ai
        return None
    
    def add_ai(self, ai_id: str, ai_name: str, port: int, algorithm: str = "simple", description: str = "", enabled: bool = True):
        """添加AI配置"""
        ai_config = {
            "ai_id": ai_id,
            "ai_name": ai_name,
            "port": port,
            "algorithm": algorithm,
            "description": description,
            "enabled": enabled
        }
        
        # 检查是否已存在
        for i, ai in enumerate(self.config["ais"]):
            if ai["ai_id"] == ai_id:
                self.config["ais"][i] = ai_config
                break
        else:
            self.config["ais"].append(ai_config)
        
        self.save_config()
    
    def remove_ai(self, ai_id: str):
        """移除AI配置"""
        self.config["ais"] = [ai for ai in self.config["ais"] if ai["ai_id"] != ai_id]
        self.save_config()
    
    def enable_ai(self, ai_id: str, enabled: bool = True):
        """启用/禁用AI"""
        for ai in self.config["ais"]:
            if ai["ai_id"] == ai_id:
                ai["enabled"] = enabled
                break
        self.save_config()
    
    def get_tournament_config(self) -> Dict:
        """获取锦标赛配置"""
        return self.config["tournament"]
    
    def get_logging_config(self) -> Dict:
        """获取日志配置"""
        return self.config["logging"]
    
    def get_reports_config(self) -> Dict:
        """获取报告配置"""
        return self.config["reports"]
    
    def get_error_handling_config(self) -> Dict:
        """获取错误处理配置"""
        tournament_config = self.config.get("tournament", {})
        error_handling = tournament_config.get("error_handling", {})
        return {
            "timeout_is_loss": error_handling.get("timeout_is_loss", False),
            "http_error_is_loss": error_handling.get("http_error_is_loss", False),
            "connection_error_is_loss": error_handling.get("connection_error_is_loss", False),
            "invalid_move_is_loss": error_handling.get("invalid_move_is_loss", False)
        }
    
    def set_ai_configs(self, ai_configs: Dict):
        """设置AI配置"""
        self.config["ais"] = list(ai_configs.values())
        self.save_config()
    
    def load_quick_config(self):
        """加载快速测试配置"""
        self.set_ai_configs(QUICK_AI_CONFIGS)

def create_sample_config():
    """创建示例配置文件"""
    config = ArenaConfig()
    config.save_config()
    print(f"示例配置文件已创建: {config.config_file}")

def create_quick_config():
    """创建快速测试配置"""
    config = ArenaConfig()
    config.load_quick_config()
    print("快速测试配置已加载")

if __name__ == "__main__":
    create_sample_config() 