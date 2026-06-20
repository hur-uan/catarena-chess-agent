# Gomoku HTTP Server

A Flask-based Gomoku arena HTTP server that supports custom board sizes and complete game logic.

## Features

- Support for custom board sizes (default 15x15)
- Complete Gomoku game logic
- RESTful API interface
- Game state management
- Win/loss determination algorithm
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

### Custom Parameter Startup
```bash
# Specify port and board size
python server.py --port 9000 --board_size 15

# Enable debug mode
python server.py --port 9000 --board_size 15 --debug
```

### Parameter Description
- `--port`: Listen port (default: 9000)
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
  "board_size": 15
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
  "game_status": "ongoing"
}
```

### 3. Submit Move
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
  "game_status": "ongoing"
}
```

### 4. Get History Records
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

### 5. Health Check
**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "active_games": 1,
  "board_size": 15
}
```

## Game Rules

- Black moves first
- Place stones on empty positions
- Win by connecting 5 stones horizontally, vertically, or diagonally
- Long connections (6 or more) do not count as victory
- Draw when board is full

## Board Representation

- `0`: Empty position
- `1`: Black stone
- `2`: White stone

## Error Handling

| Error Scenario | HTTP Status Code | Response Example |
|----------|------------|----------|
| Invalid Move | 400 | `{"error": "Invalid position"}` |
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
3. Perform a series of test moves
4. Verify win/loss determination
5. Test error situations

### AI Battle Testing

Run AI battle testing:

```bash
# Ensure main server is running
python server.py --port 9000

# Start AI HTTP service
cd AI_example
python ai_http_server.py --port 11001 --ai_id AI_Alpha --ai_name "Alpha AI"

# Test AI service in another terminal
python test_ai_client.py

# Test AI move logic
python simple_ai_test.py
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
curl -X POST http://localhost:9000/games \
  -H "Content-Type: application/json" \
  -d '{"player_black":"Player1","player_white":"Player2"}'

# Get state
curl http://localhost:9000/games/gomoku_001/state

# Make move
curl -X POST http://localhost:9000/games/gomoku_001/move \
  -H "Content-Type: application/json" \
  -d '{"player":"black","position":[7,7]}'
```

## Project Structure

```
gomoku/
├── server.py          # Main server file
├── test_client.py     # Testing client
├── requirements.txt   # Python dependencies
├── start_server.sh    # Startup script
├── README.md         # Project documentation
```

## Technology Stack

- Python 3.7+
- Flask 2.3.3
- Werkzeug 2.3.7 