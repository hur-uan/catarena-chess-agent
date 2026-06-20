# Magic Bridge HTTP Server

A Flask-based Magic Bridge arena HTTP server supporting 4-player 2v2 battles with complete bridge game logic, featuring two unique magic features.

## Features

- 4-player bridge game (2v2 battles)
- Complete bidding system (pass, bid, double, redouble)
- Complete playing system (13 tricks)
- Intelligent legal action validation
- Automatic scoring system
- Game history records
- RESTful API interface
- Error handling mechanism


## Installation

```bash
pip install -r requirements.txt
```

## Server Startup

### Basic Startup
```bash
python server.py
```

### Custom Parameter Startup
```bash
# Specify port
python server.py --port 9031

# Enable debug mode
python server.py --port 9031 --debug

# Specify listening address
python server.py --port 9031 --host 0.0.0.0
```

### Using Startup Script
```bash
./start_server.sh
```

### Parameter Description
- `--port`: Listening port (default: 9031)
- `--host`: Listening address (default: 0.0.0.0)
- `--debug`: Enable debug mode

## API Interface

### 1. Create New Game
**POST** `/games`

**Request Body:**
```json
{}
```

**Response:**
```json
{
  "game_id": "bridge_abc123",
  "status": "created",
  "message": "Game created successfully"
}
```

### 2. Join Game
**POST** `/games/{game_id}/join`

**Request Body:**
```json
{
  "player_id": 0,
  "player_name": "Alice"
}
```

**Response:**
```json
{
  "game_id": "bridge_abc123",
  "player_id": 0,
  "player_name": "Alice",
  "status": "joined"
}
```

### 3. Start Game
**POST** `/games/{game_id}/start`

**Response:**
```json
{
  "game_id": "bridge_abc123",
  "status": "started",
  "dealer_id": 0,
  "current_player_id": 1,
  "phase": "bidding"
}
```

### 4. Get Game State
**GET** `/games/{game_id}/state?player_id=0`

**Response:**
```json
{
  "game_id": "bridge_magic_abc123",
  "phase": "bidding",
  "dealer_id": 0,
  "current_player_id": 1,
  "board_id": 1,
  "vulnerability": [false, false],
  "suit_order": {
    "suit_order": ["H", "S", "C", "D"],
    "suit_names": {
      "C": "Clubs",
      "D": "Diamonds", 
      "H": "Hearts",
      "S": "Spades"
    },
    "description": "Suit priority order (left to right, priority decreasing)"
  },
  "players": [
    {
      "player_id": 0,
      "name": "Alice",
      "position": "N",
      "hand_size": 13,
      "hand": [{"suit": "S", "rank": "A", "card_id": 51, "value": 14}],
      "hand_summary": {"C": 3, "D": 4, "H": 3, "S": 3},
      "high_card_points": 12,
      "distribution_points": 2,
      "total_points": 14,
      "tricks_won": 0,
      "is_dummy": false
    }
  ],
  "bidding": {
    "calls": [],
    "current_player_id": 1,
    "is_bidding_over": false,
    "contract": null
  },
  "current_trick": [],
  "tricks_won": [0, 0],
  "score": [0, 0]
}
```

**Exchange Phase Response Example:**
```json
{
  "game_id": "bridge_magic_abc123",
  "phase": "exchanging",
  "card_exchange": {
    "exchange_requests": 1,
    "exchange_completed": false,
    "waiting_players": [1, 2, 3]
  },
  "my_exchange_request": "AS",
  "suit_order": {
    "suit_order": ["H", "S", "C", "D"],
    "suit_names": {
      "C": "Clubs",
      "D": "Diamonds", 
      "H": "Hearts",
      "S": "Spades"
    },
    "description": "Suit priority order (left to right, priority decreasing)"
  }
}
```

### 5. Make Call
**POST** `/games/{game_id}/call`

**Request Body:**
```json
{
  "player_id": 1,
  "call_type": "bid",
  "level": 1,
  "suit": "H"
}
```

**Response:**
```json
{
  "game_id": "bridge_abc123",
  "player_id": 1,
  "call_type": "bid",
  "status": "success",
  "message": "Call successful"
}
```

### 6. Play Card
**POST** `/games/{game_id}/play`

**Request Body:**
```json
{
  "player_id": 1,
  "card": "AS"
}
```

**Response:**
```json
{
  "game_id": "bridge_abc123",
  "player_id": 1,
  "card": "AS",
  "status": "success",
  "message": "Card played successfully"
}
```

### 7. Get Legal Actions
**GET** `/games/{game_id}/legal_actions?player_id=1`

**Response:**
```json
{
  "game_id": "bridge_magic_abc123",
  "player_id": 1,
  "legal_actions": [
    {"type": "call", "call_type": "pass"},
    {"type": "call", "call_type": "bid", "level": 1, "suit": "C"},
    {"type": "call", "call_type": "bid", "level": 1, "suit": "D"}
  ]
}
```

**Exchange Phase Legal Actions Example:**
```json
{
  "game_id": "bridge_magic_abc123",
  "player_id": 0,
  "legal_actions": [
    {"type": "exchange", "card": "AS"},
    {"type": "exchange", "card": "KH"},
    {"type": "exchange", "card": "QD"},
    {"type": "exchange", "card": "JC"}
  ]
}
```

### 8. Get Game History
**GET** `/games/{game_id}/history`

**Response:**
```json
{
  "game_id": "bridge_abc123",
  "created_at": "2023-01-01T12:00:00",
  "phase": "finished",
  "bidding_history": {
    "calls": [...],
    "contract": {"level": 3, "suit": "NT", "declarer_id": 1, "doubling": 1}
  },
  "tricks_history": [
    {
      "trick_number": 1,
      "cards": [[0, "AS"], [1, "KS"], [2, "QS"], [3, "JS"]]
    }
  ],
  "final_score": [400, 0],
  "winner": 0
}
```

### 9. Delete Game
**DELETE** `/games/{game_id}`

**Response:**
```json
{
  "game_id": "bridge_abc123",
  "status": "deleted"
}
```

### 10. List Games
**GET** `/games`

**Response:**
```json
{
  "games": [
    {
      "game_id": "bridge_abc123",
      "phase": "bidding",
      "players": ["Alice", "Bob", "Charlie", "David"],
      "created_at": "2023-01-01T12:00:00"
    }
  ],
  "total": 1
}
```

### 11. Health Check
**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "active_games": 1,
  "timestamp": "2023-01-01T12:00:00"
}
```

### 12. Get Suit Priority Order (Magic Feature)
**GET** `/games/{game_id}/suit_order`

**Response:**
```json
{
  "suit_order": ["H", "S", "C", "D"],
  "suit_names": {
    "C": "Clubs",
    "D": "Diamonds",
    "H": "Hearts", 
    "S": "Spades"
  },
  "description": "Suit priority order (left to right, priority decreasing)"
}
```

### 13. Request Card Exchange (Magic Feature)
**POST** `/games/{game_id}/exchange`

**Request Body:**
```json
{
  "player_id": 0,
  "card": "AS"
}
```

**Response:**
```json
{
  "game_id": "bridge_magic_abc123",
  "player_id": 0,
  "card": "AS",
  "status": "success",
  "message": "Exchange request submitted"
}
```

### 14. Execute Card Exchange (Magic Feature)
**POST** `/games/{game_id}/execute_exchange`

**Response:**
```json
{
  "game_id": "bridge_magic_abc123",
  "status": "success",
  "message": "Card exchange completed",
  "exchanged_cards": {
    "0": "KH",
    "2": "AS"
  }
}
```

### 15. Server Information
**GET** `/info`

**Response:**
```json
{
  "name": "Magic Bridge Game Server",
  "version": "1.0",
  "description": "HTTP server for Magic Bridge card game with randomized suit order and card exchange",
  "protocol": "HTTP RESTful",
  "default_port": 50000,
  "features": [
    "4-player bridge game",
    "Randomized suit order (magic feature)",
    "Card exchange between partners (magic feature)",
    "Bidding phase",
    "Playing phase",
    "Scoring system",
    "Game history"
  ]
}
```

## Card Representation

### Suits
- `C`: Clubs
- `D`: Diamonds
- `H`: Hearts
- `S`: Spades

### Ranks
- `2`-`9`: Number cards
- `T`: 10
- `J`: Jack
- `Q`: Queen
- `K`: King
- `A`: Ace

### Card String Format
- Format: `{rank}{suit}`
- Example: `AS` (Ace of Spades), `KH` (King of Hearts), `2C` (2 of Clubs)

## Call Types

### Pass
```json
{
  "player_id": 1,
  "call_type": "pass"
}
```

### Bid
```json
{
  "player_id": 1,
  "call_type": "bid",
  "level": 3,
  "suit": "NT"
}
```

### Double
```json
{
  "player_id": 1,
  "call_type": "double"
}
```

### Redouble
```json
{
  "player_id": 1,
  "call_type": "redouble"
}
```

## Game Phases

1. **waiting**: Waiting for players to join
2. **bidding**: Bidding phase
3. **exchanging**: Card exchange phase (magic feature)
4. **playing**: Playing phase
5. **finished**: Game finished

### Magic Phase Description

#### Card Exchange Phase (exchanging)
- Occurs after bidding ends and before playing begins
- Each partner can select one card from their hand for exchange
- Exchange is secret, invisible to opponents
- System executes exchange only when both partners submit exchange requests
- Automatically proceeds to playing phase after exchange completion

## Error Handling

| Error Scenario | HTTP Status | Response Example |
|----------------|-------------|------------------|
| Game not found | 404 | `{"error": "Game not found"}` |
| Invalid parameter | 400 | `{"error": "Invalid parameter"}` |
| Illegal action | 400 | `{"error": "Illegal action"}` |
| Not your turn | 400 | `{"error": "Not your turn"}` |

## Testing

### Basic Function Testing

Run test client to verify server functionality:

```bash
python test_client.py
```

The test client will:
1. Check server health status
2. Create new game and join players
3. Test bidding phase
4. Test playing phase
5. Verify error handling

### AI Battle Testing

Run AI battle test:

```bash
# Ensure main server is running
python server.py --port 50000

# Start AI HTTP service
cd AI_example
./start_ai.sh

# Test AI service in another terminal
python test_ai_client.py

# Run detailed test suite
python simple_ai_test.py
```

AI battle test will:
1. Start AI HTTP service
2. Test AI basic functionality
3. Verify AI bidding and playing logic
4. Support multiple AI service battles
5. Provide complete test suite

## Usage Examples

### Using curl for Testing

```bash
# Create game
curl -X POST http://localhost:9031/games

# Join game
curl -X POST http://localhost:9031/games/bridge_abc123/join \
  -H "Content-Type: application/json" \
  -d '{"player_id": 0, "player_name": "Alice"}'

# Start game
curl -X POST http://localhost:9031/games/bridge_abc123/start

# Make call
curl -X POST http://localhost:9031/games/bridge_abc123/call \
  -H "Content-Type: application/json" \
  -d '{"player_id": 1, "call_type": "bid", "level": 1, "suit": "H"}'

# Play card
curl -X POST http://localhost:9031/games/bridge_abc123/play \
  -H "Content-Type: application/json" \
  -d '{"player_id": 1, "card": "AS"}'
```

## Project Structure

```
bridge/
├── server.py         # HTTP server (contains all game logic)
├── test_client.py    # Test client
├── requirements.txt  # Python dependencies
├── start_server.sh   # Startup script
└── README.md        # Project documentation
```

## Technology Stack

- Python 3.7+
- Flask 2.3.3
- Werkzeug 2.3.7

## Development Notes

### Core Classes

The `server.py` file contains all game logic:

1. **BridgeCard**: Card class, handles basic card properties and comparison
2. **BridgePlayer**: Player class, manages hand and player state
3. **BiddingHistory**: Bidding history, handles bidding rules and contract determination
4. **BridgeGame**: Game core, manages game flow and state
5. **HTTP API**: Flask routes handle all RESTful interfaces

### Extension Suggestions

1. **AI Support**: Add bridge AI interface
2. **Tournament**: Support multi-table competitions
3. **Scoring System**: Improve scoring rules
4. **Web Interface**: Add visualization interface
5. **Database**: Persist game data 