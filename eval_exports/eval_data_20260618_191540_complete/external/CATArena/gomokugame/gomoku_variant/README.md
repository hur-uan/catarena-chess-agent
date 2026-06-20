# Gomoku HTTP Server

A Flask-based Gomoku arena HTTP server that supports custom rules and complete game logic.

## Features

- Support for custom board sizes (default 15x15)
- Complete game logic
- RESTful API interface
- Game state management
- History record tracking
- Error handling mechanism
- AI service support

## Install Dependencies

```bash
pip install -r requirements.txt
```

## Start Server

### Basic Startup
```bash
python server.py
```

### Custom Parameter Startup
```bash
# Specify port and board size
python server.py --port 20000 --board_size 15

# Enable debug mode
python server.py --port 20000 --board_size 15 --debug
```

### Parameter Description
- `--port`: Listen port (default: 20000)
- `--board_size`: Board size (default: 15)
- `--debug`: Enable debug mode

## API Interface

### 1. Create New Game
**POST** `/games`

**Request Body:**
```json
{
  "player_black": "Agent1_ID",
  "player_white": "Agent2_ID"
}
```

**Response:**
```json
{
  "game_id": "gomoku_001",
  "first_player": "black",
  "board_size": 15,
  "forbidden_points_count": 15
}
```

### 2. Get Game State
**GET** `/games/{game_id}/state`

**Response:**
```json
{
  "current_player": "white",
  "board": [
    [0,0,0,0,0,...],
    ...
  ],
  "last_move": [7,7],
  "game_status": "ongoing",
  "black_triplets_count": 1,
  "white_triplets_count": 0
}
```

### 3. Get Special Position Information
**GET** `/games/{game_id}/forbidden_points`

**Response:**
```json
{
  "game_id": "gomoku_001",
  "forbidden_points": [[1,2], [3,4], [5,6], ...],
  "forbidden_points_count": 15
}
```

### 4. Submit Move
**POST** `/games/{game_id}/move`

**Request Body:**
```json
{
  "player": "white",
  "position": [7,8]
}
```

**Response:**
```json
{
  "status": "valid_move",
  "game_status": "ongoing",
  "black_triplets_count": 1,
  "white_triplets_count": 1
}
```

### 5. Get History Records
**GET** `/games/{game_id}/history`

**Response:**
```json
{
  "moves": [
    {"player":"black", "position":[7,7], "timestamp":"2023-01-01T12:00:00"},
    {"player":"white", "position":[7,8], "timestamp":"2023-01-01T12:01:00"}
  ]
}
```

### 6. Health Check
**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "active_games": 1,
  "board_size": 15,
  "version": "magic_gomoku_v1.0"
}
```

## Game Rules

- Black moves first
- Place stones on empty positions
- Complete game rules
- Draw when board is full

## Board Representation

- `0`: Empty position
- `1`: Black stone
- `2`: White stone

## Error Handling

| Error Scenario | HTTP Status Code | Response Example |
|----------|------------|----------|
| Invalid Move | 400 | `{"error": "Invalid position"}` |
| Special Position Move | 400 | `{"error": "Position is forbidden"}` |
| Not Your Turn | 403 | `{"error": "Not your turn"}` |
| Game Not Found | 404 | `{"error": "Game not found"}` |

## Testing

### Basic Function Testing

Run testing client to verify server functions:

```bash
python test_client.py
```

The testing client will:
1. Check server health status
2. Create new game
3. Query special position information
4. Perform a series of test moves
5. Verify game rules
6. Test error situations

### AI Battle Testing

Run AI battle testing:

```bash
# Ensure main server is running
python server.py --port 10000

# Start AI HTTP service
cd AI_example
python ai_http_server.py --port 21000 --ai_id AI_Alpha --ai_name "Alpha AI"

# Test AI service
python test_magic_ai.py
```

AI battle testing will:
1. Start AI HTTP service
2. Test AI basic functions
3. Verify AI move logic
4. Support multiple AI service battles

## Example Usage

### Using curl for Testing

```bash
# Create game
curl -X POST http://localhost:20000/games \
  -H "Content-Type: application/json" \
  -d '{"player_black":"Player1","player_white":"Player2"}'

# Get special positions
curl http://localhost:20000/games/gomoku_001/forbidden_points

# Get state
curl http://localhost:20000/games/gomoku_001/state

# Make move
curl -X POST http://localhost:20000/games/gomoku_001/move \
  -H "Content-Type: application/json" \
  -d '{"player":"black","position":[7,7]}'
```

## Project Structure

```
gomoku_magic/
├── server.py              # Main server file
├── test_client.py         # Testing client
├── requirements.txt       # Python dependencies
├── start_server.sh        # Startup script
├── README.md             # Project documentation
└── AI_example/           # AI examples
    ├── ai_http_server.py  # AI HTTP server
    ├── test_magic_ai.py   # AI function testing
    └── ...
```

## Technology Stack

- Python 3.7+
- Flask 2.3.3
- Werkzeug 2.3.7

## Technical Features

1. **Complete Game Logic**: Supports complete Gomoku game rules
2. **AI Service Support**: AI services can automatically adapt to game rules
3. **Complete Testing**: Includes complete function testing suite 