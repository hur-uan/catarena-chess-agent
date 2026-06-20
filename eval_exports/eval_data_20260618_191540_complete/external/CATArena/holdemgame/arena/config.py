import logging

# --- Logging Configuration ---
LOGGING_CONFIG = {
    "level": logging.INFO,
    "format": '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    "file": "logs/arena.log"
}

# --- Game Server Configuration ---
GAME_SERVER_CONFIG = {
    "url": "http://localhost:9011",
    "timeout": 10
}

# --- Tournament Configuration ---
TOURNAMENT_CONFIG = {
    "rounds": 3,
    "delay_between_hands": 0.01,
    "initial_chips": 1000,
    "max_players": 10,
    "max_hands_per_round": 80,
    "blind_structure_file": "arena/blind_structure.json"
}

# --- AI Configuration ---
# Standard configuration for multiple different AI services
AI_CONFIGS = [
    {
        "ai_id": "ai_1",
        "ai_name": "AlphaBot",
        "port": 31010,
        "url": "http://localhost:31010",
        "description": "Advanced AI Player 1"
    },
    {
        "ai_id": "ai_2",
        "ai_name": "BetaBot",
        "port": 31011,
        "url": "http://localhost:31011",
        "description": "Advanced AI Player 2"
    },
    {
        "ai_id": "ai_3",
        "ai_name": "GammaBot",
        "port": 31012,
        "url": "http://localhost:31012",
        "description": "Advanced AI Player 3"
    }
]

# Quick-start configuration for testing with a single AI service
QUICK_AI_CONFIGS = [
    {
        "ai_id": f"quick_ai_{i}",
        "ai_name": f"QuickBot {i}",
        "port": 31010 + i,
        "url": f"http://localhost:{31010 + i}",
        "description": f"Quick Test AI {i}"
    } for i in range(TOURNAMENT_CONFIG["max_players"])
]

# --- Blind Structure ---
# Default blind structure if no file is specified
BLIND_STRUCTURE = {
    "levels": [
        {"level": 1, "small_blind": 5, "big_blind": 10, "duration": 10}, # duration in hands
        {"level": 2, "small_blind": 10, "big_blind": 20, "duration": 10},
        {"level": 3, "small_blind": 15, "big_blind": 30, "duration": 10},
        {"level": 4, "small_blind": 25, "big_blind": 50, "duration": 10},
    ]
}