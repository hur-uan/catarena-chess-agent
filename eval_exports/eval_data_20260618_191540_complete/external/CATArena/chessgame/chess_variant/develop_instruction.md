# Chess Game Environment Development Guide

## Project Overview

This is a complete Chess HTTP server system that includes a main game server and AI service, designed with a microservice architecture. The system is implemented based on the python-chess library and provides enhanced Chess game functionality.

## System Architecture

### Main Game Server (Port 9021)
- Complete Chess game logic
- RESTful API interface
- Game state management and win/loss determination
- Move validation and history records
- Board visualization

### AI HTTP Service (Port 41101)
- Independent AI service supporting multiple instances
- Multiple AI algorithms (simple algorithm, Minimax algorithm)
- Support for custom AI names and IDs
- Complete HTTP API interface
- Position evaluation and legal move generation

This Chess Game Environment uses python-chess lib as main engine, whose source code is under /home/working/CodeAgentGame/libraries/python-chess.

## Project Structure

```
chess_magic/
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

### 2. Game Implementation
- Chess960 starting position generation
- Enhanced game mechanics
- Advanced piece movement logic
- Fairness enforcement for both players

### 3. Move Validation
- Legal move checking
- Special move support (castling, en passant, promotion)
- Enhanced move validation
- Game end detection (checkmate, draw)

### 4. AI Features
- Simple random algorithm
- Minimax algorithm (Alpha-Beta pruning)
- Position evaluation
- Legal move generation

### 5. API Interface
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
python server.py --port 9021
```

### 3. Start AI Server
```bash
cd AI_example
python ai_http_server.py --port 41101
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

### Main Game Server (Port 9021)

#### Create Game
```bash
POST /games
{
  "player_white": "Player1",
  "player_black": "Player2",
  "seed": 12345  # Optional: for reproducible game generation
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

### AI Server (Port 41101)

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

### Adding New Game Rules

1. Add new rule implementation in the game logic:
```python
def apply_new_rule(self, board: chess.Board, game_state: dict):
    # Implement new rule
    pass
```

2. Update game state serialization:
```python
def get_game_state(self, game_id: str) -> dict:
    state = super().get_game_state(game_id)
    state['new_rule'] = self.get_new_rule_state(game_id)
    return state
```

3. Update move validation:
```python
def validate_move_with_rules(self, board: chess.Board, move: chess.Move, game_state: dict) -> bool:
    # Add validation for new rule
    pass
```

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

1. Add new rule types
2. Implement dynamic rule changes during gameplay
3. Add rule combination effects
4. Implement rule-based tournaments

## Testing Strategy

### Unit Testing
- Move validation testing
- Game state testing
- AI algorithm testing
- Game rule generation testing

### Integration Testing
- API interface testing
- End-to-end game flow testing
- Error handling testing
- Fairness testing for game rule distribution

### Performance Testing
- Concurrent connection testing
- AI response time testing
- Memory usage testing
- Game rule generation performance

## Deployment Recommendations

### Production Environment
- Use Gunicorn or uWSGI as WSGI server
- Configure Nginx as reverse proxy
- Use Redis for session management
- Configure logging and monitoring
- Ensure reproducible game generation

### Containerized Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 9021 41101
CMD ["python", "server.py"]
```

## Troubleshooting

### Common Issues

1. **Port Occupied**
   - Check if port is occupied by other processes
   - Use `netstat -tulpn | grep :9021` to check port usage

2. **Game Generation Issues**
   - Ensure seed values are properly handled
   - Check game rule validation
   - Verify game fairness

3. **Dependency Installation Failed**
   - Ensure Python version is 3.7+
   - Use virtual environment to isolate dependencies
   - Check network connection

4. **AI Server Connection Failed**
   - Ensure AI server is running
   - Check port configuration
   - Verify firewall settings

### Log Analysis
- Check Flask application logs
- Check system logs
- Use debug mode to get detailed error information
- Monitor game generation logs

## Performance Optimization

### Server Optimization
- Enable Flask caching
- Use connection pooling
- Configure appropriate thread count
- Optimize game generation

### AI Optimization
- Implement move caching
- Optimize search algorithms
- Use parallel computation
- Cache game state calculations

## Security Considerations

### API Security
- Implement authentication
- Add request limiting
- Validate input data
- Sanitize game parameters

### Data Security
- Encrypt sensitive data
- Implement access control
- Regular data backup
- Secure game generation

## Extension Plans

### Short-term Goals
- Add more game rule types
- Implement rule combinations
- Optimize performance
- Add rule-based tournaments

### Long-term Goals
- Support multiplayer games
- Implement rule editor
- Add machine learning AI
- Create rule marketplace

## Contribution Guidelines

1. Fork the project
2. Create feature branch
3. Commit changes
4. Create Pull Request
5. Ensure game fairness in contributions

## License

This project is licensed under the MIT License.


