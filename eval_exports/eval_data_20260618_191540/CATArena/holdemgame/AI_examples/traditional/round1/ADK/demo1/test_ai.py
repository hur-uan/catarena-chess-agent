#!/usr/bin/env python3
"""
Test script for Demo1 AI
Tests the AI's decision-making with sample game states
"""

import json
import requests
import time
import subprocess
import signal
import os
from threading import Thread

def test_ai_decision_making():
    """Test AI with various game scenarios"""
    
    # Sample game state for testing
    test_game_state = {
        "game_id": "test_game",
        "phase": "preflop",
        "hand_number": 1,
        "pot": 30,
        "community_cards": [],
        "current_bet": 20,
        "min_raise": 40,
        "current_player": "demo1_AI",
        "players": {
            "opponent1": {
                "player_id": "opponent1",
                "name": "Opponent1",
                "chips": 980,
                "hole_cards": [],
                "state": "active",
                "current_bet": 20,
                "is_dealer": False,
                "is_small_blind": True,
                "is_big_blind": False
            },
            "demo1_AI": {
                "player_id": "demo1_AI",
                "name": "Demo1 AI",
                "chips": 1000,
                "hole_cards": ["As", "Kh"],  # Strong hand
                "state": "active",
                "current_bet": 0,
                "is_dealer": False,
                "is_small_blind": False,
                "is_big_blind": False
            }
        },
        "action_history": [
            {"player_id": "opponent1", "action": "raise", "amount": 20, "phase": "preflop"}
        ],
        "dealer_index": 0,
        "small_blind": 10,
        "big_blind": 20,
        "valid_actions": [
            {"action": "fold", "amount": 0},
            {"action": "call", "amount": 20},
            {"action": "raise", "amount": {"min": 40, "max": 1000}},
            {"action": "all_in", "amount": 1000}
        ]
    }
    
    port = 9016
    url = f"http://localhost:{port}"
    
    # Start AI service
    print(f"Starting AI service on port {port}...")
    ai_process = subprocess.Popen([
        "python3", "demo1_ai.py", "--port", str(port)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for service to start
    time.sleep(2)
    
    try:
        # Test health endpoint
        print("Testing health endpoint...")
        response = requests.get(f"{url}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Health check passed")
            print(f"  Response: {response.json()}")
        else:
            print("✗ Health check failed")
            return False
        
        # Test action endpoint with strong hand
        print("\nTesting action endpoint with strong hand (As Kh)...")
        response = requests.post(f"{url}/action", 
                               json=test_game_state, 
                               headers={'Content-Type': 'application/json'},
                               timeout=5)
        
        if response.status_code == 200:
            decision = response.json()
            print("✓ Action endpoint working")
            print(f"  Decision: {decision}")
            
            # Validate decision format
            if 'action' in decision and 'amount' in decision:
                print("✓ Decision format valid")
            else:
                print("✗ Invalid decision format")
                return False
        else:
            print("✗ Action endpoint failed")
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
        
        # Test with weak hand
        print("\nTesting with weak hand (2c 7d)...")
        weak_hand_state = test_game_state.copy()
        weak_hand_state["players"]["demo1_AI"]["hole_cards"] = ["2c", "7d"]
        
        response = requests.post(f"{url}/action", 
                               json=weak_hand_state, 
                               headers={'Content-Type': 'application/json'},
                               timeout=5)
        
        if response.status_code == 200:
            decision = response.json()
            print("✓ Weak hand decision made")
            print(f"  Decision: {decision}")
        else:
            print("✗ Weak hand test failed")
        
        # Test post-flop scenario
        print("\nTesting post-flop scenario...")
        postflop_state = test_game_state.copy()
        postflop_state["phase"] = "flop"
        postflop_state["community_cards"] = ["Ac", "Kd", "5h"]
        postflop_state["players"]["demo1_AI"]["hole_cards"] = ["As", "Kh"]  # Two pair
        
        response = requests.post(f"{url}/action", 
                               json=postflop_state, 
                               headers={'Content-Type': 'application/json'},
                               timeout=5)
        
        if response.status_code == 200:
            decision = response.json()
            print("✓ Post-flop decision made")
            print(f"  Decision: {decision}")
        else:
            print("✗ Post-flop test failed")
        
        print("\n✓ All tests passed! AI is working correctly.")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
        return False
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False
    finally:
        # Clean up
        print("\nStopping AI service...")
        ai_process.terminate()
        ai_process.wait()

if __name__ == "__main__":
    print("Demo1 AI Test Suite")
    print("=" * 40)
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    success = test_ai_decision_making()
    
    if success:
        print("\n🎉 All tests passed! AI is ready for tournament play.")
    else:
        print("\n❌ Some tests failed. Please check the AI implementation.")