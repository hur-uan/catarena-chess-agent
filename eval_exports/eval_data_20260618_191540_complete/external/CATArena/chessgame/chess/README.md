# Chess HTTP Server

A Flask and python-chess based Chess HTTP server that provides complete Chess game functionality.

This Chess Game Environment use python-chess lib as main engine, whose source code is under /home/working/CodeAgentGame/libraries/python-chess.

## Features

- Complete Chess game logic (based on python-chess library)
- RESTful API interface
- Game state management
- Move validation and game end detection
- History record tracking
- Board visualization
- Legal move generation
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
# Specify port
python server.py --port 9020

# Enable debug mode
python server.py --port 9020 --debug
```

### Using Startup Script
```bash
./start_server.sh
```

### Parameter Description
- `--port`: Listen port (default: 9020)
- `--debug`: Enable debug mode

## API Interface

### 1. Create New Game
**POST** `/games`

**Request Body:**
```json
{
  "player_white": "Player1_ID",
  "player_black": "Player2_ID"
}
```

**Response:**
```json
{
  "game_id": "chess_001",
  "first_player": "white",
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "message": "Game created successfully"
}
```

### 2. Get Game State
**GET** `/games/{game_id}/state`

**Response:**
```json
{
  "current_player": "white",
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "last_move": "e2e4",
  "game_status": "ongoing",
  "is_check": false,
  "is_checkmate": false,
  "is_stalemate": false,
  "legal_moves": ["e7e5", "e7e6", "d7d5", "d7d6", ...]
}
```

### 3. Submit Move
**POST** `/games/{game_id}/move`

**Request Body:**
```json
{
  "player": "white",
  "move": "e2e4"
}
```

**Response:**
```json
{
  "status": "valid_move",
  "game_status": "ongoing",
  "message": "Move successful",
  "new_state": {
    "current_player": "black",
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "last_move": "e2e4",
    "game_status": "ongoing",
    "is_check": false,
    "is_checkmate": false,
    "is_stalemate": false,
    "legal_moves": ["e7e5", "e7e6", "d7d5", "d7d6", ...]
  }
}
```

### 4. Get Game History
**GET** `/games/{game_id}/history`

**Response:**
```json
{
  "moves": [
    {
      "player": "white",
      "move": "e2e4",
      "san": "e4",
      "timestamp": "2023-01-01T12:00:00"
    },
    {
      "player": "black",
      "move": "e7e5",
      "san": "e5",
      "timestamp": "2023-01-01T12:01:00"
    }
  ]
}
```

### 5. Get Board Visualization
**GET** `/games/{game_id}/board`

**Response:**
```json
{
  "game_id": "chess_001",
  "board_visual": "r n b q k b n r\np p p p p p p p\n. . . . . . . .\n. . . . . . . .\n. . . . P . . .\n. . . . . . . .\nP P P P . P P P\nR N B Q K B N R",
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
}
```

### 6. Get Legal Moves
**GET** `/games/{game_id}/legal_moves`

**Response:**
```json
{
  "game_id": "chess_001",
  "current_player": "black",
  "legal_moves": [
    {
      "uci": "e7e5",
      "san": "e5",
      "from_square": "e7",
      "to_square": "e5",
      "promotion": null
    },
    {
      "uci": "e7e6",
      "san": "e6",
      "from_square": "e7",
      "to_square": "e6",
      "promotion": null
    }
  ]
}
```

### 7. List All Games
**GET** `/games`

**Response:**
```json
{
  "games": [
    {
      "game_id": "chess_001",
      "player_white": "Player1",
      "player_black": "Player2",
      "game_status": "ongoing",
      "current_player": "black",
      "moves_count": 1,
      "created_at": "2023-01-01T12:00:00"
    }
  ],
  "total_games": 1
}
```

### 8. Health Check
**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "active_games": 1,
  "server": "Chess HTTP Server",
  "version": "1.0",
  "timestamp": "2023-01-01T12:00:00"
}
```

## Game Rules

- White moves first
- Uses standard Chess rules
- Supports all special moves:
  - Castling
  - En Passant
  - Promotion
- Game end conditions:
  - Checkmate
  - Stalemate
  - Insufficient Material
  - Fivefold Repetition
  - Seventy-five Moves

## Move Format

### UCI Format
- Standard format: `e2e4` (from square to to square)
- Promotion format: `e7e8q` (promote to queen)
- Castling: `e1g1` (kingside), `e1c1` (queenside)

### SAN Format
- Standard Algebraic Notation: `e4`, `Nf3`, `O-O` (castling)

## Board Representation

### FEN Format
```
rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1
```

### Visual Format
```
r n b q k b n r
p p p p p p p p
. . . . . . . .
. . . . . . . .
. . . . . . . .
. . . . . . . .
P P P P P P P P
R N B Q K B N R
```

## Error Handling

| Error Scenario | HTTP Status Code | Response Example |
|----------|------------|----------|
| Invalid Move | 400 | `{"error": "Invalid move"}` |
| Not Your Turn | 400 | `{"error": "Not your turn"}` |
| Game Not Found | 404 | `{"error": "Game not found"}` |
| Game Already Over | 400 | `{"error": "Game is already over"}` |

## Testing

### Basic Function Testing
```bash
python test_client.py
```

The testing client will:
1. Check server health status
2. Create new game
3. Get game state and board visualization
4. Get legal moves
5. Perform a series of test moves
6. Verify game state and history records
7. Test error situations

### Using curl for Testing

```bash
# Create game
curl -X POST http://localhost:9020/games \
  -H "Content-Type: application/json" \
  -d '{"player_white":"Player1","player_black":"Player2"}'

# Get state
curl http://localhost:9020/games/chess_001/state

# Submit move
curl -X POST http://localhost:9020/games/chess_001/move \
  -H "Content-Type: application/json" \
  -d '{"player":"white","move":"e2e4"}'
```

## Project Structure

```
chess/
├── server.py          # Main server file
├── test_client.py     # Testing client
├── requirements.txt   # Python dependencies
├── start_server.sh    # Startup script
└── README.md         # Project documentation
```

## Technology Stack

- Python 3.7+
- Flask 2.3.3
- python-chess 1.9.4
- Werkzeug 2.3.7

## Comparison with Gomoku

| Feature | Gomoku | Chess |
|------|--------|----------|
| **Board Size** | 15×15 | 8×8 |
| **Piece Types** | 2 types (black/white) | 6 types (pawn, knight, bishop, rook, queen, king) |
| **Move Rules** | Simple (any empty position) | Complex (different rules for each piece) |
| **Special Moves** | None | Castling, En Passant, Promotion |
| **Win Conditions** | Connect 5 | Checkmate, Draw, Resign |
| **State Representation** | 2D array | FEN string |
| **Move Format** | [x,y] coordinates | UCI format (e2e4) |

## Extension Suggestions

1. **AI Integration**: Integrate Chess engines
2. **Time Control**: Add timer functionality
3. **Spectator Mode**: Support multiple spectators
4. **Game Replay**: Support move replay functionality
5. **Opening Library**: Integrate opening databases
6. **Analysis Features**: Provide position analysis 