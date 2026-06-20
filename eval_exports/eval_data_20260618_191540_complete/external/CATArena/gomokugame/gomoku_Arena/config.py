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
    "url": "http://localhost:9000",
    "timeout": 10,  # AI响应超时时间(秒)
    "board_size": 15
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
    "max_games_per_ai": 10  # 每个AI最大对局数
}

# =============================================================================
# AI配置字典
# =============================================================================

# 参赛AI配置
AI_CONFIGS = {
    "AI_Alpha": {
        "ai_id": "AI_Alpha",
        "ai_name": "Alpha AI",
        "port": 11001,
        "description": "基础五子棋AI"
    },
    "AI_Beta": {
        "ai_id": "AI_Beta", 
        "ai_name": "Beta AI",
        "port": 11002,
        "description": "改进版五子棋AI"
    },
    "AI_Gamma": {
        "ai_id": "AI_Gamma",
        "ai_name": "Gamma AI", 
        "port": 11003,
        "description": "高级五子棋AI"
    }
}

# 快速AI配置（用于测试）
QUICK_AI_CONFIGS = {
    "AI_Test1": {
        "ai_id": "AI_Test1",
        "ai_name": "Test AI 1",
        "port": 11001,
        "description": "测试AI 1"
    },
    "AI_Test2": {
        "ai_id": "AI_Test2",
        "ai_name": "Test AI 2", 
        "port": 11002,
        "description": "测试AI 2"
    }
}

class ArenaConfig:
    """AI对战平台配置管理"""
    
    def __init__(self, config_file: str = "configs/arena_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """加载配置文件"""
        default_config = {
            "game_server": GAME_SERVER_CONFIG,
            "logging": LOGGING_CONFIG,
            "tournament": TOURNAMENT_CONFIG,
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
            self.save_config(default_config)
            return default_config
    
    def save_config(self, config: Dict = None):
        """保存配置文件"""
        if config is None:
            config = self.config
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"配置文件已保存: {self.config_file}")
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def get_game_server_url(self) -> str:
        """获取游戏服务器地址"""
        return self.config["game_server"]["url"]
    
    def get_timeout(self) -> int:
        """获取超时时间"""
        return self.config["game_server"]["timeout"]
    
    def get_board_size(self) -> int:
        """获取棋盘大小"""
        return self.config["game_server"]["board_size"]
    
    def get_ais(self) -> List[Dict]:
        """获取AI列表"""
        return self.config["ais"]
    
    def get_ai_config(self, ai_id: str) -> Dict:
        """获取特定AI配置"""
        for ai in self.config["ais"]:
            if ai["ai_id"] == ai_id:
                return ai
        return None
    
    def add_ai(self, ai_id: str, ai_name: str, port: int, description: str = ""):
        """添加AI配置"""
        ai_config = {
            "ai_id": ai_id,
            "ai_name": ai_name,
            "port": port,
            "description": description
        }
        
        # 检查是否已存在
        for ai in self.config["ais"]:
            if ai["ai_id"] == ai_id:
                print(f"AI {ai_id} 已存在，更新配置")
                ai.update(ai_config)
                break
        else:
            self.config["ais"].append(ai_config)
        
        self.save_config()
    
    def remove_ai(self, ai_id: str):
        """移除AI配置"""
        self.config["ais"] = [ai for ai in self.config["ais"] if ai["ai_id"] != ai_id]
        self.save_config()
    
    def get_tournament_config(self) -> Dict:
        """获取锦标赛配置"""
        return self.config["tournament"]
    
    def get_logging_config(self) -> Dict:
        """获取日志配置"""
        return self.config["logging"]
    
    def set_ai_configs(self, ai_configs: Dict):
        """设置AI配置字典"""
        self.config["ais"] = list(ai_configs.values())
        self.save_config()
    
    def load_quick_config(self):
        """加载快速测试配置"""
        self.set_ai_configs(QUICK_AI_CONFIGS)
        print("已加载快速测试配置")

def create_sample_config():
    """创建示例配置文件"""
    config = ArenaConfig()
    config.set_ai_configs(AI_CONFIGS)
    print("示例配置文件已创建: configs/arena_config.json")
    print("请根据实际情况修改AI配置")

def create_quick_config():
    """创建快速测试配置"""
    config = ArenaConfig("configs/quick_config.json")
    config.load_quick_config()
    print("快速测试配置文件已创建: configs/quick_config.json")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "quick":
            create_quick_config()
        else:
            create_sample_config()
    else:
        create_sample_config() 