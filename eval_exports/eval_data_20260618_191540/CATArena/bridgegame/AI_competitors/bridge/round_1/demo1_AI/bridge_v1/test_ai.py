#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time

def test_ai_service():
    """Test the AI service basic functionality"""
    ai_url = "http://localhost:50017"
    game_server_url = "http://localhost:9030"
    
    print("=== Testing demo1 Bridge AI ===")
    
    # Test health
    print("1. Testing health endpoint...")
    response = requests.get(f"{ai_url}/health")
    print(f"Health: {response.json()}")
    
    # Test info
    print("2. Testing info endpoint...")
    response = requests.get(f"{ai_url}/info")
    print(f"Info: {response.json()}")
    
    # Create a game
    print("3. Creating a game...")
    response = requests.post(f"{game_server_url}/games", 
                           headers={"Content-Type": "application/json"}, 
                           json={})
    if response.status_code not in [200, 201]:
        print(f"Failed to create game: {response.status_code} - {response.text}")
        return
    
    game_data = response.json()
    game_id = game_data["game_id"]
    print(f"Created game: {game_id}")
    
    # Join game
    print("4. Joining game...")
    join_data = {"game_id": game_id, "player_id": 0}
    response = requests.post(f"{ai_url}/join_game", json=join_data)
    print(f"Join result: {response.json()}")
    
    # Add other players (simple bots)
    for player_id in [1, 2, 3]:
        join_data = {"player_id": player_id, "player_name": f"TestBot_{player_id}"}
        requests.post(f"{game_server_url}/games/{game_id}/join", json=join_data)
    
    # Start game
    print("5. Starting game...")
    response = requests.post(f"{game_server_url}/games/{game_id}/start")
    print(f"Start result: {response.status_code}")
    
    # Get game state
    print("6. Getting game state...")
    response = requests.get(f"{game_server_url}/games/{game_id}/state", params={"player_id": 0})
    if response.status_code == 200:
        game_state = response.json()
        print(f"Game phase: {game_state.get('phase')}")
        print(f"Current player: {game_state.get('current_player_id')}")
        
        # Test get_action if it's our turn
        if game_state.get('current_player_id') == 0:
            print("7. Testing get_action...")
            action_data = {"game_id": game_id, "game_state": game_state}
            response = requests.post(f"{ai_url}/get_action", json=action_data)
            if response.status_code == 200:
                action = response.json()
                print(f"AI action: {action}")
            else:
                print(f"Get action failed: {response.status_code} - {response.text}")
        else:
            print(f"Not our turn (current player: {game_state.get('current_player_id')})")
    
    # Test leave game
    print("8. Testing leave game...")
    leave_data = {"game_id": game_id}
    response = requests.post(f"{ai_url}/leave_game", json=leave_data)
    print(f"Leave result: {response.json()}")
    
    # Clean up
    requests.delete(f"{game_server_url}/games/{game_id}")
    
    print("=== Test completed ===")

if __name__ == "__main__":
    test_ai_service()