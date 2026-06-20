#!/usr/bin/env python3
"""
Final validation script for Demo1 AI
Validates all requirements are met
"""

import os
import subprocess
import time
import requests
import json

def validate_files():
    """Validate all required files exist"""
    print("🔍 Validating files...")
    
    required_files = [
        'start_ai.sh',
        'demo1_ai.py',
        'requirements.txt',
        'README.md'
    ]
    
    for file in required_files:
        if os.path.exists(file):
            print(f"  ✓ {file} exists")
        else:
            print(f"  ✗ {file} missing")
            return False
    
    # Check start_ai.sh is executable
    if os.access('start_ai.sh', os.X_OK):
        print("  ✓ start_ai.sh is executable")
    else:
        print("  ✗ start_ai.sh is not executable")
        return False
    
    return True

def validate_start_script():
    """Validate start script works correctly"""
    print("\n🚀 Validating start script...")
    
    # Test without arguments
    result = subprocess.run(['bash', 'start_ai.sh'], 
                          capture_output=True, text=True)
    if result.returncode != 0 and "Usage:" in result.stdout:
        print("  ✓ Script correctly requires port argument")
    else:
        print("  ✗ Script should require port argument")
        return False
    
    # Test with invalid port
    result = subprocess.run(['bash', 'start_ai.sh', 'invalid'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print("  ✓ Script validates port number")
    else:
        print("  ✗ Script should validate port number")
        return False
    
    return True

def validate_ai_service():
    """Validate AI service functionality"""
    print("\n🤖 Validating AI service...")
    
    port = 9019
    
    # Start AI service
    print(f"  Starting AI on port {port}...")
    process = subprocess.Popen([
        'python3', 'demo1_ai.py', '--port', str(port)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for startup
    time.sleep(2)
    
    try:
        # Test health endpoint
        response = requests.get(f'http://localhost:{port}/health', timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            if health_data.get('status') == 'healthy' and health_data.get('ai_name') == 'demo1_AI':
                print("  ✓ Health endpoint working correctly")
            else:
                print("  ✗ Health endpoint response invalid")
                return False
        else:
            print(f"  ✗ Health endpoint failed: {response.status_code}")
            return False
        
        # Test action endpoint with sample data
        sample_game_state = {
            "game_id": "test",
            "phase": "preflop",
            "hand_number": 1,
            "pot": 30,
            "community_cards": [],
            "current_bet": 20,
            "min_raise": 40,
            "current_player": "demo1_AI",
            "players": {
                "demo1_AI": {
                    "player_id": "demo1_AI",
                    "name": "Demo1 AI",
                    "chips": 1000,
                    "hole_cards": ["As", "Kh"],
                    "state": "active",
                    "current_bet": 0,
                    "is_dealer": False,
                    "is_small_blind": False,
                    "is_big_blind": False
                }
            },
            "action_history": [],
            "dealer_index": 0,
            "small_blind": 10,
            "big_blind": 20,
            "valid_actions": [
                {"action": "fold", "amount": 0},
                {"action": "call", "amount": 20},
                {"action": "raise", "amount": {"min": 40, "max": 1000}}
            ]
        }
        
        response = requests.post(f'http://localhost:{port}/action',
                               json=sample_game_state,
                               headers={'Content-Type': 'application/json'},
                               timeout=5)
        
        if response.status_code == 200:
            decision = response.json()
            if 'action' in decision and 'amount' in decision:
                print(f"  ✓ Action endpoint working: {decision}")
            else:
                print("  ✗ Action endpoint response format invalid")
                return False
        else:
            print(f"  ✗ Action endpoint failed: {response.status_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"  ✗ Service validation failed: {e}")
        return False
    finally:
        # Clean up
        process.terminate()
        process.wait()

def main():
    """Main validation function"""
    print("Demo1 AI - Final Validation")
    print("=" * 50)
    
    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    all_passed = True
    
    # Run all validations
    if not validate_files():
        all_passed = False
    
    if not validate_start_script():
        all_passed = False
    
    if not validate_ai_service():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 ALL VALIDATIONS PASSED!")
        print("\nThe Demo1 AI is ready for tournament play!")
        print("\nTo start the AI:")
        print("  bash start_ai.sh 9013")
        print("\nTo check health:")
        print("  curl -s http://localhost:9013/health")
    else:
        print("❌ SOME VALIDATIONS FAILED!")
        print("Please fix the issues before deploying.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)