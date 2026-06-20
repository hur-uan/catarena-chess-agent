#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time

def test_ai_service():
    """Test the AI service functionality"""
    ai_url = "http://localhost:50009"
    game_server_url = "http://localhost:9000"
    
    print("=== Testing Demo1 AI Service ===")
    
    # Test health check
    print("1. Testing health check...")
    response = requests.get(f"{ai_url}/health")
    print(f"Health: {response.json()}")
    
    # Test AI info
    print("\n2. Testing AI info...")
    response = requests.get(f"{ai_url}/info")
    print(f"Info: {response.json()}")
    
    # Create a test game
    print("\n3. Creating test game...")
    game_data = {
        "player_black": "demo1_AI",
        "player_white": "test_player"
    }
    response = requests.post(f"{game_server_url}/games", json=game_data)
    game_info = response.json()
    game_id = game_info["game_id"]
    print(f"Game created: {game_info}")
    
    # Join the game
    print("\n4. Joining game...")
    join_data = {
        "game_id": game_id,
        "my_color": "black",
        "game_server_url": game_server_url
    }
    response = requests.post(f"{ai_url}/join_game", json=join_data)
    print(f"Join result: {response.json()}")
    
    # Get initial game state
    print("\n5. Getting game state...")
    response = requests.get(f"{game_server_url}/games/{game_id}/state")
    game_state = response.json()
    print(f"Game state: {game_state}")
    
    # Test AI move
    print("\n6. Testing AI move...")
    move_data = {
        "game_id": game_id,
        "board": game_state["board"],
        "current_player": "black"
    }
    response = requests.post(f"{ai_url}/get_move", json=move_data)
    ai_move = response.json()
    print(f"AI move: {ai_move}")
    
    # Make the move on the game server
    print("\n7. Making move on game server...")
    server_move_data = {
        "player": "black",
        "position": ai_move["move"]
    }
    response = requests.post(f"{game_server_url}/games/{game_id}/move", json=server_move_data)
    move_result = response.json()
    print(f"Move result: {move_result}")
    
    # Test a few more moves
    print("\n8. Testing multiple moves...")
    for i in range(3):
        # Get current state
        response = requests.get(f"{game_server_url}/games/{game_id}/state")
        game_state = response.json()
        
        if game_state["game_status"] != "ongoing":
            print(f"Game ended: {game_state['game_status']}")
            break
        
        current_player = game_state["current_player"]
        print(f"\nMove {i+2}, current player: {current_player}")
        
        if current_player == "black":
            # AI move
            move_data = {
                "game_id": game_id,
                "board": game_state["board"],
                "current_player": "black"
            }
            response = requests.post(f"{ai_url}/get_move", json=move_data)
            ai_move = response.json()
            
            server_move_data = {
                "player": "black",
                "position": ai_move["move"]
            }
            response = requests.post(f"{game_server_url}/games/{game_id}/move", json=server_move_data)
            print(f"AI move: {ai_move['move']}, result: {response.json()}")
        else:
            # Random move for white player
            board = game_state["board"]
            empty_positions = []
            for i in range(15):
                for j in range(15):
                    if board[i][j] == 0:
                        empty_positions.append([i, j])
            
            if empty_positions:
                import random
                random_move = random.choice(empty_positions)
                server_move_data = {
                    "player": "white",
                    "position": random_move
                }
                response = requests.post(f"{game_server_url}/games/{game_id}/move", json=server_move_data)
                print(f"Random white move: {random_move}, result: {response.json()}")
    
    # Leave game
    print("\n9. Leaving game...")
    leave_data = {"game_id": game_id}
    response = requests.post(f"{ai_url}/leave_game", json=leave_data)
    print(f"Leave result: {response.json()}")
    
    print("\n=== Test completed successfully! ===")

if __name__ == "__main__":
    test_ai_service()