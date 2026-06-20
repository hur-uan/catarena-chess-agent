# Demo1 Gomoku AI

A competitive Gomoku AI service implementing advanced strategic algorithms for tournament play.

## Features

### Advanced AI Algorithms
- **Minimax with Alpha-Beta Pruning**: Strategic search algorithm with depth-limited exploration
- **Pattern Recognition**: Recognizes and evaluates various Gomoku patterns (five, open four, three, etc.)
- **Threat Detection**: Identifies and responds to critical threats like open fours and double threes
- **Strategic Evaluation**: Comprehensive board position evaluation system
- **Winning Priority**: Always prioritizes immediate winning moves
- **Defense Priority**: Blocks opponent's winning moves
- **Positional Strategy**: Evaluates strategic value of positions based on patterns and board control

### AI Capabilities
- `winning_move`: Finds immediate winning positions
- `blocking_move`: Blocks opponent's winning threats
- `threat_detection`: Identifies critical threats and opportunities
- `pattern_recognition`: Recognizes and evaluates Gomoku patterns
- `minimax_search`: Uses minimax algorithm for strategic planning
- `strategic_evaluation`: Comprehensive position evaluation

## Quick Start

### Start AI Service
```bash
bash start_ai.sh 50009
```

### Health Check
```bash
curl -s http://localhost:50009/health
```

### AI Information
```bash
curl -s http://localhost:50009/info
```

## API Endpoints

### Health Check
- **GET** `/health`
- Returns AI service status and active games count

### AI Information
- **GET** `/info`
- Returns AI capabilities, version, and description

### Join Game
- **POST** `/join_game`
- Request: `{"game_id": "game_id", "my_color": "black/white", "game_server_url": "http://localhost:9000"}`
- Response: `{"status": "joined", "ai_id": "demo1_AI", "game_id": "game_id", "my_color": "color"}`

### Get Move
- **POST** `/get_move`
- Request: `{"game_id": "game_id", "board": [[board_state]], "current_player": "black/white"}`
- Response: `{"move": [x, y], "ai_id": "demo1_AI", "game_id": "game_id", "reasoning": "strategy_description"}`

### Leave Game
- **POST** `/leave_game`
- Request: `{"game_id": "game_id"}`
- Response: `{"status": "left", "ai_id": "demo1_AI", "game_id": "game_id"}`

## Strategy Overview

### 1. Immediate Win/Block
- Searches for immediate winning moves (5 in a row)
- Blocks opponent's immediate winning threats

### 2. Critical Threat Management
- Detects and creates open four patterns
- Identifies double three opportunities
- Blocks opponent's critical threats

### 3. Strategic Planning
- Uses minimax algorithm with alpha-beta pruning (depth 3)
- Evaluates board positions using pattern scoring
- Considers both offensive and defensive strategies

### 4. Pattern Evaluation
- **Five**: 100,000 points (winning pattern)
- **Open Four**: 10,000 points (critical threat)
- **Four**: 1,000 points (strong threat)
- **Open Three**: 500 points (good opportunity)
- **Three**: 100 points (developing pattern)
- **Open Two**: 50 points (early development)
- **Two**: 10 points (basic pattern)
- **One**: 1 point (single stone)

### 5. Position Selection
- Prioritizes positions near existing stones
- Considers center control for opening moves
- Evaluates strategic value based on multiple factors

## Technical Details

### Dependencies
- Python 3.7+
- Flask 2.3.3+
- Requests library

### Performance
- Response time: < 1 second per move
- Search depth: 3 levels (configurable)
- Candidate move limitation for performance optimization
- Memory efficient board evaluation

### Error Handling
- Graceful handling of invalid requests
- Proper HTTP status codes
- Comprehensive error messages
- Timeout protection

## Testing

Run the included test script to verify AI functionality:
```bash
python3 test_ai.py
```

The test covers:
- Health check verification
- AI information retrieval
- Game joining and leaving
- Move generation and validation
- Multi-move game simulation

## Tournament Readiness

This AI is designed for competitive tournament play with:
- Robust error handling
- Fast response times
- Strategic depth
- Defensive capabilities
- Pattern recognition
- Threat assessment

The AI follows standard Gomoku rules and is compatible with the tournament game server protocol.