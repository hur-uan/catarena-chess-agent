# Demo1 Chess AI

A sophisticated chess AI implementation designed for competitive tournament play. This AI features advanced position evaluation, strategic search algorithms, and tactical awareness.

## Features

### Advanced Evaluation System
- **Material Evaluation**: Sophisticated piece values with positional adjustments
- **Piece-Square Tables**: Position-specific bonuses for optimal piece placement
- **Pawn Structure Analysis**: Evaluation of doubled, isolated, and passed pawns
- **King Safety**: Dynamic king safety evaluation based on game phase
- **Mobility Assessment**: Considers piece mobility and control of key squares
- **Center Control**: Rewards control of central squares (e4, e5, d4, d5)

### Strategic Algorithms
- **Minimax with Alpha-Beta Pruning**: Efficient search algorithm with move ordering
- **Iterative Deepening**: Progressive depth search for optimal time management
- **Move Ordering**: Prioritizes captures, checks, and promotions for better pruning
- **Opening Book**: Basic opening principles for strong early game play
- **Endgame Knowledge**: Specialized evaluation for endgame positions

### Technical Features
- **Time Management**: Configurable thinking time with early termination
- **Game Phase Detection**: Automatic detection of opening, middlegame, and endgame
- **HTTP API**: RESTful interface compatible with tournament systems
- **Error Handling**: Robust error handling and validation
- **Logging**: Comprehensive logging for debugging and analysis

## Installation

### Prerequisites
- Python 3.7+
- pip (Python package manager)

### Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- Flask==2.3.3
- Werkzeug==2.3.7
- python-chess==1.999
- requests==2.31.0

## Usage

### Starting the AI Service

```bash
bash start_ai.sh <port>
```

Example:
```bash
bash start_ai.sh 52003
```

The script accepts exactly one argument (the port number) and will:
1. Validate the port number
2. Check for required dependencies
3. Install missing dependencies if needed
4. Start the AI service on the specified port

### Health Check

```bash
curl -s http://localhost:52003/health
```

Expected response:
```json
{
  "status": "healthy",
  "ai_id": "demo1_AI_1234567890",
  "ai_name": "demo1_AI",
  "active_games": 0,
  "timestamp": "2025-08-23T12:00:00.000000"
}
```

## API Endpoints

### Core Endpoints

#### Health Check
- **GET** `/health`
- Returns service health status and basic information

#### AI Information
- **GET** `/info`
- Returns detailed AI capabilities and description

#### Get Move (Legacy API)
- **POST** `/move`
- Request body: `{"fen": "<position>", "algorithm": "advanced"}`
- Returns the best move for the given position

### Game Management Endpoints

#### Join Game
- **POST** `/join_game`
- Request body: `{"game_id": "<id>", "my_color": "white|black", "game_server_url": "<url>"}`

#### Get Move
- **POST** `/get_move`
- Request body: `{"game_id": "<id>", "fen": "<position>", "current_player": "white|black"}`

#### Leave Game
- **POST** `/leave_game`
- Request body: `{"game_id": "<id>"}`

#### List Games
- **GET** `/games`
- Returns list of active games

## Testing

Run the comprehensive test suite:

```bash
python3 test_ai.py 52003
```

The test suite validates:
1. Health check functionality
2. AI information retrieval
3. Opening move generation
4. Middle game position analysis
5. Tactical position evaluation
6. Game management operations

## AI Strategy

### Opening Strategy
- Prioritizes central pawn moves (e4, d4)
- Develops knights to optimal squares (Nf3, Nc3, Nf6, Nc6)
- Follows classical opening principles

### Middle Game Strategy
- Maximizes piece activity and mobility
- Controls key central squares
- Evaluates pawn structure weaknesses
- Considers king safety in move selection

### Endgame Strategy
- Activates the king for endgame play
- Promotes pawns when advantageous
- Uses specialized piece-square tables for endgame positions

### Tactical Awareness
- Prioritizes captures using MVV-LVA (Most Valuable Victim - Least Valuable Attacker)
- Recognizes and plays checking moves
- Handles promotions effectively
- Supports castling when beneficial

## Performance Characteristics

- **Search Depth**: Up to 5 plies with iterative deepening
- **Thinking Time**: Configurable (default 2.0 seconds)
- **Move Ordering**: Advanced ordering for optimal alpha-beta pruning
- **Position Evaluation**: ~100+ evaluation factors
- **Response Time**: Typically < 3 seconds per move

## Tournament Compatibility

This AI is designed for tournament play and includes:
- Standardized HTTP API interface
- Robust error handling and recovery
- Configurable time controls
- Game state management
- Comprehensive logging

## Architecture

```
demo1_ai.py
├── Demo1ChessAI (Main AI Class)
│   ├── Position Evaluation
│   │   ├── Material counting
│   │   ├── Piece-square tables
│   │   ├── Pawn structure analysis
│   │   ├── King safety evaluation
│   │   └── Mobility assessment
│   ├── Search Algorithm
│   │   ├── Minimax with alpha-beta pruning
│   │   ├── Iterative deepening
│   │   ├── Move ordering
│   │   └── Time management
│   └── Game Management
│       ├── Opening book
│       ├── Game phase detection
│       └── Move generation
└── Flask HTTP Server
    ├── API endpoints
    ├── Error handling
    └── Request validation
```

## Files

- `demo1_ai.py` - Main AI implementation
- `start_ai.sh` - Service startup script
- `test_ai.py` - Comprehensive test suite
- `requirements.txt` - Python dependencies
- `README.md` - This documentation

## License

This chess AI is developed for tournament competition and educational purposes.

## Author

Demo1 AI - Advanced Chess Engine
Version 1.0