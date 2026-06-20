# GOMOKUGAME: Gomoku AI Battle Platform

A modern AI-powered Gomoku battle platform that supports multiple AI algorithms and custom AI participation in battles.

## 🚀 Quick Start

### Requirements
- Python 3.8+
- Dependencies listed in `requirements.txt`

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Demo Battle
```bash
bash start_demo_competition.sh
```

This will automatically start:
1. Gomoku game environment (port 9000)
2. Demo AI competitors (ports 51000-51005), all from `./AI_competitors/gomoku/round_1`
3. Arena battle system
4. Generate battle reports to `./gomoku_Arena/reports/demo_competition`

## 📁 Project Structure

### Core Components
- **`gomoku/`** - Standard Gomoku game environment
- **`gomoku_variant/`** - Variant Gomoku game environment
- **`gomoku_Arena/`** - Battle arena system, compatible with both environments

### AI Competitors
- **`AI_competitors/gomoku/`** - Gomoku AIs developed with SOTA LLM + Minimal Agent
- **`AI_competitors/gomoku_variant/`** - Variant Gomoku AIs developed with SOTA LLM + Minimal Agent
- **`AI_competitors/gomoku_commercial/`** - Commercial Agent developed Gomoku AIs
- **`AI_competitors/gomoku_variant_commercial/`** - Commercial Agent developed Variant Gomoku AIs
- **`AI_competitors/strong_baseline/`** - Strong baseline AIs

### Tools and Configuration
- **`ChatPrompt.py`** - Example prompts for Code Agent development of board game AIs
- **`start_ai_competitors.sh`** - Script to start AI competitors (default ports 51000-51005)
- **`gomoku_Arena/configs/`** - Battle configuration directory

## 🎯 Using Custom AI in Battles

### Step 1: Develop Your AI
Based on the example prompts in `ChatPrompt.py`, use your Agent to generate a competing AI.
```bash
python ChatPrompt.py
```

### Step 2: Start AI Service
```bash
cd <your_ai_path>
bash start_ai.sh <your_custom_port>
```

### Step 3: Configure Battle
Modify `gomoku_Arena/configs/demo_config.json` to add your AI configuration:
```json
{
  "ais": [
    {
      "ai_id": "your_ai_id",
      "ai_name": "Your AI Name",
      "port": <your_port_number>,
      "description": "AI description"
    }
  ]
}
```

### Step 4: Start Battle
```bash
python3 ./gomoku_Arena/start_arena.py \
  --config ./gomoku_Arena/configs/<your_config_file> \
  --reports-dir ./gomoku_Arena/reports/<report_output_directory>
```

## 📊 Battle Reports

After battle completion, the system generates detailed battle reports in the specified directory, including:
- Win/Loss statistics
- Win/Loss matrix
- Game records
- AI performance analysis (average thinking time)
- Complete game history and final states
- Strategy evaluation

Reports support multiple formats:
- **JSON format**: Complete structured data
- **TXT format**: Human-readable text format
- **CSV format**: Table format for data analysis
- **History reports**: Detailed history and final states for each game

## 🎮 Game Rules

### Standard Gomoku
- 15x15 board
- Black plays first
- Win by connecting 5 stones horizontally, vertically, or diagonally
- No forbidden moves supported

### API Interfaces

#### Main Game Server Interfaces (default port 9000):
- `POST /games` - Create game
- `GET /games/{game_id}/state` - Get game state
- `POST /games/{game_id}/move` - Submit move
- `GET /games/{game_id}/history` - Get game history
- `GET /health` - Health check

#### Required AI Server Interfaces:
- `GET /health` - Health check
- `GET /info` - AI information
- `POST /join_game` - Join game
- `POST /get_move` - Get AI move
- `POST /leave_game` - Leave game

## 📖 Development Guide

### Creating Custom AI

1. **Read Documentation**
   - `gomoku/README.md` - Game environment documentation
   - `gomoku/develop_instruction.md` - Development guide

2. **Reference Examples**
   - `gomoku/AI_example/` - Example AI implementations

3. **Implement Interfaces**
   - Implement standard HTTP API interfaces
   - Write `start_ai.sh` startup script

4. **Test AI**
   ```bash
   # Start game server
   cd gomoku
   python server.py --port 9000
   
   # Start AI service
   cd <your_ai_directory>
   bash start_ai.sh <port_number>
   
   # Test health check
   curl http://localhost:<port_number>/health
   ```

### Strategy Recommendations

1. **Win First**: Prioritize finding positions that can win directly
2. **Defense First**: Prevent opponent from forming 5-in-a-row
3. **Threat Building**: Create multiple attack points
4. **Position Evaluation**: Evaluate strategic value of each position
5. **Search Algorithms**: Use Minimax, Alpha-Beta pruning, etc.

## 🔧 Tech Stack

- **Python 3.8+**
- **Flask 2.3.3** - Web framework
- **Werkzeug 2.3.7** - WSGI toolkit
- **requests 2.31.0** - HTTP client

## ⚡ Performance Features

### Arena Performance Optimization
- ✅ 90% reduction in redundant HTTP calls
- ✅ 50% improvement in battle efficiency
- ✅ Timeout control mechanism (10 seconds/move)
- ✅ Concurrent battle support

### AI Performance Requirements
- Response time: < 5 seconds/move
- Memory usage: Reasonable control
- Error handling: Graceful exception handling
- Concurrency support: Support for multiple games

## 📈 Visualization Analysis

The system supports generating various trend charts:
- Total score trend chart
- Win rate trend chart
- Average score trend chart
- Comprehensive trend comparison chart

```bash
cd gomoku_Arena
python line_chart.py
```

## 🛠️ Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check port usage
   netstat -tlnp | grep 9000
   
   # Kill occupying process
   sudo kill -9 <PID>
   ```

2. **AI Service Connection Failed**
   ```bash
   # Check AI health status
   curl http://localhost:51000/health
   
   # View AI logs
   tail -f <AI_directory>/logs/*.log
   ```

3. **Dependency Installation Failed**
   ```bash
   # Use virtual environment
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## 📚 References

### Game Environment Documentation
- [Gomoku Server README](gomoku/README.md)
- [Gomoku Development Guide](gomoku/develop_instruction.md)
- [Arena Usage Guide](gomoku_Arena/README.md)
- [Battle Process Guide](gomoku_Arena/BATTLE_GUIDE.md)

### AI Examples
- [Basic AI Examples](gomoku/AI_example/)
- [Strong Baseline AIs](AI_competitors/strong_baseline/)

## 🎯 Project Features

### Comparison with Chess Platform

| Feature | Gomoku | Chess |
|---------|--------|-------|
| **Board Size** | 15×15 | 8×8 |
| **Piece Types** | 2 types (Black/White) | 6 types (King, Queen, Rook, Bishop, Knight, Pawn) |
| **Move Rules** | Simple (any empty position) | Complex (different for each piece) |
| **Special Rules** | None | Castling, En passant, Promotion |
| **Win Condition** | Connect 5 | Checkmate, Resignation, Draw |
| **State Representation** | 2D array | FEN string |
| **Move Format** | [x,y] coordinates | UCI format (e2e4) |
| **Game Duration** | Relatively short | Can be very long |
| **Strategy Complexity** | Medium | Very high |

## 🏆 Arena Features

- **Round Robin**: Each AI battles against all other AIs
- **Fair Battles**: Each AI pair exchanges black and white sides for one game each
- **Timeout Monitoring**: 10-second timeout mechanism to prevent AI deadlock
- **Detailed Logging**: Complete battle process recording
- **Multi-format Reports**: JSON, TXT, CSV formats
- **Performance Analysis**: Average thinking time statistics
- **History Tracking**: Complete game history for each match

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

Welcome to submit Issues and Pull Requests to improve this project!

Before submitting code, please ensure:
1. Code follows Python PEP 8 standards
2. Add appropriate comments and documentation
3. Test new functionality correctness
4. Update relevant documentation

## 📧 Contact

For questions or suggestions, please provide feedback through Issues.

---

**Good luck in your Gomoku AI battles!** 🎉