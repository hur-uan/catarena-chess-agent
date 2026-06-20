#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import random

def test_integration_with_main_server():
    """Test integration with the main chess server"""
    
    main_server = "http://localhost:9020"
    ai_server = "http://localhost:52003"
    
    print("Testing integration with main chess server...")
    print("=" * 50)
    
    # Check if main server is running
    try:
        response = requests.get(f"{main_server}/health", timeout=5)
        if response.status_code != 200:
            print("✗ Main chess server is not running")
            return False
        print("✓ Main chess server is running")
    except Exception as e:
        print(f"✗ Cannot connect to main server: {e}")
        return False
    
    # Check if AI server is running
    try:
        response = requests.get(f"{ai_server}/health", timeout=5)
        if response.status_code != 200:
            print("✗ AI server is not running")
            return False
        ai_data = response.json()
        print(f"✓ AI server is running: {ai_data['ai_name']}")
    except Exception as e:
        print(f"✗ Cannot connect to AI server: {e}")
        return False
    
    # Create a new game
    game_id = f"test_game_{random.randint(1000, 9999)}"
    try:
        create_payload = {
            "player_white": "demo1_AI",
            "player_black": "Human_Player"
        }
        response = requests.post(f"{main_server}/games", json=create_payload, timeout=5)
        if response.status_code != 200:
            print(f"✗ Failed to create game: {response.status_code}")
            return False
        
        game_data = response.json()
        actual_game_id = game_data["game_id"]
        print(f"✓ Created game: {actual_game_id}")
        
    except Exception as e:
        print(f"✗ Error creating game: {e}")
        return False
    
    # Get initial game state
    try:
        response = requests.get(f"{main_server}/games/{actual_game_id}/state", timeout=5)
        if response.status_code != 200:
            print(f"✗ Failed to get game state: {response.status_code}")
            return False
        
        state_data = response.json()
        print(f"✓ Got initial game state, current player: {state_data['current_player']}")
        
    except Exception as e:
        print(f"✗ Error getting game state: {e}")
        return False
    
    # Test AI move generation for the position
    try:
        ai_payload = {
            "fen": state_data["fen"],
            "algorithm": "advanced"
        }
        response = requests.post(f"{ai_server}/move", json=ai_payload, timeout=10)
        if response.status_code != 200:
            print(f"✗ AI failed to generate move: {response.status_code}")
            return False
        
        ai_move_data = response.json()
        suggested_move = ai_move_data["move"]
        print(f"✓ AI suggests move: {suggested_move} ({ai_move_data['san']})")
        
    except Exception as e:
        print(f"✗ Error getting AI move: {e}")
        return False
    
    # Test making the AI's suggested move
    try:
        move_payload = {
            "player": state_data["current_player"],
            "move": suggested_move
        }
        response = requests.post(f"{main_server}/games/{actual_game_id}/move", json=move_payload, timeout=5)
        if response.status_code != 200:
            print(f"✗ Failed to make move: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        move_result = response.json()
        print(f"✓ Move executed successfully: {move_result['status']}")
        print(f"  New current player: {move_result['new_state']['current_player']}")
        
    except Exception as e:
        print(f"✗ Error making move: {e}")
        return False
    
    # Get game history
    try:
        response = requests.get(f"{main_server}/games/{actual_game_id}/history", timeout=5)
        if response.status_code == 200:
            history_data = response.json()
            print(f"✓ Game history retrieved: {len(history_data['moves'])} moves")
        else:
            print(f"⚠ Could not get game history: {response.status_code}")
    except Exception as e:
        print(f"⚠ Error getting game history: {e}")
    
    print("\n" + "=" * 50)
    print("✓ Integration test completed successfully!")
    print("The AI can successfully:")
    print("  - Connect to the main chess server")
    print("  - Generate valid moves for chess positions")
    print("  - Integrate with the tournament system")
    
    return True

if __name__ == "__main__":
    success = test_integration_with_main_server()
    if not success:
        print("\n✗ Integration test failed!")
        exit(1)