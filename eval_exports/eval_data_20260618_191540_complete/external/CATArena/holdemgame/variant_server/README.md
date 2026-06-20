# Six Plus Hold'em (Short-Deck) HTTP Server

A Flask-based Six Plus Hold'em (Short-Deck) HTTP server that supports multiplayer battles and complete game logic.

## Project Overview

This is a Six Plus Hold'em (Short-Deck) game environment that provides AI developers with a complete testing platform. The server implements the rules of Six Plus Hold'em, supports multiplayer battles, and provides RESTful API interfaces for AI client connections.

### Key Features
- Support for multiplayer battles (up to 12 players)
- Complete Six Plus Hold'em game logic
- Support for negative chips (continue battling after losing all chips)
- RESTful API interface
- Game state management
- Hand evaluation algorithm
- History record tracking
- Error handling mechanism

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Start Server

### Basic Startup
```bash
python server.py
```

### Using Startup Script
```bash
./start_server.sh
```

### Custom Parameter Startup
```bash
# Specify port
python server.py --port 30000

# Enable debug mode
python server.py --port 30000 --debug
```

### Parameter Description
- `--port`: Listen port (default: 30000)
- `--debug`: Enable debug mode

## Game Rules

This server implements **Six Plus Hold'em (Short-Deck)** rules.

### Key Rule Changes
*   **Deck:** The deck is simplified to 36 cards, removing all cards from 2 to 5.
*   **Hand Rankings:** A **Flush** now beats a **Full House**.
*   **Straights:** The Ace can be used to form a low-end straight (`A-6-7-8-9`).

### Hand Types (from high to low)
1. Royal Flush
2. Straight Flush
3. Four of a Kind
4. **Flush**
5. **Full House**
6. Straight
7. Three of a Kind
8. Two Pair
9. One Pair
10. High Card

### Card Representation
- Card values: 6, 7, 8, 9, T(10), J(11), Q(12), K(13), A(14)
- Suits: c(clubs), d(diamonds), h(hearts), s(spades)
- Example: "As" = Ace of spades, "Kh" = King of hearts


## API Interface

### 1. Create New Game
**POST** `/games`

**Request Body:**
```json
{
  "small_blind": 5,
  "big_blind": 10,
  "max_players": 6
}
```

**Response:**
```json
{
  "game_id": "holdem_001",
  "small_blind": 5,
  "big_blind": 10,
  "max_players": 6
}
```

### 2. Add Player
**POST** `/games/{game_id}/players`

**Request Body:**
```json
{
  "player_id": "player1",
  "name": "Alice",
  "chips": 1000
}
```

**Response:**
```json
{
  "status": "player_added",
  "player_id": "player1",
  "name": "Alice",
  "chips": 1000
}
```

### 3. Start Game
**POST** `/games/{game_id}/start`

**Response:**
```json
{
  "status": "game_started",
  "game_id": "holdem_001",
  "hand_number": 1
}
```

### 4. Get Game State
**GET** `/games/{game_id}/state?player_id={player_id}`

**Response:**
```json
{
  "game_id": "holdem_001",
  "phase": "preflop",
  "hand_number": 1,
  "pot": 30,
  "community_cards": [],
  "current_bet": 10,
  "min_raise": 10,
  "current_player": "player1",
  "players": {
    "player1": {
      "player_id": "player1",
      "name": "Alice",
      "chips": 990,
      "hole_cards": ["As", "Kh"],
      "state": "active",
      "current_bet": 10,
      "total_bet": 10,
      "is_dealer": false,
      "is_small_blind": false,
      "is_big_blind": true
    }
  },
  "action_history": [...],
  "dealer_index": 0,
  "small_blind": 5,
  "big_blind": 10
}
```

### 5. Get Valid Actions
**GET** `/games/{game_id}/actions?player_id={player_id}`

**Response:**
```json
{
  "valid_actions": [
    {"action": "fold", "amount": 0},
    {"action": "call", "amount": 10},
    {"action": "raise", "amount": 20},
    {"action": "all_in", "amount": 990}
  ]
}
```

### 6. Execute Action
**POST** `/games/{game_id}/action`

**Request Body:**
```json
{
  "player_id": "player1",
  "action": "call",
  "amount": 10
}
```

**Response:**
```json
{
  "status": "action_successful",
  "message": "Action successful"
}
```

### 7. Start Next Hand
**POST** `/games/{game_id}/next_hand`

**Response:**
```json
{
  "status": "next_hand_started",
  "hand_number": 2
}
```

### 8. Get Game History
**GET** `/games/{game_id}/history`

**Response:**
```json
{
  "action_history": [...],
  "hand_number": 1
}
```

### 9. Health Check
**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "active_games": 1,
  "timestamp": "2023-01-01T12:00:00"
}
```

## Testing

### Basic Testing
Run testing client to verify server functions:

```bash
python test_client.py
```

The testing client will:
1. Check server health status
2. Create new game and add players
3. Start game and test actions
4. Perform automatic game flow
5. Test error situations

### AI Testing
Enter AI_example directory to test AI functions:

```bash
cd AI_example

# Start AI service
./start_ai.sh

# Run AI testing
python test_ai_client.py
```

### Development Guide
For detailed AI development guide, please refer to: [develop_instruction.md](develop_instruction.md)

## Example Usage

### Using curl for Testing

```bash
# Create game
curl -X POST http://localhost:30000/games \
  -H "Content-Type: application/json" \
  -d '{"small_blind":5,"big_blind":10,"max_players":6}'

# Add player
curl -X POST http://localhost:30000/games/holdem_001/players \
  -H "Content-Type: application/json" \
  -d '{"player_id":"player1","name":"Alice","chips":1000}'

# Start game
curl -X POST http://localhost:30000/games/holdem_001/start

# Get game state
curl http://localhost:30000/games/holdem_001/state?player_id=player1

# Execute action
curl -X POST http://localhost:30000/games/holdem_001/action \
  -H "Content-Type: application/json" \
  -d '{"player_id":"player1","action":"call","amount":10}'
```

## Project Structure

```
holdem/
├── server.py                    # Main server file
├── test_client.py              # Testing client
├── requirements.txt            # Python dependencies
├── start_server.sh             # Startup script
├── README.md                   # Project documentation
├── develop_instruction.md      # AI development guide
└── AI_example/                 # AI example directory
    ├── ai_http_server.py       # AI HTTP server example
    ├── ai_coordinator.py       # AI coordinator
    ├── test_ai_client.py       # AI client testing
    └── start_ai.sh             # AI startup script
```

## Technology Stack

- Python 3.7+
- Flask 2.3.3
- Werkzeug 2.3.7
- Requests 2.31.0

## Error Handling

| Error Scenario | HTTP Status Code | Response Example |
|----------|------------|----------|
| Invalid Action | 400 | `{"error": "Invalid action"}` |
| Not Your Turn | 403 | `{"error": "Not your turn"}` |
| Game Not Found | 404 | `{"error": "Game not found"}` |
| Player Not Found | 404 | `{"error": "Player not found"}` |