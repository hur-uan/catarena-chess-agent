# Chess Game Environment Development Guide

## Project Overview

This is a complete Chess HTTP server system that includes a main game server and AI service, designed with a microservice architecture. The system is implemented based on the python-chess library and provides complete Chess game functionality.

## System Architecture

### Main Game Server (Port 9020)
- Complete Chess game logic
- RESTful API interface
- Game state management and win/loss determination
- Move validation and history records
- Board visualization

### AI HTTP Service (Port 40001)
- Independent AI service supporting multiple instances
- Multiple AI algorithms (simple algorithm, Minimax algorithm)
- Support for custom AI names and IDs
- Complete HTTP API interface
- Position evaluation and legal move generation


This Chess Game Environment use python-chess lib as main engine, whose source code is under /home/working/CodeAgentGame/libraries/python-chess.

## Project Structure

```
chess/
├── server.py              # Main game server
├── test_client.py         # Testing client
├── requirements.txt       # Python dependencies
├── start_server.sh        # Main server startup script
├── README.md             # Main project documentation
├── develop_instruction.md # Development guide
└── AI_example/           # AI example directory
    ├── ai_http_server.py  # AI HTTP server
    ├── test_ai_client.py  # AI client testing
    ├── start_ai.sh        # AI service startup script
    └── README.md         # AI example documentation
```

## Core Features

### 1. Game Management
- Create new games
- Get game state
- Execute moves
- Get history records
- Board visualization

### 2. Move Validation
- Legal move checking
- Special move support (castling, en passant, promotion)
- Game end detection (checkmate, draw)

### 3. AI Features
- Simple random algorithm
- Minimax algorithm (Alpha-Beta pruning)
- Position evaluation
- Legal move generation

### 4. API Interface
- RESTful design
- JSON data format
- Complete error handling
- Health checks and status monitoring

## Technology Stack

- **Python 3.7+**
- **Flask 2.3.3** - Web framework
- **python-chess 1.999** - Chess engine
- **requests 2.31.0** - HTTP client

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start Main Game Server
```bash
python server.py --port 9020
```

### 3. Start AI Server
```bash
cd AI_example
python ai_http_server.py --port 40001
```

### 4. Run Tests
```bash
# Test main server
python test_client.py

# Test AI server
cd AI_example
python test_ai_client.py
```

## API Interface Description

### Main Game Server (Port 9020)

#### Create Game
```bash
POST /games
{
  "player_white": "Player1",
  "player_black": "Player2"
}
```

#### Get Game State
```bash
GET /games/{game_id}/state
```

#### Execute Move
```bash
POST /games/{game_id}/move
{
  "player": "white",
  "move": "e2e4"
}
```

#### Get History Records
```bash
GET /games/{game_id}/history
```

#### Get Board Visualization
```bash
GET /games/{game_id}/board
```

#### Get Legal Moves
```bash
GET /games/{game_id}/legal_moves
```

### AI Server (Port 40001)

#### Get AI Move
```bash
POST /move
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "algorithm": "simple"
}
```

#### Evaluate Position
```bash
POST /evaluate
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
}
```

#### Get Legal Moves
```bash
POST /legal_moves
{
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
}
```

## Development Guide

### Adding New AI Algorithms

1. Add new algorithm method in `ChessAI` class:
```python
def get_best_move_new_algorithm(self, board: chess.Board) -> Optional[chess.Move]:
    # Implement new algorithm
    pass
```

2. Add algorithm selection in `get_best_move` method:
```python
def get_best_move(self, board: chess.Board, algorithm: str = "simple") -> Optional[chess.Move]:
    if algorithm == "new_algorithm":
        return self.get_best_move_new_algorithm(board)
    # ... other algorithms
```

3. Update API documentation and test cases

### Integrating External Engines

You can use the `chess.engine` module to integrate external engines like Stockfish:

```python
import chess.engine

# Create engine
engine = chess.engine.SimpleEngine.popen_uci("/path/to/stockfish")

# Get best move
result = engine.play(board, chess.engine.Limit(time=2.0))
best_move = result.move
```

### Extending Game Features

1. Add new game modes (like blitz, classical)
2. Implement game replay functionality
3. Add statistical analysis features
4. Implement multiplayer game support

## Testing Strategy

### Unit Testing
- Move validation testing
- Game state testing
- AI algorithm testing

### Integration Testing
- API interface testing
- End-to-end game flow testing
- Error handling testing

### Performance Testing
- Concurrent connection testing
- AI response time testing
- Memory usage testing

## Deployment Recommendations

### Production Environment
- Use Gunicorn or uWSGI as WSGI server
- Configure Nginx as reverse proxy
- Use Redis for session management
- Configure logging and monitoring



## Troubleshooting

### Common Issues

1. **Port Occupied**
   - Check if port is occupied by other processes
   - Use `netstat -tulpn | grep :9020` to check port usage

2. **Dependency Installation Failed**
   - Ensure Python version is 3.7+
   - Use virtual environment to isolate dependencies
   - Check network connection

3. **AI Server Connection Failed**
   - Ensure AI server is running
   - Check port configuration
   - Verify firewall settings

### Log Analysis
- Check Flask application logs
- Check system logs
- Use debug mode to get detailed error information

## Performance Optimization

### Server Optimization
- Enable Flask caching
- Use connection pooling
- Configure appropriate thread count

### AI Optimization
- Implement move caching
- Optimize search algorithms
- Use parallel computation

## Security Considerations

### API Security
- Implement authentication
- Add request limiting
- Validate input data

### Data Security
- Encrypt sensitive data
- Implement access control
- Regular data backup

## Extension Plans

### Short-term Goals
- Add more AI algorithms
- Implement game replay functionality
- Optimize performance

### Long-term Goals
- Support multiplayer games
- Implement leaderboard system
- Add machine learning AI

## Contribution Guidelines

1. Fork the project
2. Create feature branch
3. Commit changes
4. Create Pull Request

## License

This project is licensed under the MIT License. 