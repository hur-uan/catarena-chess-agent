# Bridge AI Tournament Platform

A tournament platform for Bridge AI agents that supports HTTP-based AI services for 2v2 team competitions.

## Features

- **2v2 Team Format**: Supports bridge's natural 2v2 team structure
- **Multiple Tournament Types**: 
  - Round Robin: All teams vs all teams
  - Duplicate: AA vs BB format (same AI duplicated)
  - Mixed: AB vs CD format (different AIs paired)
- **HTTP AI Integration**: AIs communicate via HTTP REST API
- **Health Monitoring**: Automatic AI service health checks
- **Comprehensive Reporting**: Detailed tournament statistics and rankings
- **Flexible Configuration**: JSON-based configuration system

## Architecture

```
Bridge Arena
├── Bridge Game Server (Port 9030)
├── AI Services (Ports 50001, 50002, ...)
└── Tournament Management
    ├── Team Formation
    ├── Game Orchestration
    └── Result Analysis
```

## Quick Start

### 1. Start Bridge Game Server

```bash
cd ../bridge
python3 server.py --port 9030
```

### 2. Start AI Services

Each AI should provide HTTP endpoints:
- `GET /health` - Health check
- `POST /join_game` - Join game
- `POST /get_action` - Get AI action (bid or play card)

### 3. Run Tournament

```bash
# List configurations
./start_arena.sh --list-configs

# Create duplicate teams configuration
./start_arena.sh --create-config duplicate

# Run duplicate tournament
./start_arena.sh --config configs/duplicate_config.json --tournament-type duplicate

# Run round robin tournament
./start_arena.sh --config configs/arena_config.json --tournament-type round_robin
```

## Configuration

### AI Configuration

```json
{
  "ai_id": "AI_Alpha",
  "ai_name": "Alpha AI",
  "port": 50001,
  "description": "Basic bridge AI"
}
```

### Team Configuration

```json
{
  "team_id": "Team_Alpha_Beta",
  "team_name": "Alpha-Beta Team",
  "player1": "AI_Alpha",
  "player2": "AI_Beta",
  "description": "Alpha and Beta AI team"
}
```

### Tournament Types

#### 1. Round Robin
- Each team plays against all other teams
- Suitable for comprehensive evaluation
- More games, longer duration

#### 2. Duplicate (AA vs BB)
- Same AI duplicated for both positions
- Tests AI consistency and strategy
- Faster execution

#### 3. Mixed (AB vs CD)
- Different AIs paired together
- Tests AI compatibility and teamwork
- Balanced evaluation

## AI Service Requirements

### Health Check Endpoint
```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Join Game Endpoint
```http
POST /join_game
```

Request:
```json
{
  "game_id": "game_123",
  "position": "north",
  "game_server_url": "http://localhost:9030"
}
```

### Get Action Endpoint
```http
POST /get_action
```

Request:
```json
{
  "game_id": "game_123",
  "player_id": 0,
  "game_state": {
    "phase": "bidding",
    "current_player_id": 0,
    "players": [...],
    "bidding": {...},
    "current_trick": [...],
    "tricks_won": [0, 0],
    "score": [0, 0]
  },
  "legal_actions": [
    {"type": "call", "call_type": "pass"},
    {"type": "call", "call_type": "bid", "level": 1, "suit": "S"}
  ],
  "position": "north"
}
```

Response:
```json
{
  "action": {
    "type": "call",
    "call_type": "bid",
    "level": 1,
    "suit": "S"
  }
}
```

## File Structure

```
bridge_Arena/
├── arena.py              # Main arena logic
├── config.py             # Configuration management
├── start_arena.py        # Tournament startup script
├── start_arena.sh        # Shell wrapper script
├── requirements.txt      # Python dependencies
├── README.md            # This file
├── configs/             # Configuration files
│   ├── arena_config.json
│   ├── duplicate_config.json
│   └── mixed_config.json
├── logs/                # Tournament logs
└── reports/             # Tournament reports
```

## Usage Examples

### Basic Tournament
```bash
# Start with default configuration
./start_arena.sh

# Custom server URL
./start_arena.sh --server-url http://localhost:9030

# Multiple rounds per match
./start_arena.sh --rounds 5
```

### Duplicate Tournament
```bash
# Create duplicate configuration
./start_arena.sh --create-config duplicate

# Run duplicate tournament
./start_arena.sh --config configs/duplicate_config.json --tournament-type duplicate
```

### Mixed Teams Tournament
```bash
# Create mixed teams configuration
./start_arena.sh --create-config mixed

# Run mixed tournament
./start_arena.sh --config configs/mixed_config.json --tournament-type round_robin
```

### Configuration Management
```bash
# List all configurations
./start_arena.sh --list-configs

# Validate configuration
./start_arena.sh --validate

# Use custom configuration file
./start_arena.sh --config my_config.json
```

## Tournament Results

Results are saved in JSON format with:
- Team rankings
- Win/loss statistics
- Total scores
- Game details
- Bidding and trick history

Example report:
```json
{
  "tournament_id": "tournament_1704067200",
  "total_games": 6,
  "teams": 4,
  "team_rankings": [
    ["Team_Alpha_Beta", {
      "team_name": "Alpha-Beta Team",
      "wins": 3,
      "losses": 0,
      "ties": 0,
      "total_score": 450,
      "games_played": 3
    }]
  ],
  "detailed_results": [...]
}
```

## Troubleshooting

### Common Issues

1. **Bridge server not running**
   ```
   Error: Failed to create game
   Solution: Start bridge server on port 9030
   ```

2. **AI service not responding**
   ```
   Warning: AI Alpha AI health check failed
   Solution: Check AI service is running and /health endpoint works
   ```

3. **Configuration errors**
   ```
   Error: Configuration validation failed
   Solution: Run --validate to check configuration
   ```

### Debug Mode

Enable debug logging by modifying `config.py`:
```python
LOGGING_CONFIG = {
    "level": "DEBUG",
    "file": "logs/arena.log",
    "console": True
}
```

## Development

### Adding New AI

1. Create AI service with required endpoints
2. Add AI configuration to `config.py`
3. Update team configurations if needed
4. Test with `--validate`

### Custom Tournament Formats

Extend `BridgeArena.run_tournament()` method to support new tournament types.

### Performance Optimization

- Adjust timeout values for faster games
- Use duplicate format for quick testing
- Monitor AI response times

## License

This project is part of the CodeAgentGame platform.
