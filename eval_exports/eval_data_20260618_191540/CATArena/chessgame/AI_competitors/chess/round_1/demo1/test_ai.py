#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import time
import subprocess
import signal
import os
import sys

def test_ai_service(port=52003):
    """Test the Demo1 Chess AI service"""
    base_url = f"http://localhost:{port}"
    
    print(f"Testing Demo1 Chess AI on port {port}")
    print("=" * 50)
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Health check passed: {data['status']}")
            print(f"   AI ID: {data['ai_id']}")
            print(f"   AI Name: {data['ai_name']}")
        else:
            print(f"   ✗ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Health check error: {e}")
        return False
    
    # Test 2: AI info
    print("\n2. Testing AI info...")
    try:
        response = requests.get(f"{base_url}/info", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ AI info retrieved")
            print(f"   Name: {data['name']}")
            print(f"   Description: {data['description']}")
            print(f"   Capabilities: {', '.join(data['capabilities'])}")
        else:
            print(f"   ✗ AI info failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ AI info error: {e}")
        return False
    
    # Test 3: Opening move
    print("\n3. Testing opening move...")
    try:
        opening_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        payload = {
            "fen": opening_fen,
            "algorithm": "advanced"
        }
        response = requests.post(f"{base_url}/move", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Opening move: {data['move']} ({data['san']})")
            print(f"   Thinking time: {data['thinking_time']}s")
            print(f"   Evaluation: {data['evaluation']}")
        else:
            print(f"   ✗ Opening move failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Opening move error: {e}")
        return False
    
    # Test 4: Middle game position
    print("\n4. Testing middle game position...")
    try:
        middle_fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 4 4"
        payload = {
            "fen": middle_fen,
            "algorithm": "advanced"
        }
        response = requests.post(f"{base_url}/move", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Middle game move: {data['move']} ({data['san']})")
            print(f"   Thinking time: {data['thinking_time']}s")
            print(f"   Evaluation: {data['evaluation']}")
        else:
            print(f"   ✗ Middle game move failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Middle game move error: {e}")
        return False
    
    # Test 5: Tactical position (capture available)
    print("\n5. Testing tactical position...")
    try:
        tactical_fen = "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 4 3"
        payload = {
            "fen": tactical_fen,
            "algorithm": "advanced"
        }
        response = requests.post(f"{base_url}/move", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ Tactical move: {data['move']} ({data['san']})")
            print(f"   Thinking time: {data['thinking_time']}s")
            print(f"   Evaluation: {data['evaluation']}")
        else:
            print(f"   ✗ Tactical move failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Tactical move error: {e}")
        return False
    
    # Test 6: Game management endpoints
    print("\n6. Testing game management...")
    try:
        # Test join game
        join_payload = {
            "game_id": "test_game_123",
            "my_color": "white",
            "game_server_url": "http://localhost:40000"
        }
        response = requests.post(f"{base_url}/join_game", json=join_payload, timeout=5)
        if response.status_code == 200:
            print("   ✓ Join game successful")
        else:
            print(f"   ✗ Join game failed: {response.status_code}")
            return False
        
        # Test list games
        response = requests.get(f"{base_url}/games", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ List games: {len(data['active_games'])} active games")
        else:
            print(f"   ✗ List games failed: {response.status_code}")
            return False
        
        # Test leave game
        leave_payload = {"game_id": "test_game_123"}
        response = requests.post(f"{base_url}/leave_game", json=leave_payload, timeout=5)
        if response.status_code == 200:
            print("   ✓ Leave game successful")
        else:
            print(f"   ✗ Leave game failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ✗ Game management error: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✓ All tests passed! Demo1 Chess AI is working correctly.")
    return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 test_ai.py <port>")
        sys.exit(1)
    
    try:
        port = int(sys.argv[1])
    except ValueError:
        print("Error: Port must be a number")
        sys.exit(1)
    
    # Wait a moment for the service to start
    print("Waiting for AI service to start...")
    time.sleep(2)
    
    success = test_ai_service(port)
    if not success:
        print("\n✗ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()